"""
validator.py

AST-level SQL validation using sqlglot. This is the layer that decides
whether LLM-generated SQL is allowed to run at all, BEFORE it ever
touches the database.

Checks performed:
1. Exactly one statement (blocks "SELECT ...; DROP TABLE ...")
2. That statement must be a SELECT (blocks INSERT/UPDATE/DELETE/DROP/ALTER/etc.)
3. Every referenced table must exist in the real schema
4. Every referenced column must exist in SOME table in the real schema
   (catches hallucinated column names)
5. A LIMIT clause is enforced: added if missing, capped at 1000 if larger

This is layer 1 of defense. Layer 2 is executing only against a read-only
DB connection (see executor.py) -- belt and suspenders, not either/or.
"""
import sqlglot
from sqlglot import exp

MAX_ROWS = 1000


class ValidationError(Exception):
    """Raised when generated SQL fails a safety check. The message is
    safe to show to the end user -- it explains what was rejected and why."""
    pass


def validate_and_prepare(sql: str, schema: dict) -> str:
    """
    Validates the SQL against the schema and safety rules.
    Returns a safe, LIMIT-enforced version of the SQL if valid.
    Raises ValidationError if any check fails.
    """
    sql = sql.strip()
    if not sql:
        raise ValidationError("The generated response was empty.")

    # --- Check 1: exactly one statement ---
    try:
        statements = sqlglot.parse(sql, read="sqlite")
    except Exception as e:
        raise ValidationError(f"Could not parse the generated SQL: {e}")

    statements = [s for s in statements if s is not None]
    if len(statements) == 0:
        raise ValidationError("No valid SQL statement found.")
    if len(statements) > 1:
        raise ValidationError(
            "Multiple SQL statements were generated. Only a single SELECT "
            "statement is allowed -- this is blocked as a safety measure "
            "against statement-stacking attacks."
        )

    stmt = statements[0]

    # --- Check 2: must be a SELECT (a plain SELECT, or a UNION of SELECTs) ---
    # A UNION combining two real, valid queries is legitimate and common in
    # analytical SQL -- only a bare Select was allowed originally, which
    # incorrectly rejected safe UNION queries. SQL grammar doesn't permit
    # DELETE/DROP/etc as a UNION branch, so allowing exp.Union here doesn't
    # open a new hole; the table/column checks below still apply to every
    # branch since find_all() walks the whole tree.
    if not isinstance(stmt, (exp.Select, exp.Union)):
        stmt_type = type(stmt).__name__
        raise ValidationError(
            f"Only SELECT queries are allowed. The generated statement was "
            f"a {stmt_type}, which has been blocked."
        )

    # --- CTE aliases (WITH x AS (...)) are virtual tables, not real ones ---
    # They must be excluded from the "unknown table" check below, otherwise
    # every query using a CTE gets incorrectly rejected.
    cte_aliases = {cte.alias.lower() for cte in stmt.find_all(exp.CTE) if cte.alias}

    # --- Check 3: every referenced table must exist (excluding CTE aliases) ---
    referenced_tables = {t.name.lower() for t in stmt.find_all(exp.Table)}
    referenced_tables -= cte_aliases
    known_tables = {t.lower() for t in schema.keys()}
    unknown_tables = referenced_tables - known_tables
    if unknown_tables:
        raise ValidationError(
            f"The query references table(s) that don't exist in this "
            f"database: {', '.join(sorted(unknown_tables))}."
        )

    # --- Check 4: every referenced column must exist in SOME known table ---
    # (best-effort: we don't resolve which table each column belongs to,
    # since that requires full alias resolution -- we just confirm the
    # column name exists SOMEWHERE in the schema, which catches the most
    # common failure mode: a fully hallucinated column name)
    all_known_columns = set()
    for cols in schema.values():
        all_known_columns.update(c.lower() for c in cols)

    referenced_columns = {
        c.name.lower() for c in stmt.find_all(exp.Column) if c.name != "*"
    }
    # ignore column names that are actually aliases defined within this query
    aliases = {a.alias.lower() for a in stmt.find_all(exp.Alias) if a.alias}
    unknown_columns = referenced_columns - all_known_columns - aliases
    if unknown_columns:
        raise ValidationError(
            f"The query references column(s) that don't exist in this "
            f"database: {', '.join(sorted(unknown_columns))}."
        )

    # --- Check 5: enforce row limit ---
    existing_limit = stmt.args.get("limit")
    if existing_limit is None:
        stmt = stmt.limit(MAX_ROWS)
    else:
        try:
            limit_value = int(existing_limit.expression.this)
            if limit_value > MAX_ROWS:
                stmt.set("limit", exp.Limit(expression=exp.Literal.number(MAX_ROWS)))
        except (AttributeError, ValueError):
            stmt.set("limit", exp.Limit(expression=exp.Literal.number(MAX_ROWS)))

    return stmt.sql(dialect="sqlite")


if __name__ == "__main__":
    from schema_loader import load_schema

    schema = load_schema("olist_real.db")

    test_cases = [
        ("SELECT COUNT(*) FROM orders", "should pass, limit added"),
        ("SELECT * FROM orders LIMIT 5000", "should pass, limit capped to 1000"),
        ("DELETE FROM orders", "should be REJECTED - not a SELECT"),
        ("DROP TABLE orders", "should be REJECTED - not a SELECT"),
        ("SELECT * FROM orders; DROP TABLE orders;", "should be REJECTED - multiple statements"),
        ("SELECT fake_column FROM orders", "should be REJECTED - unknown column"),
        ("SELECT * FROM fake_table", "should be REJECTED - unknown table"),
        ("UPDATE orders SET order_status='delivered'", "should be REJECTED - not a SELECT"),
    ]

    for sql, expectation in test_cases:
        print(f"\nSQL: {sql}")
        print(f"Expectation: {expectation}")
        try:
            safe_sql = validate_and_prepare(sql, schema)
            print(f"RESULT: PASSED -> {safe_sql}")
        except ValidationError as e:
            print(f"RESULT: REJECTED -> {e}")
