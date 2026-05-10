# Contexly - Codebase Context Engine

> Give your AI agent a GPS, not a map dump.
> Contexly tells agents exactly where to edit, what can break, and why.

[![PyPI](https://img.shields.io/pypi/v/contexly)](https://pypi.org/project/contexly/)
![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.10+-blue)
![Tests](https://img.shields.io/badge/tests-79%20passed-brightgreen)
![Version](https://img.shields.io/badge/version-0.1.0-orange)

Contexly extracts the logic skeleton of your codebase: function signatures,
conditions, calls, returns, and impact paths.

Context Engine for AI Coding Agents - Stop missing dependencies.

## Why Contexly

Most agent failures are not syntax bugs. They are navigation bugs.
The model edits 2-3 obvious files, misses dependent files, then reports "done".

Contexly solves this by giving an execution-level map first, then targeted context.

What you get:

- Compact, searchable logic trees
- Context lookup by file, function, and behavior intent
- Fast CLI + MCP workflow for day-to-day coding tasks

## How Agents Use Contexly

```bash
# Agent gets task: "fix pivot hedge logic"
contexly query . "pivot hedge" 2 2
```

Agent gets back:

```text
price_monitor.py [L39-130]   <- signal decided here
round_manager.py [L110-157]  <- amount calculated here
round_manager.py [L164-443]  <- order execution path
Impact: claim_manager.py reads pivot_count too
```

Agent edits exactly those files. Nothing else.
No hallucinated edits, no missed dependency hops.

## Why I Built This

I was building a SaaS product on top of OpenClaw + n8n
(roughly 700k lines combined).

As a solo developer using coding agents daily, I kept seeing
the same failure: the agent patched 2-3 files and declared success,
while real impact lived elsewhere.

Contexly was built to fix that exact failure mode.

## Bonus: Contexly Flags Smells

Contexly surfaces patterns like duplicate execution functions,
legacy overlap, and risky impact chains while building/querying context.

This helps agents avoid copy-paste regressions before they happen.

## Real Example - Polymarket Trading Bot

Ran on a real 13-file Python trading bot:

| | Before | After |
|---|---|---|
| Tokens sent to AI | 197,068 | 7,727 |
| Compression | - | **95.8%** |
| AI reads raw code? | Every message | Never |

Same understanding. 25x fewer tokens.


## Supported Languages

| Language | Extensions | Parser |
|---|---|---|
| Python | `.py` | tree-sitter |
| JavaScript | `.js`, `.mjs` | tree-sitter |
| TypeScript | `.ts`, `.tsx` | tree-sitter |
| Go | `.go` | tree-sitter |
| HTML | `.html`, `.htm` | fallback parser + frontend signal tracker |
| CSS | `.css`, `.scss`, `.sass`, `.less` | fallback parser + selector tracker |

Files with unsupported extensions are skipped automatically.

## Installation

```bash
pip install contexly
```

Dev install (with test tools):

```bash
pip install -e ".[dev]"
```

## Quick Start

```bash
# 1) Build a logic tree
contexly tree .

# 2) Get high-level repository map
contexly index . 0

# 3) Query relevant context
contexly query . "test query" 2 1

# 4) Open generated HTML tree
contexly view .

# Optional: force fresh tree build (ignore cached tree.json)
contexly --rebuild query . "test query" 2 1
```

## CLI Commands

### `contexly init <path>`

Initialize `.contexly/` metadata for a project.

### `contexly tree <path>`

Build a logic skeleton tree and save outputs to:

- `.contexly/tree.json` — machine-readable skeleton
- `.contexly/tree.html` — visual browser explorer

**Example output:**

```text
Building logic tree for: my-api/
Files processed:    11
Raw token estimate: 84,310
Tree tokens:        3,920
Compression:        95.4%  (21x smaller)

File roles:
  ENTRY    2 file(s)   main.go, server.go
  CORE     5 file(s)
  TEST     4 file(s)
```

Skeleton of one function (raw → compressed):

```text
# Raw source (~42 tokens)
func ProcessOrder(ctx context.Context, order Order) error {
    if order.Amount <= 0 {
        return ErrInvalidAmount
    }
    user, err := db.GetUser(ctx, order.UserID)
    if err != nil {
        return err
    }
    return payments.Charge(ctx, user, order.Amount)
}

# Contexly skeleton (~11 tokens)
~ProcessOrder(ctx, order)[L24-36]
  ?if order.Amount <= 0
  >db.GetUser()
  >payments.Charge()
  <err / nil
```

### `contexly index <path> [level]`

Print compact index from existing tree or create one if missing.

- `level=0` -> repo map
- `level=1` -> file index (default)

### `contexly query <path> "<query>" [depth] [level]`

Search context and build targeted result around matched files.

- `depth` = how many dependency hops from matched files (`1` = direct links)
- `level` = output detail (`1` = index view, `2` = function skeletons)
- Add `--rebuild` before command to ignore cached tree and force fresh analysis.

Examples:

```bash
contexly query . "rate limiting" 1 2
contexly query . "auth flow" 2 1 --debug
```

### `contexly impact <path> <function_name> [file_hint]`

Preview downstream impact before editing a function.
Shows direct callers, indirect impact chain, dataflow dependencies, and side effects.

Flags:
- `--depth N` — traverse up to N hops in call graph (default: 2, max: 5)
- `--dataflow` — include data flow analysis (configs, state, side effects)
- `--show-paths` — display complete call paths from entry points to target function
- `--exclude <role>` — skip files by role (e.g., `--exclude legacy`)

Examples:

```bash
# Basic impact analysis
contexly impact . run_coin_round

# Deep analysis with dataflow
contexly impact . execute_trade --depth 3 --dataflow

# Show complete call paths and side effects
contexly impact . process_payment --depth 3 --dataflow --show-paths

# Exclude legacy code from analysis
contexly impact . handle_request --depth 2 --exclude legacy
```

See [IMPACT_ANALYSIS.md](IMPACT_ANALYSIS.md) for detailed workflow guide.

### `contexly status <path>`

Show current tree summary and compression info.

### `contexly view <path or html_file>`

Open generated tree HTML in the browser.

### `contexly session ...`

Session commands for optional progress tracking:

- `session new <path> "Task name"`
- `session update <path> <done|in_progress|todo> "text"`
- `session step <path> "completed" "next"`
- `session status <path>`

## MCP for Agents

Contexly provides an MCP server for Claude, Copilot, Cursor, Continue, Windsurf, and other MCP-compatible clients.

Start MCP server:

```bash
contexly-mcp
```

or

```bash
python contexly_mcp.py
```

See full setup examples in [MCP_SETUP.md](MCP_SETUP.md) and [mcp.example.json](mcp.example.json).

## Documentation Map

- [AGENT_REFERENCE.md](AGENT_REFERENCE.md): complete agent workflow guide
- [MCP_TOOL_REFERENCE.md](MCP_TOOL_REFERENCE.md): quick MCP signatures and examples
- [REPO_STRUCTURE.md](REPO_STRUCTURE.md): repository and module structure
- [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md): documentation navigation
- [MCP_SETUP.md](MCP_SETUP.md): client integration setup
- [IMPACT_ANALYSIS.md](IMPACT_ANALYSIS.md): deep impact analysis workflow and flags

## Known Limitations

- React/TSX extraction is much better now, but highly dynamic component patterns can still produce partial skeletons.
- Import connection quality depends on resolver hints (`tsconfig.json` paths, Vite aliases, re-export patterns).
- If output looks stale or unexpectedly thin, use `--rebuild` to bypass cache and regenerate context.

If you hit a bad case, open an issue with a minimal repro project. That helps improve parser coverage quickly.

## Roadmap

- v0.2.0 - AI coding agent CLI (automated refactoring powered by Contexly logic maps)
- v0.2.0 - VS Code extension (interactive context + impact visualization in editor)
- v0.2.0 - Rust support (foundation ready)
- v0.3.0 - Cloud context sync (share context snapshots across teams)
- v0.3.0 - Java support

**Currently Supported Languages:** Python, JavaScript, TypeScript, Go

## Contributing

Please open an issue or pull request with clear reproduction steps and expected behavior.

## License

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Distributed under the MIT License. See [LICENSE](LICENSE).
