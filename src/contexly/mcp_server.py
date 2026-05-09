"""Contexly MCP server.

Exposes Contexly tree/index/query/impact/session capabilities as MCP tools over stdio.

╔═══════════════════════════════════════════════════════════════════════════════╗
║                    CONTEXLY MCP SERVER USAGE GUIDE FOR AGENTS                 ║
╚═══════════════════════════════════════════════════════════════════════════════╝

WHAT IS CONTEXLY?
─────────────────
Contexly reduces large codebases (1M+ lines) to ~35K tokens using logic skeletons.
This MCP server exposes tools to build, query, analyze, and reason about codebases.

CORE WORKFLOW (ALWAYS START HERE)
──────────────────────────────────
1. agent_contract(path)
   → Read operating rules and capabilities for this project
   → Returns contract, system_prompt, session guidance
   → Use this to understand what you can and cannot do

2. tree(path)
   → Build or refresh the codebase tree
   → Returns: file_count, token_estimate, entry_files, orphan_files
   → Call when: project first loaded, after major changes, when context is stale
   → Output: saved to contexly-outputs/[project]/tree.json

3. index(path, level)
   → Get lightweight text index (NOT JSON tree)
   → level=0: repo map (high-level structure)
   → level=1: file index (all files with roles)
   → Use when: you need quick text overview, not full tree detail

4. query(path, query_text, depth=1, level=2, top_k=8, debug=false)
   → Search codebase for relevant context
   → Args:
      - query_text: what you're looking for (e.g., "fetch user balance")
      - depth: how many connection hops to include (1-3 recommended)
      - level: detail level (1=file names, 2=functions, 3=logic)
      - top_k: number of matches to rank
      - debug: include search score metadata
   → Returns: scored matches, seed_files, targeted_context, targeted_context_file
   → Use when: before coding, to gather context about a specific task

5. next_in_progress(path, query_text, top_k=8)
   → Generate a chat-ready execution breakdown WITHOUT writing session.md
   → Args: same as query
   → Returns: suggested_next_in_progress (string), breakdown (array of steps)
   → Use when: planning next step, want ranked files + suggested actions
   → IMPORTANT: This tool does NOT persist session.md

6. impact(path, function_name, file_hint="")
   → Preview what changes if you modify a function
   → Args:
      - function_name: name of function to modify
      - file_hint: optional filename hint if function name is ambiguous
   → Returns: impact_preview (affected files, call chains, risks)
   → Use when: before making API/signature-breaking changes

OPTIONAL SESSION TRACKING (use only if user asks)
──────────────────────────────────────────────────

7. session_new(path, task)
   → Create a new .contexly/session.md file
   → Args: task description (e.g., "Fix withdraw function")
   → Returns: session_file path
   → Use when: user explicitly requests session persistence

8. session_update(path, status, text)
   → Update session.md with done/in_progress/todo entries
   → Args:
      - status: one of "done", "in_progress", "todo"
      - text: concise summary (keep ≤120 chars)
   → Returns: session_file path
   → Use when: user asks to log progress

9. session_step(path, completed, next_in_progress)
   → Compact: log a completed item AND set next in-progress in one call
   → Args:
      - completed: what was just finished (auto-truncated to ~120 chars)
      - next_in_progress: what's next (or empty string)
   → Returns: session_file path
   → Use when: user asks for persistent step logging

10. session_status(path)
    → Read current .contexly/session.md content
    → Args: path only
    → Returns: session_file path and raw markdown content
    → Use when: need to check current context or session state

11. capabilities()
    → List all MCP tools and recommended flow
    → Args: none
    → Returns: tool list, recommended_flow array
    → Use when: agent needs to understand its own capabilities

TYPICAL AGENT EXECUTION FLOW
────────────────────────────

Entry Point:
  1. Call agent_contract(path) to read rules
  2. Call tree(path) to ensure fresh tree data

For a Feature Implementation Task:
  1. Call query(path, "task description", depth=1, level=2)
  2. Call next_in_progress(path, "task description") to get breakdown
  3. Show breakdown to user in chat
  4. Implement changes based on context
  5. (Optional) Call session_step(path, "completed X", "next Y") if user asks

For a Risky Change (API/signature modification):
  1. Call query(path, "specific function context")
  2. Call impact(path, "function_name", "file_hint")
  3. Review impact_preview
  4. Warn user about affected call sites
  5. Proceed with implementation

For Multi-Step Work:
  1. Call query for each logical step
  2. Call impact before each signature change
  3. (Optional) Use session_step to track progress if user wants
  4. Show next_in_progress breakdown between steps

IMPORTANT DESIGN PRINCIPLES
───────────────────────────
• query() and next_in_progress() do NOT write to session.md automatically
• tree() and other tools output to contexly-outputs/[project_name]/
• session.md is ONLY created/updated when user explicitly asks
• All context stays in chat by default; persistence is opt-in
• Call agent_contract() at start to learn what rules apply
• Always respect the contract—do not skip recommended checks
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List

from mcp.server.fastmcp import FastMCP

from contexly.agent.session import Session
from contexly.core.tree_builder import TreeBuilder


mcp = FastMCP("Contexly MCP")


def _resolve_path(path: str | None) -> str:
    target = path or "."
    return os.path.abspath(target)


def _outputs_base() -> Path:
    return Path(os.path.expanduser("~")) / ".vscode" / "github-repo-context" / "contexly-outputs"


def _output_dir(target_path: str) -> Path:
    name = Path(_resolve_path(target_path)).name
    out_dir = _outputs_base() / name
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _load_or_build_tree(path: str) -> tuple[TreeBuilder, Any, Path]:
    builder = TreeBuilder()
    out_dir = _output_dir(path)
    tree_file = out_dir / "tree.json"
    if tree_file.exists():
        tree = builder.load(str(tree_file))
    else:
        tree = builder.build(path)
        builder.save(tree, str(tree_file))
    return builder, tree, tree_file


def _session_file_path(path: str) -> Path:
    return Path(_resolve_path(path)) / ".contexly" / "session.md"


def _extract_functions(node: Any, max_items: int = 6) -> List[str]:
    funcs: List[str] = []
    for raw in getattr(node, "main_functions", []) or []:
        name = str(raw).split("[", 1)[0].strip()
        if name:
            funcs.append(name)

    if not funcs:
        skeleton = getattr(node, "skeleton_text", "") or ""
        for line in skeleton.splitlines():
            match = re.match(r"\s*[~]?(\w+)\(", line)
            if match:
                funcs.append(match.group(1))

    deduped: List[str] = []
    for fn in funcs:
        if fn not in deduped:
            deduped.append(fn)
    return deduped[:max_items]


def _build_next_step_from_matches(tree_obj: Any, matches: List[Dict[str, Any]], query_text: str) -> Dict[str, Any]:
    steps: List[Dict[str, Any]] = []
    for idx, match in enumerate(matches[:3], start=1):
        path = match.get("path", "")
        node = tree_obj.nodes.get(path)
        if not node:
            continue
        funcs = _extract_functions(node)
        conf = match.get("confidence", "LOW")
        score = float(match.get("score", 0.0) or 0.0)
        step = {
            "step": idx,
            "file": path,
            "confidence": conf,
            "score": score,
            "functions": funcs,
            "suggested_action": (
                f"Inspect {path} first and validate functions: "
                f"{', '.join(funcs[:3]) if funcs else 'entry logic block'}"
            ),
        }
        steps.append(step)

    if steps:
        top = steps[0]
        lead = top["file"]
        fn_hint = ", ".join(top["functions"][:2]) if top["functions"] else "primary logic"
        suggested = f"Start with {lead} ({fn_hint}), then move to next ranked dependency file."
    else:
        suggested = f"No strong match for '{query_text}'. Start from entry files and narrow by impact()."

    return {
        "suggested_next_in_progress": suggested,
        "breakdown": steps,
    }


@mcp.tool()
def tree(path: str = ".") -> Dict[str, Any]:
    """Build codebase tree and save JSON output."""
    builder = TreeBuilder()
    target = _resolve_path(path)
    tree_obj = builder.build(target)
    out_dir = _output_dir(target)
    tree_file = out_dir / "tree.json"
    builder.save(tree_obj, str(tree_file))

    return {
        "project_path": target,
        "tree_json": str(tree_file),
        "file_count": tree_obj.file_count,
        "total_tokens": tree_obj.total_tokens,
        "raw_token_estimate": tree_obj.raw_token_estimate,
        "reduction_percent": tree_obj.reduction_percent,
        "entry_files": tree_obj.entry_files,
        "orphan_files": tree_obj.orphan_files,
    }


@mcp.tool()
def index(path: str = ".", level: int = 1) -> Dict[str, Any]:
    """Return lightweight index text (level 0 map, level 1 file index)."""
    builder, tree_obj, tree_file = _load_or_build_tree(_resolve_path(path))
    text = builder.to_repo_map(tree_obj) if level == 0 else builder.to_index(tree_obj)
    return {
        "project_path": _resolve_path(path),
        "tree_json": str(tree_file),
        "level": level,
        "token_estimate": max(1, len(text) // 4),
        "text": text,
    }


@mcp.tool()
def query(
    path: str,
    query_text: str,
    depth: int = 1,
    level: int = 2,
    top_k: int = 8,
    debug: bool = False,
) -> Dict[str, Any]:
    """Search relevant files and return targeted tree context for a query."""
    target = _resolve_path(path)
    builder, tree_obj, tree_file = _load_or_build_tree(target)

    scored = builder.search_index(tree_obj, query_text, top_k=top_k)
    seed_files = [
        r["path"]
        for r in scored
        if r.get("confidence") in ("HIGH", "MED") and r.get("role") != "LEGACY"
    ]
    if not seed_files and scored:
        non_legacy = [r["path"] for r in scored if r.get("role") != "LEGACY"]
        seed_files = [non_legacy[0]] if non_legacy else [scored[0]["path"]]

    targeted = builder.get_targeted_tree(
        tree_obj,
        seed_files,
        depth=depth,
        level=level,
        auto_exclude_legacy=True,
    )

    q_slug = query_text.lower().replace(" ", "_")[:30]
    out_dir = _output_dir(target)
    targeted_file = out_dir / f"targeted_{q_slug}.txt"
    targeted_file.write_text(targeted, encoding="utf-8")

    result: Dict[str, Any] = {
        "project_path": target,
        "tree_json": str(tree_file),
        "query": query_text,
        "depth": depth,
        "level": level,
        "matches": scored,
        "seed_files": seed_files,
        "targeted_context": targeted,
        "targeted_context_file": str(targeted_file),
    }
    if debug:
        result["debug"] = {
            "auto_exclude_legacy": True,
            "top_k": top_k,
        }
    return result


@mcp.tool()
def next_in_progress(path: str, query_text: str, top_k: int = 8) -> Dict[str, Any]:
    """Return chat-ready next-step breakdown from current tree context without writing session.md."""
    target = _resolve_path(path)
    builder, tree_obj, tree_file = _load_or_build_tree(target)
    scored = builder.search_index(tree_obj, query_text, top_k=top_k)
    plan = _build_next_step_from_matches(tree_obj, scored, query_text)
    return {
        "project_path": target,
        "tree_json": str(tree_file),
        "query": query_text,
        "matches": scored,
        "suggested_next_in_progress": plan["suggested_next_in_progress"],
        "breakdown": plan["breakdown"],
        "note": "Chat-first guidance only; this tool does not update session.md.",
    }


@mcp.tool()
def impact(path: str, function_name: str, file_hint: str = "") -> Dict[str, Any]:
    """Return impact preview for changing a function."""
    target = _resolve_path(path)
    builder, tree_obj, tree_file = _load_or_build_tree(target)
    preview = builder.get_impact_preview(
        tree_obj,
        function_name=function_name,
        file_hint=file_hint or None,
    )
    return {
        "project_path": target,
        "tree_json": str(tree_file),
        "function_name": function_name,
        "file_hint": file_hint,
        "impact_preview": preview,
    }


@mcp.tool()
def session_new(path: str = ".", task: str = "General Session") -> Dict[str, Any]:
    """Create or reset Contexly session markdown."""
    target = _resolve_path(path)
    sess = Session(target)
    sess.create(task)
    return {"project_path": target, "session_file": str(sess.session_file), "task": task}


@mcp.tool()
def session_update(path: str, status: str, text: str) -> Dict[str, Any]:
    """Update Contexly session markdown (status: done|in_progress|todo)."""
    target = _resolve_path(path)
    sess = Session(target)
    sess.update(status, text)
    return {"project_path": target, "status": status, "session_file": str(sess.session_file)}


@mcp.tool()
def session_step(path: str, completed: str, next_in_progress: str = "") -> Dict[str, Any]:
    """Record a short completed step and optionally set the next active step."""
    target = _resolve_path(path)
    sess = Session(target)
    sess.complete_step(completed, next_in_progress)
    return {
        "project_path": target,
        "session_file": str(sess.session_file),
        "completed": completed,
        "next_in_progress": next_in_progress,
    }


@mcp.tool()
def session_status(path: str = ".") -> Dict[str, Any]:
    """Get current session markdown content."""
    target = _resolve_path(path)
    sess = Session(target)
    return {
        "project_path": target,
        "session_file": str(sess.session_file),
        "content": sess.read_status(),
    }


@mcp.tool()
def agent_contract(path: str = ".") -> Dict[str, Any]:
    """Return the required Contexly agent operating contract and current session status."""
    target = _resolve_path(path)
    sess = Session(target)
    session_file = _session_file_path(target)
    has_session = session_file.exists()

    contract = [
        "Call query(path, query_text, depth=1, level=2) before coding.",
        "Call next_in_progress(path, query_text) to generate a chat-ready breakdown.",
        "Build/refresh tree(path) when context is stale or project changed.",
        "Before risky signature changes, call impact(path, function_name, file_hint).",
        "Present next_in_progress suggestions to the user in agent chat.",
        "Do not auto-update session.md unless the user explicitly asks for persistence.",
    ]

    system_prompt = (
        "You are an implementation agent using Contexly MCP. "
        "Use query for scoped context, next_in_progress for breakdown planning, and impact "
        "before API/signature changes. Report next steps in agent chat. "
        "Only write session.md when user explicitly requests session persistence."
    )

    return {
        "project_path": target,
        "session_file": str(session_file),
        "has_session": has_session,
        "contract": contract,
        "system_prompt": system_prompt,
        "session_content": sess.read_status(),
    }


@mcp.tool()
def bootstrap_agent(path: str = ".", task: str = "General Session") -> Dict[str, Any]:
    """Initialize session if missing and return first-step MCP calls for any coding agent."""
    target = _resolve_path(path)
    sess = Session(target)
    session_file = _session_file_path(target)
    created = False

    if not session_file.exists():
        sess.create(task)
        created = True

    next_calls = [
        {"tool": "session_status", "args": {"path": target}},
        {"tool": "tree", "args": {"path": target}},
        {"tool": "query", "args": {"path": target, "query_text": task, "depth": 1, "level": 2}},
    ]

    return {
        "project_path": target,
        "session_file": str(session_file),
        "session_created": created,
        "task": task,
        "next_calls": next_calls,
    }


@mcp.tool()
def capabilities() -> Dict[str, Any]:
    """Describe available Contexly MCP tools and expected usage."""
    return {
        "name": "Contexly MCP",
        "transport": "stdio",
        "tools": [
            "tree",
            "index",
            "query",
            "next_in_progress",
            "impact",
            "session_new",
            "session_update",
            "session_step",
            "session_status",
            "agent_contract",
            "bootstrap_agent",
            "capabilities",
        ],
        "recommended_flow": [
            "agent_contract(path)",
            "tree(path)",
            "query(path, query_text, depth=1, level=2)",
            "next_in_progress(path, query_text)",
            "impact(path, function_name)",
            "(optional) session_step/session_update only on explicit user request",
        ],
    }


def main() -> None:
    """Run MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
