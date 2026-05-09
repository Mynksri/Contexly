# Contexly Documentation Index

Complete guide to all documentation files for agents, developers, and users.

---

## 📚 Documentation Files

### For AI Agents (START HERE)

1. **[AGENT_REFERENCE.md](AGENT_REFERENCE.md)** ⭐ MAIN GUIDE
   - **Length**: ~800 lines, detailed
   - **For**: AI agents learning Contexly for the first time
   - **Contains**:
     - What is Contexly?
     - 11 tools with signatures, parameters, return types
     - Typical agent workflows (bug fix, multi-step feature, risky changes)
     - Best practices for agents
     - FAQ section
   - **Start here if**: You're new to Contexly and want full understanding
   - **Read time**: 15-20 minutes

2. **[MCP_TOOL_REFERENCE.md](MCP_TOOL_REFERENCE.md)** 🚀 QUICK LOOKUP
   - **Length**: ~200 lines, concise
   - **For**: Fast signature/parameter lookup during coding
   - **Contains**:
     - All 11 tool signatures in one place
     - Quick parameter reference
     - Copy-paste call examples
     - Return type reference
     - Error handling guide
   - **Start here if**: You know what you need, just need quick syntax
   - **Read time**: 2-5 minutes

3. **[REPO_STRUCTURE.md](REPO_STRUCTURE.md)** 🗂️ PROJECT LAYOUT
   - **Length**: ~500 lines, reference
   - **For**: Understanding folder organization and file purposes
   - **Contains**:
     - Complete folder structure (src/, tests/, contexly-outputs/, agent-presets/)
     - Module descriptions with key functions
     - Configuration file explanations (pyproject.toml, pytest.ini, etc.)
     - Data structure definitions (tree.json format)
     - Output directory structure
   - **Start here if**: You want to understand project layout or find specific code
   - **Read time**: 10-15 minutes to skim, detailed reference for lookups

---

### In Source Code

4. **[src/contexly/mcp_server.py](src/contexly/mcp_server.py)** 📝 EMBEDDED GUIDE
   - **Location**: First 120 lines (docstring)
   - **For**: Quick reference while reading source code
   - **Contains**:
     - Core workflow overview (5 steps)
     - Tool usage summary
     - Design principles
   - **Access**: Open file and read docstring at top
   - **Read time**: 2-3 minutes

---

### For Setup & Integration

5. **[MCP_SETUP.md](MCP_SETUP.md)** ⚙️ CLIENT CONFIGURATION
   - **For**: Setting up Contexly MCP with AI agents (Claude, Copilot, Cursor, etc.)
   - **Contains**:
     - One-time local setup commands
     - Universal MCP server block (copy-paste)
     - Client-specific configuration (9 supported clients)
     - Tool list reference
   - **Use when**: First installing/configuring Contexly with a client
   - **Read time**: 5 minutes

6. **[README.md](README.md)** 📖 PROJECT OVERVIEW
   - **For**: High-level project description and quick start
   - **Contains**:
     - Problem statement (1M lines = $100+ in tokens)
     - Solution (95%+ reduction)
     - Installation
     - Quick usage examples
     - Pointer to MCP_SETUP
   - **Read time**: 2 minutes

---

### Configuration Files

7. **[pyproject.toml](pyproject.toml)** 📦
   - Package metadata, dependencies, build config
   - Two CLI entrypoints: `contexly`, `contexly-mcp`
   - Python >=3.10 required

8. **[pytest.ini](pytest.ini)** 🧪
   - Test configuration
   - pythonpath = src (enables src-layout)
   - Run: `pytest tests -q`

9. **[.gitignore](.gitignore)** 🔒
   - Excludes Python artifacts, test cache, session files, outputs

---

## 🎯 Quick Navigation by Use Case

### "I'm an AI agent, how do I use Contexly?"
**→** Start with [AGENT_REFERENCE.md](AGENT_REFERENCE.md)
- Learn the 5-step workflow
- Understand all 11 tools
- Read workflow examples

### "I need tool signatures and parameters NOW"
**→** Use [MCP_TOOL_REFERENCE.md](MCP_TOOL_REFERENCE.md)
- All signatures in one place
- Copy-paste examples
- Return types reference

### "I need to understand the codebase layout"
**→** Read [REPO_STRUCTURE.md](REPO_STRUCTURE.md)
- src/contexly/ module breakdown
- tests/ organization
- Configuration files explained

### "I need to set up Contexly with my MCP client"
**→** Follow [MCP_SETUP.md](MCP_SETUP.md)
- Copy universal server block
- Find your client (Claude, Copilot, Cursor, etc.)
- Paste and configure

### "I'm debugging a tool call"
**→** Check [MCP_TOOL_REFERENCE.md](MCP_TOOL_REFERENCE.md) → "Error Handling"
- Common error scenarios
- Solutions for each

### "What should my system prompt be?"
**→** See [agent-presets/system_prompt_contexly.txt](agent-presets/system_prompt_contexly.txt)
- Ready-to-use system prompt
- Mandatory workflow rules
- Session behavior guidelines

---

## 📊 Documentation Size & Scope

| Document | Size | Audience | Scope |
|----------|------|----------|-------|
| AGENT_REFERENCE.md | 800 lines | Agents | Complete guide, detailed |
| MCP_TOOL_REFERENCE.md | 200 lines | Agents/Developers | Quick reference, concise |
| REPO_STRUCTURE.md | 500 lines | Developers | Project layout, detailed |
| MCP_SETUP.md | 100 lines | Anyone setting up | Configuration, practical |
| README.md | 50 lines | Everyone | Overview, marketing |
| mcp_server.py docstring | 120 lines | Code readers | In-file guide |

