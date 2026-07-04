"""
03 - Multilingual Content Studio
Goal: a localization studio that translates a text into several languages
AND checks the quality of each translation before delivering it, with a
self-correction loop if the quality is judged insufficient.

Base pattern (book p.18-20): Manager pattern (agents-as-tools).
Advanced features added:
- Translation agents generated dynamically from a config (no copy-paste
  needed to add a language)
- A "reviewer" agent that scores each translation (0-100) and lists issues
  found (Pydantic structured output)
- Self-correction loop: if the score is too low, the manager asks for another
  translation taking the reviewer's feedback into account
- Final output formatted as a Markdown table

Extra task - Templated Content Localization:
- Real support/marketing content often contains merge fields like
  {customer_name} or {order_id}. check_placeholders verifies these survive
  translation unchanged, and a broken placeholder now forces a retry just
  like a low quality score does.
"""

import asyncio
import os
import re

from dotenv import load_dotenv
from pydantic import BaseModel

from agents import Agent, Runner, function_tool

load_dotenv()

PLACEHOLDER_PATTERN = r"\{[a-zA-Z0-9_]+\}"

SAMPLE_TEMPLATE = (
    "Hi {customer_name}, your order {order_id} has shipped and will arrive by "
    "{eta_date}. Thank you for choosing us!"
)

LANGUAGES = {
    "es": "Spanish",
    "fr": "French",
    "it": "Italian",
    "de": "German",
    "ar": "Arabic",
}


def _make_translation_agent(language_name: str) -> Agent:
    return Agent(
        name=f"{language_name} translator",
        instructions=(
            f"Translate the user's message to {language_name}. "
            "Reply with only the translation, nothing else."
        ),
    )


translation_agents = {code: _make_translation_agent(name) for code, name in LANGUAGES.items()}

translation_tools = [
    translation_agents[code].as_tool(
        tool_name=f"translate_to_{code}",
        tool_description=f"Translate the user's message to {name}",
    )
    for code, name in LANGUAGES.items()
]


class ReviewResult(BaseModel):
    score: int
    issues: list[str]


reviewer_agent = Agent(
    name="Translation reviewer",
    instructions=(
        "You review a translation for accuracy, natural phrasing, and cultural "
        "appropriateness. Score it from 0 (unusable) to 100 (perfect) and list "
        "concrete issues if any (empty list if none). The input will contain both "
        "the original text and the translation to review."
    ),
    output_type=ReviewResult,
)

review_tool = reviewer_agent.as_tool(
    tool_name="review_translation",
    tool_description=(
        "Review a translation's quality. Pass a single string containing both "
        "the original text and the translation, e.g. "
        "'Original: Hello\\nTranslation (Spanish): Hola'."
    ),
)


@function_tool
def check_placeholders(original: str, translation: str) -> str:
    """Verify that every template placeholder (e.g. {customer_name}) found in the
    original text is preserved unchanged in the translation. Use this whenever the
    text being translated looks like a template (contains {curly_braces})."""
    original_placeholders = set(re.findall(PLACEHOLDER_PATTERN, original))
    if not original_placeholders:
        return "No placeholders detected in the original text."

    translation_placeholders = set(re.findall(PLACEHOLDER_PATTERN, translation))
    missing = original_placeholders - translation_placeholders
    extra = translation_placeholders - original_placeholders

    if not missing and not extra:
        return "OK: all placeholders preserved."

    issues = []
    if missing:
        issues.append(f"missing: {', '.join(sorted(missing))}")
    if extra:
        issues.append(f"unexpected: {', '.join(sorted(extra))}")
    return "Placeholder issue - " + "; ".join(issues)


manager_agent = Agent(
    name="manager_agent",
    instructions=(
        "You are a localization manager coordinating specialist translators.\n"
        "For every target language the user requests:\n"
        "1. Call the matching translate_to_<code> tool to get a first translation.\n"
        "2. Call review_translation with the original text and that translation.\n"
        "3. If the original text contains template placeholders (curly braces like "
        "{customer_name}), also call check_placeholders with the original and the "
        "translation, and treat any reported issue as a hard failure.\n"
        "4. If the quality score is below 70, or a placeholder issue was found, call "
        "the same translation tool once more, quoting the specific issues so the "
        "translator can fix them, and use the improved result.\n"
        "Present the final results as a Markdown table with columns: "
        "Language | Translation | Score | Placeholders OK?.\n"
        f"Available target languages (code: name): {', '.join(f'{c}: {n}' for c, n in LANGUAGES.items())}."
    ),
    tools=translation_tools + [review_tool, check_placeholders],
)


async def main():
    print("Multilingual Content Studio")
    print(f"Available languages: {', '.join(LANGUAGES)}")
    print("Type 'exit' to quit, or /template to try a sample text with placeholders.\n")

    while True:
        text = input("Text to translate: ").strip()
        if text.lower() in {"exit", "quit", "q"}:
            break
        if text == "/template":
            text = SAMPLE_TEMPLATE
            print(f"Using sample template: {text}")
        if not text:
            continue

        langs = input(f"Target languages, comma-separated ({'/'.join(LANGUAGES)}): ").strip()
        if not langs:
            continue

        prompt = f"Translate the following text to these languages [{langs}]: {text}"
        result = await Runner.run(manager_agent, prompt)
        print(f"\n{result.final_output}\n")


if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Add your OPENAI_API_KEY to a .env file (see .env.example).")
    asyncio.run(main())
