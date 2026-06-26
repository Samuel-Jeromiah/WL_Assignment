# MedQuery-AI

Ask plain-English questions about biomedical literature and get answers backed
by real SQL - not vibes. MedQuery-AI pulls articles from **PubMed**, normalises
them into **Postgres**, and uses an LLM to translate natural language into
**validated, read-only SQL** over that data.

> **What it is (and isn't):** this is *LLM-powered text-to-SQL*, not vector RAG.
> For a structured corpus, questions like *"how many articles per year"* or
> *"top 5 journals"* need exact counting and filtering - which SQL does
> deterministically and embeddings do not. The LLM's job is translation; the
> database is the source of truth.

| Component | Detail |
|---|---|
| Data source | PubMed E-utilities (`Esearch` + `Efetch`) via Biopython |
| Storage | Postgres (Neon), 6 normalized tables, dedup via `ON CONFLICT` |
| LLM | **Groq** (`llama-3.3-70b-versatile`) for NL -> SQL |
| UI | Streamlit - Search, Detail, and natural-language Q&A |
| Safety | Layered SQL guard + read-only execution + 5s statement timeout |

## Architecture

```
PubMed API  --Esearch/Efetch--►  ETL (src/etl.py)  --►  Neon Postgres
                                  transform + dedup       journals · authors · mesh_terms
                                                          articles · article_authors · article_mesh
                                                                │
                          Streamlit Search / Detail  ◄----------┤
                                                                │
                          Q&A:  question --► Groq --► SQL  ------┘
                                 └-► sql_guard.validate_sql() -► read-only execute (5s timeout)
```

## Why it's interesting

- **Schema-grounded NL->SQL.** A tightly-scoped prompt gives the model the exact
  schema and hard rules (single `SELECT`, no DML/DDL, always `LIMIT`), so it
  emits narrow, safe queries.
- **Defense in depth on the query path.** Even if the model misbehaves:
  (1) the prompt constrains it, (2) `sql_guard.validate_sql` rejects multiple
  statements / comments / forbidden keywords, (3) execution runs on a read-only
  connection, and (4) a `statement_timeout` kills runaway queries.
- **Idempotent ETL.** `ON CONFLICT DO NOTHING` means the pipeline is safe to
  re-run (e.g. on a schedule) without duplicating rows.
- **3NF schema + trigram index.** Junction tables for authors/MeSH, plus a
  `pg_trgm` GIN index for fast `ILIKE` keyword search.

## Run it

You need two free accounts: **Groq** (LLM) and **Neon** (Postgres).

### 1. Configure
```bash
cp .env.example .env       # then fill in the values below
```
- `GROQ_API_KEY` - free key from <https://console.groq.com>
- `DATABASE_URL` - your Neon **pooled** connection string, with
  `?sslmode=require` and the `+psycopg` driver
  (`postgresql+psycopg://user:pass@host/neondb?sslmode=require`)
- `PUBMED_EMAIL` - NCBI requires an email with every API call
- `DATABASE_URL_READONLY` *(optional)* - a SELECT-only Neon role; leave blank to
  reuse `DATABASE_URL` (the SQL guard + timeout still protect the query path)

### 2. Create the schema (on Neon)
Open Neon's SQL editor (or `psql` with your connection string) and run
[`sql/schema.sql`](sql/schema.sql) - it creates the 6 tables, indexes, and the
`pg_trgm` extension. *(The `GRANT ... pubmed_readonly` lines only apply if you
created that optional read-only role; otherwise ignore them.
[`sql/setup_db.sql`](sql/setup_db.sql) is for a local Postgres only.)*

### 3. Install + seed
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python src/etl.py        # pulls ~200 PubMed articles into Neon (idempotent)
```

### 4. Launch
```bash
streamlit run src/app.py
```

## Deploy (free) - Streamlit Community Cloud

1. Push this repo to GitHub.
2. On <https://share.streamlit.io>, create an app pointing at `src/app.py`.
3. In **Advanced settings -> Secrets**, add `GROQ_API_KEY`, `DATABASE_URL`
   (and `DATABASE_URL_READONLY` if used), and `PUBMED_*` values.
4. Deploy. (Seed the Neon DB once via `etl.py` from your machine first.)

> Free tiers sleep after inactivity - the first request may take a few seconds
> to wake. Hugging Face Spaces (Streamlit SDK) works as an alternative host.

## Using the UI

- **Search** - keyword (title + abstract `ILIKE`), year range, journal filter; CSV/JSON export.
- **Detail** - full abstract, ordered authors, MeSH terms, deep-link to PubMed.
- **Q&A** - ask in plain English; the generated SQL is shown, validated, then executed read-only.

**Try:** *"How many articles per year"* · *"Top 3 journals by article count"* ·
*"Articles mentioning CAR-T"*. Ask *"drop the articles table"* and watch the
guard block it.

## Schema

```sql
journals(id PK, name UNIQUE)
authors(id PK, full_name UNIQUE)
mesh_terms(id PK, term UNIQUE)
articles(pmid PK, title, abstract, year, journal_id -> journals)
article_authors(article_id -> articles, author_id -> authors, position)
article_mesh(article_id -> articles, mesh_id -> mesh_terms)
```

## Stack

Python · Biopython · SQLAlchemy · Postgres (Neon) · Streamlit · Groq (Llama-3.3-70B)
