# 02 — Research Assistant

## Objective

A research assistant: it searches the web, decides when to archive a finding, keeps a queryable history in a real database, and can generate a Markdown report from a past research entry.

## Base pattern (book p.9-10)

Combines a **Data** tool (`WebSearchTool`, OpenAI's hosted web search) with an **Action** tool (save). The book used an undefined `db.insert(...)` — here it's a real **SQLite** database.

## Specific prerequisites

`WebSearchTool()` requires your OpenAI account to have access to hosted web search. If you get an error, swap it for a custom tool (see "Go further").

## Advanced features already implemented

- **SQLite persistence** (`research.db`, created automatically) instead of a JSON file: a clean schema with `id`, `query`, `summary`, `created_at`.
- **Queryable history** the agent can use itself (`list_saved_research`) — you can ask "what have I already searched about X?" in natural language.
- **Markdown export** (`export_to_markdown`): generates a `reports/research_<id>.md` file from an archived entry.
- **Direct CLI commands** `/history` and `/export <id>` that bypass the LLM for purely deterministic operations — faster and free (no API call to list or export).

## Extra task: Weekly Digest

A richer, second task on top of single-entry lookup: `/digest [days]` gathers **every** research entry saved in the last N days (7 by default) and hands them all to a second agent, `digest_agent`, whose only job is synthesis — grouping related findings, spotting recurring themes, and flagging contradictions across multiple sources. This is a genuinely different skill from search-and-save: multi-source synthesis, closer to real research work. The digest is also saved as `reports/digest_<timestamp>.md`.

## Run the project

```bash
cd 02-search-agent
python search_agent.py
```

## Example interaction

```
You: Search for the latest news about OpenAI and save a summary.
Agent: I found several recent updates... [summary] Research saved with id 1.

You: /history
#1 [2026-07-02T21:10:00] latest news about OpenAI -> I found several recent updates...

You: /export 1
Report exported: reports/research_1.md

You: /digest 7
Agent: ## Recurring themes
- Multiple entries mention increased focus on agent tooling...
## Notable contradictions
- None found across the 3 entries reviewed.
(Digest saved to reports/digest_20260704_101500.md)

You: exit
```

## What to observe

- The agent chains **search then save decision** in a single run — it only saves if it judges the user wants to keep the info (look at the `instructions`).
- The `/history` and `/export` commands **never** go through the LLM (`_list_history_direct`, `_export_to_markdown`): this is a deliberate architectural choice — you don't need an LLM to read a database.
- Open `research.db` with a SQLite client (e.g. the "SQLite Viewer" extension in VS Code) to see the raw data.

## Go further

- Swap `WebSearchTool()` for a `@function_tool` calling a free search API (Wikipedia, DuckDuckGo) if you don't have access to OpenAI's hosted search.
- Add a `tags` column (categorization) and a `search_by_tag(tag)` tool to filter history.
- Add a `pytest` test that checks `save_research` followed by `list_saved_research` correctly returns the inserted entry, using a temporary SQLite database (pytest's `tmp_path`).
