"""
04 - Customer Support Center
Goal: a support center that routes requests to the right specialized agent,
relies on realistic order data (mock DB), keeps a persistent trace of each
ticket, and can hand control back to triage if the topic changes.

Base pattern (book p.21-23): decentralized pattern (handoffs).
Advanced features added:
- Mock orders DB (dict) queried by real tools, not a static string
- Handoff back to triage from every specialized agent (suggested by the
  book on p.23, implemented here)
- Persistent ticket history in SQLite (who handled what, and how)
- /tickets command: analytics — how many tickets per agent
- Multi-turn conversation that continues with the last agent who replied

Extra task - Bulk Order Status Check:
- track_multiple_orders handles a whole list of order ids in a single tool
  call, so a customer can ask about several orders at once instead of one
  id per message - a common real support scenario.
"""

import asyncio
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from agents import Agent, Runner, function_tool

load_dotenv()

DB_FILE = Path(__file__).parent / "support.db"

MOCK_ORDERS = {
    "12345": {"product": "Wireless headphones", "status": "in transit", "eta_days": 2},
    "67890": {"product": "Mechanical keyboard", "status": "delivered", "eta_days": 0},
    "54321": {"product": "4K monitor", "status": "processing", "eta_days": 5},
}


def init_db() -> None:
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                customer_message TEXT NOT NULL,
                handled_by TEXT NOT NULL,
                resolution TEXT NOT NULL
            )
            """
        )


def log_ticket(customer_message: str, handled_by: str, resolution: str) -> None:
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            "INSERT INTO tickets (created_at, customer_message, handled_by, resolution) VALUES (?, ?, ?, ?)",
            (datetime.now().isoformat(timespec="seconds"), customer_message, handled_by, resolution),
        )


def print_ticket_analytics() -> None:
    with sqlite3.connect(DB_FILE) as conn:
        rows = conn.execute(
            "SELECT handled_by, COUNT(*) FROM tickets GROUP BY handled_by ORDER BY COUNT(*) DESC"
        ).fetchall()
    if not rows:
        print("No tickets logged yet.\n")
        return
    print("Tickets handled per agent:")
    for handled_by, count in rows:
        print(f"- {handled_by}: {count}")
    print()


@function_tool
def search_knowledge_base(query: str) -> str:
    """Search a mock internal knowledge base for a technical answer."""
    return f"[Knowledge base] For '{query}', try restarting the related service and trying again."


@function_tool
def initiate_purchase_order(product: str, quantity: int) -> str:
    """Create a mock purchase order and return a generated order id."""
    new_id = str(10000 + len(MOCK_ORDERS) + 1)
    MOCK_ORDERS[new_id] = {"product": product, "status": "processing", "eta_days": 5}
    return f"Order created (id {new_id}): {quantity}x {product}."


@function_tool
def track_order_status(order_id: str) -> str:
    """Look up the real (mock) status of an order by id."""
    order = MOCK_ORDERS.get(order_id.strip())
    if order is None:
        return f"No order found with id {order_id}."
    if order["status"] == "delivered":
        return f"Order {order_id} ({order['product']}): delivered."
    return f"Order {order_id} ({order['product']}): status '{order['status']}', estimated delivery in {order['eta_days']} day(s)."


@function_tool
def track_multiple_orders(order_ids: list[str]) -> str:
    """Look up the status of several orders at once, given a list of order ids."""
    if not order_ids:
        return "No order ids provided."
    lines = ["Bulk order status:"]
    for order_id in order_ids:
        order = MOCK_ORDERS.get(order_id.strip())
        if order is None:
            lines.append(f"- {order_id}: not found.")
        elif order["status"] == "delivered":
            lines.append(f"- {order_id} ({order['product']}): delivered.")
        else:
            lines.append(
                f"- {order_id} ({order['product']}): status '{order['status']}', "
                f"ETA {order['eta_days']} day(s)."
            )
    return "\n".join(lines)


@function_tool
def initiate_refund_process(order_id: str, reason: str) -> str:
    """Start a mock refund for an order, only eligible if it was already delivered."""
    order = MOCK_ORDERS.get(order_id.strip())
    if order is None:
        return f"No order found with id {order_id}."
    if order["status"] != "delivered":
        return f"Order {order_id} is not eligible for a refund (current status: {order['status']})."
    return f"Refund initiated for order {order_id} ({order['product']}). Reason on file: {reason}."


technical_support_agent = Agent(
    name="Technical Support Agent",
    instructions=(
        "You provide expert assistance with resolving technical issues, system "
        "outages, or product troubleshooting. Use search_knowledge_base when relevant. "
        "If the customer's request is not about a technical issue, hand off to the Triage Agent."
    ),
    tools=[search_knowledge_base],
)

sales_assistant_agent = Agent(
    name="Sales Assistant Agent",
    instructions=(
        "You help clients browse the product catalog, recommend suitable solutions, "
        "and facilitate purchase transactions using initiate_purchase_order. "
        "If the customer's request is not about a purchase, hand off to the Triage Agent."
    ),
    tools=[initiate_purchase_order],
)

order_management_agent = Agent(
    name="Order Management Agent",
    instructions=(
        "You assist clients with inquiries regarding order tracking, delivery "
        "schedules, and processing returns or refunds, using track_order_status "
        "for a single order, track_multiple_orders when the customer mentions "
        "more than one order id at once, and initiate_refund_process for refunds. "
        "If the customer's request is unrelated to an existing order, hand off to "
        "the Triage Agent."
    ),
    tools=[track_order_status, track_multiple_orders, initiate_refund_process],
)

triage_agent = Agent(
    name="Triage Agent",
    instructions=(
        "You act as the first point of contact, assessing customer queries and "
        "directing them promptly to the correct specialized agent."
    ),
    handoffs=[technical_support_agent, sales_assistant_agent, order_management_agent],
)

# Every specialized agent can hand control back to triage if the topic changes (book p.23).
for specialized_agent in (technical_support_agent, sales_assistant_agent, order_management_agent):
    specialized_agent.handoffs.append(triage_agent)


async def main():
    init_db()
    print("Customer Support Center — commands: /tickets, exit\n")
    print("Example available order ids:", ", ".join(MOCK_ORDERS), "\n")

    history: list = []
    current_agent = triage_agent

    while True:
        user_input = input("Customer: ").strip()
        if user_input.lower() in {"exit", "quit", "q"}:
            break
        if user_input == "/tickets":
            print_ticket_analytics()
            continue
        if not user_input:
            continue

        history.append({"role": "user", "content": user_input})
        result = await Runner.run(current_agent, history)
        print(f"[{result.last_agent.name}] {result.final_output}\n")

        log_ticket(user_input, result.last_agent.name, result.final_output)
        history = result.to_input_list()
        current_agent = result.last_agent


if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Add your OPENAI_API_KEY to a .env file (see .env.example).")
    asyncio.run(main())
