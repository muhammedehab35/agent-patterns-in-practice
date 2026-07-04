# Practical Guide to Agents — Hands-on Projects

This repo is based on OpenAI's **["A Practical Guide to Building Agents"](https://openai.com)** guide, but it doesn't just reproduce its code snippets. Each pattern from the book is the foundation for a **real, small application**, with a concrete objective, a real integration (free API, local database) and advanced features: conversation memory, persistence, self-correction, layered guardrails, analytics. On top of that, every project has a **second, richer task** grafted onto the same architecture, to push past "hello world" agent demos.

Goal of this repo: understand agent patterns by building tools you'd actually use, not throwaway demos.

## Prerequisites

- Python 3.9+
- An OpenAI API key ([platform.openai.com](https://platform.openai.com/api-keys))
- No other key required: external integrations (weather) use free public APIs with no authentication.

## Installation

```bash
git clone <your-repo-url>
cd practical-guide-to-agents
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # then paste your OPENAI_API_KEY inside
```

## The 5 projects

| # | Project | Base pattern (book) | Extra task |
|---|---------|-----------------------|--------------|
| 01 | [Weather Assistant](01-weather-agent/) | Model + Tool + Instructions (p.7) — real Open-Meteo API, multi-day forecasts, units, conversation memory | **Trip Planner**: `compare_weather` recommends a destination between two cities based on severe-weather days and temperature |
| 02 | [Research Assistant](02-search-agent/) | Data + Action tools (p.9-10) — SQLite persistence, queryable history, Markdown export | **Weekly Digest**: a second agent synthesizes every research entry from the last N days into one cohesive report |
| 03 | [Multilingual Content Studio](03-manager-translation/) | Manager pattern (p.18-20) — dynamically generated translator agents, reviewer agent, self-correction loop | **Templated Content Localization**: `check_placeholders` guarantees merge fields like `{customer_name}` survive translation unchanged |
| 04 | [Customer Support Center](04-customer-service-handoffs/) | Decentralized handoffs (p.21-23) — mock orders DB, handoff back to triage, ticket analytics | **Bulk Order Status Check**: `track_multiple_orders` answers a query covering several order ids in one call |
| 05 | [Layered Guardrails](05-guardrails-churn-detection/) | Guardrails (p.24-30) — 4 combined layers: rules, LLM classifier, output PII filter, tool gating | **Second high-risk domain + audit trail**: `delete_account` is gated the same way as refunds, and every high-risk attempt is logged to a SQLite audit table |

Each folder has its own `README.md`: objective, what's already implemented ("Advanced features"), the extra task with an example interaction, how to run the script, and remaining ideas to push it even further ("Go further").

## Suggested reading order

Follow the order 01 → 05: complexity (number of agents, layers of protection, persistence) increases progressively, in line with the book's recommendation to start with a single agent before moving to multi-agent systems.

## Project structure

```
practical-guide-to-agents/
├── README.md                 # you are here
├── requirements.txt
├── .env.example
├── .gitignore
├── 01-weather-agent/
│   ├── README.md
│   └── weather_agent.py
├── 02-search-agent/
│   ├── README.md
│   └── search_agent.py       # creates research.db and reports/ on first run
├── 03-manager-translation/
│   ├── README.md
│   └── translation_manager.py
├── 04-customer-service-handoffs/
│   ├── README.md
│   └── triage_system.py      # creates support.db on first run
└── 05-guardrails-churn-detection/
    ├── README.md
    └── guardrails_demo.py    # creates guardrails_audit.db on first run
```

Databases (`*.db`) and generated reports (`reports/`) are created automatically the first time you run a script, and are excluded from version control via `.gitignore` — everyone who clones the repo starts with a clean slate.

## Tech stack

- [`openai-agents`](https://github.com/openai/openai-agents-python) — agent orchestration
- `sqlite3` (stdlib) — local persistence for projects 02, 04 and 05, no server install needed
- `requests` — calls to the free public [Open-Meteo](https://open-meteo.com/) weather API (no key required)
- `pydantic` — structured outputs (guardrails, reviewer, weather reports)

## License

MIT — feel free to fork, modify, and reuse to learn.
