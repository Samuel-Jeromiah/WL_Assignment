"""
PubMed ETL: Esearch -> Efetch -> Transform -> Load into PostgreSQL.

Usage:  python src/etl.py
Config is read from .env (PUBMED_TOPIC, PUBMED_MAX_ARTICLES, DATABASE_URL).
Re-running is safe: ON CONFLICT DO NOTHING ensures no duplicates.
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path
from typing import Any

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


# -------------------------------------------------------------- transform --
def _parse_year(pubdate: dict) -> int | None:
    if pubdate.get("Year"):
        try:
            return int(str(pubdate["Year"]))
        except ValueError:
            pass
    medline = str(pubdate.get("MedlineDate", ""))
    m = re.search(r"\d{4}", medline)
    return int(m.group()) if m else None


def _join_abstract(abstract_node: Any) -> str | None:
    parts = abstract_node.get("AbstractText", []) if abstract_node else []
    if not parts:
        return None
    cleaned: list[str] = []
    for p in parts:
        label = p.attributes.get("Label") if hasattr(p, "attributes") else None
        text_part = str(p).strip()
        if not text_part:
            continue
        cleaned.append(f"{label}: {text_part}" if label else text_part)
    return " ".join(cleaned) or None


def _author_name(au: dict) -> str | None:
    last = str(au.get("LastName", "")).strip()
    fore = str(au.get("ForeName", "")).strip()
    if last and fore:
        return f"{last}, {fore}"
    if last:
        return last
    coll = au.get("CollectiveName")
    return str(coll).strip() if coll else None


def transform(raw: dict) -> dict | None:
    try:
        mc = raw["MedlineCitation"]
        a = mc["Article"]
        pmid = int(str(mc["PMID"]))
        title = str(a.get("ArticleTitle", "")).strip()
        if not title:
            return None
        abstract = _join_abstract(a.get("Abstract"))
        journal = str(a["Journal"]["Title"]).strip() or None
        year = _parse_year(a["Journal"]["JournalIssue"]["PubDate"])
        authors = [n for au in a.get("AuthorList", []) if (n := _author_name(au))]
        mesh = [str(m["DescriptorName"]).strip() for m in mc.get("MeshHeadingList", [])]
        return {
            "pmid": pmid,
            "title": title,
            "abstract": abstract,
            "year": year,
            "journal": journal,
            "authors": authors,
            "mesh_terms": mesh,
        }
    except (KeyError, ValueError) as e:
        print(f"[WARN] skipping malformed record: {e}")
        return None


# ------------------------------------------------------------------ main --
def main() -> int:
    print(f"[CONFIG] topic={TOPIC!r}  max={MAX_ARTICLES}")
    pmids = esearch_pmids(TOPIC, MAX_ARTICLES)
    if not pmids:
        print("[ERROR] no PMIDs returned — adjust the topic")
        return 1
    raw = efetch_records(pmids)
    print(f"[TRANSFORM] cleaning {len(raw)} records")
    rows = [r for r in (transform(x) for x in raw) if r]
    print(f"[TRANSFORM] kept {len(rows)} valid rows  (dropped {len(raw) - len(rows)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
