"""
run_benchmark.py

Runs all 25 benchmark questions through the REAL pipeline (LLM -> validate
-> execute -> possibly retry), and grades each one against the pre-verified
expected answer.

Run this after any change to prompt_builder.py, validator.py, or the model
itself, to track whether accuracy improved or regressed -- don't rely on
"it feels like it's working better," track the actual number.
"""
import time
from benchmark import BENCHMARK
from pipeline import ask_question


def run():
    results = []
    by_difficulty = {"easy": [0, 0], "medium": [0, 0], "hard": [0, 0]}  # [passed, total]

    for item in BENCHMARK:
        qid = item["id"]
        difficulty = item["difficulty"]
        question = item["question"]

        by_difficulty[difficulty][1] += 1

        start = time.time()
        result = ask_question(question)
        elapsed = time.time() - start

        if result["status"] != "success":
            passed = False
            detail = f"[{result['status'].upper()}] {result['message']}"
        else:
            try:
                passed = item["check"](result["columns"], result["rows"])
            except Exception as e:
                passed = False
                detail = f"Checker crashed: {e}"
            else:
                detail = f"rows={result['rows'][:3]}"

        if passed:
            by_difficulty[difficulty][0] += 1

        results.append({
            "id": qid, "difficulty": difficulty, "question": question,
            "passed": passed, "detail": detail, "elapsed": round(elapsed, 2),
            "retried": result.get("retried", False),
        })

        status_str = "PASS" if passed else "FAIL"
        retry_str = " (retried)" if result.get("retried") else ""
        print(f"[{status_str}]{retry_str} #{qid} ({difficulty}, {elapsed:.1f}s): {question}")
        if not passed:
            print(f"       {detail}")

    total_passed = sum(1 for r in results if r["passed"])
    print(f"\n{'='*60}")
    print(f"OVERALL: {total_passed}/{len(BENCHMARK)} ({100*total_passed/len(BENCHMARK):.0f}%)")
    for diff in ["easy", "medium", "hard"]:
        p, t = by_difficulty[diff]
        print(f"  {diff}: {p}/{t} ({100*p/t:.0f}%)")

    avg_time = sum(r["elapsed"] for r in results) / len(results)
    retried_count = sum(1 for r in results if r["retried"])
    print(f"\nAverage response time: {avg_time:.2f}s per question")
    print(f"Questions that needed a retry: {retried_count}/{len(BENCHMARK)}")

    failed = [r for r in results if not r["passed"]]
    if failed:
        print(f"\n{'='*60}")
        print("FAILED QUESTIONS (review these):")
        for r in failed:
            print(f"  #{r['id']} ({r['difficulty']}): {r['question']}")
            print(f"     {r['detail']}")

    return results


if __name__ == "__main__":
    run()
