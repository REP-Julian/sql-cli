# Offline Conversational AI Design

Date: 2026-11-05

## Intent

Give SQLCLI a normal offline conversation path so greetings and general how-to questions do not get misread as requests about the selected database. The screenshot examples `:chat hello` and `:chat how do I delete a column?` should receive natural replies, while `:ask` remains dedicated to schema-based SQL suggestions.

## Approaches considered

1. **Separate `:chat` command (selected).** Keeps conversational replies apart from the SQL-only `:ask` contract and makes each path predictable. It requires users to use `:chat` for general conversation.
2. **Automatically route through `:ask`.** Avoids a new command, but the app must classify mixed questions and SQL requests; mistakes can make ordinary questions look like SQL or vice versa.
3. **Change only the prompt.** Smallest code change, but it cannot provide multi-turn context or reliably turn the SQL-only parser into a conversational interface.

## Goals

- Add `:chat <message>` for ordinary local conversation and general how-to questions.
- Keep recent messages from the current SQLCLI run in context so follow-up questions make sense.
- Let the user explicitly save, view, and remove personal memory that can be included in later chat sessions.
- Use the user's selected `Qwen3.5-2B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf` for all SQLCLI AI requests through the configured local Ollama service, retaining SQLCLI's CPU/RAM checks.
- Do not execute SQL generated or shown in chat.

## Non-goals and anti-goals

- Do not claim the model knows everything, is always correct, or learns by changing its weights.
- No internet search or live facts while offline.
- Do not change `:ask` from its SQL-or-clarification output contract.
- Do not automatically save private facts from chat; persistent memory is user-controlled and removable.
- No disabling resource protections.

## Constraints and implementation calls

- The exact GGUF was not found in the project's model folder or Downloads. Obtain it from the [publisher's Hugging Face repository](https://huggingface.co/HauhauCS/Qwen3.5-2B-Uncensored-HauhauCS-Aggressive); the Q4_K_M file is about 1.27 GB.
- This is a 2B uncensored fine-tune that advertises stronger refusal removal; that changes refusal behavior, not the amount of knowledge or reasoning guaranteed by the model.
- Import the single GGUF into the existing Ollama model folder with a Modelfile, under the local tag `qwen3.5:2b-uncensored`. Ollama's import flow supports a `FROM <path-to-gguf>` Modelfile.
- Set the project's `.env` model selection to that tag so chat, SQL suggestions, and SQL correction all use the selected model. Keep the general config default intact for other project installs.
- Verify the installed Ollama build can load this Qwen3.5 GGUF before switching SQLCLI to the new tag. Do not silently replace the Ollama runtime if compatibility fails.
- Keep the existing Ollama URL and CPU/RAM safeguards; the model alias preserves SQLCLI's 2B memory estimate.
- Use Ollama's local conversational interface with a system instruction that answers general questions directly and acknowledges uncertainty.
- Keep session chat history bounded to a small recent window appropriate for SQLCLI's 4K context setting; add only explicitly saved memory to later sessions.
- Store memory in a separate JSON file in the user's profile, not in the project `.env` or database. Provide commands to list and clear it.
- `:chat how do I delete a column?` may explain the general MySQL operation and show an example, but it must not act on the connected database.
- The model can answer from its training and supplied context, but cannot guarantee complete knowledge or fresh facts.

## Acceptance

`:chat hello` gives a natural greeting; a follow-up can refer to earlier messages in the same run; a user-saved fact is available after restarting SQLCLI and can be removed; general SQL how-to questions are answered without being treated as changes to the user's database; `:ask` remains SQL-focused; chat, SQL suggestions, and SQL correction use the selected GGUF model; all model calls remain subject to existing resource checks.
