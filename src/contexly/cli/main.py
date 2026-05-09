"""
CLI entry point for Contexly.
Commands: init, tree, status, view
"""

import sys
import os
from pathlib import Path

# Central output folder - all trees saved here, not inside target projects
CONTEXLY_OUTPUTS_BASE = Path(os.path.expanduser("~")) / ".vscode" / "github-repo-context" / "contexly-outputs"


def _get_output_dir(target_path: str) -> Path:
    """Return the output dir for a given target, creating it if needed."""
    project_name = Path(os.path.abspath(target_path)).name
    out_dir = CONTEXLY_OUTPUTS_BASE / project_name
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def main():
    args = sys.argv[1:]
    if not args:
        print_help()
        return

    cmd = args[0]
    path = args[1] if len(args) > 1 else "."

    if cmd == "init":
        cmd_init(path)
    elif cmd == "tree":
        cmd_tree(path)
    elif cmd == "view":
        cmd_view(path)
    elif cmd == "status":
        cmd_status(path)
    elif cmd == "index":
        level = int(args[2]) if len(args) > 2 else 1
        cmd_index(path, level)
    elif cmd == "query":
        query_args = args[2:]
        debug = "--debug" in query_args
        positional = [a for a in query_args if a != "--debug"]
        query_str = positional[0] if len(positional) > 0 else ""
        depth = int(positional[1]) if len(positional) > 1 else 1
        level = int(positional[2]) if len(positional) > 2 else 2
        cmd_query(path, query_str, depth=depth, level=level, debug=debug)
    elif cmd == "impact":
        function_name = args[2] if len(args) > 2 else ""
        file_hint = args[3] if len(args) > 3 else None
        cmd_impact(path, function_name, file_hint)
    elif cmd == "session":
        cmd_session(args[1:])
    elif cmd in ("-h", "--help", "help"):
        print_help()
    else:
        print(f"Unknown command: {cmd}")
        print_help()


def cmd_init(path: str):
    """Initialize Contexly for a project."""
    print(f"Initializing Contexly for: {os.path.abspath(path)}")
    contexly_dir = Path(path) / ".contexly"
    contexly_dir.mkdir(exist_ok=True)
    print("Created .contexly directory")
    print(f"Run 'contexly tree {path}' to build the logic tree")


def cmd_tree(path: str):
    """Build and display tree stats."""
    from contexly.core.tree_builder import TreeBuilder
    from contexly.ui.tree_renderer import TreeRenderer

    abs_path = os.path.abspath(path)
    print(f"Building logic tree for: {abs_path}")
    print("   Extracting logic skeletons...")

    builder = TreeBuilder()
    tree = builder.build(path)

    # Role summary
    role_counts: dict = {}
    for node in tree.nodes.values():
        r = getattr(node, "role", "UNKNOWN")
        role_counts[r] = role_counts.get(r, 0) + 1

    print(f"\nResults:")
    print(f"   Files processed:    {tree.file_count}")
    print(f"   Raw token estimate: {tree.raw_token_estimate:,}")
    print(f"   Tree tokens:        {tree.total_tokens:,}")
    print(f"   Compression:        {tree.reduction_percent:.1f}%")
    print(f"   Ratio:              {tree.raw_token_estimate // max(tree.total_tokens, 1)}x smaller")

    print(f"\nFile roles:")
    for role in ["ENTRY", "CORE", "UTIL", "TEST", "SCRIPT", "ORPHAN"]:
        if role in role_counts:
            print(f"   {role:<8} {role_counts[role]} file(s)")

    if getattr(tree, "orphan_files", []):
        print(f"\nOrphan files (not imported by anything):")
        for f in tree.orphan_files:
            print(f"   - {f}")

    # Save to central output folder
    out_dir = _get_output_dir(path)
    tree_file = str(out_dir / "tree.json")
    builder.save(tree, tree_file)
    print(f"\nTree saved: {tree_file}")

    # Generate HTML visualization
    renderer = TreeRenderer()
    html_path = str(out_dir / "tree.html")
    renderer.save(tree, html_path)
    print(f"Visual tree: {html_path}")
    print(f"   Open in browser to explore your codebase")


def cmd_view(path: str):
    """Open visual tree in browser."""
    import webbrowser
    # Support both: 'contexly view .' (target project) and 'contexly view <abs_path_to_html>'
    p = Path(path)
    if p.suffix == ".html" and p.exists():
        html_path = p
    else:
        out_dir = _get_output_dir(path)
        html_path = out_dir / "tree.html"
    if not html_path.exists():
        print(f"No tree found at: {html_path}")
        print("Run 'contexly tree <path>' first.")
        return
    webbrowser.open(html_path.as_uri())
    print(f"Opening: {html_path}")


