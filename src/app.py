"""PubMed Explorer — Streamlit UI (Light Theme, Interview-Ready)."""
from __future__ import annotations

import time

import streamlit as st
from sqlalchemy import text

from db import get_engine, get_readonly_engine
from llm import nl_to_sql
from queries import (
    get_article_detail,
    list_journals,
    run_readonly_query,
    search_articles,
    year_bounds,
)
from sql_guard import SQLValidationError, extract_sql, validate_sql

# ============================================================ PAGE CONFIG ==
st.set_page_config(
    page_title="PubMed Explorer",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================ THEME / CSS ==
st.markdown(
    """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  :root {
    --primary: #0D9488;
    --primary-soft: #F0FDFA;
    --primary-mid: #CCFBF1;
    --text: #1E293B;
    --muted: #64748B;
    --bg: #FFFFFF;
    --surface: #F8FAFC;
    --border: #E2E8F0;
    --accent: #6366F1;
    --accent-soft: #EEF2FF;
    --danger: #EF4444;
    --shadow-sm: 0 1px 3px rgba(0,0,0,0.06);
    --shadow-md: 0 4px 12px rgba(0,0,0,0.08);
  }

  html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
  .block-container { padding-top: 1.5rem !important; padding-bottom: 2rem !important; max-width: 1320px; }

  /* ----------- Tabs ----------- */
  .stTabs [data-baseweb="tab-list"] {
    gap: 0; border-bottom: 2px solid var(--border); background: transparent;
  }
  .stTabs [data-baseweb="tab"] {
    height: 48px; padding: 0 28px; font-size: 0.95rem; font-weight: 600;
    color: var(--muted); background: transparent; border-radius: 8px 8px 0 0;
    border-bottom: 2px solid transparent; margin-bottom: -2px;
  }
  .stTabs [data-baseweb="tab"]:hover { color: var(--text); background: var(--surface); }
  .stTabs [aria-selected="true"] {
    color: var(--primary) !important; background: var(--primary-soft) !important;
    border-bottom: 2px solid var(--primary) !important;
  }

  /* ----------- Buttons ----------- */
  button[kind="primary"] {
    background: var(--primary) !important; color: #fff !important;
    border: none !important; border-radius: 8px !important;
    font-weight: 600 !important; font-size: 0.88rem !important;
    box-shadow: var(--shadow-sm) !important; transition: all 0.15s ease;
  }
  button[kind="primary"]:hover { filter: brightness(1.1); transform: translateY(-1px); box-shadow: var(--shadow-md) !important; }

  button[kind="secondary"] {
    background: var(--bg) !important; color: var(--text) !important;
    border: 1.5px solid var(--border) !important; border-radius: 10px !important;
    font-weight: 500 !important; min-height: 64px !important;
    white-space: normal !important; text-align: left !important;
    padding: 12px 16px !important; line-height: 1.4 !important;
    transition: all 0.15s ease;
  }
  button[kind="secondary"]:hover {
    border-color: var(--primary) !important; background: var(--primary-soft) !important;
    color: var(--primary) !important; transform: translateY(-1px);
    box-shadow: var(--shadow-sm) !important;
  }

  /* ----------- Metric cards ----------- */
  div[data-testid="stMetric"] {
    background: var(--bg); border: 1.5px solid var(--border);
    border-top: 3px solid var(--primary); border-radius: 10px;
    padding: 14px 18px; box-shadow: var(--shadow-sm);
  }
  div[data-testid="stMetricLabel"] {
    font-size: 0.72rem; color: var(--muted);
    letter-spacing: 0.06em; text-transform: uppercase; font-weight: 600;
  }
  div[data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: 700; color: var(--text); }

  /* ----------- Section eyebrows ----------- */
  .eyebrow {
    font-size: 0.7rem; font-weight: 700; letter-spacing: 0.12em;
    color: var(--primary); text-transform: uppercase;
    margin: 1.2rem 0 0.5rem 0; padding-bottom: 4px;
    border-bottom: 2px solid var(--primary-mid); display: inline-block;
  }

  /* ----------- Pipeline banner ----------- */
  .pipeline-banner {
    display: flex; align-items: center; justify-content: center;
    gap: 6px; padding: 14px 20px; margin: 0.5rem 0 1rem 0;
    background: linear-gradient(135deg, var(--primary-soft), var(--accent-soft));
    border: 1.5px solid var(--border); border-radius: 12px;
    font-size: 0.82rem; font-weight: 500; color: var(--text);
  }
  .pipeline-step {
    background: var(--bg); border: 1px solid var(--border); border-radius: 8px;
    padding: 6px 14px; font-weight: 600; font-size: 0.78rem;
    box-shadow: var(--shadow-sm);
  }
  .pipeline-arrow { color: var(--primary); font-weight: 700; font-size: 1.1rem; }

  /* ----------- Code blocks ----------- */
  pre code { font-size: 0.84rem !important; line-height: 1.55 !important; }
  pre { padding: 14px !important; background: var(--surface) !important; border: 1px solid var(--border) !important; border-radius: 8px !important; }

  /* ----------- Dataframe ----------- */
  div[data-testid="stDataFrameResizable"] { font-size: 0.9rem; border-radius: 10px; overflow: hidden; border: 1px solid var(--border); }

  /* ----------- Sidebar ----------- */
  section[data-testid="stSidebar"] { background: var(--surface) !important; border-right: 1.5px solid var(--border) !important; }
  section[data-testid="stSidebar"] .stMarkdown h3 { color: var(--text); margin-top: 0.2rem; }

  /* ----------- Containers ----------- */
  div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 12px !important; border: 1px solid var(--border) !important;
    background: var(--bg) !important; box-shadow: var(--shadow-sm);
  }

  /* ----------- Headings ----------- */
  h1 { font-size: 1.9rem !important; font-weight: 700 !important; color: var(--text) !important; margin-bottom: 0 !important; }
  h2 { font-size: 1.4rem !important; margin-top: 1.2rem !important; color: var(--text) !important; }
  h3 { font-size: 1.15rem !important; margin-top: 0.6rem !important; color: var(--text) !important; }
  h4 { font-size: 1.02rem !important; color: var(--text) !important; }

  /* ----------- Captions ----------- */
  div[data-testid="stCaptionContainer"], .stCaption { color: var(--muted) !important; }

  /* ----------- Inputs ----------- */
  div[data-baseweb="input"] { border-radius: 8px !important; }
  input { font-family: 'Inter', sans-serif !important; }

  /* ----------- Tags / pills ----------- */
  .tag-pill {
    display: inline-block; padding: 4px 12px; margin: 3px 4px 3px 0;
    background: var(--primary-soft); color: var(--primary);
    border: 1px solid var(--primary-mid); border-radius: 20px;
    font-size: 0.8rem; font-weight: 500;
  }
  .tag-pill-accent {
    display: inline-block; padding: 4px 12px; margin: 3px 4px 3px 0;
    background: var(--accent-soft); color: var(--accent);
    border: 1px solid #C7D2FE; border-radius: 20px;
    font-size: 0.8rem; font-weight: 500;
  }

  /* ----------- Trace bar ----------- */
  .trace-bar {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 18px; margin: 8px 0;
    background: var(--primary-soft); border: 1px solid var(--primary-mid);
    border-radius: 10px; font-size: 0.82rem; font-weight: 500; color: var(--text);
  }
  .trace-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--primary); }

  /* ----------- Empty state ----------- */
  .empty-state {
    text-align: center; padding: 60px 20px; color: var(--muted);
  }
  .empty-state .icon { font-size: 3rem; margin-bottom: 10px; }
  .empty-state .title { font-size: 1.1rem; font-weight: 600; color: var(--text); }
  .empty-state .desc { font-size: 0.88rem; margin-top: 6px; }

  /* ----------- Number input hide steppers ----------- */
  button[data-testid="stNumberInputStepUp"],
  button[data-testid="stNumberInputStepDown"] { display: none !important; }
</style>
    """,
    unsafe_allow_html=True,
)

# ============================================================== ENGINES ==
engine = get_engine()
ro_engine = get_readonly_engine()


@st.cache_data(ttl=300)
def get_stats() -> dict:
    with engine.connect() as c:
        return {
            "articles": c.execute(text("SELECT COUNT(*) FROM articles")).scalar(),
            "journals": c.execute(text("SELECT COUNT(*) FROM journals")).scalar(),
            "authors": c.execute(text("SELECT COUNT(*) FROM authors")).scalar(),
            "mesh": c.execute(text("SELECT COUNT(*) FROM mesh_terms")).scalar(),
        }


@st.cache_data(ttl=300)
def cached_year_bounds() -> tuple[int, int]:
    return year_bounds(engine)


@st.cache_data(ttl=300)
def cached_journals() -> list[str]:
    return list_journals(engine)


@st.cache_data(ttl=300)
def cached_search(kw, yr_from, yr_to, journals_t, limit):
    journals = list(journals_t) if journals_t else None
    return search_articles(engine, kw, yr_from, yr_to, journals, limit)


@st.cache_data(ttl=300)
def cached_detail(pmid: int):
    return get_article_detail(engine, pmid)


# Column alias cleanup for LLM-generated results
FRIENDLY_COLS = {
    "n": "Count", "name": "Name", "count": "Count",
    "pmid": "PMID", "title": "Title", "year": "Year",
    "journal": "Journal", "abstract": "Abstract",
    "full_name": "Author", "term": "MeSH Term",
    "n_authors": "Authors", "n_mesh": "MeSH",
    "article_count": "Article Count",
}


def friendly_columns(df):
    """Rename raw SQL aliases to human-friendly labels."""
    return df.rename(columns={c: FRIENDLY_COLS.get(c, c.replace("_", " ").title()) for c in df.columns})


# ============================================================ SESSION ==
ss = st.session_state
ss.setdefault("detail_pmid_str", "")
ss.setdefault("qa_input", "")
ss.setdefault("qa_run", None)


# ============================================================ HEADER ==
head_left, head_right = st.columns([0.55, 0.45])
with head_left:
    st.markdown("# 🔬 PubMed Explorer")
    st.caption("End-to-end pipeline: PubMed API → ETL → PostgreSQL → Streamlit + Local LLM")
with head_right:
    s = get_stats()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Articles", f"{s['articles']:,}")
    m2.metric("Journals", f"{s['journals']:,}")
    m3.metric("Authors", f"{s['authors']:,}")
    m4.metric("MeSH", f"{s['mesh']:,}")

# Architecture pipeline banner
st.markdown(
    """
    <div class="pipeline-banner">
        <span class="pipeline-step">📡 PubMed API</span>
        <span class="pipeline-arrow">→</span>
        <span class="pipeline-step">⚙️ ETL (Python)</span>
        <span class="pipeline-arrow">→</span>
        <span class="pipeline-step">🗄️ PostgreSQL</span>
        <span class="pipeline-arrow">→</span>
        <span class="pipeline-step">🖥️ Streamlit UI</span>
        <span class="pipeline-arrow">→</span>
        <span class="pipeline-step">🤖 Ollama LLM</span>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================ SIDEBAR ==
yr_lo, yr_hi = cached_year_bounds()
journals_all = cached_journals()

with st.sidebar:
    st.markdown("### 🎛️ Search Filters")
    kw = st.text_input("Keyword", placeholder="checkpoint, CAR-T …", help="Searches title and abstract")
    yr_range = st.slider("Year range", yr_lo, yr_hi, (yr_lo, yr_hi))
    journals_pick = st.multiselect("Journals", options=journals_all, default=[])
    limit = st.slider("Max results", 10, 200, 50, 10)

    st.divider()

    st.markdown("##### 📌 Current Topic")
    st.info("**cancer immunotherapy** · 200 articles loaded via NCBI E-utilities")

    with st.expander("🏗️ How It Works", expanded=False):
        st.markdown("""
**1. Extract** — `etl.py` calls PubMed Esearch + Efetch to pull articles by topic.

**2. Transform** — Cleans titles, abstracts, authors, MeSH terms. Handles malformed records.

**3. Load** — Inserts into PostgreSQL (5 normalized tables). `ON CONFLICT` prevents duplicates.

**4. Serve** — Streamlit reads from Postgres with parameterized queries.

**5. Q&A** — Ollama (`qwen2.5-coder:0.5b`) translates natural language → SQL. Executes under a read-only DB role with 5s timeout.
        """)

    st.divider()
    st.markdown("##### Stack")
    st.caption("PostgreSQL · Biopython · Streamlit · Ollama / `qwen2.5-coder:0.5b`")


# ============================================================ TABS ==
tab_search, tab_detail, tab_qa = st.tabs(["🔍  Search", "📄  Detail", "💬  Q&A"])


# ============================================================ SEARCH ==
with tab_search:
    df = cached_search(
        kw or None,
        yr_range[0],
        yr_range[1],
        tuple(journals_pick),
        limit,
    )

    head_l, head_r = st.columns([0.55, 0.45])
    with head_l:
        st.markdown(
            f"### Results &nbsp;<span style='color:#64748B; font-weight:400; font-size:0.9rem;'>· {len(df)} matches</span>",
            unsafe_allow_html=True,
        )
    with head_r:
        if not df.empty:
            d1, d2 = st.columns(2)
            d1.download_button(
                "📥 Download CSV", data=df.to_csv(index=False),
                file_name="pubmed_results.csv", mime="text/csv",
                use_container_width=True, type="primary", key="search_csv",
            )
            d2.download_button(
                "📥 Download JSON", data=df.to_json(orient="records", indent=2),
                file_name="pubmed_results.json", mime="application/json",
                use_container_width=True, type="primary", key="search_json",
            )

    if df.empty:
        st.markdown(
            "<div class='empty-state'>"
            "<div class='icon'>🔍</div>"
            "<div class='title'>No matching articles</div>"
            "<div class='desc'>Try loosening the filters in the sidebar — broaden the year range or remove journal restrictions.</div>"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        # Jump-to-detail row above the table
        with st.container(border=True):
            j1, j2 = st.columns([0.78, 0.22])
            with j1:
                pmid_choice = st.selectbox(
                    "Pick an article to view details",
                    options=df["pmid"].tolist(),
                    format_func=lambda p: f"{p} · {df.loc[df.pmid == p, 'title'].iloc[0][:90]}",
                    label_visibility="collapsed",
                )
            with j2:
                if st.button("Open in Detail →", type="primary", use_container_width=True):
                    ss.detail_pmid_str = str(int(pmid_choice))
                    st.success(f"✅ PMID {pmid_choice} ready — switch to the **Detail** tab.")

        st.dataframe(
            df, use_container_width=True, hide_index=True, height=480,
            column_config={
                "pmid": st.column_config.NumberColumn("PMID", format="%d", width="small"),
                "title": st.column_config.TextColumn("Title", width="large"),
                "year": st.column_config.NumberColumn("Year", width="small"),
                "journal": st.column_config.TextColumn("Journal", width="medium"),
                "n_authors": st.column_config.NumberColumn("Authors", width="small"),
                "n_mesh": st.column_config.NumberColumn("MeSH", width="small"),
            },
        )


# ============================================================ DETAIL ==
with tab_detail:
    st.markdown("### Article Details")

    pmid_str = st.text_input(
        "Enter PMID",
        placeholder="e.g. 41463227",
        key="detail_pmid_str",
        help="Type a PMID, or pick one from the Search tab and click 'Open in Detail'.",
    )

    pmid_val = int(pmid_str) if pmid_str.strip().isdigit() else 0

    if not pmid_val:
        st.markdown(
            "<div class='empty-state'>"
            "<div class='icon'>📄</div>"
            "<div class='title'>No article selected</div>"
            "<div class='desc'>Enter a PMID above, or go to the <b>Search</b> tab → pick an article → click <b>\"Open in Detail →\"</b></div>"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        article = cached_detail(pmid_val)
        if not article:
            st.warning(f"No article with PMID **{pmid_val}** found in the database.")
        else:
            with st.container(border=True):
                st.markdown(f"#### {article['title']}")
                c1, c2, c3 = st.columns([0.22, 0.55, 0.23])
                c1.metric("Year", article["year"] or "—")
                c2.metric("Journal", (article["journal"] or "—"))
                with c3:
                    st.write("")
                    st.link_button(
                        "Open on PubMed ↗",
                        url=f"https://pubmed.ncbi.nlm.nih.gov/{article['pmid']}/",
                        use_container_width=True,
                    )

            st.markdown("<div class='eyebrow'>Abstract</div>", unsafe_allow_html=True)
            with st.container(border=True):
                st.write(article["abstract"] or "_No abstract on file._")

            ac, mc = st.columns(2)
            with ac:
                st.markdown(
                    f"<div class='eyebrow'>Authors · {len(article['authors'])}</div>",
                    unsafe_allow_html=True,
                )
                with st.container(border=True):
                    if article["authors"]:
                        pills = "".join(f"<span class='tag-pill'>{a}</span>" for a in article["authors"])
                        st.markdown(pills, unsafe_allow_html=True)
                    else:
                        st.write("_None_")
            with mc:
                st.markdown(
                    f"<div class='eyebrow'>MeSH Terms · {len(article['mesh_terms'])}</div>",
                    unsafe_allow_html=True,
                )
                with st.container(border=True):
                    if article["mesh_terms"]:
                        pills = "".join(f"<span class='tag-pill-accent'>{t}</span>" for t in article["mesh_terms"])
                        st.markdown(pills, unsafe_allow_html=True)
                    else:
                        st.write("_None_")


# ============================================================ Q&A ==
with tab_qa:
    st.markdown("### Natural-Language Q&A")
    st.caption(
        "A local LLM (`qwen2.5-coder:0.5b`) translates your question into SQL. "
        "Queries execute under a **read-only** DB role with a **5-second timeout**."
    )

    st.markdown("<div class='eyebrow'>Try an example</div>", unsafe_allow_html=True)
    EXAMPLES = [
        "How many articles are in the database?",
        "List 5 articles published in 2024",
        "Top 3 journals by article count",
        "Articles mentioning CAR-T",
        "How many articles per year",
    ]
    row1 = st.columns(3)
    row2 = st.columns(3)
    grid = row1 + row2
    for i, ex in enumerate(EXAMPLES):
        if grid[i].button(ex, key=f"ex_{i}", use_container_width=True):
            ss.qa_input = ex

    st.write("")

    with st.container(border=True):
        qcol, bcol = st.columns([0.84, 0.16])
        with qcol:
            question = st.text_input(
                "Question", placeholder="e.g. How many articles were published in 2023?",
                key="qa_input", label_visibility="collapsed",
            )
        with bcol:
            ask = st.button("Ask →", type="primary", use_container_width=True, disabled=not question.strip())

    if ask:
        t_start = time.time()
        with st.spinner("🤖 Translating your question to SQL… (may take 5–15s on first run)"):
            try:
                raw = nl_to_sql(question)
            except Exception as e:
                ss.qa_run = {"phase": "llm", "raw": None, "sql": None, "df": None,
                             "error": f"LLM call failed: {e}", "time": 0}
            else:
                candidate = extract_sql(raw)
                try:
                    safe_sql = validate_sql(candidate)
                except SQLValidationError as e:
                    ss.qa_run = {"phase": "guard", "raw": raw, "sql": candidate,
                                 "df": None, "error": str(e), "time": 0}
                else:
                    try:
                        df_q = run_readonly_query(ro_engine, safe_sql)
                        elapsed = round(time.time() - t_start, 1)
                        ss.qa_run = {"phase": "ok", "raw": raw, "sql": safe_sql,
                                     "df": df_q, "error": None, "time": elapsed}
                    except Exception as e:
                        ss.qa_run = {"phase": "db", "raw": raw, "sql": safe_sql,
                                     "df": None, "error": f"{type(e).__name__}: {e}", "time": 0}

    run = ss.qa_run
    if run:
        st.divider()

        if run["phase"] == "guard":
            st.error(f"🛡️  **Blocked by SQL safety guard** — {run['error']}")
            with st.expander("View blocked SQL"):
                st.code(run["sql"] or "", language="sql")
            with st.expander("View raw LLM output"):
                st.code(run["raw"] or "")

        elif run["phase"] == "llm":
            err_msg = run["error"]
            if "memory" in err_msg.lower() or "ram" in err_msg.lower():
                st.error("⚠️ Ollama needs more memory to load the model. **Try clicking Ask again** — it usually works on the second attempt.")
            else:
                st.error(err_msg)

        elif run["phase"] == "db":
            st.error(f"Query failed — {run['error']}")
            with st.expander("View generated SQL", expanded=True):
                st.code(run["sql"] or "", language="sql")

        else:  # ok
            dfq = friendly_columns(run["df"])
            elapsed = run.get("time", 0)

            # Pipeline trace bar
            st.markdown(
                f"<div class='trace-bar'>"
                f"<span class='trace-dot'></span> <b>Question</b> received"
                f"&nbsp;&nbsp;→&nbsp;&nbsp;"
                f"<span class='trace-dot'></span> <b>SQL generated</b> by LLM"
                f"&nbsp;&nbsp;→&nbsp;&nbsp;"
                f"<span class='trace-dot'></span> <b>{len(dfq)} rows</b> returned in <b>{elapsed}s</b>"
                f"</div>",
                unsafe_allow_html=True,
            )

            rl, rr = st.columns([0.55, 0.45])
            with rl:
                st.markdown(
                    f"### Results &nbsp;<span style='color:#64748B; font-weight:400; font-size:0.9rem;'>· {len(dfq)} rows</span>",
                    unsafe_allow_html=True,
                )
            with rr:
                if not dfq.empty:
                    dl1, dl2 = st.columns(2)
                    dl1.download_button(
                        "📥 Download CSV", data=dfq.to_csv(index=False),
                        file_name="qa_results.csv", mime="text/csv",
                        use_container_width=True, type="primary", key="qa_csv",
                    )
                    dl2.download_button(
                        "📥 Download JSON", data=dfq.to_json(orient="records", indent=2),
                        file_name="qa_results.json", mime="application/json",
                        use_container_width=True, type="primary", key="qa_json",
                    )

            if dfq.empty:
                st.info("Query ran successfully but returned no rows.")
            else:
                table_height = min(60 + len(dfq) * 38, 500)
                st.dataframe(dfq, use_container_width=True, hide_index=True, height=table_height)

            with st.expander("View generated SQL", expanded=True):
                st.code(run["sql"], language="sql")
