# PubMed Explorer — Full-Stack Assignment

A local end-to-end system that pulls articles from PubMed, stores them in
PostgreSQL, serves them through a Streamlit UI, and lets you ask
natural-language questions answered by a locally-hosted LLM.

## What's inside

| Component | Detail |
|---|---|
| Data source | PubMed E-utilities (`Esearch` + `Efetch`) via Biopython |
| Storage | PostgreSQL 18, 6 normalized tables, dedup via `ON CONFLICT` |
| UI | Streamlit, 3 tabs: Search, Detail, Q&A |
| LLM | Ollama serving `qwen2.5-coder:1.5b` (small, SQL-tuned) |
| Safety | Read-only DB role + Python SQL validator + 5s statement timeout |

## Architecture

```
PubMed API
    │
    │  Esearch → PMIDs        Efetch → XML records
    ▼
ETL  (src/etl.py)
    │  transform: flatten nested XML, normalize fields, dedup
    ▼
PostgreSQL
    journals · authors · mesh_terms      (lookup tables, unique constraints)
    articles                              (PMID = PK)
    article_authors · article_mesh        (junction tables)
    │
    ├──────────► Streamlit Search / Detail tabs (read-write engine)
    │
    └──────────► LLM Q&A tab
                    Ollama → SQL string
                    → sql_guard.validate_sql()
                    → execute under pubmed_readonly role
```

## Technical Highlights & Design Decisions

To ensure this application meets enterprise-grade standards, several advanced engineering patterns were implemented beyond the basic requirements:

1. **Idempotent Data Pipelines:** The `src/etl.py` script utilizes strict PostgreSQL `ON CONFLICT DO NOTHING` constraints. This guarantees that the pipeline can be run repeatedly (e.g., via a daily cron job) without ever creating duplicate records or corrupting the database.
2. **3rd Normal Form (3NF) Architecture:** Rather than storing flat, comma-separated strings for authors and medical keywords, the database employs Junction Tables (`article_authors` and `article_mesh`). This heavily normalized structure prevents data duplication and accelerates aggregation queries.
3. **Advanced Trigram Indexing:** To ensure lightning-fast ILIKE text searches across tens of thousands of abstracts, the `pg_trgm` extension was enabled, and a GIN index was applied to the `articles` table.
4. **SQL Translation over Vector Embeddings:** For the Q&A feature, an NL-to-SQL architecture was chosen over semantic Vector Search (RAG). Medical datasets require precise counting, filtering, and exact-match filtering (e.g., "How many articles were published in 2024?"), which LLM SQL translation handles deterministically, whereas vector embeddings struggle with exact math.

## File layout

```
AISH_Assignment/
├── .env / .env.example          # Configuration (see below)
├── requirements.txt             # Python deps
├── sql/
│   ├── setup_db.sql             # Creates DB + 2 roles
│   └── schema.sql               # Creates 6 tables + indexes
└── src/
    ├── etl.py                   # PubMed → Postgres ETL
    ├── db.py                    # SQLAlchemy engine factories
    ├── queries.py               # Parameterized SQL helpers
    ├── llm.py                   # Ollama NL → SQL
    ├── sql_guard.py             # Python-layer SQL validator
    └── app.py                   # Streamlit UI (3 tabs)
```

## Prerequisites