---

## 🔄 Reading Path Recommendations

### Path 1: Agent Developer (First Time)
1. Read [README.md](README.md) (2 min) - understand problem/solution
2. Read [AGENT_REFERENCE.md](AGENT_REFERENCE.md) (20 min) - learn workflow
3. Skim [MCP_TOOL_REFERENCE.md](MCP_TOOL_REFERENCE.md) (5 min) - bookmark for later
4. Skim [REPO_STRUCTURE.md](REPO_STRUCTURE.md) (10 min) - understand project layout
5. **Now ready to code!**

### Path 2: Existing Agent, Adding Feature
1. Skim [AGENT_REFERENCE.md](AGENT_REFERENCE.md) relevant section
2. Use [MCP_TOOL_REFERENCE.md](MCP_TOOL_REFERENCE.md) for quick lookup
3. Refer to [REPO_STRUCTURE.md](REPO_STRUCTURE.md) if modifying code

### Path 3: Setting Up MCP for First Time
1. Read [MCP_SETUP.md](MCP_SETUP.md) (5 min)
2. Follow client-specific instructions
3. Verify with test call

### Path 4: Understanding Repository Structure
1. Skim [REPO_STRUCTURE.md](REPO_STRUCTURE.md)
2. Check [pyproject.toml](pyproject.toml) for dependencies
3. Browse src/contexly/ modules

---

## 🎓 Learning the 11 Tools

### Tier 1: Essential (Learn First)
1. `agent_contract()` - Read project rules
2. `tree()` - Load codebase structure
3. `query()` - Search for context
4. **Why**: These 3 enable 80% of agent workflows

### Tier 2: Advanced Planning
5. `next_in_progress()` - Get execution plan
6. `impact()` - Check for breaking changes
7. **Why**: Enable multi-step tasks and safe refactoring

### Tier 3: Optional Persistence
8. `session_new()` - Create session
9. `session_update()` - Log progress
10. `session_step()` - Log step
11. `session_status()` - Read progress
12. **Why**: Only use if user explicitly asks for logging

### Tier 4: Utility
- `index()` - Quick text overview
- `capabilities()` - Discover tools

---

## ✅ Documentation Checklist for Agents

Before integrating Contexly, verify you've:

- [ ] Read [AGENT_REFERENCE.md](AGENT_REFERENCE.md) sections 1-2 (What is Contexly, 5-step workflow)
- [ ] Bookmarked [MCP_TOOL_REFERENCE.md](MCP_TOOL_REFERENCE.md) for quick lookup
- [ ] Understood the core workflow: agent_contract → tree → query → next_in_progress → implement
- [ ] Know NOT to auto-create session.md (only on user request)
- [ ] Reviewed one workflow example from [AGENT_REFERENCE.md](AGENT_REFERENCE.md) relevant to your use case
- [ ] Set up MCP following [MCP_SETUP.md](MCP_SETUP.md)
- [ ] Tested at least one tool call (e.g., `agent_contract()`)

---

## 🔗 Key Design Principles (Quick Review)

1. **Chat-First**: All context stays in chat by default
2. **No Auto-Session**: Never create session.md without user request
3. **Always Contract First**: Call `agent_contract()` before other tools
4. **Right Tool for Job**:
   - Context? → `query()`
   - Plan? → `next_in_progress()`
   - Risk? → `impact()`
5. **Respect Project Rules**: agent_contract defines what you can/cannot do

---

## 📞 Troubleshooting Documentation

### "Tool X failed"
→ Check [MCP_TOOL_REFERENCE.md](MCP_TOOL_REFERENCE.md) "Error Handling" section

### "I don't understand what tool to use"
→ Read [AGENT_REFERENCE.md](AGENT_REFERENCE.md) "Workflow Examples" section

### "Where is module X in the code?"
→ Check [REPO_STRUCTURE.md](REPO_STRUCTURE.md) for file mapping

### "How do I configure my MCP client?"
→ Follow [MCP_SETUP.md](MCP_SETUP.md)

### "What's the exact signature for tool X?"
→ Open [MCP_TOOL_REFERENCE.md](MCP_TOOL_REFERENCE.md) "All 11 Tools (Signatures Only)"

---

## 📝 Document Maintenance

All documentation files live in: **contexly/ root directory**

When updating Contexly:
1. Update [AGENT_REFERENCE.md](AGENT_REFERENCE.md) if tool signatures change
2. Update [MCP_TOOL_REFERENCE.md](MCP_TOOL_REFERENCE.md) with new tools
3. Update [REPO_STRUCTURE.md](REPO_STRUCTURE.md) if folder layout changes
4. Update [mcp_server.py](src/contexly/mcp_server.py) docstring with core workflow changes

---

## 🎯 One-Minute Summary

**Contexly** = Tool that reduces 1M-line codebases to 35K tokens using logic skeletons.

**5-Step Agent Workflow**:
1. Read rules: `agent_contract(path)`
2. Load tree: `tree(path)`
3. Search: `query(path, "task")`
4. Plan: `next_in_progress(path, "task")`
5. Code based on context

**Key Rule**: Never auto-create session.md. Sessions optional, user-requested only.

**Documentation**:
- **New to Contexly?** → [AGENT_REFERENCE.md](AGENT_REFERENCE.md)
- **Quick lookup?** → [MCP_TOOL_REFERENCE.md](MCP_TOOL_REFERENCE.md)
- **Understanding code?** → [REPO_STRUCTURE.md](REPO_STRUCTURE.md)
- **Setting up MCP?** → [MCP_SETUP.md](MCP_SETUP.md)

---

**Last Updated**: 2024  
**For**: AI Agents, Developers, Users  
**Version**: Contexly 0.1.0
