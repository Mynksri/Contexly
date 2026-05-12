# Contexly Agent Reference Guide

Complete guide for AI agents integrating Contexly MCP into their workflow.

**Last Updated**: 2024  
**Package Version**: 0.1.0  
**Target Audience**: AI agents (Claude, Copilot, Cursor, Continue, etc.)

---

## 📖 Quick Start: The 5-Step Agent Workflow

Every agent workflow with Contexly follows this pattern:

```
Step 1: Read Rules  → agent_contract(path)
    ↓
Step 2: Load Tree   → tree(path)
    ↓
Step 3: Search      → query(path, user_task_description)
    ↓
Step 4: Plan        → next_in_progress(path, user_task_description)
    ↓
Step 5: Code        → (implement based on context)
```

**Key Principle**: Steps 1-4 are *chat-first*. Session.md is **NOT created automatically**. Only when user explicitly asks "log this" do you call session_* tools.

---

## 🛠️ The 11 Contexly Tools

### Tool 1: `agent_contract(path)`

**Purpose**: Read operating rules for this project

**Signature**:
```python
agent_contract(path: str = ".") → dict
```

**Returns**:
```json
{
  "project_path": "/path/to/project",
  "contract": "string describing rules and constraints",
  "system_prompt": "recommended system prompt for agents",
  "session_guidance": "when/how to use session tracking"
}
```

**When to Use**:
- ✅ ALWAYS call this first, before any other tool
- ✅ At project initialization
- ✅ Tells you what rules to follow for THIS project

**Example**:
```
Agent to User: "Let me understand what rules apply to your project first..."
→ Call: agent_contract("/path/to/my-project")
← Returns: contract rules that say "minimize edits", "preserve test structure", etc.
Agent: "Got it. I'll be careful with tests and prefer surgical changes."
```

---

### Tool 2: `tree(path)`

**Purpose**: Build a codebase skeleton tree (95% token reduction)

**Signature**:
```python
tree(path: str = ".") → dict
```

**Returns**:
```json
{
  "root_path": "/path/to/project",
  "file_count": 150,
  "total_tokens": 8500,
  "raw_token_estimate": 450000,
  "reduction_percent": 98.1,
  "entry_files": ["main.py", "run.py"],
  "orphan_files": [],
  "nodes": {
    "core/balance.py": {
      "path": "core/balance.py",
      "language": "python",
      "skeleton_text": "FILE:core/balance.py [python]\n\nFUNC:fetch_balance(user_id)\n  intent: Retrieve current balance for user\n  calls: [db.query(), cache.get()]\n  returns: Balance dict or error\n\nFUNC:update_balance(user_id, amount)\n  intent: Update balance after transaction\n  calls: [db.update(), notify_service()]\n  returns: Success boolean",
      "token_estimate": 85,
      "main_functions": ["fetch_balance[24-50]", "update_balance[52-100]"],
      "connections": ["db.py", "cache.py", "notify_service.py"],
      "role": "CORE",
      "imported_by": ["main.py"],
      "is_entry_point": false
    }
  }
}
```

**Key Fields**:
- `skeleton_text`: Logic summary (NOT full source) with intent, calls, returns
- `token_estimate`: How many tokens this file uses
- `reduction_percent`: How much you saved (usually 95%+)
- `role`: One of CORE, UTIL, CONFIG, TEST, DOC

**When to Use**:
- ✅ At project load (step 2 of workflow)
- ✅ After major file changes
- ✅ When context feels stale or tree.json is missing
- ✅ Takes ~2-5 seconds for typical projects

**Cost**:
- Time: proportional to project size (100 files ≈ 2-3 sec)
- Output: 50KB-200KB JSON saved to `contexly-outputs/[project]/tree.json`

**Example**:
```
Agent: "I need to understand this backend service structure."
→ Call: tree("/path/to/backend-service")
← Returns: 42 files, 18500 tokens, 95.2% reduction
   entry_files: ["main.py", "app.py"]
   nodes: user_service.py (CORE), db_handler.py (CORE), config.py (UTIL)
Agent: "Got the tree. 42 files, down from ~650K tokens to 18.5K. Entry points are main.py and app.py, core logic in user_service and db_handler."
```

---

### Tool 3: `index(path, level=1)`

