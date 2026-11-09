# SQL Prompt Improvement Design

Date: 2026-11-05

## Intent

Improve how SQLCLI's existing local `:ask` feature interprets everyday SQL requests, so users receive more accurate schema-grounded SQL suggestions and clearer follow-up questions when a request is ambiguous.

## Approaches considered

1. **Improve SQL prompts only (selected).** Refine the request instructions for intent, schema use, ambiguity, and concise safe output. This fits the existing SQL-only `:ask` flow and keeps runtime, model, and resource use unchanged.
2. **Add conversational chat and memory.** This would require a separate conversation interface and persistent local state. It is outside the selected scope.
3. **Change to a larger or different model.** This could improve capability, but increases downloads and memory/CPU requirements. It is outside the selected scope.

## Goals

- Interpret common plain-language database requests more reliably, including modestly misspelled or informal wording.
- Use only the connected database and supplied schema; never invent tables or columns.
- Ask a short, useful clarification when the requested intent, target, or condition is unclear.
- Preserve the current output contract: one SQL statement or `CLARIFY: ...`; generated SQL is shown for review and never executed by the AI.
- Keep data-changing query safeguards intact.

## Non-goals and anti-goals

- No general conversation mode, multi-turn chat, persistent memory, or model training.
- No Ollama/model change, new dependency, network service, or added resource use beyond a modest prompt change.
- No weakening of SQL safety rules or automatic execution.

## Constraints and implementation calls

- Keep the existing `suggest_sql` and `:ask` flow, schema input, local Ollama endpoint, output parsing, and resource checks.
- Change only the SQL-generation prompt in `sqlcli/ai.py` and, if needed, focused prompt-related tests.
- Evaluate representative requests such as list/count/filter/sort requests, vague update/delete requests, greetings, and requests for nonexistent schema names. Greetings remain outside SQL scope and should get a brief redirect or clarification under the existing `CLARIFY:` contract.
- Prompt changes can guide model behavior but cannot guarantee accuracy; the configured compact model remains a capability limit.

## Acceptance

Representative plain-language SQL requests produce a valid, schema-grounded suggestion or a concise clarification. Ambiguous data changes remain blocked from suggestion without a specific scope. Existing `:ask` SQL-only behavior and safety checks remain intact.
