# Contexly MCP Tool Quick Reference

Copy-paste signatures and quick examples. For detailed docs, see [AGENT_REFERENCE.md](AGENT_REFERENCE.md).

---

## All 11 Tools (Signatures Only)

```
1. agent_contract(path: str = ".") → dict
2. tree(path: str = ".") → dict
3. index(path: str = ".", level: int = 1) → str
4. query(path: str, query_text: str, depth: int = 1, level: int = 2, top_k: int = 8, debug: bool = false) → dict
5. next_in_progress(path: str, query_text: str, top_k: int = 8) → dict
6. impact(path: str, function_name: str, file_hint: str = "") → dict
7. session_new(path: str = ".", task: str = "General Session") → str
8. session_update(path: str, status: str, text: str) → str
9. session_step(path: str, completed: str, next_in_progress: str) → str
10. session_status(path: str = ".") → dict
11. capabilities() → dict
```

---

## Core Workflow

```
Step 1: agent_contract(path)           Read rules
Step 2: tree(path)                    Load tree
Step 3: query(path, task)             Search context
Step 4: next_in_progress(path, task)  Suggest steps
Step 5: Implement based on context
```

---

## Tool Matrix: When to Use

| When | Call | Key Args |
|------|------|----------|
| **Start** | `agent_contract(path)` | none |
| **First load** | `tree(path)` | none |
| **Quick overview** | `index(path, level=1)` | level: 0-3 |
| **Search context** | `query(path, text, depth=1)` | depth, level, top_k |
| **Get plan** | `next_in_progress(path, text)` | top_k |
| **Check risk** | `impact(path, func, hint)` | function_name |
| **Log request** | `session_new(path, task)` | task |
| **Log done item** | `session_update(path, status, text)` | status: done/in_progress/todo |
| **Log step** | `session_step(path, done, next)` | completed, next_in_progress |
| **Check progress** | `session_status(path)` | none |
| **What can I do?** | `capabilities()` | none |

---

## Parameter Quick Reference

### `query()` Parameters
```
path:       Project root path (str)
query_text: What to search for (str)
depth:      1=direct, 2=+1 hop, 3=+2 hops (int)
level:      1=files, 2=functions, 3=full logic (int)
top_k:      Return top K matches (int, default 8)
debug:      Include scores (bool, default false)
```

### `next_in_progress()` Parameters
```
path:       Project root path (str)
query_text: Task description (str)
top_k:      Number of steps (int, default 8)
```

### `impact()` Parameters
```
path:           Project root path (str)
function_name:  Function to change (str)
file_hint:      Filename if ambiguous (str, optional)
```

### `session_update()` Statuses
```
"done"           → [DONE]
"in_progress"    → [IN_PROGRESS]
"todo"           → [TODO]
```

---

## Common Calls (Copy-Paste)

### Initialize Project
```python
agent_contract("path/to/project")
tree("path/to/project")
```

### Search for Context
```python
query(
  path="path/to/project",
  query_text="what you're looking for",
  depth=1,
  level=2,
  top_k=8
)
```

### Get Next Steps
```python
next_in_progress(
  path="path/to/project",
  query_text="task description",
  top_k=8
)
```

### Check Risk Before Change
```python
impact(
  path="path/to/project",
  function_name="function_to_modify",
  file_hint="optional_filename.py"
)
```

### Log Progress (If User Asked)
```python
session_new("path/to/project", "Task name")
session_step("path/to/project", "What was done", "What's next")
```

---

## Return Types

### `agent_contract()` Returns
```json
{
  "project_path": "str",
  "contract": "str (operating rules)",
  "system_prompt": "str (agent system prompt)",
  "session_guidance": "str (session behavior guidance)"
}
```

### `tree()` Returns
```json
{
  "root_path": "str",
  "file_count": int,
  "total_tokens": int,
  "raw_token_estimate": int,
  "reduction_percent": float,
  "entry_files": ["str"],
  "orphan_files": ["str"],
  "nodes": {
    "filename": {
      "path": "str",
      "language": "str",
      "skeleton_text": "str",
      "token_estimate": int,
      "main_functions": ["str"],
      "connections": ["str"],
      "role": "CORE|UTIL|CONFIG|TEST|DOC",
      "imported_by": ["str"],
      "is_entry_point": bool
    }
  }
}
```

### `query()` Returns
```json
{
  "query": "str",
  "matches": [
    {
      "file": "str",
      "function": "str",
      "score": float,
      "context": "str"
    }
  ],
  "seed_files": ["str"],
  "targeted_context": "str",
  "targeted_context_file": "str"
}
```

### `next_in_progress()` Returns
```json
{
  "suggested_next_in_progress": "str",
  "breakdown": [
    {
      "step": int,
      "file": "str",
      "action": "str"
    }
  ],
  "confidence": float
}
```

### `impact()` Returns
```json
{
  "function": "str",
  "file": "str",
  "calls_made": int,
  "called_by": int,
  "affected_files": ["str"],
  "breaking_changes_risk": "LOW|MEDIUM|HIGH",
  "impact_preview": "str",
  "recommendations": ["str"]
}
```

### `session_status()` Returns
```json
{
  "session_file": "str (path)",
  "content": "str (markdown content)",
  "task": "str",
  "last_updated": "str (timestamp)"
}
```

### `capabilities()` Returns
```json
{
  "tools": [
    {
      "name": "str",
      "description": "str"
    }
  ],
  "recommended_flow": ["str"],
  "session_behavior": "str"
}
```

---

## Error Handling

### If tool returns error:

**Tool failed (no tree.json)**
```
Solution: Call tree(path) first to build tree.json
```

**Query returned no matches**
```
Solution: 
- Broaden query_text (try shorter, more general terms)
- Increase top_k (default 8, try 16)
- Increase depth (default 1, try 2-3)
```

**Impact shows HIGH risk**
```
Solution:
- Warn user about affected files
- Ask permission to proceed
- Make minimal changes
- Add default parameters for backward compatibility
```

**Session operations fail**
```
Solution: Ensure session_new() was called first
```

---

## Output Directory

All tools write to:
```
<project>/.contexly/
```

Files created:
- `tree.json` — main skeleton tree
- `targeted_[slug].txt` — query-specific context
- `session.md` — progress log (if session_new called)
- `tree-data.js` — offline browser bundle
- `design-index.html` — interactive tree viewer

---

## Key Design Principles

1. **No Auto-Session**: tools don't create .contexly/session.md automatically
2. **Chat-First**: all context stays in chat by default
3. **Opt-In Persistence**: session_* tools only called if user asks
4. **Always Start with agent_contract()**: read rules before proceeding
5. **Use right tool**: query for context, next_in_progress for steps, impact for risks

---

## Agents: Quick Checklist

- [ ] Call `agent_contract(path)` at start
- [ ] Call `tree(path)` on first load
- [ ] Never auto-create session (wait for user request)
- [ ] Use `query()` before coding
- [ ] Use `impact()` before signature changes
- [ ] Use `next_in_progress()` between multi-step tasks
- [ ] Show results to user in chat
- [ ] Ask permission before implementing
- [ ] Respect the project's agent_contract rules
- [ ] Keep session summaries ≤120 chars (auto-truncated)

---

**For more details, read [AGENT_REFERENCE.md](AGENT_REFERENCE.md) or [REPO_STRUCTURE.md](REPO_STRUCTURE.md)**