**Purpose**: Lightweight text index (not JSON tree—quick overview)

**Signature**:
```python
index(path: str = ".", level: int = 1) → str
```

**Parameters**:
- `level=0`: High-level repo map
- `level=1`: All files with roles
- `level=2`: Files + main functions
- `level=3`: Files + all functions (verbose)

**Returns**: Plain text (Markdown format)
```
# Repository Index (level=1)

## Entry Points (3 files)
- main.py
- run.py
- bootstrap.py

## Core Modules (7 files)
- balance_manager.py (CORE)
- claim_manager.py (CORE)
- db.py (CORE)
- ...

## Utilities (4 files)
- config.py (UTIL)
- logging.py (UTIL)
- ...
```

**When to Use**:
- ✅ Need quick text summary (before reading full tree.json)
- ✅ Sharing structure with user
- ✅ Finding entry points
- ✅ Understanding file roles

**Example**:
```
User: "What files are in this project?"
→ Call: index("/path/to/my-project", level=1)
← Returns: text listing all 50 files by role
Agent: Pastes into chat so user can see structure
```

---

### Tool 4: `query(path, query_text, depth=1, level=2, top_k=8, debug=false)`

**Purpose**: Keyword-ranked search with dependency expansion for context relevant to a task

**Signature**:
```python
query(
  path: str,
  query_text: str,           # "what to search for"
  depth: int = 1,            # how many hops (1-3)
  level: int = 2,            # detail (1=files, 2=functions, 3=logic)
  top_k: int = 8,            # return top K matches
  debug: bool = false        # include scores
) → dict
```

**Returns**:
```json
{
  "query": "fetch user balance",
  "matches": [
    {
      "file": "core/balance.py",
      "function": "fetch_balance",
      "score": 0.92,
      "context": "FUNC:fetch_balance(user_id) [line 24-50]\n  intent: Retrieve balance\n  calls: [db.query(), cache.get()]"
    },
    {
      "file": "db.py",
      "function": "query",
      "score": 0.65,
      "context": "FUNC:query(sql, params) [line 100-130]\n  intent: Execute database query"
    }
  ],
  "seed_files": ["core/balance.py"],
  "targeted_context": "Full context for top matches",
  "targeted_context_file": "contexly-outputs/backend-service/targeted_fetch_user_balance.txt"
}
```

**Parameters Explained**:
- `depth=1`: Direct matches only (faster)
- `depth=2`: Direct + one hop away (functions that call matched functions)
- `depth=3`: Direct + two hops away (broader context, slower)
- `level=1`: Just file names and paths
- `level=2`: Function names and signatures
- `level=3`: Full skeleton logic (intent, calls, returns)
- `top_k=8`: Return top 8 matches (increase for broader context)
- `debug=false`: Hide scoring details (set true for troubleshooting)

**When to Use**:
- ✅ User asks you to implement something: "add withdrawal feature"
- ✅ Need context before coding
- ✅ Step 3 of core workflow
- ✅ Takes ~1-2 seconds

**Example Scenarios**:

**Scenario 1: New Feature Implementation**
```
User: "I need to add email notifications when balance changes."
→ Call: query(
    path=r"C:\my-project",
    query_text="balance change notification",
    depth=2,
    level=2,
    top_k=8
)
← Returns: Files related to balance updates, notification system, email service
Agent: "I found where balance updates happen, the notification system, and email service. Let me show you the plan..."
```

**Scenario 2: Bug Investigation**
```
User: "There's a bug with session expiration."
→ Call: query(
    path=r"C:\my-project",
    query_text="session timeout authentication logout",
    depth=1,
    level=3
)
← Returns: All authentication and session functions with full logic
Agent: "Found the issue in the session handler. Here's what's wrong..."
```

**How It Works - Scoring Algorithm**:

The search uses **keyword-ranked matching** (not vector embeddings). Here's how results are scored:

1. **Filename match** (+4.0 points) — Query tokens in file/folder name
2. **Function name match** (+3.0 points) — Query tokens in function names
3. **Skeleton text match** (+0.8 per occurrence) — Query tokens in logic skeleton
4. **Tag match** (+2.0 points) — Query tokens in #tags (#api-call, #state-heavy, etc)
5. **Role bonus** (+1.0) — Files marked ENTRY or CORE get priority
6. **LEGACY role penalty** (×0.5) — Deprecated code deprioritized

