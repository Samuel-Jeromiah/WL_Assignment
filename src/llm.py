"""NL -> SQL via Ollama. Designed for narrow, schema-aware translation.

Keep scope tight: titles, years, journals, authors, MeSH terms. The prompt
deliberately constrains the model to safer, simpler SELECT queries.
"""
from __future__ import annotations

import os
from pathlib import Path

import ollama
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:1.5b")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")


SCHEMA_PROMPT = """You translate natural-language questions into a single read-only PostgreSQL SELECT query.

# Schema

journals(id, name)
authors(id, full_name)              -- full_name format: "Last, First"
mesh_terms(id, term)
articles(pmid PRIMARY KEY, title, abstract, year, journal_id REFERENCES journals)
article_authors(article_id REFERENCES articles, author_id REFERENCES authors, position)
article_mesh(article_id REFERENCES articles, mesh_id REFERENCES mesh_terms)

# Hard rules
- Output ONLY the SQL query. No prose, no markdown fences, no explanation.
- Use a SINGLE SELECT statement. No semicolons. No comments.
- Never use INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE/GRANT.
- Use ILIKE for case-insensitive text matching with %wildcards%.
- Always alias tables (a, j, au, mt, aa, am).
- LEFT JOIN journals when journal info may be missing.
- Always add LIMIT 50 unless the user asks for a count or specific number.

# Examples

Q: How many articles were published in 2023?
A: SELECT COUNT(*) AS n FROM articles WHERE year = 2023

Q: List articles from Nature
A: SELECT a.pmid, a.title, a.year FROM articles a JOIN journals j ON a.journal_id = j.id WHERE j.name ILIKE '%Nature%' LIMIT 50

Q: Top 5 journals by article count
A: SELECT j.name, COUNT(*) AS n FROM articles a JOIN journals j ON a.journal_id = j.id GROUP BY j.name ORDER BY n DESC LIMIT 5
"""


def nl_to_sql(question: str) -> str:
    """Call Ollama and return raw model output (still needs validation)."""
    client = ollama.Client(host=OLLAMA_HOST)
    resp = client.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": SCHEMA_PROMPT},
            {"role": "user", "content": question},
        ],
        options={"temperature": 0.1},
    )
    return resp["message"]["content"]
