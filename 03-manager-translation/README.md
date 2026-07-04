# 03 — Multilingual Content Studio

## Objective

A localization studio: give it a text and a list of target languages, and the system translates **and** checks the quality of each translation before delivering it, correcting itself if needed.

## Base pattern (book p.18-20)

**Manager pattern**: a central `manager_agent` orchestrates specialized agents exposed as tools (`agent.as_tool(...)`), and remains the sole point of contact for the user.

## Advanced features already implemented

- **Dynamically generated agents** from a `LANGUAGES` dict (`es`, `fr`, `it`, `de`, `ar`) — adding a language takes one line, no need to copy-paste an `Agent(...)` block per language like in the book.
- **Reviewer agent** (`reviewer_agent`): structured Pydantic output (`score: int`, `issues: list[str]`) that evaluates each translation.
- **Self-correction loop**: if the quality score is below 70, the manager asks for another translation citing the issues found — a concrete illustration of the book's criterion on p.4: *"[the agent] can proactively correct its actions if needed"*.
- **Formatted output**: the manager delivers a Markdown table (language / translation / score), ready to use.

## Extra task: Templated Content Localization

A richer, second task beyond plain sentences: real support and marketing content is full of merge fields like `{customer_name}` or `{order_id}`. The new `check_placeholders` tool verifies these survive translation **byte-for-byte** — an LLM can easily "helpfully" translate or drop a placeholder, which would silently break a production email template. The manager now treats any placeholder mismatch as a hard failure requiring a retry, exactly like a low quality score. Type `/template` at the prompt to try a ready-made example.

## Run the project

```bash
cd 03-manager-translation
python translation_manager.py
```

## Example interaction

```
Text to translate: Our new product launch is a game changer
Target languages, comma-separated (es/fr/it/de/ar): es,fr

| Language | Translation | Score |
|---|---|---|
| Spanish | El lanzamiento de nuestro nuevo producto lo cambia todo | 92 |
| French | Le lancement de notre nouveau produit change la donne | 95 |
```

```
Text to translate: /template
Using sample template: Hi {customer_name}, your order {order_id} has shipped and will arrive by {eta_date}. Thank you for choosing us!
Target languages, comma-separated (es/fr/it/de/ar): es,fr

| Language | Translation | Score | Placeholders OK? |
|---|---|---|---|
| Spanish | Hola {customer_name}, tu pedido {order_id} ha sido enviado y llegará antes del {eta_date}. ¡Gracias por elegirnos! | 94 | Yes |
| French | Bonjour {customer_name}, votre commande {order_id} a été expédiée et arrivera avant le {eta_date}. Merci de votre confiance ! | 96 | Yes |
```

## What to observe

- The manager **never translates itself**: it always delegates, then has the reviewer validate before delivering.
- Check the tool-call traces if you enable them (see the SDK's tracing docs): you should see the sequence `translate_to_X` → `review_translation` → sometimes a second `translate_to_X` if the score was low.
- Compare with project 04: here a single agent (the manager) always replies to the user; in the decentralized pattern, it's the specialized agents themselves that reply after a handoff.

## Known limitation (improvement idea)

When the manager asks for a "corrected" translation, it passes the original text plus the issues found in a single message to the translator — but the translator agent's instructions say to "translate the received message", so it might misinterpret this enriched instruction. A real production version would give the translation tool a dedicated `revision_notes` parameter instead of mixing everything into one string.

## Go further

- Fix the limitation above: give the translation tool an optional second parameter `revision_notes: str` that the translator explicitly uses if provided.
- Add automatic source-language detection (`detect_language` tool) so you don't have to ask the user.
- Cap the number of re-translations at 1 with an explicit counter in the instructions, to avoid a costly loop if the score stays low indefinitely.