**Confidence levels based on final score:**
- HIGH: score ≥ 12
- MED: score ≥ 5
- LOW: score < 5

**Stopwords filtered**: "the", "is", "and", "or", etc. are ignored

**Token processing**: camelCase and snake_case automatically split:
- "fetchUserBalance" → ["fetch", "user", "balance"]
- "rate_limiting" → ["rate", "limiting"]

This approach is simple, deterministic, and fast (~1-2 seconds on large codebases).

**Important**: `query()` does NOT write to session.md. Results stay in chat.

---

### Tool 5: `next_in_progress(path, query_text, top_k=8)`

**Purpose**: Get chat-ready execution plan WITHOUT persisting to session.md

**Signature**:
```python
next_in_progress(
  path: str,
  query_text: str,
  top_k: int = 8
) → dict
```

**Returns**:
```json
{
  "suggested_next_in_progress": "Implement balance update → notify service → persist to DB",
  "breakdown": [
    {
      "step": 1,
      "file": "core/balance.py",
      "action": "Update balance_manager.update_balance() to call notify_service"
    },
    {
      "step": 2,
      "file": "services/notification.py",
      "action": "Ensure notify_service() logs the notification"
    },
    {
      "step": 3,
      "file": "db.py",
      "action": "Verify DB write after notification"
    }
  ],
  "confidence": 0.89
}
```

**When to Use**:
- ✅ Step 4 of core workflow (planning before coding)
- ✅ Need structured next-step breakdown (not just context)
- ✅ Show user the plan before implementing
- ✅ Between multi-step tasks: "Here's what's next..."

**Key Difference from `query()`**:
- `query()` returns context (skeleton text, function details)
- `next_in_progress()` returns a breakdown (which files to touch, in what order)
- Neither writes to session.md

**Example**:
```
Agent: "Let me suggest the next steps for you."
→ Call: next_in_progress(
    path=r"C:\my-project",
    query_text="implement withdrawal transaction"
)
← Returns breakdown: 
  1. Update TransactionManager.create_withdrawal
  2. Add balance validation in balance_manager
  3. Log to audit trail
  4. Send confirmation email
Agent to User: "Here's my suggested plan:
  Step 1: Update TransactionManager.create_withdrawal
  Step 2: Add balance validation
  Step 3: Log to audit trail
  Step 4: Send confirmation email
  Should I proceed?"
```

---

### Tool 6: `impact(path, function_name, file_hint="")`

**Purpose**: Predict what breaks if you modify a function

**Signature**:
```python
impact(
  path: str,
  function_name: str,      # name of function you want to change
  file_hint: str = ""      # optional filename hint if ambiguous
) → dict
```

**Returns**:
```json
{
  "function": "withdraw",
  "file": "core/transactions.py",
  "calls_made": 4,
  "called_by": 7,
  "affected_files": [
    "main.py",
    "services/notification.py",
    "db.py"
  ],
  "breaking_changes_risk": "HIGH",
  "impact_preview": "7 files call withdraw(). Changing signature would break: main.py:withdraw(amount) → needs retry_count param",
  "recommendations": [
    "Add retry_count as optional parameter with default",
    "Update 3 call sites in main.py and handlers",
    "Test notification service integration"
  ]
}
```

**When to Use**:
- ✅ BEFORE changing function signature (add param, remove param, change return type)
- ✅ BEFORE changing function behavior in breaking ways
- ✅ Check for risky changes before you make them
- ✅ Answer user: "Is it safe to rename this function?"

**Risk Levels**:
- `LOW`: Function called by ≤2 files, no breaking risks
- `MEDIUM`: Called by 3-5 files, some affected areas
- `HIGH`: Called by 6+ files, or signature change needed

**Example**:
```
Agent to User: "I'm about to change the withdraw() signature. Let me check impact first..."
→ Call: impact(
    path=r"C:\my-project",
    function_name="withdraw"
)
← Returns: HIGH risk, 7 files call it, signature change needed
Agent: "Heads up: This is a HIGH-risk change. 7 files call withdraw().
Here's what I'll do:
1. Add new optional parameter with default value (backward compatible)
2. Update 3 call sites
3. Test all integration points
Is this OK?"
```

