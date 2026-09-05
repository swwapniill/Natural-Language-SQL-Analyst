"""
llm_query.py

Sends a natural-language question + the schema/rules prompt to Claude,
and returns the raw text response (SQL, or a NO_QUERY/REFUSED message).

This file does NOT execute the SQL or validate it -- that's Day 3-4.
Today's job is only: question in, SQL text out.
"""
import os
from anthropic import Anthropic
from prompt_builder import build_system_prompt

MODEL = "claude-sonnet-4-5"  # good balance of quality/cost for SQL generation


def get_client() -> Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Run: export ANTHROPIC_API_KEY=your_key_here"
        )
    return Anthropic(api_key=api_key)


def ask_llm_for_sql(question: str) -> str:
    """
    Sends the question to the LLM with the schema/rules system prompt.
    Returns the raw text response -- could be SQL, or a NO_QUERY:/REFUSED: message.
    """
    client = get_client()
    system_prompt = build_system_prompt()

    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
        system=system_prompt,
        messages=[{"role": "user", "content": question}],
    )

    # response.content is a list of blocks; for a plain text reply there's one text block
    text = "".join(block.text for block in response.content if block.type == "text")
    return text.strip()


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
