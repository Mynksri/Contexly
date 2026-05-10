# Contexly Repository Structure Guide

Complete folder organization and file purposes for AI agents.

---

## 📁 Root Directory Layout

```
contexly/
├── src/contexly/              # Main package code (src-layout)
├── tests/                     # Pytest test suite
├── contexly-outputs/          # Generated artifact directory
├── agent-presets/             # Agent system/task prompts
├── pyproject.toml             # Package metadata and dependencies
├── pytest.ini                 # Pytest configuration
├── MCP_SETUP.md               # MCP client setup guide
├── mcp.example.json           # Example MCP server block
├── README.md                  # Project overview
├── REPO_STRUCTURE.md          # This file
└── .gitignore                 # Git exclusions
```

---

## 📦 src/contexly/ — Core Package

Main implementation of Contexly logic skeletons and tree analysis.

### Tree Building
- **`core/tree_builder.py`**
  - `TreeBuilder` class: orchestrates tree construction
  - Methods: `build()` (recursively analyze directory), `_extract_functions()`, `_score_roles()`
  - Outputs: tree.json with skeleton text, token estimates, call graphs
  - Called by: MCP `tree()` tool

- **`core/skeleton_extractor.py`**
  - `SkeletonExtractor` class: generates logic skeletons from source code
  - Language-specific parsers using tree-sitter (Python, JS, TS)
  - Returns: intent/decision/calls/returns structure (NOT full source)
  - ~95% token reduction while preserving logic flow
  - Called by: TreeBuilder

### Context Management
- **`core/context_manager.py`**
  - `ContextManager` class: manages tree navigation and context retrieval
  - Methods: `get_context()`, `get_function_context()`, `find_connections()`
  - Handles file/function lookups in tree.json
  - Called by: MCP query/impact tools

### Querying & Analysis
- **`core/query_engine.py`**
  - `QueryEngine` class: semantic search over skeleton trees
  - Methods: `search()` (find matching contexts), `rank_results()` (score by relevance)
  - Takes: query_text, depth, level, top_k parameters
  - Returns: ranked matches with scores
  - Called by: MCP `query()` tool

- **`core/impact_analyzer.py`**
  - `ImpactAnalyzer` class: predict change impact
  - Methods: `analyze_impact()` (given function, find affected code)
  - Returns: impact_preview (at-risk files, call chains, breaking changes)
  - Called by: MCP `impact()` tool

### Session Tracking (Optional)
- **`agent/session.py`**
  - `Session` class: manages .contexly/session.md for persistent tracking
  - Methods:
    - `create(task)` → initializes session.md with task header
    - `update(status, summary)` → adds DONE/IN_PROGRESS/TODO entries
    - `complete_step(done_text, next_text)` → logs step + sets next
    - `build_context(tree, query)` → generates context payload
  - ASCII Status Format: `[DONE]`, `[IN_PROGRESS]`, `[TODO]`
  - Auto-truncates summaries to ≤120 chars (rolling window)
  - Key Design: only writes to .contexly/session.md on explicit user request
  - Called by: MCP session_* tools

### MCP Server
- **`mcp_server.py`**
  - FastMCP server exposing 11 Contexly tools over stdio
  - Entry point: `main()` function (called by contexly-mcp CLI)
  - Tools exposed:
    1. `tree(path=".")` — build skeleton tree
    2. `index(path, level)` — lightweight text index
    3. `query(path, query_text, depth, level, top_k, debug)` — search
    4. `next_in_progress(path, query_text, top_k)` — suggest next steps
    5. `impact(path, function_name, file_hint)` — change impact preview
    6. `session_new(path, task)` — start session
    7. `session_update(path, status, text)` — log progress
    8. `session_step(path, completed, next_in_progress)` — compact step log
    9. `session_status(path)` — read session state
    10. `agent_contract(path)` — read project rules
    11. `capabilities()` — list tools and workflow
  - Transport: stdio (MCP Protocol)
  - Dependencies: contextly.core, contextly.agent

