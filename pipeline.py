"""
pipeline.py

Ties together Day 2 (LLM) + Day 3-4 (validation + execution) into one
function: ask a question in plain English, get back either results or a
clear explanation of why it was refused/failed.
"""
import re

from llm_query_groq import ask_llm_for_sql, ask_llm_to_fix_sql
from validator import validate_and_prepare, ValidationError
from schema_loader import load_schema
from executor import execute_readonly, ExecutionError, QueryTimeout

DB_PATH = "olist_real.db"
MAX_RETRIES = 1


def _extract_assumption(sql: str):
    """Pulls out a leading assumption comment if the LLM included one,
    so it can be shown to the user separately from the raw SQL later
    (Day 9's output layer). Handles both -- and /* */ comment styles.
    Also strips a redundant leading 'Assumption:' label from the comment
    text itself, since the caller adds its own 'Assumption:' label when
    displaying it -- without this, output reads 'Assumption: Assumption: ...'"""
    stripped = sql.strip()
    dash_match = re.match(r"^--\s*(.+)", stripped)
    block_match = re.match(r"^/\*\s*(.+?)\s*\*/", stripped, re.DOTALL)

    text = None
    if dash_match:
        text = dash_match.group(1).strip()
    elif block_match:
        text = block_match.group(1).strip()

    if text:
        text = re.sub(r"^assumption:\s*", "", text, flags=re.IGNORECASE)
    return text


def ask_question(question: str) -> dict:
    """
    Runs the full pipeline for one natural-language question, including
    Day 5's self-correction retry: if the SQL fails validation (unknown
    table/column) or fails at execution (real DB error), the error is fed
    back to the LLM once for a corrected attempt. Timeouts are NOT
    retried -- an expensive query will just time out again, so retrying
    wastes time and API cost rather than fixing anything.

    Returns a dict with a 'status' key that is one of:
      'success'  -> {'status', 'sql', 'assumption', 'columns', 'rows', 'retried'}
      'refused'  -> {'status', 'message'}   (destructive request blocked)
      'no_query' -> {'status', 'message'}   (out of scope / can't be answered)
      'error'    -> {'status', 'message', 'retried'}  (failed even after retry)
    """
    schema = load_schema(DB_PATH)
    raw_response = ask_llm_for_sql(question)
    retried = False

    for attempt in range(MAX_RETRIES + 1):
        if raw_response.startswith("REFUSED:"):
            return {"status": "refused", "message": raw_response[len("REFUSED:"):].strip()}

        if raw_response.startswith("NO_QUERY:"):
            return {"status": "no_query", "message": raw_response[len("NO_QUERY:"):].strip()}

        try:
            safe_sql = validate_and_prepare(raw_response, schema)
        except ValidationError as e:
            if attempt < MAX_RETRIES:
                raw_response = ask_llm_to_fix_sql(question, raw_response, str(e))
                retried = True
                continue
            return {
                "status": "error",
                "message": f"The generated query was rejected: {e}",
                "retried": retried,
            }

        try:
            columns, rows = execute_readonly(DB_PATH, safe_sql)
        except QueryTimeout as e:
            # Deliberately NOT retried -- see docstring.
            return {"status": "error", "message": str(e), "retried": retried}
        except ExecutionError as e:
            if attempt < MAX_RETRIES:
                raw_response = ask_llm_to_fix_sql(question, safe_sql, str(e))
                retried = True
                continue
            return {"status": "error", "message": str(e), "retried": retried}

        return {
            "status": "success",
            "sql": safe_sql,
            "assumption": _extract_assumption(raw_response),
            "columns": columns,
            "rows": rows,
            "retried": retried,
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
        if result.get("retried"):
            print("(Note: first attempt failed, this is the corrected result after 1 retry)\n")
        if result["assumption"]:
            print(f"Assumption: {result['assumption']}\n")
        print(f"SQL run: {result['sql']}\n")
        print(f"Columns: {result['columns']}")
        for row in result["rows"][:20]:
            print(" ", row)
        if len(result["rows"]) > 20:
            print(f"  ... and {len(result['rows']) - 20} more rows")
    else:
        retried_note = " (after 1 retry)" if result.get("retried") else ""
        print(f"[{result['status'].upper()}{retried_note}] {result['message']}")
