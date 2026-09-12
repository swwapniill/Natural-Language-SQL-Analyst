"""
app.py

Day 10-11: the Streamlit interface. This does NOT contain any new logic --
it calls the exact same pipeline.ask_question() and output_formatter
functions that have already been tested (25/25 benchmark, 19/19 edge
cases) via the command line. The app is just a front door onto code
that's already proven correct.

Run with: streamlit run app.py
"""
import streamlit as st
import pandas as pd
import matplotlib
matplotlib.use("Agg")
from PIL import Image

from pipeline import ask_question
from output_formatter import build_summary, build_table, build_chart_figure, _is_money_column, _format_money, _pretty_label

APP_ICON = Image.open("icon.png")
GITHUB_URL = "https://github.com/swwapniill/Natural-Language-SQL-Analyst"

st.set_page_config(page_title="Chatalyst", page_icon=APP_ICON, layout="wide")

MAX_QUESTIONS_PER_SESSION = 15

if "question_count" not in st.session_state:
    st.session_state.question_count = 0

# ---------------- Sidebar: dataset credibility ----------------
with st.sidebar:
    col_icon, col_name = st.columns([1, 4])
    with col_icon:
        st.image("icon.png", width=48)
    with col_name:
        st.markdown("### Chatalyst")
    st.caption("Olist E-Commerce · real Brazilian marketplace data, 2016–2018 · loaded into SQLite")

    with st.container(border=True):
        st.metric("Orders", "99,441")
        st.metric("Customers", "96,096")
        st.metric("Sellers", "3,095")
        st.metric("Products", "32,951")

    with st.container(border=True):
        st.markdown(
            "**Safety**\n\n"
            "Every query is parsed and validated before it runs — SELECT-only, "
            "real tables/columns only, read-only connection, 10s timeout. "
            "Destructive or out-of-scope requests are declined, not attempted.\n\n"
            "Validated against 25 accuracy checks and 19 adversarial edge cases."
        )

    remaining = MAX_QUESTIONS_PER_SESSION - st.session_state.question_count
    st.caption(f"This is a shared public demo running on a free-tier API quota. "
               f"{max(remaining, 0)} question{'s' if remaining != 1 else ''} left this session.")

    st.markdown(f"[View source on GitHub ↗]({GITHUB_URL})")

# ---------------- Main ----------------
header_col1, header_col2 = st.columns([1, 8])
with header_col1:
    st.image("icon.png", width=64)
with header_col2:
    st.title("Chatalyst")
st.caption(
    "Ask a question about the Olist e-commerce dataset in plain English. "
    "A read-only SQL query is generated, validated, and run against the real database."
)

EXAMPLE_QUESTIONS = [
    ("💰", "What are the top 5 product categories by revenue?"),
    ("👥", "How many unique customers do we have?"),
    ("📈", "What was revenue by month?"),
    ("🗺️", "Which state has the most customers?"),
]

if "question_input" not in st.session_state:
    st.session_state.question_input = ""

st.write("**Try an example:**")
row1 = st.columns(2)
row2 = st.columns(2)
button_slots = row1 + row2
for slot, (icon, eq) in zip(button_slots, EXAMPLE_QUESTIONS):
    if slot.button(f"{icon} {eq}", use_container_width=True):
        st.session_state.question_input = eq

question = st.text_input(
    "Your question",
    key="question_input",
    placeholder="e.g. What are the top 5 product categories by revenue?",
)

ask_clicked = st.button("Ask", type="primary")

if ask_clicked and st.session_state.question_count >= MAX_QUESTIONS_PER_SESSION:
    st.error(
        f"You've reached the {MAX_QUESTIONS_PER_SESSION}-question limit for this demo session. "
        f"This protects the shared free-tier API quota for other visitors. "
        f"Refresh the page to reset, or clone the repo to run it with your own API key."
    )
elif ask_clicked and question.strip():
    st.session_state.question_count += 1
    with st.spinner("Generating and running your query..."):
        result = ask_question(question)

    summary = build_summary(question, result)

    if result["status"] == "refused":
        st.warning(f"🚫 {summary}")
    elif result["status"] == "no_query":
        st.info(f"ℹ️ {summary}")
    elif result["status"] == "error":
        st.error(f"⚠️ {summary}")
    else:
        st.success(summary)

        df = build_table(result["columns"], result["rows"])

        # Single-value results (e.g. "how many orders") get a big, readable
        # number instead of a cramped 1x1 table -- this is the case that
        # previously looked plainest.
        if len(df) == 1 and len(df.columns) == 1:
            col_name = df.columns[0]
            value = df.iloc[0, 0]
            display_value = _format_money(value) if _is_money_column(col_name) else f"{value:,}" if isinstance(value, (int, float)) else str(value)
            # raw SQL aggregate names like "COUNT(*)" don't prettify cleanly --
            # fall back to a generic label rather than showing "Count(*)"
            metric_label = "Result" if any(c in col_name for c in "()*") else _pretty_label(col_name)
            st.metric(label=metric_label, value=display_value)
        else:
            display_df = df.copy()
            for col in display_df.columns:
                is_id_col = "id" in col.lower()
                if _is_money_column(col):
                    display_df[col] = display_df[col].apply(_format_money)
                elif not is_id_col and pd.api.types.is_string_dtype(display_df[col]):
                    # "health_beauty" -> "Health Beauty" in the table too,
                    # matching the chart -- but never touch ID/hash columns,
                    # prettifying those would corrupt real identifiers.
                    display_df[col] = display_df[col].apply(
                        lambda v: _pretty_label(v) if isinstance(v, str) and "_" in v else v
                    )
            display_df.columns = [_pretty_label(c) if "(" not in c else c for c in display_df.columns]

            fig = build_chart_figure(result["columns"], result["rows"])

            if fig:
                table_col, chart_col = st.columns([1, 1])
                with table_col:
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
                with chart_col:
                    st.pyplot(fig)
            else:
                st.dataframe(display_df, use_container_width=True, hide_index=True)

        with st.expander("View the SQL that was run"):
            st.code(result["sql"], language="sql")
            if result.get("retried"):
                st.caption("Note: the first attempt failed and was automatically corrected on retry.")

elif ask_clicked:
    st.warning("Type a question first.")

st.divider()
footer_col1, footer_col2 = st.columns([3, 1])
with footer_col1:
    st.caption(
        "Built on the real Olist Brazilian e-commerce dataset. "
        "Read-only by design -- no query can modify or delete data, enforced at both "
        "the SQL-parsing level and the database connection level."
    )
with footer_col2:
    st.caption(f"[GitHub repo ↗]({GITHUB_URL})")
