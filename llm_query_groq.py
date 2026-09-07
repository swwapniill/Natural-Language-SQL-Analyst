"""
llm_query_groq.py

Uses Groq's free tier instead of Gemini's. Groq requires no credit card
and gives a much more usable daily quota (consistently reported across
many sources as 1,000-14,400 requests/day depending on model, vs the
20/day wall we hit on gemini-3.6-flash).

Groq only serves open-source models (Llama, etc.), not Gemini/GPT/Claude --
that's fine here, since this project's LLM just needs to be decent at
schema-grounded SQL generation, not a frontier general-purpose model.

Get a free key at: https://console.groq.com/keys (email or Google sign-in,
no card needed).
"""
import os
from groq import Groq
from prompt_builder import build_system_prompt

# Confirmed against the live /v1/models endpoint for this account --
# llama-3.3-70b-versatile has been fully retired, not just renamed.
# gpt-oss-120b is a current, active model with tool/reasoning support
# and a large context window, well suited to schema-grounded SQL generation.
MODEL = "openai/gpt-oss-120b"


def get_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Run: export GROQ_API_KEY=your_key_here"
        )
    return Groq(api_key=api_key)


def ask_llm_for_sql(question: str) -> str:
    """
    Sends the question to Groq with the schema/rules system prompt.
    Returns the raw text response -- could be SQL, or a NO_QUERY:/REFUSED: message.
    """
    client = get_client()
    system_prompt = build_system_prompt()

    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        max_tokens=3000,
        temperature=0,  # deterministic-leaning output is preferable for SQL generation
    )

    return completion.choices[0].message.content.strip()


def ask_llm_to_fix_sql(question: str, failed_sql: str, error_message: str) -> str:
    """
    Day 5 self-correction retry, same contract as the Gemini version:
    sends the original question, the SQL that failed, and the exact error
    back to the LLM for one corrected attempt.
    """
    client = get_client()
    system_prompt = build_system_prompt()

    retry_message = (
        f"Original question: {question}\n\n"
        f"You previously generated this SQL:\n{failed_sql}\n\n"
        f"Running it produced this error:\n{error_message}\n\n"
        f"Fix the query and provide a corrected SELECT statement. "
        f"Follow the same rules and output format as before -- SQL only, "
        f"optionally with a leading assumption comment. If the error means "
        f"the question genuinely cannot be answered from this schema, "
        f"respond with NO_QUERY: <reason> instead."
    )

    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": retry_message},
        ],
        max_tokens=3000,
        temperature=0,
    )

    return completion.choices[0].message.content.strip()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        q = " ".join(sys.argv[1:])
    else:
        q = "How many unique customers do we have?"

    print(f"Question: {q}\n")
    result = ask_llm_for_sql(q)
    print("LLM response:")
    print(result)