def cmd_status(path: str):
    """Show current session status."""
    out_dir = _get_output_dir(path)
    tree_file = out_dir / "tree.json"
    if tree_file.exists():
        import json
        data = json.loads(tree_file.read_text())
        print(f"Tree: {data['file_count']} files, "
              f"{data['total_tokens']:,} tokens, "
              f"{data['reduction_percent']:.1f}% compression")
        if data.get("entry_files"):
            print(f"Entry files:  {data['entry_files']}")
        if data.get("orphan_files"):
            print(f"Orphan files: {data['orphan_files']}")
    else:
        print(f"No tree built yet for: {os.path.abspath(path)}")
        print("Run 'contexly tree <path>' first.")


def cmd_index(path: str, level: int = 1):
    """
    Build and print a lightweight index of the codebase.

    level=0  â†’ Repo map  (~200-600 tokens)
    level=1  â†’ File skeletons index  (~1-3K tokens)  [default]
    """
    from contexly.core.tree_builder import TreeBuilder

    abs_path = os.path.abspath(path)
    builder = TreeBuilder()

    # Try loading existing tree first (fast path)
    out_dir = _get_output_dir(path)
    tree_file = out_dir / "tree.json"
    if tree_file.exists():
        tree = builder.load(str(tree_file))
        print(f"  (loaded cached tree from {tree_file})")
    else:
        print(f"Building tree for: {abs_path} ...")
        tree = builder.build(path)
        builder.save(tree, str(tree_file))

    if level == 0:
        result = builder.to_repo_map(tree)
        label = "REPO MAP (Level 0)"
    else:
        result = builder.to_index(tree)
        label = "FILE INDEX (Level 1)"

    print(f"\n=== {label} ===")
    print(result)
    tokens = max(1, len(result) // 4)
    print(f"\n~{tokens} tokens")


def cmd_query(path: str, query: str, depth: int = 1, level: int = 2, debug: bool = False):
    """
    Smart search: find relevant files and build a targeted tree.

    path     â€” project directory
    query    â€” natural language query, e.g. "fix rate limiting"
    depth    â€” connection depth to expand (0=seed only, 1=direct, 2=transitive)
    level    â€” detail level for output (0=map, 1=index, 2=full skeleton)
    """
    from contexly.core.tree_builder import TreeBuilder
    from contexly.agent.session import Session

    if not query:
        print("Usage: contexly query <path> \"<query>\" [depth] [level]")
        print("Example: contexly query . \"fix rate limiting\" 1 2")
        return

    abs_path = os.path.abspath(path)
    builder = TreeBuilder()

    # Auto-update session if it exists
    sess = Session(path)
    if (Path(path) / ".contexly" / "session.md").exists():
        sess.update("in_progress", f"Query: {query[:60]}")

    out_dir = _get_output_dir(path)
    tree_file = out_dir / "tree.json"
    if tree_file.exists():
        tree = builder.load(str(tree_file))
        print(f"  (loaded cached tree from {tree_file})")
    else:
        print(f"Building tree for: {abs_path} ...")
        tree = builder.build(path)
        builder.save(tree, str(tree_file))

    # Phase 1: show index search results
    print(f"\nSearching for: '{query}'")
    scored = builder.search_index(tree, query, top_k=8)
    if not scored:
        print("  No matching files found.")
        return

    print("\nTop matches:")
    for r in scored:
        fname = Path(r["path"]).name
        funcs = ", ".join(r["matched_functions"][:3]) if r["matched_functions"] else "â€”"
        tags = " ".join(r["matched_tags"][:3])
        print(f"  {r['confidence']:<4} {fname:<40} score={r['score']:>5}  [{funcs}]  {tags}")
        if debug:
            print(f"       role={r.get('role', 'UNKNOWN')} | reason={r.get('reason', '')}")

    # Phase 2: build targeted tree
    seed_files = [
        r["path"] for r in scored
        if r["confidence"] in ("HIGH", "MED") and r.get("role") != "LEGACY"
    ]
    if debug:
        legacy_blocked = [r["path"] for r in scored if r.get("role") == "LEGACY"]
        if legacy_blocked:
            print(f"\nDebug: skipped LEGACY auto-seeds: {', '.join(Path(p).name for p in legacy_blocked)}")
    if not seed_files:
        non_legacy = [r["path"] for r in scored if r.get("role") != "LEGACY"]
        seed_files = [non_legacy[0]] if non_legacy else [scored[0]["path"]]

    print(f"\nBuilding targeted tree (depth={depth}) around {len(seed_files)} seed file(s)...")
    targeted = builder.get_targeted_tree(
        tree,
        seed_files,
        depth=depth,
        level=level,
        auto_exclude_legacy=True,
    )
    print(targeted)

    # Save targeted output
    q_slug = query.lower().replace(" ", "_")[:30]
    targeted_file = out_dir / f"targeted_{q_slug}.txt"
    targeted_file.write_text(targeted, encoding="utf-8")
    print(f"\nSaved: {targeted_file}")


def cmd_impact(path: str, function_name: str, file_hint: str = None):
    """
    Show impact preview before editing a function.
    Lists all callers detected via call_graph + skeleton references.
    """
    from contexly.core.tree_builder import TreeBuilder

    if not function_name:
        print("Usage: contexly impact <path> <function_name> [file_hint]")
        print("Example: contexly impact . execute_trade trade_executor")
        return

    builder = TreeBuilder()
    out_dir = _get_output_dir(path)
    tree_file = out_dir / "tree.json"
    if tree_file.exists():
        tree = builder.load(str(tree_file))
    else:
        print(f"Building tree for: {os.path.abspath(path)} ...")
        tree = builder.build(path)
        builder.save(tree, str(tree_file))

    result = builder.get_impact_preview(tree, function_name, file_hint)
    print(result)


def _parse_session_target_and_text(args: list[str]) -> tuple[str, str]:
    """
    Parse optional <path> and required <text> from session subcommand args.

    Accepted:
            contexly session done "summary"
            contexly session done /path/to/project "summary"
    """
    if not args:
        return ".", ""

    if len(args) >= 2 and Path(args[0]).exists():
        return args[0], " ".join(args[1:]).strip()
    return ".", " ".join(args).strip()


def cmd_session(raw_args: list[str]):
    """Manage markdown session tracker used by the agent."""
    from contexly.agent.session import Session

    if not raw_args:
        print("Usage: contexly session <new|done|todo|status> [path] [text]")
        return

    sub = raw_args[0]
    rest = raw_args[1:]

    if sub == "new":
        path, task = _parse_session_target_and_text(rest)
        if not task:
            print("Usage: contexly session new [path] \"<task>\"")
            return
        sess = Session(path)
        sess.create(task)
        print(f"Session created: {sess.session_file}")
        return

    if sub == "done":
        path, summary = _parse_session_target_and_text(rest)
        if not summary:
            print("Usage: contexly session done [path] \"<summary>\"")
            return
        sess = Session(path)
        sess.update("done", summary)
        print("Session updated (COMPLETED).")
        return

    if sub == "todo":
        path, item = _parse_session_target_and_text(rest)
        if not item:
            print("Usage: contexly session todo [path] \"<item>\"")
            return
        sess = Session(path)
        sess.update("todo", item)
        print("Session updated (TODO).")
        return

    if sub == "status":
        path = rest[0] if rest else "."
        sess = Session(path)
        print(sess.read_status())
        return

    print(f"Unknown session subcommand: {sub}")
    print("Usage: contexly session <new|done|todo|status> [path] [text]")


def print_help():
    print("""
Contexly - Codebase Context Engine

USAGE:
    contexly init [path]                         Initialize Contexly for a project
    contexly tree [path]                         Build full logic skeleton tree
    contexly index [path] [level]                Lightweight index (level 0=map, 1=skeletons)
        contexly query [path] "<query>" [depth] [level] [--debug]  Smart search + targeted tree
    contexly impact [path] <func> [file_hint]    Show callers before editing a function
        contexly session new [path] "<task>"         Start/update markdown session tracker
        contexly session done [path] "<summary>"     Mark completed work in session.md
        contexly session todo [path] "<item>"        Add todo item in session.md
        contexly session status [path]                Print current session.md
    contexly view [path]                         Open visual tree in browser
    contexly status [path]                       Show session status

LEVELS:
  0  Repo map          ~200-600 tokens  (what's where â€” ultra fast)
  1  File index        ~1-3K tokens     (names + imports + tags)
  2  Full skeleton     ~5-30K tokens    (logic + conditions + state) [default]
  3  Full skeleton + project context header

EXAMPLES:
    contexly index . 0                           # ultra-lightweight repo map
    contexly index . 1                           # file skeletons with tags
        contexly query . "fix rate limiting" 1 2     # search + targeted depth-1 skeleton
        contexly query . "fix rate limiting" 1 2 --debug  # print ranking reasons
    contexly query . "balance calculation" 0 1   # search + depth-0 index output
    contexly impact . execute_trade              # who calls execute_trade?
        contexly session new . "Fix Polymarket bot"
        contexly session done . "balance_manager.py fixed - line 47"
        contexly session todo . "Fix trade executor"
        contexly session status .
    contexly tree .                              # full tree (existing behavior)
    contexly view .
""")


if __name__ == "__main__":
    main()

