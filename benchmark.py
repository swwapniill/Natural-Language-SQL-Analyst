"""
benchmark.py

25 question/expected-answer pairs, written and verified against the real
database BEFORE running any of them through the LLM pipeline. This is
the ground truth -- if the pipeline's answer doesn't match, the pipeline
is wrong, not the benchmark.

Each question has a 'check' function: given the pipeline's raw column/row
output, it returns True if the answer is correct. This is deliberately
NOT an exact-SQL-text match -- two different correct queries can produce
the same right answer, so we check the RESULT, not the query structure.

Difficulty tiers:
  easy   (8):  single table, simple filter/aggregate
  medium (10): one join, one aggregation/group-by
  hard   (7):  multi-join, date math, CTEs, percentages
"""


def _first_value(columns, rows):
    """Helper: most single-aggregate questions return one row, one column."""
    if not rows:
        return None
    return rows[0][0]


def _approx(actual, expected, tolerance=0.5):
    """Float comparison with tolerance -- the LLM's SQL might round
    differently (e.g. ROUND vs no ROUND) and still be correct."""
    try:
        return abs(float(actual) - float(expected)) <= tolerance
    except (TypeError, ValueError):
        return False


BENCHMARK = [
    # ---------------- EASY (8) ----------------
    {
        "id": 1, "difficulty": "easy",
        "question": "How many orders are there in total?",
        "expected": 99441,
        "check": lambda cols, rows: _first_value(cols, rows) == 99441,
    },
    {
        "id": 2, "difficulty": "easy",
        "question": "How many unique customers do we have?",
        "expected": 96096,
        "notes": "Tests customer_id vs customer_unique_id -- using customer_id would wrongly give 99441.",
        "check": lambda cols, rows: _first_value(cols, rows) == 96096,
    },
    {
        "id": 3, "difficulty": "easy",
        "question": "How many sellers are there?",
        "expected": 3095,
        "check": lambda cols, rows: _first_value(cols, rows) == 3095,
    },
    {
        "id": 4, "difficulty": "easy",
        "question": "How many products have no category assigned?",
        "expected": 610,
        "notes": "Tests handling of NULL product_category_name.",
        "check": lambda cols, rows: _first_value(cols, rows) == 610,
    },
    {
        "id": 5, "difficulty": "easy",
        "question": "How many orders were canceled?",
        "expected": 625,
        "check": lambda cols, rows: _first_value(cols, rows) == 625,
    },
    {
        "id": 6, "difficulty": "easy",
        "question": "What are all the possible order statuses?",
        "expected": {"approved", "canceled", "created", "delivered", "invoiced",
                     "processing", "shipped", "unavailable"},
        "notes": "Tests whether the LLM knows there are 8 statuses, not just 2.",
        "check": lambda cols, rows: {r[0] for r in rows} == {
            "approved", "canceled", "created", "delivered", "invoiced",
            "processing", "shipped", "unavailable"
        },
    },
    {
        "id": 7, "difficulty": "easy",
        "question": "How many reviews have a score of 5?",
        "expected": 57328,
        "check": lambda cols, rows: _first_value(cols, rows) == 57328,
    },
    {
        "id": 8, "difficulty": "easy",
        "question": "How many distinct product categories are there?",
        "expected": 73,
        "check": lambda cols, rows: _first_value(cols, rows) == 73,
    },

    # ---------------- MEDIUM (10) ----------------
    {
        "id": 9, "difficulty": "medium",
        "question": "What is our total revenue, not including shipping?",
        "expected": 13591643.70,
        "check": lambda cols, rows: _approx(_first_value(cols, rows), 13591643.70, tolerance=1.0),
    },
    {
        "id": 10, "difficulty": "medium",
        "question": "What is our total revenue including shipping costs?",
        "expected": 15843553.24,
        "check": lambda cols, rows: _approx(_first_value(cols, rows), 15843553.24, tolerance=1.0),
    },
    {
        "id": 11, "difficulty": "medium",
        "question": "How many orders contain more than one item?",
        "expected": 9803,
        "check": lambda cols, rows: _first_value(cols, rows) == 9803,
    },
    {
        "id": 12, "difficulty": "medium",
        "question": "How much was paid in total for order 0016dfedd97fc2950e388d2971d718c7?",
        "expected": 70.55,
        "notes": "Tests SUM across split payments (this order has 2 payment rows).",
        "check": lambda cols, rows: _approx(_first_value(cols, rows), 70.55, tolerance=0.01),
    },
    {
        "id": 13, "difficulty": "medium",
        "question": "What are the top 5 product categories by revenue?",
        "expected": "health_beauty",
        "notes": "Tests category translation join. Top category by revenue is health_beauty.",
        "check": lambda cols, rows: len(rows) >= 1 and any(
            "health_beauty" in str(cell).lower() for cell in rows[0]
        ),
    },
    {
        "id": 14, "difficulty": "medium",
        "question": "How many orders have no review at all?",
        "expected": 768,
        "notes": "Tests LEFT JOIN vs INNER JOIN -- INNER JOIN would silently give the wrong (smaller) universe.",
        "check": lambda cols, rows: _first_value(cols, rows) == 768,
    },
    {
        "id": 15, "difficulty": "medium",
        "question": "What is the average review score?",
        "expected": 4.086,
        "check": lambda cols, rows: _approx(_first_value(cols, rows), 4.086, tolerance=0.05),
    },
    {
        "id": 16, "difficulty": "medium",
        "question": "How many customers have placed more than one order?",
        "expected": 2997,
        "notes": "Must use customer_unique_id, not customer_id, or this will be wrong.",
        "check": lambda cols, rows: _first_value(cols, rows) == 2997,
    },
    {
        "id": 17, "difficulty": "medium",
        "question": "What is the most common payment type?",
        "expected": "credit_card",
        "check": lambda cols, rows: len(rows) >= 1 and "credit_card" in str(rows[0]).lower(),
    },
    {
        "id": 18, "difficulty": "medium",
        "question": "How many orders were split across more than one payment transaction (multiple rows in order_payments for the same order)?",
        "expected": 2961,
        "notes": (
            "Originally worded 'more than one payment method', which turned out to be "
            "genuinely ambiguous: 2246 orders have >1 DISTINCT payment_type, but 2961 "
            "orders have >1 payment ROW (some orders split one payment type across "
            "multiple transactions, e.g. two separate credit_card charges). The LLM's "
            "answer of 2246 to the original wording was a legitimate reading, not a bug -- "
            "the question itself was the problem. Reworded to be unambiguous."
        ),
        "check": lambda cols, rows: _first_value(cols, rows) == 2961,
    },

    # ---------------- HARD (7) ----------------
    {
        "id": 19, "difficulty": "hard",
        "question": "On average, how many days does it take from purchase to delivery for delivered orders?",
        "expected": 12.56,
        "check": lambda cols, rows: _approx(_first_value(cols, rows), 12.56, tolerance=0.5),
    },
    {
        "id": 20, "difficulty": "hard",
        "question": "Which seller has generated the highest total revenue?",
        "expected": "4869f7a5dfa277a7dca6462dcf3b52b2",
        "check": lambda cols, rows: len(rows) >= 1 and "4869f7a5dfa277a7dca6462dcf3b52b2" in str(rows[0]),
    },
    {
        "id": 21, "difficulty": "hard",
        "question": "What percentage of delivered orders arrived after the estimated delivery date?",
        "expected": 8.11,
        "check": lambda cols, rows: _approx(_first_value(cols, rows), 8.11, tolerance=1.0),
    },
    {
        "id": 22, "difficulty": "hard",
        "question": "For each order status, what is the average number of items per order?",
        "expected": "delivered=1.14",
        "notes": "Checks that 'delivered' status average is close to 1.14 items/order.",
        "check": lambda cols, rows: any(
            "delivered" in str(r[0]).lower() and _approx(r[-1], 1.14, tolerance=0.1)
            for r in rows
        ),
    },
    {
        "id": 23, "difficulty": "hard",
        "question": "Which state has the most unique customers?",
        "expected": "SP",
        "notes": "Must count customer_unique_id per state, not customer_id.",
        "check": lambda cols, rows: len(rows) >= 1 and "SP" in str(rows[0]),
    },
    {
        "id": 24, "difficulty": "hard",
        "question": "What was our total revenue in January 2017?",
        "expected": 120312.87,
        "check": lambda cols, rows: any(_approx(cell, 120312.87, tolerance=5.0) for r in rows for cell in r),
    },
    {
        "id": 25, "difficulty": "hard",
        "question": "How many customers have placed more than 3 orders?",
        "expected": 49,
        "notes": "Naturally invites a CTE. Low number is correct given ~3% repeat-purchase rate.",
        "check": lambda cols, rows: _first_value(cols, rows) == 49,
    },
]


if __name__ == "__main__":
    print(f"Benchmark loaded: {len(BENCHMARK)} questions")
    by_difficulty = {}
    for q in BENCHMARK:
        by_difficulty.setdefault(q["difficulty"], 0)
        by_difficulty[q["difficulty"]] += 1
    print(by_difficulty)
