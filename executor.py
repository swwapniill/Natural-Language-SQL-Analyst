"""
executor.py

Layer 2 of defense: executes validated SQL against a connection that is
opened in TRUE read-only mode at the SQLite level (not just "we promise
not to write") -- if validator.py ever has a bug that lets something
destructive through, this connection physically cannot write to disk.

Also enforces a real query timeout: SQLite doesn't support this natively,
so we use set_progress_handler to abort a query that's taken too long,
rather than just hoping queries are always fast.
"""
import sqlite3
import time

QUERY_TIMEOUT_SECONDS = 10


class ExecutionError(Exception):
    """Raised when a validated query still fails at execution time
    (e.g. a runtime SQL error, or a timeout)."""
    pass


class QueryTimeout(ExecutionError):
    """Raised specifically when a query exceeds QUERY_TIMEOUT_SECONDS."""
    pass


def execute_readonly(db_path: str, sql: str, timeout_seconds: int = QUERY_TIMEOUT_SECONDS):
    """
    Executes SQL against a read-only connection to db_path.
    Returns (column_names: list[str], rows: list[tuple]).
    Raises ExecutionError on any failure, QueryTimeout specifically if the
    query ran longer than timeout_seconds.

    IMPORTANT: this function does NOT validate the SQL -- call
    validator.validate_and_prepare() first. This is layer 2, not layer 1.
    """
    # mode=ro opens the file such that SQLite itself refuses any write
    # operation at the OS/driver level -- enforced independently of
    # whatever the validator already checked.
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)

    start_time = time.time()

    def _progress_handler():
        # Returning non-zero from this callback aborts the currently
        # running SQLite operation. n=1000 means SQLite checks in every
        # ~1000 virtual machine instructions, giving near-real-time
        # timeout enforcement without a separate thread.
        if time.time() - start_time > timeout_seconds:
            return 1
        return 0

    conn.set_progress_handler(_progress_handler, 1000)

    try:
        cur = conn.cursor()
        cur.execute(sql)
        columns = [desc[0] for desc in cur.description] if cur.description else []
        rows = cur.fetchall()
        return columns, rows
    except sqlite3.OperationalError as e:
        if "interrupted" in str(e).lower():
            raise QueryTimeout(
                f"Query exceeded the {timeout_seconds}-second time limit and was stopped."
            )
        raise ExecutionError(f"Database error while running the query: {e}")
    except sqlite3.Error as e:
        raise ExecutionError(f"Database error while running the query: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    print("Test 1: normal fast query")
    cols, rows = execute_readonly("olist_real.db", "SELECT COUNT(*) FROM orders")
    print(f"  columns={cols}, rows={rows}")

    print("\nTest 2: confirm read-only actually blocks writes at the DB level")
    try:
        execute_readonly("olist_real.db", "DELETE FROM orders")
        print("  FAIL: this should never print -- a write was not blocked!")
    except Exception as e:
        print(f"  PASSED (write correctly blocked): {type(e).__name__}: {e}")

    print("\nTest 3: deliberately slow query to test the timeout")
    # a full cross join of order_items with itself is ~112,650^2 rows --
    # this should take much longer than 10 seconds and get interrupted
    slow_sql = "SELECT COUNT(*) FROM order_items a, order_items b"
    try:
        cols, rows = execute_readonly("olist_real.db", slow_sql, timeout_seconds=3)
        print(f"  Query finished before timeout: {rows}")
    except QueryTimeout as e:
        print(f"  PASSED (timeout correctly enforced): {e}")
    except Exception as e:
        print(f"  Different error occurred: {type(e).__name__}: {e}")