---

### Tool 7: `session_new(path, task)`

**Purpose**: Create .contexly/session.md for persistent task tracking

**Signature**:
```python
session_new(
  path: str = ".",
  task: str = "General Session"
) → str
```

**Returns**: Path to created session.md file

**When to Use**:
- ✅ ONLY when user explicitly asks to log progress
- ✅ Example: "Log what we're doing" or "Start a session for this task"
- ❌ NOT automatically (agent should NOT call this without user request)

**Creates File**:
```
.contexly/session.md
─────────────────
# Task: Implement withdrawal feature

## Progress
[TODO] Database schema migration
[TODO] Backend withdrawal logic
[TODO] Frontend UI
[TODO] Testing

Last updated: 2024-01-20 10:00:00
```

**Example**:
```
User: "Log this work for me."
Agent: "Got it, starting a session."
→ Call: session_new(r"C:\my-project", "Add withdrawal feature")
← Returns: ".contexly/session.md created"
Agent: "Session started. I'll update it as we go."
```

---

### Tool 8: `session_update(path, status, text)`

**Purpose**: Add entry to session.md (one item)

**Signature**:
```python
session_update(
  path: str,
  status: str,            # "done", "in_progress", "todo"
  text: str               # summary ≤120 chars
) → str
```

**Returns**: Path to session.md

**Status Values**:
- `"done"` → `[DONE]`
- `"in_progress"` → `[IN_PROGRESS]`
- `"todo"` → `[TODO]`

**Text Truncation**: Automatically keeps ≤120 characters (rolling window)

**Example**:
```
→ Call: session_update(
    r"C:\my-project",
    "done",
    "Implemented balance withdrawal logic in core/transactions.py"
)
← Returns: ".contexly/session.md updated"
```

Session file now has:
```
[DONE] Implemented balance withdrawal logic
[IN_PROGRESS] Testing transaction handling
```

---

### Tool 9: `session_step(path, completed, next_in_progress)`

**Purpose**: Compact: log DONE item + set IN_PROGRESS in one call

**Signature**:
```python
session_step(
  path: str,
  completed: str,          # what just finished
  next_in_progress: str    # what's next (or "" for none)
) → str
```

**Returns**: Path to session.md

**When to Use**:
- ✅ Cleaner than calling session_update twice
- ✅ Natural workflow: step done → move to next

**Example**:
```
→ Call: session_step(
    r"C:\my-project",
    "Database migration completed and tested",
    "Backend withdrawal logic implementation"
)
← Returns: ".contexly/session.md updated"
```

Session file now shows:
```
[DONE] Database migration completed and tested
[IN_PROGRESS] Backend withdrawal logic implementation
[TODO] Frontend UI
```

---

### Tool 10: `session_status(path)`

**Purpose**: Read current session.md content

**Signature**:
```python
session_status(path: str = ".") → dict
```

**Returns**:
```json
{
  "session_file": ".contexly/session.md",
  "content": "[DONE] Schema migration\n[IN_PROGRESS] Backend logic\n[TODO] Frontend",
  "task": "Implement withdrawal feature",
  "last_updated": "2024-01-20 10:15:00"
}
```

**When to Use**:
- ✅ Check current progress mid-task
- ✅ Resume after context loss
- ✅ Show user current status

**Example**:
```
Agent: "Let me check where we were..."
→ Call: session_status(r"C:\my-project")
← Returns: Current session showing what's done/in progress/todo
Agent: "OK, we finished the schema, now working on backend logic."
```

---

### Tool 11: `capabilities()`

**Purpose**: List all tools and recommended workflow

**Signature**:
```python
capabilities() → dict
```

**Returns**:
```json
{
  "tools": [
    {
      "name": "agent_contract",
      "description": "Read project rules"
    },
    {
      "name": "tree",
      "description": "Build codebase skeleton tree"
    },
    ...
  ],
  "recommended_flow": [
    "1. agent_contract(path)",
    "2. tree(path)",
    "3. query(path, user_task)",
    "4. next_in_progress(path, user_task)",
    "5. Implement based on context"
  ],
  "session_behavior": "Optional—only use if user asks"
}
```

