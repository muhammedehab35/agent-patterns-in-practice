# 04 — Customer Support Center

## Objective

A support center that routes requests to the right specialist, relies on real order data (simulated but consistent, not static strings), keeps a persistent trace of every exchange, and knows how to hand control back to triage if the topic changes mid-conversation.

## Base pattern (book p.21-23)

**Decentralized pattern (handoffs)**: the `triage_agent` receives every request and transfers control (`handoffs=[...]`) to one of the 3 specialized agents. Each specialized agent becomes fully responsible once it has received control.

## Advanced features already implemented

- **Mock orders DB** (`MOCK_ORDERS`): tools query a real dict with status, product, and ETA — no hardcoded text per call.
- **Handoff back to triage**: every specialized agent can hand control back (`specialized_agent.handoffs.append(triage_agent)`) if the request falls outside its scope — this is the optional extension suggested by the book on p.23, implemented here.
- **Persistent ticket history** in SQLite (`support.db`): every exchange is logged with the agent that handled it and the resolution given.
- **Analytics** (`/tickets`): number of tickets handled per agent, computed directly from the database.
- **Smart multi-turn conversation**: after a handoff, subsequent turns continue with the last agent that replied (`result.last_agent`) — no systematic return to triage on every message.

## Extra task: Bulk Order Status Check

A richer, second task beyond one-order-at-a-time lookups: `track_multiple_orders` accepts a **list** of order ids in a single tool call, so a customer asking "what's the status of orders 12345, 67890, and 54321?" gets one consolidated reply instead of three separate exchanges — a common real support scenario the original book pattern doesn't cover.

## Run the project

```bash
cd 04-customer-service-handoffs
python triage_system.py
```

## Example interaction

```
Customer: Can you give me an update on order 12345?
[Order Management Agent] Order 12345 (Wireless headphones): status 'in transit', estimated delivery in 2 day(s).

Customer: And I'd like a refund for that order.
[Order Management Agent] Order 12345 is not eligible for a refund (current status: in transit).

Customer: OK, one more thing: my network printer is not responding.
[Technical Support Agent] According to our knowledge base, try restarting the related service.

Customer: /tickets
Tickets handled per agent:
- Order Management Agent: 2
- Technical Support Agent: 1

Customer: Can you check on orders 12345, 67890 and 54321 for me?
[Order Management Agent] Bulk order status:
- 12345 (Wireless headphones): status 'in transit', ETA 2 day(s).
- 67890 (Mechanical keyboard): delivered.
- 54321 (4K monitor): status 'processing', ETA 5 day(s).
```

Note: the 3rd message ("network printer") was initially sent to `current_agent` (Order Management Agent from the previous turn) but that agent, seeing it wasn't within its scope, handed control back to triage, which re-routed to technical support — all in a single turn, invisible to the customer.

## What to observe

- `result.last_agent.name` changes throughout the conversation: proof that control genuinely moves between agents.
- A refund request on an "in transit" order is rejected by the tool's own business logic (`initiate_refund_process`), not by the LLM — a critical business rule should never rely solely on the model's good judgment.
- Open `support.db` to see the full trace of every ticket.

## Go further

- Add an "escalated" status: if a customer repeats the same complaint twice without resolution, a guardrail (see project 05) triggers a "transfer to a human" notification (cf. book p.31, "Plan for human intervention").
- Add a `get_customer_history(customer_id)` tool that queries `support.db` to give the agent context on the same customer's previous tickets.
- Replace `MOCK_ORDERS` with a real pre-populated `orders.db` SQLite file, to bring the project even closer to a real e-commerce backend.
