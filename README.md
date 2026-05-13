# Contexly - Codebase Context Engine

> Give your AI agent a GPS, not a map dump.
> Contexly tells agents exactly where to edit, what can break, and why.

[![PyPI](https://img.shields.io/pypi/v/contexly)](https://pypi.org/project/contexly/)
![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.10+-blue)
![Tests](https://img.shields.io/badge/tests-88%20passed-brightgreen)
![Version](https://img.shields.io/badge/version-0.2.1-blue)

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
| JavaScript | `.js`, `.jsx`, `.mjs` | tree-sitter |
| TypeScript | `.ts`, `.tsx` | tree-sitter |
| Go | `.go` | tree-sitter |
| C | `.c`, `.h` | tree-sitter |
| C++ | `.cpp`, `.hpp`, `.cc`, `.hh`, `.cxx` | tree-sitter |
| Java | `.java` | tree-sitter |
| Rust | `.rs` | tree-sitter |
| C# | `.cs` | tree-sitter |
| HTML | `.html`, `.htm` | fallback + embedded `<script>` extraction + frontend signal tracker |
| CSS | `.css`, `.scss`, `.sass`, `.less` | fallback + selector tracker |
| Vue | `.vue` | fallback + `<script>` extraction + reactive binding tracker |
| Svelte | `.svelte` | fallback + `<script>` extraction + reactive binding tracker |

Frontend-aware extraction covers:
- JSX/TSX component patterns
- HTML classes, ids, data-attributes
- External script and stylesheet links
- Inline `<script>` blocks parsed through the JavaScript extractor
- Vue `v-model`, `v-bind`, `v-on`, `defineProps`, `defineEmits`
- Svelte `bind:`, `on:`, `export let`, `$store` references

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

Risk tiers in output:
- `LOW` — minimal downstream impact detected
- `MEDIUM` — some high-impact side effects detected
- `HIGH` — broad risky dependencies (API/DB/notifications/blockchain etc.)
- `PRODUCTION-CRITICAL` — large blast radius likely for live systems

Dynamic risk rules (optional):
- Contexly infers risk domains from whatever side-effect labels it detects at runtime.
- You can customize side-effect detection rules per project via `.contexly/risk_rules.json`.

Example `.contexly/risk_rules.json`:

```json
{
  "effect_rules": [
    {"label": "queue", "keywords": ["kafka", "rabbitmq", "sqs"]},
    {"label": "payments", "keywords": ["stripe", "razorpay", "charge"]}
  ]
}
```

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

## Real-World Validation: OpenClaw

Contexly has been thoroughly tested on **OpenClaw**, a large-scale **AI agent platform** with **400k+ lines of code** across multiple languages (TypeScript, Python, JavaScript, Go, HTML, CSS).

The codebase includes agent runtime internals, skill management, multi-provider integration, and complex orchestration logic - making it an ideal real-world test case for Contexly's scalability.

**Key Results:**
- **17,358 total files** analyzed
- **5,281 files indexed** in final tree
- **Raw tokens:** ~40M+
- **Tree tokens (compressed):** 1,771,552
- **Compression ratio:** 95.7% (47x smaller)
- **Query performance:** <2 seconds (cached)

**All 8 CLI commands tested successfully:**
- ✅ contexly init
- ✅ contexly tree
- ✅ contexly status
- ✅ contexly index (levels 0 & 1)
- ✅ contexly query (with depth/level)
- ✅ contexly impact (with --dataflow, --show-paths)
- ✅ contexly view
- ✅ contexly session

**See complete test report:** [OpenClaw Test Report](tests/fixtures/openclaw/OPENCLAW_TEST_REPORT.md)

This validates Contexly's production readiness for large, multi-language enterprise codebases.

## Release Notes

### v0.2.1 (May 2026) — Multi-Language & Framework Support
**Major Additions:**
- **5 new compiled languages:** C, C++, Java, Rust, C# via tree-sitter with full function/class extraction
- **2 frontend frameworks:** Vue and Svelte with reactive binding tracking (`v-model`, `bind:`, `$store`, etc.)
- **Enhanced HTML extraction:** inline `<script>` block parsing, EXTERNAL_LIBS tracking, frontend role hints
- **Test coverage:** 79 → 88 tests (9 new language validation tests)
- **Professional roadmap:** Contexly Agent (autonomous refactoring), Contexly Cloud, v1.0.0 SaaS platform

**Language Support Matrix:**
| Tier | Languages |
|---|---|
| Full Extraction | Python, JavaScript, TypeScript, Go, C, C++, Java, Rust, C# |
| Frontend-Aware | HTML, CSS (+ Vue, Svelte) |
| Components | Vue, Svelte (script + template binding tracking) |

**Breaking Changes:** None

**Status:** Production release — foundation for v0.2.1 Contexly Agent launch

### v0.1.0 (April 2026) — Foundation
- Core extraction engine (Python, JS, TS, Go)
- HTML/CSS frontend-aware extraction
- Impact analysis with risk tiers
- MCP server support

## Documentation Map

- [AGENT_REFERENCE.md](AGENT_REFERENCE.md): complete agent workflow guide
- [MCP_TOOL_REFERENCE.md](MCP_TOOL_REFERENCE.md): quick MCP signatures and examples
- [REPO_STRUCTURE.md](REPO_STRUCTURE.md): repository and module structure
- [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md): documentation navigation
- [MCP_SETUP.md](MCP_SETUP.md): client integration setup
- [IMPACT_ANALYSIS.md](IMPACT_ANALYSIS.md): deep impact analysis workflow and flags
- [tests/fixtures/openclaw/OPENCLAW_TEST_REPORT.md](tests/fixtures/openclaw/OPENCLAW_TEST_REPORT.md): real-world validation report on 400k+ LOC codebase
- [tests/fixtures/openclaw/openclaw-tree.json](tests/fixtures/openclaw/openclaw-tree.json): sample tree artifact demonstrating 95.7% compression on large codebase

## Known Limitations

- React/TSX extraction is much better now, but highly dynamic component patterns can still produce partial skeletons.
- C/C++ function extraction uses tree-sitter; header-only templates and macro-heavy code may produce thin output.
- Vue/Svelte use script-block extraction (no dedicated tree-sitter grammar); deeply nested reactive logic may be partially captured.
- Import connection quality depends on resolver hints (`tsconfig.json` paths, Vite aliases, re-export patterns).
- If output looks stale or unexpectedly thin, use `--rebuild` to bypass cache and regenerate context.

If you hit a bad case, open an issue with a minimal repro project. That helps improve parser coverage quickly.

## Roadmap

### v0.1.x — Stability & Language Coverage (current)
- ✅ Core extraction engine (Python, JS, TS, Go)
- ✅ HTML/CSS frontend-aware extraction with inline script parsing
- ✅ C, C++, Java, Rust, C# via tree-sitter
- ✅ Vue and Svelte component extraction with reactive binding tracking
- ✅ Impact analysis with risk tiers, call paths, and dataflow
- ✅ MCP server for Claude, Copilot, Cursor, Windsurf, Continue

### v0.2.1 — Agentic Coding Layer *(next)*
- **Contexly Agent** — autonomous refactoring agent powered by Contexly logic maps; runs targeted multi-file edits with zero hallucinated hops
- **VS Code Extension** — inline context panel, live impact preview, and one-click query from inside the editor
- Ruby, PHP, Swift, Kotlin language support
- Richer call graph visualization in the HTML tree explorer

### v0.3.0 — Team & Cloud
- **Contexly Cloud** — share, version, and diff context snapshots across teams; no raw code leaves your machine
- GitHub Actions integration — auto-generate context on every PR for faster agent-assisted reviews
- Fine-grained `.contexlyignore` rules and multi-repo workspace support

### v1.0.0 — Platform
- **contexly.dev** — web dashboard for browsing, searching, and sharing public repo context maps
- API for programmatic context retrieval (SaaS-ready)
- Enterprise SSO, audit logs, and private deployment options

**Currently Supported Languages:** Python, JavaScript, TypeScript, Go, C, C++, Java, Rust, C#, HTML, CSS, Vue, Svelte

## Contributing

Please open an issue or pull request with clear reproduction steps and expected behavior.

## License

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Distributed under the MIT License. See [LICENSE](LICENSE).