**When to Use**:
- ✅ Discovery: "What can I do?"
- ✅ Sanity check: "Is this tool available?"

---

## 🎯 Workflow Examples

### Example 1: Simple Bug Fix

**User**: "Fix the bug where balance doesn't update after withdrawal."

**Your Workflow**:

1. **Initialize**
   ```
   Call: agent_contract(r"C:\project")
   Read: operating rules
   ```

2. **Load Tree**
   ```
   Call: tree(r"C:\project")
   Inspect: entry_files, role assignments
   ```

3. **Search for Bug Context**
   ```
   Call: query(
     path=r"C:\project",
     query_text="balance update withdrawal",
     depth=2,
     level=2
   )
   Get: where balance is updated, withdrawal logic
   ```

4. **Understand Impact**
   ```
   Call: impact(r"C:\project", "update_balance")
   Check: how many places call update_balance
   ```

5. **Implement Fix**
   - Show user the bug location
   - Explain the fix
   - Ask permission
   - Fix it

6. **No Session (unless asked)**
   - If user didn't ask → don't create session
   - Context stays in chat

---

### Example 2: Multi-Step Feature with Progress Logging

**User**: "Add withdrawal feature. Log progress as we go."

**Your Workflow**:

1. **Initialize + Load Tree** (same as Example 1)

2. **Search for Context**
   ```
   Call: query(
     path=r"C:\project",
     query_text="transaction handling balance update notification",
     depth=2,
     level=3
   )
   ```

3. **Get Execution Plan**
   ```
   Call: next_in_progress(r"C:\project", "add withdrawal feature")
   Get: suggested steps
   ```

4. **Show Plan to User**
   ```
   Agent: "Here's what I'll do:
     1. Add withdrawal schema to database
     2. Implement withdraw() function
     3. Add notifications
     4. Add UI button
   Logging progress as we go. OK?"
   ```

5. **Start Session (USER ASKED)**
   ```
   Call: session_new(r"C:\project", "Add withdrawal feature")
   ```

6. **Step 1: Database Schema**
   ```
   Call: query(r"C:\project", "database schema migrations")
   → Implement schema changes
   Call: session_step(
     r"C:\project",
     "Added withdrawal schema",
     "Implement withdraw() function"
   )
   ```

7. **Step 2: Backend Logic**
   ```
   Call: query(r"C:\project", "transaction processing")
   → Implement withdraw() in TransactionManager
   Call: session_step(
     r"C:\project",
     "Implemented withdraw() in TransactionManager",
     "Add notification service"
   )
   ```

8. **Step 3: Notifications**
   ```
   Call: query(r"C:\project", "notification system email alerts")
   → Integrate notifications
   Call: session_step(
     r"C:\project",
     "Integrated withdrawal notifications",
     "Test end-to-end"
   )
   ```

9. **Final Check**
   ```
   Call: session_status(r"C:\project")
   Show user complete progress log
   ```

---

### Example 3: Risky API Change

**User**: "I need to add a retry parameter to the withdraw function."

**Your Workflow**:

1. **Initialize** (agent_contract + tree)

2. **Assess Impact FIRST**
   ```
   Call: impact(r"C:\project", "withdraw", "core/transactions.py")
   Get: HIGH risk, 12 files call withdraw
   ```

3. **Show Risk Analysis**
   ```
   Agent: "⚠️ HIGH-RISK CHANGE
   Current: withdraw(user_id, amount)
   Proposed: withdraw(user_id, amount, retry_count=3)
   
   Impact:
   - 12 files call this function
   - 5 call sites need updates (add default param)
   - 2 tests will fail (assert exact params)
   
   My recommendation:
   1. Add retry_count with default=3 (backward compatible)
   2. Update 5 call sites (explicit params)
   3. Fix 2 failing tests
   4. Deploy carefully
   
   Proceed?"
   ```

4. **Implement with Extra Care**
   - Make minimal changes
   - Preserve backward compatibility
   - Test thoroughly

5. **Document Changes**
   - Explain each change
   - Show before/after

---

## 🚀 Best Practices for Agents

### 1. Always Start with `agent_contract()`
```python
# ✅ GOOD
def start_task(path):
    contract = agent_contract(path)
    rules = contract['contract']
    # Check rules before proceeding
    if 'minimize_edits' in rules:
        # Use surgical approach
```