- **Python 3.10+** (tested on 3.14)
- **PostgreSQL 15+** (tested on 18)
- **Ollama** running locally (tested on 0.23). [Install instructions](https://ollama.com/download)
- **~2 GB free disk** for the LLM model and Postgres data
- **~3 GB free RAM** when the LLM model is loaded

## Setup

### 1. Clone and configure
```powershell
git clone <this-repo>
cd AISH_Assignment
copy .env.example .env       # then edit .env with your real values
```

Required edits in `.env`:
- `PUBMED_EMAIL` — NCBI requires an email with every API call
- *(Optional)* change `DATABASE_URL` / `DATABASE_URL_READONLY` passwords. The defaults match `sql/setup_db.sql` and are fine for local dev — but change both files together before deploying anywhere shared.

### 2. Create the database and users
```powershell
psql -U postgres -f sql/setup_db.sql            # creates pubmed_db + 2 roles
psql -U postgres -d pubmed_db -f sql/schema.sql # creates 6 tables, indexes, and grants
```

### 3. Python environment
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 4. Pull the LLM
```powershell
ollama pull qwen2.5-coder:1.5b      # ~1 GB
```

> Disk-constrained? Set `OLLAMA_MODELS` to a path on a drive with space
> before running `ollama serve` — see [Troubleshooting](#troubleshooting).

### 5. Load PubMed data
```powershell
python src/etl.py
```

Expected output:
```
[ESEARCH] total matches in PubMed: 24455  ->  fetching 200
[EFETCH] 200/200
[OK] inserted=200  skipped=0
[TOTALS] {'articles': 200, 'journals': 123, 'authors': 886, 'mesh_terms': 285}
```

Re-running is safe — `ON CONFLICT DO NOTHING` makes it idempotent.

### 6. Launch the app
```powershell
streamlit run src/app.py
```

Open http://localhost:8501.

## Using the UI

### Search tab
- Free-text keyword (matches title + abstract via `ILIKE`)
- Year range slider (auto-detected from your data)
- Multi-select journal filter
- Results table with PMID, title, year, journal, author count, MeSH count
- **CSV / JSON export** buttons

### Detail tab
- Auto-populates from a row picked in Search, or paste any PMID directly
- Full abstract, ordered author list, MeSH terms, deep-link to PubMed

### Q&A tab
- One-click example questions, or free-text input
- Shows the **generated SQL** in a code block (assignment requirement)
- Runs only after passing safety validation
- Results render with CSV / JSON export

#### Example questions that work well

| Question | Generated SQL pattern |
|---|---|
| How many articles are in the database? | `SELECT COUNT(*) FROM articles` |
| List 5 articles published in 2024 | `WHERE year = 2024 LIMIT 5` |
| Top 3 journals by article count | `GROUP BY j.name ORDER BY COUNT DESC LIMIT 3` |
| Articles mentioning CAR-T | `ILIKE '%CAR-T%'` on title and abstract |
| How many articles per year | `GROUP BY year ORDER BY year` |

#### Safety model

Four layers protect the database from harmful SQL:

1. **Prompt** instructs the model to emit only `SELECT`/`WITH`, no semicolons, no comments.
2. **`sql_guard.validate_sql`** rejects multiple statements, comment markers, and forbidden keywords (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE`, `GRANT`, ...).
3. **DB role** `pubmed_readonly` only has `SELECT` grants.
4. **Statement timeout** of 5 seconds prevents runaway queries.

Try asking *"drop the articles table"* — the LLM may output `DROP TABLE`, but the guard blocks it.

## Schema reference

```sql
journals(id PK, name UNIQUE)
authors(id PK, full_name UNIQUE)
mesh_terms(id PK, term UNIQUE)
articles(pmid PK, title, abstract, year, journal_id → journals)
article_authors(article_id → articles, author_id → authors, position)
article_mesh(article_id → articles, mesh_id → mesh_terms)
```

Indexes on `articles.year`, `articles.journal_id`, and a GIN/trigram index
on `articles.title` for fast `ILIKE` keyword search.

## Configuration reference (`.env`)

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | App's read-write connection (UI + ETL) |
| `DATABASE_URL_READONLY` | Read-only connection for LLM-generated SQL |
| `PUBMED_EMAIL` | Required by NCBI for E-utilities |
| `PUBMED_API_KEY` | Optional — raises rate limit from 3/s to 10/s |
| `PUBMED_TOPIC` | Topic string for `Esearch` |
| `PUBMED_MAX_ARTICLES` | 100–200 per assignment spec |
| `PUBMED_REQUIRE_ABSTRACT` | If `true`, only fetch articles that have abstracts |
| `OLLAMA_MODEL` | Model tag served by Ollama |
| `OLLAMA_HOST` | Ollama server URL (default `http://localhost:11434`) |

## Troubleshooting

**`ollama pull` fails with "not enough space on the disk"**
By default Ollama stores models under `%USERPROFILE%\.ollama\models`. To
relocate to another drive:
```powershell
[Environment]::SetEnvironmentVariable("OLLAMA_MODELS", "D:\OllamaModels", "User")
# stop any running ollama, then `ollama serve` will use the new path
```

**LLM call fails with "model requires more system memory"**
Switch `OLLAMA_MODEL` in `.env` to a smaller model:
- `qwen2.5-coder:1.5b` — recommended, ~1 GB on disk, ~2 GB RAM
- `gemma3:4b` — better quality but needs ~4 GB RAM

**ETL fetches 0 PMIDs**
PubMed treats stop-words ("in", "of", "the") oddly. Quote multi-word
topics, e.g. `PUBMED_TOPIC="cancer immunotherapy"` rather than
`PUBMED_TOPIC=cancer in immunotherapy`.

**Streamlit shows "Connection refused"**
Ensure both Postgres and Ollama are running:
```powershell
Get-Process postgres, ollama
```

## Deliverables checklist

- [x] ETL script — `src/etl.py`
- [x] Database schema — `sql/schema.sql` + `sql/setup_db.sql`
- [x] App code — `src/app.py`, `src/db.py`, `src/queries.py`, `src/llm.py`, `src/sql_guard.py`
- [x] README — this file
- [ ] 2–3 min demo video — *optional, recommended for submission*
- [ ] AWS deployment — *stretch goal, not implemented*

## License

Submitted for assessment use.
