"""
pipeline.py

Ties together Day 2 (LLM) + Day 3-4 (validation + execution) into one
function: ask a question in plain English, get back either results or a
clear explanation of why it was refused/failed.
"""
import re

from llm_query_gemini import ask_llm_for_sql
from validator import validate_and_prepare, ValidationError
from schema_loader import load_schema
from executor import execute_readonly, ExecutionError, QueryTimeout

DB_PATH = "olist_real.db"


def _extract_assumption(sql: str):
    """Pulls out a leading assumption comment if the LLM included one,
    so it can be shown to the user separately from the raw SQL later
    (Day 9's output layer). Handles both -- and /* */ comment styles."""
    stripped = sql.strip()
    dash_match = re.match(r"^--\s*(.+)", stripped)
    if dash_match:
        return dash_match.group(1).strip()
    block_match = re.match(r"^/\*\s*(.+?)\s*\*/", stripped, re.DOTALL)
    if block_match:
        return block_match.group(1).strip()
    return None


def ask_question(question: str) -> dict:
    """
    Runs the full pipeline for one natural-language question.

    Returns a dict with a 'status' key that is one of:
      'success'  -> {'status', 'sql', 'assumption', 'columns', 'rows'}
      'refused'  -> {'status', 'message'}   (destructive request blocked)
      'no_query' -> {'status', 'message'}   (out of scope / can't be answered)
      'error'    -> {'status', 'message'}   (validation or execution failure)
    """
    raw_response = ask_llm_for_sql(question)

    if raw_response.startswith("REFUSED:"):
        return {"status": "refused", "message": raw_response[len("REFUSED:"):].strip()}

    if raw_response.startswith("NO_QUERY:"):
        return {"status": "no_query", "message": raw_response[len("NO_QUERY:"):].strip()}

    schema = load_schema(DB_PATH)

    try:
        safe_sql = validate_and_prepare(raw_response, schema)
    except ValidationError as e:
        return {"status": "error", "message": f"The generated query was rejected: {e}"}

    try:
        columns, rows = execute_readonly(DB_PATH, safe_sql)
    except QueryTimeout as e:
        return {"status": "error", "message": str(e)}
    except ExecutionError as e:
        return {"status": "error", "message": str(e)}

    return {
        "status": "success",
        "sql": safe_sql,
        "assumption": _extract_assumption(raw_response),
        "columns": columns,
        "rows": rows,
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        q = " ".join(sys.argv[1:])
    else:
        q = "How many unique customers do we have?"

    print(f"Question: {q}\n")
    result = ask_question(q)

    if result["status"] == "success":
        if result["assumption"]:
            print(f"Assumption: {result['assumption']}\n")
        print(f"SQL run: {result['sql']}\n")
        print(f"Columns: {result['columns']}")
        for row in result["rows"][:20]:
            print(" ", row)
        if len(result["rows"]) > 20:
            print(f"  ... and {len(result['rows']) - 20} more rows")
    else:
        print(f"[{result['status'].upper()}] {result['message']}")
