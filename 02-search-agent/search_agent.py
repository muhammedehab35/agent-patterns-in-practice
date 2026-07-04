"""
02 - Research Assistant
Goal: a research assistant that searches the web, archives its findings in a
real SQLite database (not a throwaway JSON file), lets you find them again
later, and can export a Markdown report.

Base pattern (book p.9-10): Data tool (search) + Action tool (save).
Advanced features added:
- SQLite persistence with a clean schema (id, query, summary, date)
- A tool to browse history (list_saved_research)
- Markdown export of an archived research entry
- Dedicated CLI commands (/history, /export) that bypass the LLM for
  deterministic operations (faster, no unnecessary API cost)

Extra task - Weekly Digest:
- /digest [days] gathers every research entry from the last N days (default 7)
  and hands them to a second agent (digest_agent) whose only job is to
  synthesize multiple sources into one cohesive overview - a genuinely
  different task from single-query search, closer to real research work.
"""

import asyncio
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from agents import Agent, Runner, WebSearchTool, function_tool

load_dotenv()

BASE_DIR = Path(__file__).parent
DB_FILE = BASE_DIR / "research.db"
REPORTS_DIR = BASE_DIR / "reports"


def init_db() -> None:
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS research (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                summary TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


@function_tool
def save_research(query: str, summary: str) -> str:
    """Save a research query and its summary to the local database. Returns the entry id."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.execute(
            "INSERT INTO research (query, summary, created_at) VALUES (?, ?, ?)",
            (query, summary, datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
        return f"Research saved with id {cursor.lastrowid}."


@function_tool
def list_saved_research(limit: int = 10) -> str:
    """List the most recent saved research entries, most recent first."""
    with sqlite3.connect(DB_FILE) as conn:
        rows = conn.execute(
            "SELECT id, query, summary, created_at FROM research ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()

    if not rows:
        return "No saved research yet."

    lines = []
    for row_id, query, summary, created_at in rows:
        snippet = summary if len(summary) <= 100 else summary[:97] + "..."
        lines.append(f"#{row_id} [{created_at}] {query} -> {snippet}")
    return "\n".join(lines)


def _export_to_markdown(research_id: int) -> str:
    with sqlite3.connect(DB_FILE) as conn:
        row = conn.execute(
            "SELECT id, query, summary, created_at FROM research WHERE id = ?",
            (research_id,),
        ).fetchone()

    if row is None:
        return f"No research found with id {research_id}."

    row_id, query, summary, created_at = row
    REPORTS_DIR.mkdir(exist_ok=True)
    report_path = REPORTS_DIR / f"research_{row_id}.md"
    report_path.write_text(
        f"# Research #{row_id}\n\n**Query:** {query}\n\n**Date:** {created_at}\n\n## Summary\n\n{summary}\n",
        encoding="utf-8",
    )
    return f"Report exported: {report_path}"


@function_tool
def export_to_markdown(research_id: int) -> str:
    """Export a saved research entry (by id) to a Markdown report file."""
    return _export_to_markdown(research_id)


def _fetch_recent_entries(days: int) -> list[tuple[int, str, str, str]]:
    cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
    with sqlite3.connect(DB_FILE) as conn:
        rows = conn.execute(
            "SELECT id, query, summary, created_at FROM research WHERE created_at >= ? ORDER BY id ASC",
            (cutoff,),
        ).fetchall()
    return rows


digest_agent = Agent(
    name="Digest agent",
    instructions=(
        "You receive a list of research entries (query + summary pairs) collected "
        "over a period of time. Synthesize them into a single, cohesive digest: "
        "group related findings, highlight recurring themes, and note any "
        "contradictions between sources. Structure your answer with short headers."
    ),
)


async def _run_digest(days: int) -> None:
    entries = _fetch_recent_entries(days)
    if not entries:
        print(f"No research entries found in the last {days} day(s).\n")
        return

    combined = "\n\n".join(f"Query: {q}\nSummary: {s}" for _, q, s, _ in entries)
    result = await Runner.run(
        digest_agent,
        f"Here are {len(entries)} research entries from the last {days} day(s):\n\n{combined}",
    )

    REPORTS_DIR.mkdir(exist_ok=True)
    digest_path = REPORTS_DIR / f"digest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    digest_path.write_text(f"# Research Digest ({days}-day window)\n\n{result.final_output}\n", encoding="utf-8")

    print(f"Agent: {result.final_output}")
    print(f"(Digest saved to {digest_path})\n")


search_agent = Agent(
    name="Research assistant",
    instructions=(
        "You help the user search the internet and archive useful findings. "
        "After a web search, propose to save_research a concise summary if the "
        "user seems to want to keep it. Use list_saved_research when the user "
        "asks about past research. Always answer in the same language as the user."
    ),
    tools=[WebSearchTool(), save_research, list_saved_research, export_to_markdown],
)


async def main():
    init_db()
    print("Research Assistant — commands: /history, /export <id>, /digest [days], exit\n")
    history: list = []

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in {"exit", "quit", "q"}:
            break
        if not user_input:
            continue

        if user_input == "/history":
            print(_list_history_direct())
            continue

        if user_input.startswith("/export"):
            parts = user_input.split()
            if len(parts) != 2 or not parts[1].isdigit():
                print("Usage: /export <id>\n")
                continue
            print(_export_to_markdown(int(parts[1])) + "\n")
            continue

        if user_input.startswith("/digest"):
            parts = user_input.split()
            days = int(parts[1]) if len(parts) == 2 and parts[1].isdigit() else 7
            await _run_digest(days)
            continue

        history.append({"role": "user", "content": user_input})
        result = await Runner.run(search_agent, history)
        print(f"Agent: {result.final_output}\n")
        history = result.to_input_list()


def _list_history_direct() -> str:
    """Direct DB read for the /history command, bypassing the LLM entirely."""
    with sqlite3.connect(DB_FILE) as conn:
        rows = conn.execute(
            "SELECT id, query, summary, created_at FROM research ORDER BY id DESC LIMIT 10"
        ).fetchall()
    if not rows:
        return "No saved research yet.\n"
    lines = [f"#{r[0]} [{r[3]}] {r[1]} -> {r[2][:80]}" for r in rows]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Add your OPENAI_API_KEY to a .env file (see .env.example).")
    asyncio.run(main())
