"""
output_formatter.py

Day 9: turns a raw pipeline result into something a non-technical person
can actually read -- a results table, a chart when the data shape
supports one, and a one-line plain-English restatement of what was run.

Design decision (stated explicitly, not hidden): the "plain English
restatement" is built from the ORIGINAL QUESTION plus the LLM's stated
assumption (if any), not from a second LLM call asking it to summarize
itself. This is cheaper, has no extra failure mode, and is arguably more
trustworthy -- it shows the user exactly what they asked and exactly
what assumption was applied, rather than a paraphrase that could drift
from either.
"""
import re
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # no display needed, just save to file
import matplotlib.pyplot as plt


def build_summary(question: str, result: dict) -> str:
    """One-line plain-English restatement of what was run."""
    if result["status"] == "refused":
        return f"Declined: {result['message']}"
    if result["status"] == "no_query":
        return f"Can't answer that from this data: {result['message']}"
    if result["status"] == "error":
        return f"Something went wrong: {result['message']}"

    summary = f'You asked: "{question}"'
    if result.get("assumption"):
        summary += f" — I assumed: {result['assumption']}."
    row_count = len(result["rows"])
    summary += f" ({row_count} row{'s' if row_count != 1 else ''} returned"
    if result.get("retried"):
        summary += ", corrected after 1 retry"
    summary += ")"
    return summary


def build_table(columns: list, rows: list) -> pd.DataFrame:
    """Results as a pandas DataFrame -- easy to display in Streamlit later,
    or print/export in the meantime."""
    return pd.DataFrame(rows, columns=columns)


_DATE_COL_HINTS = ("date", "timestamp", "_at", "year", "month", "ym")

_MONEY_COL_HINTS = ("revenue", "price", "payment", "value", "freight", "total", "spend", "paid")


def _is_money_column(col_name: str) -> bool:
    return any(h in col_name.lower() for h in _MONEY_COL_HINTS)


def _format_money(v) -> str:
    try:
        return f"${float(v):,.2f}"
    except (TypeError, ValueError):
        return str(v)


def _pretty_label(col_name: str) -> str:
    """'category_name' -> 'Category Name' -- for chart titles/axis labels only,
    the raw column name is still used everywhere the code needs to match it."""
    return col_name.replace("_", " ").title()


def _looks_like_date_column(col_name: str, sample_values) -> bool:
    name_hint = any(h in col_name.lower() for h in _DATE_COL_HINTS)
    if not name_hint:
        return False
    for v in sample_values[:3]:
        if isinstance(v, str) and re.match(r"^\d{4}(-\d{2}){0,2}", v):
            return True
    return False


def _is_numeric_column(sample_values) -> bool:
    return all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in sample_values if v is not None)


def _select_chart_data(columns: list, rows: list):
    """
    Shared heuristic, used by both the file-saving CLI version and the
    Streamlit figure version, so the chart-selection logic only lives in
    one place. Returns None if no chart suits this data shape, otherwise
    a dict with everything needed to draw it.
    """
    if len(rows) <= 1 or len(columns) < 2:
        return None

    numeric_col_idx = None
    for i in range(len(columns)):
        sample = [r[i] for r in rows[:10]]
        if _is_numeric_column(sample):
            numeric_col_idx = i
            break
    if numeric_col_idx is None:
        return None

    label_col_idx = None
    for i in range(len(columns)):
        if i == numeric_col_idx:
            continue
        label_col_idx = i
        break
    if label_col_idx is None:
        return None

    labels_raw = [r[label_col_idx] for r in rows[:20]]
    is_date = _looks_like_date_column(columns[label_col_idx], [r[label_col_idx] for r in rows[:3]])
    is_id_like = "id" in columns[label_col_idx].lower()

    if is_date or is_id_like:
        labels = [str(v) for v in labels_raw]
    else:
        # "health_beauty" -> "Health Beauty" -- raw snake_case values look
        # unfinished in a chart; prettify anything that isn't a date or ID.
        labels = [_pretty_label(str(v)) for v in labels_raw]

    values = [r[numeric_col_idx] for r in rows[:20]]
    is_money = _is_money_column(columns[numeric_col_idx])

    return {
        "labels": labels,
        "values": values,
        "is_date": is_date,
        "is_money": is_money,
        "metric_label": _pretty_label(columns[numeric_col_idx]),
        "axis_label": _pretty_label(columns[label_col_idx]),
    }


def _draw_chart(chart_data, fig=None, ax=None):
    """Draws onto the given figure/axes (creating new ones if not passed),
    applying the same styling either way. Returns (fig, ax)."""
    if fig is None or ax is None:
        fig, ax = plt.subplots(figsize=(8, 4.5))

    if chart_data["is_date"]:
        ax.plot(chart_data["labels"], chart_data["values"], marker="o")
        ax.set_title(f"{chart_data['metric_label']} over {chart_data['axis_label']}")
    else:
        ax.bar(chart_data["labels"], chart_data["values"])
        ax.set_title(f"{chart_data['metric_label']} by {chart_data['axis_label']}")

    ax.set_ylabel(chart_data["metric_label"])
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    if chart_data["is_money"]:
        ax.yaxis.set_major_formatter(lambda x, pos: f"${x:,.0f}")
    fig.tight_layout()
    return fig, ax


def choose_and_build_chart(columns: list, rows: list, output_path: str = "chart.png"):
    """
    CLI-oriented version: saves the chart to a PNG file and returns the
    path, or None if this data shape doesn't suit a chart. Used by the
    command-line tools (run this file directly, or from other scripts
    that need a file on disk).
    """
    chart_data = _select_chart_data(columns, rows)
    if chart_data is None:
        return None

    fig, ax = _draw_chart(chart_data)
    fig.savefig(output_path, dpi=100)
    plt.close(fig)
    return output_path


def build_chart_figure(columns: list, rows: list):
    """
    Streamlit-oriented version: returns a matplotlib Figure object directly
    for inline display via st.pyplot(fig), with no file written to disk.
    Returns None if this data shape doesn't suit a chart.
    """
    chart_data = _select_chart_data(columns, rows)
    if chart_data is None:
        return None
    fig, ax = _draw_chart(chart_data)
    return fig


def display_result(question: str, result: dict, chart_path: str = "chart.png"):
    """Convenience wrapper: prints summary + table, generates chart if
    appropriate, returns (summary, dataframe_or_None, chart_path_or_None)."""
    summary = build_summary(question, result)
    print(summary)

    if result["status"] != "success":
        return summary, None, None

    df = build_table(result["columns"], result["rows"])

    display_df = df.copy()
    for col in display_df.columns:
        if _is_money_column(col):
            display_df[col] = display_df[col].apply(_format_money)
    print(display_df.to_string(index=False, max_rows=20))

    chart = choose_and_build_chart(result["columns"], result["rows"], chart_path)
    if chart:
        print(f"\n[Chart saved to {chart}]")
    else:
        print("\n[No chart generated -- data shape doesn't suit one (single value, or no clear label+metric pair)]")

    return summary, df, chart


if __name__ == "__main__":
    import sys
    from pipeline import ask_question

    q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "What are the top 5 product categories by revenue?"
    result = ask_question(q)
    display_result(q, result)