### 2. Never Auto-Create Session
```python
# ❌ BAD
def implement_feature(path, task):
    session_new(path, task)  # Wrong! User didn't ask
    # ... implement ...

# ✅ GOOD
def implement_feature(path, task):
    # Only create session if user explicitly asks
    if user_asked_to_log:
        session_new(path, task)
```

### 3. Use `next_in_progress()` for Planning
```python
# ✅ GOOD
def plan_implementation(path, task):
    plan = next_in_progress(path, task)
    show_to_user(plan['breakdown'])
    ask_permission()
```

### 4. Call `impact()` Before Risky Changes
```python
# ✅ GOOD
def change_function_signature(path, func_name):
    impact = impact(path, func_name)
    if impact['breaking_changes_risk'] in ['MEDIUM', 'HIGH']:
        warn_user(impact['recommendations'])
        ask_permission()
```

### 5. Keep Session Summaries Concise
```python
# ❌ BAD - Too long
session_step(path, "Implemented the withdrawal feature which involved adding database migrations, backend logic, frontend UI, notifications", "")

# ✅ GOOD - Concise (≤120 chars auto-truncated)
session_step(path, "Implemented withdrawal feature with DB migration, backend, UI, notifications", "")
```

### 6. Use Right Tool for Right Job
```
Need:                        Use Tool:
─────────────────────────────────────────
Quick overview              index()
Search for context          query()
Suggested next steps        next_in_progress()
Change impact               impact()
Persistent logging          session_* (if user asks)
Read all rules             agent_contract()
```

---

## 📊 Data Flow

```
Agent Request
    ↓
[agent_contract] ← Rules, contract for project
    ↓
[tree] ← Codebase structure (token reduction)
    ↓
[query] ← Context for task
    ↓
[next_in_progress] ← Suggested steps (chat-ready)
    ↓
Agent implements based on context
    ↓
[impact] ← (if changing signatures)
    ↓
[session_step] ← (optional, if user asks)
    ↓
Chat shows progress, results
```

---

## 🔗 Related Files

- **[MCP_SETUP.md](MCP_SETUP.md)** — Configure MCP for your client (Claude, Copilot, Cursor, etc.)
- **[REPO_STRUCTURE.md](REPO_STRUCTURE.md)** — Folder layout and file purposes
- **[agent-presets/system_prompt_contexly.txt](agent-presets/system_prompt_contexly.txt)** — System prompt to copy into your agent
- **[agent-presets/task_prompt_template.txt](agent-presets/task_prompt_template.txt)** — Task template

---

## ❓ Frequently Asked Questions

**Q: Do I have to create a session?**  
A: No. Sessions are optional. By default, all context stays in chat. Only create session.md if user explicitly asks to log progress.

**Q: What's the difference between `query()` and `next_in_progress()`?**  
A: `query()` returns context (what code exists). `next_in_progress()` returns a plan (what files to touch, in what order).

**Q: When should I call `impact()`?**  
A: Before making changes to function signatures, APIs, return types, or any breaking changes. Use impact() to warn about affected areas.

**Q: How long does `tree()` take?**  
A: Depends on project size. Typical: 2-5 seconds for 100-300 files. Time scales linearly with files.

**Q: Can I call tools multiple times?**  
A: Yes, as many times as you need. tree() is cached (subsequent calls read from contexly-outputs/), so re-runs are fast.

**Q: What if `agent_contract()` says I should do something I disagree with?**  
A: Respect the contract. It reflects the project owner's rules. If you think there's a better way, show the user both options and let them decide.

---

## 📞 Support & Debugging

If a tool call fails:

1. Check the path is correct (absolute or relative to where you're running)
2. Ensure tree.json exists at contexly-outputs/[project]/ (or call tree() first)
3. For queries returning no results:
   - Try broader query_text
   - Increase top_k
   - Increase depth
4. If session.md operations fail:
   - Ensure user called session_new() first
   - Check .contexly/ directory exists

---

**Generated for Contexly v0.1.0 MCP Server**  
**For agents: Claude, Copilot, Cursor, Continue, Windsurf, OpenCode, OpenClaw, Hermes, Antigravity**
