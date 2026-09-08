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


def choose_and_build_chart(columns: list, rows: list, output_path: str = "chart.png"):
    """
    Heuristic chart selection based on the SHAPE of the result, not the
    question text:
      - 0 or 1 row  -> no chart (a single number doesn't need a chart)
      - 1 label column (text or date) + 1 numeric column -> bar or line
      - date-like label column -> line chart (trend over time)
      - text/categorical label column -> bar chart (comparison across items)
      - anything else (many columns, no clear single metric) -> no chart

    Returns the output_path if a chart was created, or None if no chart
    was appropriate for this data shape (this is a deliberate decision,
    not a failure -- not every result should have a chart).
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

    labels = [str(r[label_col_idx]) for r in rows[:20]]
    values = [r[numeric_col_idx] for r in rows[:20]]

    is_date = _looks_like_date_column(columns[label_col_idx], [r[label_col_idx] for r in rows[:3]])

    plt.figure(figsize=(8, 4.5))
    if is_date:
        plt.plot(labels, values, marker="o")
        plt.xticks(rotation=45, ha="right")
        plt.title(f"{columns[numeric_col_idx]} over {columns[label_col_idx]}")
    else:
        plt.bar(labels, values)
        plt.xticks(rotation=45, ha="right")
        plt.title(f"{columns[numeric_col_idx]} by {columns[label_col_idx]}")
    plt.ylabel(columns[numeric_col_idx])
    plt.tight_layout()
    plt.savefig(output_path, dpi=100)
    plt.close()
    return output_path


def display_result(question: str, result: dict, chart_path: str = "chart.png"):
    """Convenience wrapper: prints summary + table, generates chart if
    appropriate, returns (summary, dataframe_or_None, chart_path_or_None)."""
    summary = build_summary(question, result)
    print(summary)

    if result["status"] != "success":
        return summary, None, None

    df = build_table(result["columns"], result["rows"])
    print(df.to_string(index=False, max_rows=20))

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
