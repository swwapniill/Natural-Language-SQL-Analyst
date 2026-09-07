"""
llm_query.py (Gemini version)

Sends a natural-language question + the schema/rules prompt to Gemini,
and returns the raw text response (SQL, or a NO_QUERY/REFUSED message).

Uses Google's free API tier via Google AI Studio (not Vertex AI, which
needs billing). Get a free key at: https://aistudio.google.com/apikey

This file does NOT execute the SQL or validate it -- that's Day 3-4.
Today's job is only: question in, SQL text out.
"""
import os
from google import genai
from prompt_builder import build_system_prompt

# gemini-3.6-flash has an extremely tight free-tier quota (20 requests/DAY,
# confirmed via a live 429 error) -- unusable for a benchmark of 25 questions.
# gemini-2.0-flash is an older, established model with a documented free
# tier in the hundreds-to-1500/day range. If this also turns out to be
# wrong, the live error message will tell us the real number, same as
# it did for 3.6-flash -- don't trust blog posts over the actual API.
MODEL = "gemini-2.0-flash"


def get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Run: export GEMINI_API_KEY=your_key_here"
        )
    return genai.Client(api_key=api_key)


def ask_llm_for_sql(question: str) -> str:
    """
    Sends the question to Gemini with the schema/rules system prompt.
    Returns the raw text response -- could be SQL, or a NO_QUERY:/REFUSED: message.
    """
    client = get_client()
    system_prompt = build_system_prompt()

    response = client.models.generate_content(
        model=MODEL,
        contents=question,
        config={
            "system_instruction": system_prompt,
            "max_output_tokens": 3000,
        },
    )

    return response.text.strip()


def ask_llm_to_fix_sql(question: str, failed_sql: str, error_message: str) -> str:
    """
    Day 5: self-correction retry. Used when the first SQL attempt was
    syntactically a valid SELECT but failed validation (unknown column/table)
    or failed at execution (a real DB error, e.g. bad join logic).

    Sends the original question, the SQL that failed, and the exact error
    back to the LLM, and asks for one corrected attempt. Same schema/rules
    system prompt as the first attempt -- this is a follow-up, not a
    from-scratch retry with different context.
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

    response = client.models.generate_content(
        model=MODEL,
        contents=retry_message,
        config={
            "system_instruction": system_prompt,
            "max_output_tokens": 3000,
        },
    )

    return response.text.strip()


if __name__ == "__main__":
    # quick manual test -- run this file directly to try a question from the command line
    import sys

    if len(sys.argv) > 1:
        q = " ".join(sys.argv[1:])
    else:
        q = "How many unique customers do we have?"

    print(f"Question: {q}\n")
    result = ask_llm_for_sql(q)
    print("LLM response:")
    print(result)
