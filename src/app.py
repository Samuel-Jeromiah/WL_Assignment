"""PubMed Explorer — Streamlit UI."""
from __future__ import annotations

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
  :root {
    --accent: #FF4B6E;
    --accent-soft: rgba(255, 75, 110, 0.10);
    --border: rgba(255, 255, 255, 0.08);
    --surface: rgba(255, 255, 255, 0.03);
    --muted: rgba(232, 234, 240, 0.55);
  }

  /* App-level breathing room */
  .block-container { padding-top: 1.8rem !important; padding-bottom: 3rem !important; max-width: 1320px; }

  /* ----------- Tabs ----------- */
  .stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    border-bottom: 1px solid var(--border);
    margin-top: 0.4rem;
  }
  .stTabs [data-baseweb="tab"] {
    height: 48px;
    padding: 0 26px;
    font-size: 1.0rem;
    font-weight: 500;
    color: var(--muted);
    border-radius: 10px 10px 0 0;
    background: transparent;
  }
  .stTabs [data-baseweb="tab"]:hover { color: #E8EAED; background: var(--surface); }
  .stTabs [aria-selected="true"] {
    color: var(--accent) !important;
    background: var(--accent-soft) !important;
    border-bottom: 2px solid var(--accent);
  }

  /* ----------- Suggestion cards (secondary buttons) ----------- */
  button[kind="secondary"] {
    min-height: 70px !important;
    white-space: normal !important;
    text-align: left !important;
    padding: 14px 16px !important;
    line-height: 1.4 !important;
    border-radius: 12px !important;
    font-weight: 500 !important;
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    color: #E8EAED !important;
    transition: all 0.14s ease;
  }
  button[kind="secondary"]:hover {
    border-color: var(--accent) !important;
    background: var(--accent-soft) !important;
    transform: translateY(-1px);
  }

  /* ----------- Primary buttons (Ask, downloads, Open) ----------- */
  button[kind="primary"] {
    min-height: 40px !important;
    padding: 0 18px !important;
    border-radius: 10px !important;
    font-weight: 500 !important;
  }

  /* ----------- Section eyebrows ----------- */
  .eyebrow {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    color: var(--accent);
    text-transform: uppercase;
    margin: 1.0rem 0 0.6rem 0;
  }

  /* ----------- Code blocks softer ----------- */
  pre code { font-size: 0.86rem !important; line-height: 1.55 !important; }
  pre { padding: 14px !important; background: rgba(0,0,0,0.25) !important; border: 1px solid var(--border) !important; }

  /* ----------- Metric cards ----------- */
  div[data-testid="stMetric"] {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 12px 16px;
  }
  div[data-testid="stMetricLabel"] { font-size: 0.74rem; color: var(--muted); letter-spacing: 0.04em; text-transform: uppercase; }
  div[data-testid="stMetricValue"] { font-size: 1.5rem; }

  /* ----------- Dataframe ----------- */
  div[data-testid="stDataFrameResizable"] { font-size: 0.92rem; border-radius: 10px; overflow: hidden; }

  /* ----------- Sidebar ----------- */
  section[data-testid="stSidebar"] { background: #11141C; border-right: 1px solid var(--border); }
  section[data-testid="stSidebar"] .stMarkdown h3 { color: #E8EAED; margin-top: 0.2rem; }

  /* ----------- Bordered containers tighter ----------- */
  div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 12px !important;
    background: var(--surface);
  }

  /* ----------- Heading sizing ----------- */
  h1 { font-size: 2.0rem !important; font-weight: 700 !important; margin-bottom: 0 !important; }
  h2 { font-size: 1.45rem !important; margin-top: 1.4rem !important; }
  h3 { font-size: 1.15rem !important; margin-top: 0.8rem !important; }
  h4 { font-size: 1.02rem !important; }

  /* ----------- Caption color ----------- */
  div[data-testid="stCaptionContainer"], .stCaption { color: var(--muted) !important; }

  /* ----------- Number input ----------- */
  div[data-baseweb="input"] { border-radius: 10px; }
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


# ============================================================ SESSION ==
ss = st.session_state
ss.setdefault("detail_pmid", 0)
ss.setdefault("qa_input", "")
ss.setdefault("qa_run", None)


# ============================================================ HEADER ==
head_left, head_right = st.columns([0.55, 0.45])
with head_left:
    st.markdown("# 🔬 PubMed Explorer")
    st.caption("Local end-to-end: PubMed → PostgreSQL → Streamlit + local LLM Q&A.")
with head_right:
    s = get_stats()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Articles", f"{s['articles']:,}")
    m2.metric("Journals", f"{s['journals']:,}")
    m3.metric("Authors", f"{s['authors']:,}")
    m4.metric("MeSH", f"{s['mesh']:,}")


# ============================================================ SIDEBAR ==
yr_lo, yr_hi = cached_year_bounds()
journals_all = cached_journals()

with st.sidebar:
    st.markdown("### 🎛️ Search filters")
    st.caption("Used by the **Search** tab.")
    kw = st.text_input("Keyword", placeholder="checkpoint, CAR-T …", help="Searches title and abstract")
    yr_range = st.slider("Year range", yr_lo, yr_hi, (yr_lo, yr_hi))
    journals_pick = st.multiselect("Journals", options=journals_all, default=[])
    limit = st.slider("Max results", 10, 200, 50, 10)

    st.divider()
    st.markdown("##### Stack")
    st.caption(
        "PostgreSQL · Biopython · Streamlit · "
        "Ollama / `qwen2.5-coder:1.5b`"
    )


# ============================================================ TABS ==
tab_search, tab_detail, tab_qa = st.tabs(["🔍  Search", "📄  Detail", "💬  Q&A"])


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
            f"### Results &nbsp;<span style='color:rgba(232,234,240,0.45); font-weight:400; font-size:0.95rem;'>· {len(df)} matches</span>",
            unsafe_allow_html=True,
        )
    with head_r:
        if not df.empty:
            d1, d2 = st.columns(2)
            d1.download_button(
                "Download CSV",
                data=df.to_csv(index=False),
                file_name="pubmed_results.csv",
                mime="text/csv",
                use_container_width=True,
                type="primary",
                key="search_csv",
            )
            d2.download_button(
                "Download JSON",
                data=df.to_json(orient="records", indent=2),
                file_name="pubmed_results.json",
                mime="application/json",
                use_container_width=True,
                type="primary",
                key="search_json",
            )

    if df.empty:
        st.info("No matching articles. Loosen the filters in the sidebar and try again.")
    else:
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            height=480,
            column_config={
                "pmid": st.column_config.NumberColumn("PMID", format="%d", width="small"),
                "title": st.column_config.TextColumn("Title", width="large"),
                "year": st.column_config.NumberColumn("Year", width="small"),
                "journal": st.column_config.TextColumn("Journal", width="medium"),
                "n_authors": st.column_config.NumberColumn("Authors", width="small"),
                "n_mesh": st.column_config.NumberColumn("MeSH", width="small"),
            },
        )

        st.markdown("<div class='eyebrow'>Jump to one</div>", unsafe_allow_html=True)
        with st.container(border=True):
            j1, j2 = st.columns([0.78, 0.22])
            with j1:
                pmid_choice = st.selectbox(
                    "Pick an article",
                    options=df["pmid"].tolist(),
                    format_func=lambda p: f"{p} · {df.loc[df.pmid == p, 'title'].iloc[0][:90]}",
                    label_visibility="collapsed",
                )
            with j2:
                if st.button("Open in Detail →", type="primary", use_container_width=True):
                    ss.detail_pmid = int(pmid_choice)
                    st.success(f"PMID {pmid_choice} ready — switch to the **Detail** tab.")


