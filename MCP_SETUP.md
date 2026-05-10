# Contexly MCP Setup (All Agents)

This guide gives ready-to-paste MCP setup for:
- OpenClaw
- Hermes
- Claude Code
- VS Code Copilot
- OpenCode
- Antigravity
- Windsurf
- Continue
- Cursor

It also defines how to get chat-first next-step breakdowns from MCP without forced session logging.

## 1) One-time local setup

```bash
cd contexly
python -m pytest tests -q
python contexly_mcp.py
```

Optional package mode:

```bash
pip install -e .
python -m contexly.mcp_server
```

## 2) Universal MCP server block (copy-paste)

Use this same block in each client's MCP server config area:

```json
{
  "mcpServers": {
    "contexly": {
      "command": "python",
      "args": ["contexly_mcp.py"],
      "cwd": "/path/to/contexly",
      "env": {
        "PYTHONUTF8": "1"
      }
    }
  }
}
```

A ready file exists at `mcp.example.json`.

## 3) Client-specific quick mapping

Most clients now expose either:
- an MCP JSON editor, or
- an MCP settings UI where this same server block can be pasted.

Use this mapping:

1. Claude Code
- Open MCP settings.
- Add server named `contexly`.
- Paste the universal server block.

2. VS Code Copilot
- Open MCP/Tools configuration in Copilot settings.
- Add `contexly` server with same `command`, `args`, `cwd`, `env`.

3. Cursor
- Open Cursor MCP settings.
- Add server using universal block.

4. Continue
- In Continue MCP section, add `contexly` using universal block.

5. Windsurf
- In MCP servers section, add universal block.

6. OpenCode
- In MCP config, add universal block.

7. OpenClaw
- In MCP server config, add universal block.

8. Hermes
- In MCP server config, add universal block.

9. Antigravity
- In MCP server config, add universal block.

If a client uses a different root key than `mcpServers`, keep inner server object unchanged and only adapt outer wrapper as per that client.

## 4) Contexly MCP tools

- `tree(path=".")`
- `index(path=".", level=1)`
- `query(path, query_text, depth=1, level=2, top_k=8, debug=false)`
- `next_in_progress(path, query_text, top_k=8)`
- `impact(path, function_name, file_hint="")`
- `session_new(path=".", task="General Session")`
- `session_update(path, status, text)`
- `session_step(path, completed, next_in_progress="")`
- `session_status(path=".")`
- `agent_contract(path=".")`
- `bootstrap_agent(path=".", task="General Session")`
- `capabilities()`

## 5) Required agent workflow (final contract)

To make agent work exactly as you want:

1. `agent_contract(path)`
- Agent reads operating rules.

2. `next_in_progress(path, query_text)`
- Returns breakdown and suggested next step for agent chat.

3. `query(path, query_text, depth=1, level=2)`
- Pulls targeted context before coding.

4. Edit code

5. `impact(path, function_name, file_hint)`
- Run before signature/API-level edits.

6. Share `suggested_next_in_progress` + `breakdown` in agent chat.
- Keep guidance file-specific and concise.

7. Optional persistence only if user asks:
- `session_step(path, "...", "...")` and `session_update(path, "todo", "...")`.

This keeps planning in chat by default, with session.md as optional persistence.

## 6) System prompt and task prompt you should use

Already added in repo:
- `agent-presets/system_prompt_contexly.txt`
- `agent-presets/task_prompt_template.txt`

Recommended system prompt (short form):

```text
You are a coding agent connected to Contexly MCP.
Use query before coding.
Call next_in_progress to generate a practical execution breakdown.
Share that breakdown in agent chat.
Use impact before risky API changes.
Only update session.md if the user explicitly requests persistence.
```

## 7) What else to keep in GitHub repo (next steps)

Add these next for production-grade workflow:

1. MCP compatibility docs
- Keep this file up to date when adding tools.

2. Prompt pack versioning
- Version prompts in `agent-presets/`.
- Add changelog when prompt behavior changes.

3. CI checks
- Add workflow to run tests + import smoke + lint.
- Validate MCP server starts.

4. Example projects
- Add 1 small and 1 large sample for benchmarked behavior.

5. Security + policy
- Add allowlist for tool actions in agent docs.
- Define forbidden operations policy.

6. Observability
- Add simple logs for MCP tool calls and durations.

7. Release path
- Tag versions and publish release notes for tool/schema changes.

## 8) Suggested immediate additions (your next commit)

1. Add `.github/workflows/ci.yml`:
- test, lint, import-check

2. Add `MCP_CHANGELOG.md`:
- track tool additions and schema updates

3. Add `agent-presets/README.md`:
- explain when to use each prompt

4. Add `examples/`:
- `small_repo_demo`
- `large_repo_demo`

## 9) Troubleshooting

- `ModuleNotFoundError: contexly`
  - Use launcher mode: `python contexly_mcp.py`
  - Or install package: `pip install -e .`

- Tools not visible in client
  - Recheck MCP server block
  - Restart client
  - Ensure `cwd` points to this repo

- Session updates not happening
  - Ensure agent calls `agent_contract` and `bootstrap_agent`
  - Ensure agent prompt includes Contexly workflow requirements
