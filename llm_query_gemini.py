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

# If this model name has been renamed/retired by the time you run this,
# go to https://aistudio.google.com, check "Get API key" -> model list,
# and swap in whatever their current free-tier flash model is called.
MODEL = "gemini-3.6-flash"


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
