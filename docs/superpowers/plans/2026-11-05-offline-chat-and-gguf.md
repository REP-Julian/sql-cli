# Offline Chat and Selected GGUF Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a conversational `:chat` command with session context and user-controlled memory, using the user's selected Qwen3.5 2B uncensored GGUF for every SQLCLI AI feature.

**Architecture:** Import the exact GGUF into the existing local Ollama model store under `qwen3.5:2b-uncensored`; set this project’s ignored `.env` to that model. Add a separate `/api/chat` client and a per-user memory module, then connect them through a `:chat` command without changing the SQL-only behavior of `:ask`.

**Tech Stack:** Python 3.10+, Ollama HTTP API and Modelfile, JSON local memory, Windows PowerShell.

**Spec:** `docs/superpowers/specs/2026-11-05-offline-chat-design.md`

## Global Constraints

- Use the exact file `Qwen3.5-2B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf` from the publisher repository; do not substitute another model.
- Keep the existing Ollama URL, CPU/RAM guard, and CPU-only inference limits.
- Use `qwen3.5:2b-uncensored` for `:chat`, `:ask`, and SQL correction in this project only; leave general configuration defaults unchanged.
- Do not store chat memory in `.env`, database tables, or the repository; use `~/.sqlcli_memory.json` and save only facts the user explicitly asks to remember.
- Keep current-session context to the most recent 8 chat messages; persistent memory is capped at 20 entries of at most 300 characters each.
- Never execute SQL shown in a conversational answer.
- If the installed Ollama build cannot load the selected Qwen3.5 GGUF, stop before replacing/upgrading the runtime and report the compatibility issue.
- Do not add automated tests or run the test suite unless the user asks; perform only the Ollama/model and chat smoke checks explicitly included in the approved design.

## Review Focus

- `:chat hello`: respond with a natural conversational greeting, not a SQL clarification.
- Follow-up chat turn: use recent messages from the same SQLCLI run, bounded to 8 messages.
- Saved memory: include only user-entered memories, preserve them across launches, and allow listing and deletion.
- `:chat how do I delete a column?`: explain the general MySQL operation without touching the connected database.
- Existing `:ask`: remain schema-grounded and preserve the SQL-or-clarification output contract.
- Import failure: preserve current model settings and runtime if Ollama cannot load the selected GGUF.

---

### Task 1: Import and select the requested GGUF for this project

**Files:**
- Create: `models/Qwen3.5-2B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf` (ignored local model asset)
- Create: `models/Modelfile.qwen35-2b-uncensored` (ignored local import recipe)
- Modify: `.env` only at `SQLCLI_OLLAMA_MODEL`

**Interfaces:**
- Produces: Ollama tag `qwen3.5:2b-uncensored`, visible to the existing `/api/tags` check and SQLCLI settings.

- [x] Download the exact Q4_K_M file from the publisher repository into `models/` and confirm the local file size is approximately 1.27 GB.
- [x] Create the Ollama model from a Modelfile whose `FROM` points to that exact local GGUF.
- [x] Start Ollama through SQLCLI so it uses the `.env`-configured model store (`C:\sqlCLI\models`); do not assume the GGUF source folder is also the Ollama store.
- [x] Confirm the bundled Ollama model store lists `qwen3.5:2b-uncensored` and responds to a short local greeting prompt.
- [x] Only after import and smoke check succeed, update `.env` so `SQLCLI_OLLAMA_MODEL=qwen3.5:2b-uncensored`; preserve every other `.env` value.
- [x] If import or load fails because the bundled Ollama build lacks support, stop here without changing `.env` or replacing Ollama.

### Task 2: Add local chat generation and explicit memory storage

**Files:**
- Modify: `sqlcli/ai.py`
- Create: `sqlcli/chat_memory.py`

**Interfaces:**
- Produce `chat_response(message: str, history: list[dict[str, str]], memories: list[str], url: str, model: str) -> str` in `sqlcli/ai.py`.
- Produce memory helpers for load, add, list, and remove operations in `sqlcli/chat_memory.py`; persist to `Path.home() / ".sqlcli_memory.json"`.

- [x] Add a `/api/chat` request path that passes a system message, saved memory, the last 8 session messages, and the current user message; return only assistant text.
- [x] Reuse existing resource checks, timeouts, and Ollama error handling patterns.
- [x] Implement explicit memory operations with JSON validation and atomic writes; enforce 20 notes maximum and 300 characters per note.
- [x] Do not change `suggest_sql`, `correct_sql`, or their SQL output handling in this task.

### Task 3: Expose `:chat` in the CLI and document it

**Files:**
- Modify: `sqlcli/cli.py`
- Modify: `README.md`

**Interfaces:**
- `:chat <message>` sends a local conversational turn.
- `:chat remember <fact>` saves an explicit memory.
- `:chat memory` lists saved memories.
- `:chat forget <number|all>` removes selected saved memories.
- `:chat reset` clears current-session history without deleting saved memory.

- [x] Initialize bounded in-memory chat history in `main()` and wire the five `:chat` actions to the Task 2 interfaces.
- [x] Require AI to be enabled and call `ensure_ready(settings)` before generation, as `:ask` does.
- [x] Keep `:ask` and SQL correction using the configured model and SQL-only response handling.
- [x] Update CLI help and the README with the chat and memory commands, explain offline knowledge limits, and show the two screenshot cases.
- [x] Run the approved smoke checks: greeting, same-session follow-up, persistent memory after restarting SQLCLI, memory removal, and a general SQL how-to response. Inspect the scoped diff and preserve all pre-existing edits.

**Completion check:** The selected model imports and runs through local Ollama; `:chat` behaves conversationally with bounded session context and explicit persistent memory; SQL requests continue through `:ask`; no SQL is executed by chat.
