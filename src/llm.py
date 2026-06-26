"""NL -> SQL via a hosted LLM (Groq). Designed for narrow, schema-aware translation.

Keep scope tight: titles, years, journals, authors, MeSH terms. The prompt
deliberately constrains the model to safer, simpler SELECT queries.

Swapped from local Ollama to Groq so the app is cloud-deployable (Streamlit
Cloud / HF Spaces) without a local model server. The nl_to_sql() contract is
unchanged: it returns raw model text that still goes through the SQL guard.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

# Any current Groq chat model works; 70B gives the most reliable SQL.
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")


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

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Create a free key at "
                "https://console.groq.com and add it to your .env "
                "(or the deploy host's secrets)."
            )
        _client = Groq(api_key=api_key)
    return _client


def nl_to_sql(question: str) -> str:
    """Call the LLM and return raw model output (still needs validation)."""
    resp = _get_client().chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SCHEMA_PROMPT},
            {"role": "user", "content": question},
        ],
        temperature=0.1,
    )
    return resp.choices[0].message.content or ""
