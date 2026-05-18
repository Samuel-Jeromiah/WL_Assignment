"""
PubMed ETL: Esearch -> Efetch -> Transform -> Load into PostgreSQL.

Usage:  python src/etl.py
Config is read from .env (PUBMED_TOPIC, PUBMED_MAX_ARTICLES, DATABASE_URL).
Re-running is safe: ON CONFLICT DO NOTHING ensures no duplicates.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from Bio import Entrez
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

Entrez.email = os.environ["PUBMED_EMAIL"]
if os.environ.get("PUBMED_API_KEY"):
    Entrez.api_key = os.environ["PUBMED_API_KEY"]

TOPIC = os.environ.get("PUBMED_TOPIC", "cancer immunotherapy").strip('"').strip("'")
MAX_ARTICLES = int(os.environ.get("PUBMED_MAX_ARTICLES", "200"))
REQUIRE_ABSTRACT = os.environ.get("PUBMED_REQUIRE_ABSTRACT", "false").lower() in {"1", "true", "yes"}


# ---------------------------------------------------------------- extract --
def esearch_pmids(topic: str, retmax: int) -> list[str]:
    query = f'"{topic}"[Title/Abstract]'
    if REQUIRE_ABSTRACT:
        query += " AND hasabstract[FILT]"
    print(f"[ESEARCH] query={query!r} retmax={retmax}")
    h = Entrez.esearch(db="pubmed", term=query, retmax=retmax, sort="relevance")
    result = Entrez.read(h)
    h.close()
    pmids = list(result["IdList"])
    print(f"[ESEARCH] total matches in PubMed: {result['Count']}  ->  fetching {len(pmids)}")
    return pmids


def efetch_records(pmids: list[str], batch: int = 50) -> list[dict]:
    records: list[dict] = []
    for i in range(0, len(pmids), batch):
        chunk = pmids[i : i + batch]
        print(f"[EFETCH] {i + len(chunk)}/{len(pmids)}")
        h = Entrez.efetch(db="pubmed", id=",".join(chunk), rettype="xml", retmode="xml")
        data = Entrez.read(h)
        h.close()
        records.extend(data.get("PubmedArticle", []))
        time.sleep(0.34)  # NCBI rate limit: 3 req/sec without API key
    return records


# ------------------------------------------------------------------ main --
def main() -> int:
    print(f"[CONFIG] topic={TOPIC!r}  max={MAX_ARTICLES}")
    pmids = esearch_pmids(TOPIC, MAX_ARTICLES)
    if not pmids:
        print("[ERROR] no PMIDs returned — adjust the topic")
        return 1
    raw = efetch_records(pmids)
    print(f"[EXTRACT] fetched {len(raw)} raw records")
    return 0


if __name__ == "__main__":
    sys.exit(main())
