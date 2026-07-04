# 05 — Layered Guardrails (Safe Support Agent)

## Objective

A "production-grade" support agent protected by **multiple combined layers of defense**, exactly like the book's diagram on p.25 — not a single isolated guardrail.

## Base pattern (book p.24-30)

Input and output guardrails, run in parallel with the main agent ("optimistic execution"), which raise an exception if a condition is triggered.

## The 4 implemented layers

| Layer | Type (book) | Implementation | Cost |
|---|---|---|---|
| 1 | Deterministic rules (p.27) | `prompt_injection_tripwire` — regex against jailbreak attempts | No LLM call, near instant |
| 2 | LLM classifier (p.26) | `churn_detection_tripwire` — dedicated agent that judges churn risk | 1 extra LLM call |
| 3 | Output PII filter (p.26) | `pii_leak_tripwire` — regex on the agent's response (email, phone, card number) | No LLM call |
| 4 | Tool safeguards (p.26) | `initiate_refund` refuses to run until `confirmed=True` is explicitly passed | Handled by tool design, not the LLM alone |

## Extra task: Second High-Risk Domain + Audit Trail

A richer, second task beyond a single gated tool: `delete_account` is a **second** high-risk action (account deletion, not just refunds), gated the exact same way — proving the confirmation pattern generalizes to any irreversible action, not just money. On top of that, every high-risk tool call (whether it was just requested or actually executed) is now logged to a SQLite audit table (`guardrails_audit.db`), so a security review can reconstruct exactly what was attempted and whether it was genuinely confirmed — the concrete, persisted version of the book's "Plan for human intervention" (p.31).

## Run the project

```bash
cd 05-guardrails-churn-detection
python guardrails_demo.py
```

## Expected output (summary)

```
Tool risk matrix:
- search_faq: low (read-only)
- initiate_refund: high (irreversible financial action)
- delete_account: high (irreversible account action)

--- 1. Normal question ---
Response: To reset your password...

--- 2. Prompt injection attempt (rule layer) ---
Blocked by an INPUT guardrail (rule-based or LLM classifier).

--- 3. Churn risk (LLM layer) ---
Blocked by an INPUT guardrail (rule-based or LLM classifier).

--- 4. Refund without confirmation (tool gating) ---
Response: To confirm, you'd like a refund of $49.99 for order 12345? ...

--- 5. Attempt to leak personal data (output layer) ---
Blocked by the OUTPUT guardrail (potential PII leak detected).

--- 6. Account deletion without confirmation (second high-risk domain) ---
Response: To confirm, you'd like to permanently delete account ACC-9981? ...

High-risk action audit log:
- [2026-07-04T10:15:00] initiate_refund -> refund 49.99 for order 12345 (requested (awaiting confirmation))
- [2026-07-04T10:15:01] delete_account -> delete account ACC-9981 (reason: no longer needed) (requested (awaiting confirmation))
```

## What to observe

- Scenario 2 is blocked **before it even reaches the main agent**: the rules layer is deliberately the first, cheapest line of defense.
- Scenario 4 is **not** blocked: the refusal comes from the tool's design (`confirmed=False` by default), not a guardrail. That's the difference between a guardrail (blocks the whole request) and a tool safeguard (forces a confirmation step within the normal flow).
- Scenario 5 is probabilistic: depending on the model, the agent may refuse to repeat the email (thanks to the explicit instruction) or do it anyway, in which case the output guardrail catches it. Re-run a few times if needed to observe both outcomes.

## Difference from the book

The book's pseudo-code uses `Guardrail(guardrail_function=...)` and a single `GuardrailTripwireTriggered` exception. The current SDK distinguishes `@input_guardrail`/`InputGuardrailTripwireTriggered` from `@output_guardrail`/`OutputGuardrailTripwireTriggered`. Check the [official docs](https://github.com/openai/openai-agents-python) if the API has changed further.

## Go further

- Add a "Moderation" layer (book p.26) by calling OpenAI's moderation API in addition to the 4 current layers.
- Turn scenarios 4 and 6 into a real interactive confirmation: in a CLI loop, ask for `input("Confirm? (y/n)")` before calling the agent again with the confirmation info.
- Extend the audit log to also record guardrail triggers (not just tool actions), so `guardrails_audit.db` becomes a single source of truth for every security-relevant event, not only high-risk tool calls.
