"""
verify_benchmark_checkers.py

Sanity check for the benchmark itself: runs the VERIFIED ground-truth SQL
for each of the 25 questions directly against the database, then feeds
that known-correct result into the corresponding check() function.

If any of these fail, the checker function has a bug -- this must be
fixed before the benchmark is trusted to grade the actual LLM pipeline.
"""
import sqlite3
from benchmark import BENCHMARK

conn = sqlite3.connect("olist_real.db")
cur = conn.cursor()

GROUND_TRUTH_SQL = {
    1: "SELECT COUNT(*) FROM orders",
    2: "SELECT COUNT(DISTINCT customer_unique_id) FROM customers",
    3: "SELECT COUNT(*) FROM sellers",
    4: "SELECT COUNT(*) FROM products WHERE product_category_name IS NULL",
    5: "SELECT COUNT(*) FROM orders WHERE order_status='canceled'",
    6: "SELECT DISTINCT order_status FROM orders",
    7: "SELECT COUNT(*) FROM order_reviews WHERE review_score=5",
    8: "SELECT COUNT(DISTINCT product_category_name) FROM products",
    9: "SELECT SUM(price) FROM order_items",
    10: "SELECT SUM(price+freight_value) FROM order_items",
    11: "SELECT COUNT(*) FROM (SELECT order_id FROM order_items GROUP BY order_id HAVING COUNT(*)>1)",
    12: "SELECT SUM(payment_value) FROM order_payments WHERE order_id='0016dfedd97fc2950e388d2971d718c7'",
    13: """SELECT t.product_category_name_english, SUM(oi.price) as rev
           FROM order_items oi JOIN products p ON oi.product_id=p.product_id
           JOIN product_category_name_translation t ON p.product_category_name=t.product_category_name
           GROUP BY t.product_category_name_english ORDER BY rev DESC LIMIT 5""",
    14: "SELECT COUNT(*) FROM orders o LEFT JOIN order_reviews r ON o.order_id=r.order_id WHERE r.review_id IS NULL",
    15: "SELECT AVG(review_score) FROM order_reviews",
    16: "SELECT COUNT(*) FROM (SELECT customer_unique_id FROM customers GROUP BY customer_unique_id HAVING COUNT(*)>1)",
    17: "SELECT payment_type, COUNT(*) c FROM order_payments GROUP BY payment_type ORDER BY c DESC LIMIT 1",
    18: "SELECT COUNT(*) FROM (SELECT order_id FROM order_payments GROUP BY order_id HAVING COUNT(*)>1)",
    19: """SELECT AVG(julianday(order_delivered_customer_date) - julianday(order_purchase_timestamp))
           FROM orders WHERE order_status='delivered' AND order_delivered_customer_date IS NOT NULL""",
    20: """SELECT s.seller_id, SUM(oi.price) as rev FROM order_items oi
           JOIN sellers s ON oi.seller_id=s.seller_id GROUP BY s.seller_id ORDER BY rev DESC LIMIT 1""",
    21: """SELECT 100.0*SUM(CASE WHEN order_delivered_customer_date > order_estimated_delivery_date THEN 1 ELSE 0 END)/COUNT(*)
           FROM orders WHERE order_status='delivered' AND order_delivered_customer_date IS NOT NULL""",
    22: """SELECT o.order_status, AVG(item_count) FROM orders o
           JOIN (SELECT order_id, COUNT(*) as item_count FROM order_items GROUP BY order_id) oi
           ON o.order_id=oi.order_id GROUP BY o.order_status""",
    23: "SELECT customer_state, COUNT(DISTINCT customer_unique_id) c FROM customers GROUP BY customer_state ORDER BY c DESC LIMIT 1",
    24: """SELECT SUM(oi.price) FROM orders o JOIN order_items oi ON o.order_id=oi.order_id
           WHERE strftime('%Y-%m', o.order_purchase_timestamp) = '2017-01'""",
    25: """WITH oc AS (SELECT c.customer_unique_id, COUNT(*) n FROM customers c
           JOIN orders o ON c.customer_id=o.customer_id GROUP BY c.customer_unique_id HAVING COUNT(*)>3)
           SELECT COUNT(*) FROM oc""",
}

passed, failed = 0, 0
for item in BENCHMARK:
    qid = item["id"]
    sql = GROUND_TRUTH_SQL[qid]
    cur.execute(sql)
    rows = cur.fetchall()
    columns = [d[0] for d in cur.description]

    ok = item["check"](columns, rows)
    status = "PASS" if ok else "FAIL"
    if ok:
        passed += 1
    else:
        failed += 1
    print(f"[{status}] #{qid} ({item['difficulty']}): {item['question']}")
    if not ok:
        print(f"       ground truth rows: {rows}")
        print(f"       expected: {item['expected']}")

print(f"\n{passed}/{len(BENCHMARK)} checker functions correctly validate their own ground truth")
if failed:
    print(f"*** {failed} checker(s) are BUGGY and must be fixed before using this benchmark ***")