### CLI & Utilities
- **`cli/main.py`**
  - Entry point for `contexly` CLI command
  - Commands:
    - `contexly tree /path/to/project` — build tree
    - `contexly query /path "what to search"` — search codebase
    - `contexly index /path` — show file index
    - `contexly impact /path function_name` — predict impact
  - Uses: TreeBuilder, QueryEngine, ImpactAnalyzer

- **`__init__.py`**
  - Package public API exports
  - Exports: TreeBuilder, SkeletonExtractor, ContextManager, QueryEngine, ImpactAnalyzer, Session, TodoEngine
  - Clean removal of hallucination_guard after deprecation

### Support Files
- **`language_config.py`**
  - Language-specific configuration
  - Defines parsers (tree-sitter), syntax rules, import patterns per language
  - Supports: Python, JavaScript, TypeScript, more can be added

- **`utils/`**
  - `file_utils.py` — file I/O, path normalization, git ignore parsing
  - `token_counter.py` — estimate tokens for skeleton vs. raw source
  - `logging_config.py` — structured logging for MCP server

---

## 🧪 tests/ — Test Suite

pytest-based test suite (56 passing tests, Python 3.10+).

### Test Files by Module

- **`test_tree_builder.py`**
  - Tests: tree construction, skeleton generation, token counting, role assignment
  - Example: `test_build_tree_basic()`, `test_skeleton_extraction()`

- **`test_query_engine.py`**
  - Tests: semantic search, ranking, depth traversal, parameter validation
  - Example: `test_query_returns_ranked_matches()`, `test_depth_2_includes_indirect_calls()`

- **`test_context_manager.py`**
  - Tests: tree navigation, function lookups, connection finding
  - Example: `test_get_function_context_from_tree()`

- **`test_impact_analyzer.py`**
  - Tests: change impact prediction, affected file detection, breaking change warnings
  - Example: `test_analyze_impact_detects_call_sites()`

- **`test_session.py`**
  - Tests: session creation, status tracking, step logging, truncation
  - Example: `test_create_and_update_session()`, `test_complete_step_uses_short_rolling_summaries()`

- **`test_mcp_integration.py`**
  - Integration: MCP tool invocation, response schemas, error handling
  - Example: `test_tree_tool_generates_valid_json()`, `test_query_tool_with_real_tree()`

### Configuration
- **`pytest.ini`**
  ```ini
  [pytest]
  pythonpath = src
  testpaths = tests
  ```
  - Sets PYTHONPATH to src/ (finds contexly package)
  - Runs tests from tests/ directory
  - Run with: `pytest tests -q` or `pytest -v`

---

## 📤 contexly-outputs/ — Generated Artifacts

Directory where all MCP tools write outputs per project.

### Structure
```
contexly-outputs/
├── [project-name]/
│   ├── tree.json                 # Main codebase skeleton tree
│   ├── targeted_[query-slug].txt # Query-specific context snippets
│   ├── session.md                # Optional session tracking (if created)
│   ├── tree-data.js              # Offline bundle for browser UI
│   └── design-index.html         # Interactive tree visualization
│
└── hallucination-archive/        # Deprecated feature archive
    ├── hallucination_guard.py    # Original implementation
    ├── test_hallucination_guard.py
    └── README.md                 # Archival note
```

### File Descriptions

- **`tree.json`** (Main Output)
  ```json
  {
    "root_path": "/path/to/project",
    "file_count": 150,
    "total_tokens": 8500,
    "raw_token_estimate": 450000,
    "reduction_percent": 98.1,
    "entry_files": ["main.py"],
    "orphan_files": [],
    "nodes": {
      "module.py": {
        "path": "module.py",
        "language": "python",
        "skeleton_text": "FILE:module.py...",
        "token_estimate": 85,
        "main_functions": ["func_name[line_start-line_end]"],
        "connections": ["other.py"],
        "role": "CORE",
        "imported_by": [],
        "is_entry_point": true
      }
    }
  }
  ```
  - Built by: `tree()` MCP tool
  - Size: typically 50KB-200KB for 100-500 file projects
  - Persists: stays on disk for repeated queries

