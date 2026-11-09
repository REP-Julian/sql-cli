# SQL Prompt Improvement Implementation Plan

> **For agentic workers:** Follow this plan in order. Keep changes limited to the prompt in `sqlcli/ai.py`.

**Goal:** Improve local `:ask` interpretation of common plain-language SQL requests while retaining its safe SQL-or-clarification contract.

**Architecture:** Refine the instructions assembled by `suggest_sql` in `sqlcli/ai.py`. Keep Ollama transport, schema formatting, output parsing, CLI routing, and SQL safety behavior as-is.

**Tech Stack:** Python 3.10+, local Ollama `/api/generate`, existing MySQL schema metadata.

**Spec:** `docs/superpowers/specs/2026-11-05-sql-prompt-design.md`

## Global Constraints

- Return one SQL statement or `CLARIFY: ...` only.
- Use only tables and columns present in the supplied schema.
- Never suggest an unscoped `UPDATE` or `DELETE`.
- The AI only suggests SQL; SQLCLI does not execute its suggestion automatically.
- Do not add dependencies, change models, or change resource safeguards.
- Keep the change inside the existing `suggest_sql` prompt in `sqlcli/ai.py`.
- Do not add or run tests unless the user asks for testing or verification.

## Review Focus

- Ambiguous request: ask one concise, useful clarification instead of guessing.
- Missing table or column: do not invent schema names; clarify.
- Greeting or non-SQL request: use the existing `CLARIFY:` redirect behavior.
- Data-changing request without a precise scope: do not produce an `UPDATE` or `DELETE`.
- Clear read request with informal wording or a minor typo: infer the intended request when the schema makes it unambiguous.

---

### Task 1: Refine the local SQL request instructions

**Files:**
- Modify: `sqlcli/ai.py` in `suggest_sql`

**Interfaces:**
- Consumes: `question`, the selected database name, `database.tables`, and existing Ollama settings.
- Produces: one SQL statement or `CLARIFY: ...`, consumed by the existing parser and `:ask` command.

- [x] Review the current prompt and preserve its existing SQL safety requirements.
- [x] Refine the prompt so common list, count, filter, sort, and limit requests map to the schema-grounded SQL intent; preserve requested limits and do not assume unavailable fields.
- [x] Make ambiguity behavior explicit: ask only for information needed to choose a table, column, value, or safe write scope; keep the clarification brief.
- [x] Keep greetings and non-SQL requests under the existing `CLARIFY:` contract; do not add conversational output.
- [x] Inspect the resulting diff and confirm only the SQL prompt changed; do not modify the pre-existing working-tree edits.

**Completion check:** The prompt text still requests exactly one safe SQL statement or `CLARIFY: ...`, and the parser, resource checks, and CLI flow are unchanged. Automated tests are not part of this plan unless requested.
