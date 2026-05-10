# Contexly - Codebase Context Engine

> Give your AI agent a GPS, not a map dump.
> Contexly tells agents exactly where to edit, what can break, and why.

[![PyPI](https://img.shields.io/pypi/v/contexly)](https://pypi.org/project/contexly/)
![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.10+-blue)
![Tests](https://img.shields.io/badge/tests-63%20passed-brightgreen)
![Version](https://img.shields.io/badge/version-0.1.0-orange)

Contexly extracts the logic skeleton of your codebase: function signatures,
conditions, calls, returns, and impact paths.

Not raw code. The behavior map.

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

Agent immediately sees:

- `price_monitor.py` - signal decision point
- `round_manager.py` - amount calculation
- `round_manager.py` - execution path
- impact chain for related downstream modules

Then it edits only relevant files, not the whole repo.

## Why I Built This

I was building a SaaS product on top of OpenClaw + n8n
(roughly 700k lines combined).

My agent kept patching a few files and missing cross-codebase impact.
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

Examples:

```bash
contexly query . "rate limiting" 1 2
contexly query . "auth flow" 2 1 --debug
```

### `contexly impact <path> <function_name> [file_hint]`

Preview downstream impact before editing a function.

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

## Roadmap

- v0.2.0 - Rust and Java support
- v0.2.0 - VS Code extension
- v0.3.0 - Cloud context sync

## Contributing

Please open an issue or pull request with clear reproduction steps and expected behavior.

## License

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Distributed under the MIT License. See [LICENSE](LICENSE).
