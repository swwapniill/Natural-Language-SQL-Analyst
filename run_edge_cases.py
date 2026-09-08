"""
run_edge_cases.py

Runs all 19 edge cases through the real pipeline and grades each against
its pre-defined expected behavior. Unlike run_benchmark.py, this grades
BEHAVIOR (refused / no_query / success-with-assumption), not a numeric answer.
"""
from edge_cases import EDGE_CASES
from pipeline import ask_question


def run():
    results = []
    by_category = {}

    for case in EDGE_CASES:
        cid = case["id"]
        category = case["category"]
        question = case["question"]

        by_category.setdefault(category, [0, 0])
        by_category[category][1] += 1

        result = ask_question(question)

        try:
            passed = case["check"](result)
        except Exception as e:
            passed = False
            result = {"status": "error", "message": f"Checker crashed: {e}"}

        if passed:
            by_category[category][0] += 1

        results.append({"id": cid, "category": category, "question": question,
                         "passed": passed, "result": result})

        status_str = "PASS" if passed else "FAIL"
        print(f"[{status_str}] #{cid} ({category}): {question}")
        print(f"       actual status: {result['status']}"
              + (f", assumption: {result.get('assumption')}" if result.get("assumption") else "")
              + (f", message: {result.get('message')}" if result.get("message") else ""))
        if not passed:
            print(f"       EXPECTED: {case['expected_behavior']}")

    total_passed = sum(1 for r in results if r["passed"])
    print(f"\n{'='*60}")
    print(f"OVERALL: {total_passed}/{len(EDGE_CASES)} ({100*total_passed/len(EDGE_CASES):.0f}%)")
    for cat in by_category:
        p, t = by_category[cat]
        print(f"  {cat}: {p}/{t}")

    failed = [r for r in results if not r["passed"]]
    if failed:
        print(f"\n{'='*60}")
        print("FAILED CASES (review these -- these are safety/behavior gaps):")
        for r in failed:
            print(f"  #{r['id']} ({r['category']}): {r['question']}")
            print(f"     actual: {r['result']}")

    return results


if __name__ == "__main__":
    run()