- **`targeted_[query-slug].txt`** (Query Outputs)
  - Text context for specific searches
  - Examples:
    - `targeted_fetch_user_balance.txt` — all functions related to "fetch user balance"
    - `targeted_database_connection.txt` — database-related context
  - Built by: `query()` MCP tool
  - Retention: kept for reference, can be deleted safely

- **`session.md`** (Optional Session Log)
  - Format (ASCII status markers):
    ```
    # Task: Implement withdraw feature
    
    [DONE] Database schema changes
    [IN_PROGRESS] Authentication middleware
    [TODO] Withdrawal transaction logic
    
    Last updated: 2024-01-20 14:30:00
    ```
  - Built by: `session_new()`, `session_update()`, `session_step()` tools
  - Key: only created when user explicitly requests via MCP
  - Auto-truncates step summaries to ≤120 characters

- **`tree-data.js`** (Offline Browser Bundle)
  - JavaScript file with embedded tree.json
  - Format: `window.__TREE_DATA__ = {...full tree.json...}`
  - Used by: design-index.html for offline visualization
  - Generated: via PowerShell script or manual `tree.json → tree-data.js` conversion
  - Size: ~10x tree.json size due to browser escaping

- **`design-index.html`** (Interactive Tree UI)
  - Standalone HTML5 tree visualizer
  - Features:
    - Left sidebar: file list with search, "Make Tree Of This Part" button
    - Right canvas: full tree or connected-part filtered view
    - Mode display: "FULL TREE VIEW" or "CONNECTED PART VIEW: filename"
    - Hierarchy: Files (trunk) → Functions (branch) → Logic (leaf)
    - Styling: professional grey/white palette, glassy panels
  - Data load priority:
    1. Try load embedded tree-data.js (offline mode)
    2. Fall back to fetch("tree.json") (server mode)
  - Usage: Open in browser (works with file:// URLs thanks to tree-data.js)

---

## 🤖 agent-presets/ — Agent Integration Files

System prompts and task templates for AI agent clients.

### Configuration Files

- **`system_prompt_contexly.txt`**
  - System prompt for AI agents using Contexly MCP
  - Content:
    - Tool usage rules (when to call tree, query, impact)
    - Mandatory workflow (5-step recommended flow)
    - Session behavior (optional logging only)
    - Code change guidelines (minimize edits, prefer targeted fixes)
  - Used by: Claude Code, VS Code Copilot, Cursor, Windsurf, Continue
  - Key Rule: "session.md only updated on explicit user request, not automatic"

- **`task_prompt_template.txt`**
  - Template for task execution with Contexly context
  - Includes:
    - Query execution format
    - next_in_progress breakdown interpretation
    - Implementation guidelines
    - Impact analysis process
    - Optional session logging
  - Usage: Agents prepend this to task descriptions

---

## ⚙️ Configuration Files (Root)

### Package & Build

**`pyproject.toml`**
```toml
[project]
name = "contexly-engine"
version = "0.1.0"
requires-python = ">=3.10"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project.scripts]
contexly = "contexly.cli.main:main"
contexly-mcp = "contexly.mcp_server:main"

[project.dependencies]
tree-sitter>=0.21.0
tree-sitter-python>=0.21.0
tree-sitter-javascript>=0.21.0
tree-sitter-typescript>=0.21.0
watchdog>=3.0.0
click>=8.0.0
mcp>=1.0.0
```
- Hatchling: modern build backend
- Two CLI entrypoints:
  - `contexly` — CLI tool (tree, query, index, impact commands)
  - `contexly-mcp` — MCP server (expose tools to AI agents)
- Python >=3.10 required for type hints
- Optional dev dependencies: pytest, black, ruff

**`pytest.ini`**
```ini
[pytest]
pythonpath = src
testpaths = tests
```
- Enables src-layout (pythonpath = src)
- Discovers tests in tests/ directory
- Run: `pytest tests -q`

### MCP & Documentation

**`MCP_SETUP.md`**
- MCP server configuration for all agents:
  - Claude Code, VS Code Copilot, Cursor, Windsurf, Continue, OpenCode, OpenClaw, Hermes, Antigravity
- Universal server block (copy-paste to MCP config):
  ```json
  {
    "mcpServers": {
      "contexly": {
        "command": "python",
        "args": ["contexly_mcp.py"],
        "cwd": "/path/to/contexly"
      }
    }
  }
  ```
- Per-client quick mapping (which config file to edit)

**`mcp.example.json`**
- Ready-to-use MCP server configuration
- Copy to client MCP config with path adjustments

**`README.md`**
- Project overview, problem/solution, quick start
- Install: `pip install -e .`
- Usage: `contexly tree /path`, `contexly query /path "what to find"`
- Points to: MCP_SETUP.md for agent setup

**`REPO_STRUCTURE.md`** (This file)
- Complete folder and file reference for AI agents
- Explains purpose of each module, tool, and config file
- Shows data structures (tree.json format, session.md format)
- Documents MCP tools and typical agent workflows

### Version Control

**`.gitignore`**
```
__pycache__/
*.pyc
*.egg-info/
dist/
build/
.pytest_cache/
.coverage
.contexly/
contexly-outputs/
```
- Excludes Python build artifacts, test caches, session files, outputs

---

## 🔄 Data Flow Diagram

```
┌─────────────────────┐
│  Agent (MCP Client) │
└──────────┬──────────┘
           │
           ├─ tree(path) ────────────┐
           │                         ↓
           ├─ query(path, text)──SkeletonExtractor
           │                    TreeBuilder
           ├─ next_in_progress──ContextManager
           │                    QueryEngine
           ├─ impact(path, fn)──ImpactAnalyzer
           │                         ↓
           ├─ session_new ────────Session
           ├─ session_update     (optional)
           ├─ session_step         ↓
           └─ session_status    .contexly/
                                session.md
                                   
           All Tools Output ──→ contexly-outputs/[project]/
                                ├── tree.json
                                ├── targeted_*.txt
                                ├── session.md
                                ├── tree-data.js
                                └── design-index.html
```

---

## ✅ Key Design Principles

1. **Src-Layout Package**: 
   - Code in `src/contexly/` keeps package clean
   - Tests in `tests/` separate from source
   - Easy installation and distribution

2. **Skeleton-Based Reduction**:
   - 95%+ token reduction (1M → 35K lines)
   - Preserves logic flow (intent/decision/calls/returns)
   - Enables AI agents to understand large codebases

3. **MCP-First Exposure**:
   - All tools exposed via MCP (stdio protocol)
   - Works with any MCP-compatible agent
   - No forced persistence (session optional)

4. **Optional Session Tracking**:
   - Sessions only created on user request
   - Default behavior: all context stays in chat
   - When user asks → `session_new()` + `session_step()` available

5. **Offline-Ready Artifacts**:
   - tree-data.js bundles data for browser viewing
   - design-index.html works from file:// URLs
   - No server required for visualization

---

## 📚 For AI Agents: Quick Reference

### When to Call Each Tool

| Tool | Situation | Called By |
|------|-----------|-----------|
| `tree()` | Project loaded first time or context stale | Agent initialization |
| `index()` | Need quick text overview of repo structure | Planning phase |
| `query()` | Searching for specific context (e.g., "fetch balance") | Before coding |
| `next_in_progress()` | Get suggested next files/steps (chat-ready) | Between steps |
| `impact()` | Before changing function signature or API | Risk assessment |
| `agent_contract()` | Start: learn what rules apply to this project | Agent initialization |
| `session_new()` | User asks to log progress explicitly | On user request only |
| `session_update()` | User wants persistent step logging | On user request only |
| `session_step()` | User wants to log completed + next in one call | On user request only |
| `session_status()` | Check current session state | On user request |
| `capabilities()` | Understand what tools are available | Discovery |

### Typical 5-Step Agent Workflow

1. **Initialize**: Call `agent_contract(path)` to read project rules
2. **Load**: Call `tree(path)` to ensure fresh tree data
3. **Search**: Call `query(path, "task")` to gather context
4. **Plan**: Call `next_in_progress(path, "task")` to get suggested next files
5. **Implement**: Code based on context, call `impact()` before signature changes
6. **(Optional)**: Call `session_step()` if user asks for persistent progress tracking

---

Generated for Contexly v0.1.0 — MCP-enabled codebase context engine.