# ============================================================ DETAIL ==
with tab_detail:
    st.markdown("### Article details")

    pmid_input = st.number_input(
        "PMID",
        min_value=0,
        step=1,
        format="%d",
        key="detail_pmid",
        help="Type a PMID, or pick one from the Search tab and click 'Open in Detail'.",
    )

    if not pmid_input:
        st.info("Enter a PMID above, or pick one from the **Search** tab.")
    else:
        article = cached_detail(int(pmid_input))
        if not article:
            st.warning(f"No article with PMID {pmid_input} in the database.")
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
                    st.write(" · ".join(article["authors"]) if article["authors"] else "_None_")
            with mc:
                st.markdown(
                    f"<div class='eyebrow'>MeSH terms · {len(article['mesh_terms'])}</div>",
                    unsafe_allow_html=True,
                )
                with st.container(border=True):
                    st.write(" · ".join(article["mesh_terms"]) if article["mesh_terms"] else "_None_")


# ============================================================ Q&A ==
with tab_qa:
    st.markdown("### Natural-language Q&A")
    st.caption(
        "A local LLM (`qwen2.5-coder:1.5b`) translates your question into SQL. "
        "Queries execute under a read-only DB role with a 5-second timeout."
    )

    st.markdown("<div class='eyebrow'>Try an example</div>", unsafe_allow_html=True)
    EXAMPLES = [
        "How many articles are in the database?",
        "List 5 articles published in 2024",
        "Top 3 journals by article count",
        "Articles mentioning CAR-T",
        "How many articles per year",
    ]
    # 3 + 2 grid
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
                "Question",
                placeholder="e.g. How many articles were published in 2023?",
                key="qa_input",
                label_visibility="collapsed",
            )
        with bcol:
            ask = st.button(
                "Ask →",
                type="primary",
                use_container_width=True,
                disabled=not question.strip(),
            )

    if ask:
        with st.spinner("Translating to SQL…"):
            try:
                raw = nl_to_sql(question)
            except Exception as e:
                ss.qa_run = {"phase": "llm", "raw": None, "sql": None, "df": None,
                             "error": f"LLM call failed: {e}"}
            else:
                candidate = extract_sql(raw)
                try:
                    safe_sql = validate_sql(candidate)
                except SQLValidationError as e:
                    ss.qa_run = {"phase": "guard", "raw": raw, "sql": candidate,
                                 "df": None, "error": str(e)}
                else:
                    try:
                        df_q = run_readonly_query(ro_engine, safe_sql)
                        ss.qa_run = {"phase": "ok", "raw": raw, "sql": safe_sql,
                                     "df": df_q, "error": None}
                    except Exception as e:
                        ss.qa_run = {"phase": "db", "raw": raw, "sql": safe_sql,
                                     "df": None, "error": f"{type(e).__name__}: {e}"}

    run = ss.qa_run
    if run:
        st.divider()

        if run["phase"] == "guard":
            st.error(f"🛡️  Blocked by safety guard — {run['error']}")
            with st.expander("View blocked SQL"):
                st.code(run["sql"] or "", language="sql")
            with st.expander("View raw LLM output"):
                st.code(run["raw"] or "")

        elif run["phase"] == "llm":
            st.error(run["error"])

        elif run["phase"] == "db":
            st.error(f"Query failed — {run['error']}")
            with st.expander("View generated SQL", expanded=True):
                st.code(run["sql"] or "", language="sql")

        else:  # ok
            dfq = run["df"]
            rl, rr = st.columns([0.55, 0.45])
            with rl:
                st.markdown(
                    f"### Results &nbsp;<span style='color:rgba(232,234,240,0.45); font-weight:400; font-size:0.95rem;'>· {len(dfq)} rows</span>",
                    unsafe_allow_html=True,
                )
            with rr:
                if not dfq.empty:
                    dl1, dl2 = st.columns(2)
                    dl1.download_button(
                        "Download CSV",
                        data=dfq.to_csv(index=False),
                        file_name="qa_results.csv",
                        mime="text/csv",
                        use_container_width=True,
                        type="primary",
                        key="qa_csv",
                    )
                    dl2.download_button(
                        "Download JSON",
                        data=dfq.to_json(orient="records", indent=2),
                        file_name="qa_results.json",
                        mime="application/json",
                        use_container_width=True,
                        type="primary",
                        key="qa_json",
                    )

            if dfq.empty:
                st.info("Query ran but returned no rows.")
            else:
                st.dataframe(dfq, use_container_width=True, hide_index=True, height=380)

            with st.expander("View generated SQL", expanded=False):
                st.code(run["sql"], language="sql")
