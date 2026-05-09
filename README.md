# Contexly - Codebase Context Engine

> AI doesn't need your code. It needs your logic.

[![PyPI](https://img.shields.io/pypi/v/contexly)](https://pypi.org/project/contexly/)
![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.10+-blue)
![Tests](https://img.shields.io/badge/tests-56%20passed-brightgreen)
![Version](https://img.shields.io/badge/version-0.1.0-orange)

Contexly extracts logic skeletons from large codebases so AI agents get the structure they need without paying token costs for full source.

## Why Contexly

Large codebases are expensive to feed directly into LLMs. A 1M-line repository can cost $100+ per session and still lose context between chats.

Contexly reduces this by building compact, searchable logic trees:

- 1,000,000 lines -> ~35,000-40,000 tokens (typical)
- Usually 95%+ token reduction
- Searchable context by file, function, and logic intent
- MCP-native workflow for AI agents

## Package Name vs Command Name

Contexly uses different names for package install and CLI command:

- PyPI package name: `contexly`
- CLI command: `contexly`
- MCP command: `contexly-mcp`

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

Build a logic skeleton tree and save artifacts to central output folder:

`~/.vscode/github-repo-context/contexly-outputs/<project-name>/`

Outputs:

- `tree.json`
- `tree.html`

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

## Validation Snapshot

Recent local checks:

- `pytest tests -q` -> `56 passed`
- `contexly tree .` -> PASS
- `contexly index . 0` -> PASS
- `contexly query . "sample query"` -> PASS

## Documentation Map

- [AGENT_REFERENCE.md](AGENT_REFERENCE.md): complete agent workflow guide
- [MCP_TOOL_REFERENCE.md](MCP_TOOL_REFERENCE.md): quick MCP signatures and examples
- [REPO_STRUCTURE.md](REPO_STRUCTURE.md): repository and module structure
- [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md): documentation navigation
- [MCP_SETUP.md](MCP_SETUP.md): client integration setup

## Roadmap to Public Launch

- Final end-to-end checks on fresh environment
- Version bump (when needed)
- Git tag and release notes
- PyPI publish for `pip install contexly-engine`

After PyPI publish, add downloads badge:

```markdown
![Downloads](https://img.shields.io/pypi/dm/contexly)
```

## Contributing

Please open an issue or pull request with clear reproduction steps and expected behavior.

## License

MIT
