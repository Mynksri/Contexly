"""
TreeBuilder â€” Assembles individual file skeletons into a full codebase tree.

The tree represents the entire codebase structure with inter-file connections.
This is what gets sent to AI â€” not raw code.
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, asdict, field
from contexly.core.extractor import SkeletonExtractor, FileSkeleton


FILE_ROLES = {
    "ENTRY":  "Entry point (main app file)",
    "CORE":   "Core logic â€” imported by entry/other core files",
    "UTIL":   "Utility/helper â€” used by multiple files",
    "TEST":   "Test file",
    "LEGACY": "Standalone legacy flow duplicating core logic",
    "SCRIPT": "Standalone analysis/debug script",
    "ORPHAN": "Not imported by any other file in this project",
}


STOPWORDS = {
    "fix", "bug", "error", "errors", "issue", "issues", "problem", "broken",
    "not", "working", "fails", "failed", "add", "change", "update",
    "the", "a", "an", "in", "for", "to", "of", "new", "make",
    "get", "set", "check", "handle", "test",
}


ROLE_MULTIPLIERS = {
    "CORE": 1.0,
    "ENTRY": 1.0,
    "UTIL": 0.8,
    "SCRIPT": 0.3,
    "ORPHAN": 0.1,
    "LEGACY": 0.05,
    "TEST": 0.2,
}


@dataclass
class TreeNode:
    """One node in the codebase tree (represents one file)."""
    path: str
    language: str
    skeleton_text: str
    token_estimate: int
    imports: List[str]
    connections: List[str]  # other files this file imports/uses
    role: str               # ENTRY / CORE / UTIL / TEST / SCRIPT / ORPHAN
    imported_by: List[str]  # which files import this file
    is_entry_point: bool
    has_duplicate_funcs: List[str]  # function names that appear more than once
    line_range: str = ""            # "start-end" e.g., "39-480"
    main_functions: List[str] = field(default_factory=list)  # top functions with line numbers
    warnings: List[str] = field(default_factory=list)


@dataclass
class CodebaseTree:
    """Full codebase tree â€” collection of all file nodes."""
    root_path: str
    nodes: Dict[str, TreeNode]  # {relative_path: TreeNode}
    total_tokens: int
    raw_token_estimate: int
    file_count: int
    reduction_percent: float
    entry_files: List[str]    # files classified as ENTRY
    orphan_files: List[str]   # files not imported by anyone
    state_summaries: List[Dict[str, Any]] = field(default_factory=list)  # cross-file lifecycle for state-heavy classes
    project_summary: str = ""       # high-level codebase description
    core_strategy: str = ""         # key algorithmic approach
    state_management: str = ""      # how state is managed across files
    call_graph: List[str] = field(default_factory=list)


class TreeBuilder:
    """
    Builds a complete codebase tree from source files.
    
    Usage:
        builder = TreeBuilder()
        tree = builder.build("/path/to/project")
        text = builder.to_ai_text(tree)          # full tree for AI
        chunk = builder.get_relevant_chunk(tree, "fix balance calculation")
    """

    def __init__(self):
        self.extractor = SkeletonExtractor()

    def build(
        self,
        root_path: str,
        exclude_dirs: Optional[List[str]] = None,
        exclude_roles: Optional[List[str]] = None,
        exclude_file_patterns: Optional[List[str]] = None,
    ) -> CodebaseTree:
        """Build complete tree from a directory."""
        if exclude_roles is None:
            # Keep all discovered files by default.
            # Excluding ORPHAN/SCRIPT globally can collapse some JS/TS repos to 0 files.
            exclude_roles = []
        skeletons = self.extractor.extract_directory(
            root_path,
            exclude_dirs=exclude_dirs,
            exclude_file_patterns=exclude_file_patterns,
        )
        aliases = self._load_module_aliases(root_path)

        nodes = {}
        total_tokens = 0

        for filepath, skeleton in skeletons.items():
            text = self.extractor.to_text(skeleton)
            tokens = self.extractor.estimate_tokens(text)
            total_tokens += tokens

            connections = self._find_connections(
                skeleton.imports,
                list(skeletons.keys()),
                current_path=filepath,
                aliases=aliases,
            )

            # Compute line range
            line_range = f"{skeleton.functions[0].line_start if skeleton.functions else 1}-{skeleton.total_lines}" if skeleton.functions else f"1-{skeleton.total_lines}"
            
            # Compute main functions (top 3-5 most important ones)
            main_funcs = self._extract_main_functions(skeleton)

            nodes[filepath] = TreeNode(
                path=filepath,
                language=skeleton.language,
                skeleton_text=text,
                token_estimate=tokens,
                imports=skeleton.imports,
                connections=connections,
                role="",            # will be set by _classify_files
                imported_by=[],
                is_entry_point=skeleton.is_entry_point,
                has_duplicate_funcs=self._find_duplicate_funcs(skeleton),
                line_range=line_range,
                main_functions=main_funcs,
                warnings=[],
            )

        # Build reverse index: who imports who
        for path, node in nodes.items():
            for conn in node.connections:
                if conn in nodes:
                    nodes[conn].imported_by.append(path)

        # Classify every file
        self._classify_files(nodes, skeletons)
        self._mark_legacy_files(nodes, skeletons)

        # Optional role filtering for token-efficient default output.
        if exclude_roles:
            nodes = {
                p: n for p, n in nodes.items()
                if n.role not in set(exclude_roles)
            }

            # Rebuild imported_by after filtering so references stay accurate.
            for node in nodes.values():
                node.imported_by = []
            for path, node in nodes.items():
                node.connections = [c for c in node.connections if c in nodes]
                for conn in node.connections:
                    nodes[conn].imported_by.append(path)

        stats = self.extractor.get_stats(skeletons)
        state_summaries = self._build_state_summaries(skeletons)
        call_graph = self._build_call_graph(nodes, skeletons)

        entry_files = [p for p, n in nodes.items() if n.role == "ENTRY"]
        orphan_files = [p for p, n in nodes.items() if n.role == "ORPHAN"]
        
        # Build top-level summaries
        project_summary, core_strategy, state_mgmt = self._build_project_summaries(
            skeletons, nodes, entry_files, state_summaries
        )

        return CodebaseTree(
            root_path=root_path,
            nodes=nodes,
            total_tokens=sum(n.token_estimate for n in nodes.values()),
            raw_token_estimate=stats["raw_token_estimate"],
            file_count=len(nodes),
            reduction_percent=stats["reduction_percent"],
            entry_files=entry_files,
            orphan_files=orphan_files,
            state_summaries=state_summaries,
            project_summary=project_summary,
            core_strategy=core_strategy,
            state_management=state_mgmt,
            call_graph=call_graph,
        )

    def _mark_legacy_files(
        self,
        nodes: Dict[str, "TreeNode"],
        skeletons: Dict[str, FileSkeleton],
    ) -> None:
        """Mark standalone legacy files that duplicate multiple core function names."""
        core_func_names: Dict[str, Set[str]] = {}
        for path, node in nodes.items():
            if node.role not in ("CORE", "UTIL", "ENTRY"):
                continue
            sk = skeletons.get(path)
            if not sk:
                continue
            names = {f.name for f in sk.functions}
            for cls in sk.classes:
                names.update(m.name for m in cls.methods)
            core_func_names[path] = names

        for path, node in nodes.items():
            sk = skeletons.get(path)
            if not sk:
                continue
            local_names = {f.name for f in sk.functions}
            for cls in sk.classes:
                local_names.update(m.name for m in cls.methods)

            dupes = set()
            for other_path, other_names in core_func_names.items():
                if other_path == path:
                    continue
                dupes.update(local_names.intersection(other_names))

            standalone_like = node.is_entry_point or not node.imported_by
            if len(dupes) >= 3 and standalone_like:
                node.role = "LEGACY"
                dupe_list = ", ".join(sorted(dupes)[:8])
                node.warnings.append(
                    f"Duplicates {dupe_list} from core files; consider main.py + round_manager.py flow"
                )

    def _build_state_summaries(
        self,
        skeletons: Dict[str, FileSkeleton],
    ) -> List[Dict[str, Any]]:
        """Build cross-file lifecycle summaries for state-heavy classes."""
        candidates: List[Dict[str, Any]] = []

        for path, skeleton in skeletons.items():
            for cls in skeleton.classes:
                field_names = []
                for field_line in cls.fields:
                    match = re.match(r'^@?([A-Za-z_][A-Za-z0-9_]*)\s*:', field_line)
                    if match:
                        field_names.append(match.group(1))
                if field_names and (
                    len(field_names) >= 6
                    or cls.name.lower().endswith(("state", "context", "store", "model"))
                ):
                    candidates.append({
                        "class_name": cls.name,
                        "path": path,
                        "fields": field_names,
                        "updates": {},
                    })

        if not candidates:
            return []

        for path, skeleton in skeletons.items():
            file_stem = Path(path).stem
            funcs: List[tuple[str, List[str], Optional[str]]] = []
            for func in skeleton.functions:
                label = func.name if path in [c["path"] for c in candidates] else f"{file_stem}.{func.name}"
                funcs.append((label, func.state_writes, None))
            for cls in skeleton.classes:
                for method in cls.methods:
                    label = f"{cls.name}.{method.name}"
                    funcs.append((label, method.state_writes, cls.name))

            for label, writes, owner_class in funcs:
                for candidate in candidates:
                    touched = []
                    for write in writes:
                        if "." not in write:
                            continue
                        base, attr = write.split(".", 1)
                        if attr not in candidate["fields"]:
                            continue
                        if base == "state":
                            touched.append(attr)
                        elif base == "self" and owner_class == candidate["class_name"]:
                            touched.append(attr)
                    unique_touched = []
                    for attr in touched:
                        if attr not in unique_touched:
                            unique_touched.append(attr)

                    same_file = path == candidate["path"]
                    min_overlap = 1 if same_file else 3
                    if len(unique_touched) >= min_overlap:
                        existing = candidate["updates"].setdefault(label, [])
                        for attr in unique_touched:
                            if attr not in existing:
                                existing.append(attr)

        summaries = []
        for candidate in candidates:
            ordered_updates = []
            for label, attrs in sorted(
                candidate["updates"].items(),
                key=lambda item: (-len(item[1]), item[0]),
            ):
                summary = ", ".join(attrs[:10])
                if len(attrs) > 10:
                    summary += ", ..."
                ordered_updates.append(f"{label} -> {summary}")
            summaries.append({
                "class_name": candidate["class_name"],
                "path": candidate["path"],
                "field_count": len(candidate["fields"]),
                "fields": candidate["fields"],
                "updated_by": ordered_updates,
            })

        return summaries

    def _find_duplicate_funcs(self, skeleton: FileSkeleton) -> List[str]:
        """Find function names that appear more than once in a file."""
        names = [f.name for f in skeleton.functions]
        for cls in skeleton.classes:
            names.extend(m.name for m in cls.methods)
        seen = set()
        dupes = []
        for n in names:
            if n in seen and n not in dupes:
                dupes.append(n)
            seen.add(n)
        return dupes

    def _extract_main_functions(self, skeleton: FileSkeleton) -> List[str]:
        """Extract top 3-5 most important functions with line numbers."""
        candidates = []
        for func in skeleton.functions:
            # Score functions by importance
            complexity = len(func.conditions) + len(func.calls) + len(func.state_writes)
            is_async = 1 if func.is_async else 0
            score = complexity * 10 + is_async * 5
            candidates.append((func.name, func.line_start, func.line_end, score))
        
        for cls in skeleton.classes:
            for method in cls.methods:
                complexity = len(method.conditions) + len(method.calls) + len(method.state_writes)
                is_async = 1 if method.is_async else 0
                score = complexity * 10 + is_async * 5
                candidates.append((f"{cls.name}.{method.name}", method.line_start, method.line_end, score))
        
        # Sort by score and take top 3-5
        candidates.sort(key=lambda x: -x[3])
        result = []
        for name, start, end, _ in candidates[:5]:
            result.append(f"{name}[{start}-{end}]")
        return result

    def _build_project_summaries(
        self,
        skeletons: Dict[str, FileSkeleton],
        nodes: Dict[str, "TreeNode"],
        entry_files: List[str],
        state_summaries: List[Dict[str, Any]],
    ) -> tuple[str, str, str]:
        """Build project-level summaries: overall description, core strategy, state management."""
        # Infer from filenames and major state classes first, then fallback to purposes.
        file_names = set(nodes.keys())
        has_round_flow = "round_manager.py" in file_names
        has_claim_flow = "claim_manager.py" in file_names
        has_price_flow = "price_monitor.py" in file_names
        has_trade_flow = "trade_executor.py" in file_names

        if has_round_flow and has_claim_flow and has_price_flow:
            project_summary = (
                "Polymarket short-interval momentum + pivot arbitrage bot "
                "with dynamic hedging and staged claim execution"
            )
        else:
            project_summary = "Automated trading and portfolio management system with multi-asset support"

        if has_round_flow and has_trade_flow and has_claim_flow:
            core_strategy = (
                "Primary momentum entry -> reversal pivot hedge -> multi-pivot recovery -> "
                "CLOB exit first -> on-chain redeem fallback"
            )
        else:
            core_strategy = "Multi-phase execution with state tracking, risk guards, and post-round settlement"

        if state_summaries:
            total_fields = sum(s.get("field_count", 0) for s in state_summaries)
            state_names = [s.get("class_name", "State") for s in state_summaries]
            state_mgmt = (
                f"Heavy usage of {', '.join(state_names)} "
                f"({total_fields} tracked fields) for per-round lifecycle state"
            )
        else:
            state_mgmt = "Stateful round-based processing with per-coin tracking and phase transitions"

        return project_summary, core_strategy, state_mgmt

    def _build_call_graph(
        self,
        nodes: Dict[str, "TreeNode"],
        skeletons: Dict[str, FileSkeleton],
    ) -> List[str]:
        """Build compact cross-file call graph from connected files and known symbol names."""
        symbols_by_file: Dict[str, Set[str]] = {}
        for path, sk in skeletons.items():
            names = {f.name for f in sk.functions}
            for cls in sk.classes:
                names.update(m.name for m in cls.methods)
            symbols_by_file[path] = names

        graph_lines: List[str] = []
        for path, node in sorted(nodes.items()):
            sk = skeletons.get(path)
            if not sk:
                continue
            for func in sk.functions:
                edges = []
                for call in func.calls:
                    short = call.split(".")[-1]
                    for conn in node.connections:
                        if short in symbols_by_file.get(conn, set()):
                            edges.append(f"{Path(conn).stem}.{short}")
                if edges:
                    src = f"{Path(path).stem}.{func.name}"
                    deduped = []
                    for edge in edges:
                        if edge not in deduped:
                            deduped.append(edge)
                    graph_lines.append(f"{src} -> {', '.join(deduped[:6])}")

        return graph_lines[:60]

    def _classify_files(
        self,
        nodes: Dict[str, "TreeNode"],
        skeletons: Dict[str, FileSkeleton],
    ):
        """
        Assign a role to each file based on import graph analysis.
        Classification order (highest priority first):
          TEST   > ENTRY > ORPHAN/SCRIPT > UTIL > CORE > ORPHAN
        CORE/UTIL credit only counts from non-ORPHAN importers.
        """
        all_imported: Set[str] = set()
        for node in nodes.values():
            all_imported.update(node.connections)

        # --- Pass 1: mark TEST and ENTRY, clear is_entry_point for test files ---
        for path, node in nodes.items():
            fname = os.path.basename(path).lower()
            if (
                fname.startswith("test_")
                or fname.endswith("_test.py")
                or fname.startswith("demo_")
            ):
                node.role = "TEST"
                node.is_entry_point = False  # test files are never entry points

        # --- Pass 2: ENTRY (has main/asyncio, not imported by real code) ---
        for path, node in nodes.items():
            if node.role:  # already classified
                continue
            # Only mark ENTRY if it's not imported by any non-test file
            real_importers = [
                p for p in node.imported_by
                if nodes.get(p) and nodes[p].role not in ("TEST", "SCRIPT", "ORPHAN")
            ]
            if node.is_entry_point and not real_importers:
                node.role = "ENTRY"

        # --- Pass 3: everything else ---
        for path, node in nodes.items():
            if node.role:  # already classified
                continue

            fname = os.path.basename(path).lower()
            skeleton = skeletons.get(path)

            if skeleton and skeleton.language == "html":
                html_text = node.skeleton_text.lower()
                has_frontend_assets = any(
                    marker in html_text
                    for marker in (
                        "html_classes =",
                        "html_ids =",
                        "data_attrs =",
                        "external_libs =",
                        "html_role_hints =",
                        "<script",
                        "class=",
                        "classname=",
                        "id=",
                        "data-",
                    )
                )
                if has_frontend_assets:
                    node.role = "ENTRY" if not node.imported_by else "CORE"
                    continue

            # Count how many NON-orphan files import this file
            quality_importers = [
                p for p in node.imported_by
                if nodes.get(p) and nodes[p].role not in ("ORPHAN", "SCRIPT", "TEST")
            ]

            if not node.imported_by:
                # Nobody imports this â€” standalone script or orphan
                # SCRIPT = has imports of stdlib only, or is a debug/analysis file
                if not node.connections:
                    node.role = "SCRIPT"  # pure standalone, no project imports
                else:
                    node.role = "ORPHAN"  # has project imports but nobody uses it
                continue

            if not quality_importers:
                # Only imported by ORPHAN/SCRIPT/TEST files â€” effectively orphaned
                node.role = "ORPHAN"
                continue

            # UTIL: imported by 3+ quality files
            if len(quality_importers) >= 3:
                node.role = "UTIL"
                continue

            # CORE: imported by at least one quality file
            node.role = "CORE"

        # --- Pass 4: anything still unclassified â†’ ORPHAN ---
        for path, node in nodes.items():
            if not node.role:
                node.role = "ORPHAN"

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    #  MULTI-LEVEL OUTPUT
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def to_repo_map(self, tree: CodebaseTree) -> str:
        """
        Level 0 â€” Repo Map.
        Ultra-lightweight overview: file name + role + top functions only.
        Typical cost: ~200-600 tokens for any project.
        Ideal for Phase 1 of 2-phase retrieval â€” let AI understand 'what's where'.
        """
        project_name = Path(tree.root_path).name
        lines = [
            f"REPO:{project_name}  [{tree.file_count} files | ~{tree.total_tokens:,} tokens | {tree.reduction_percent:.1f}% compression]",
        ]
        if tree.project_summary:
            lines.append(f"  PROJECT:{tree.project_summary}")
        if tree.core_strategy:
            lines.append(f"  STRATEGY:{tree.core_strategy}")
        lines.append("")

        # Group by role for readability
        role_order = ["ENTRY", "CORE", "UTIL", "TEST", "LEGACY", "SCRIPT", "ORPHAN", "UNKNOWN"]
        by_role: Dict[str, List[tuple]] = {r: [] for r in role_order}
        for path, node in sorted(tree.nodes.items()):
            role = node.role or "UNKNOWN"
            fname = Path(path).name
            lr = node.line_range or ""
            funcs = ", ".join(
                f.split("[")[0] for f in (node.main_functions or [])[:4]
            )
            warn = " âš ï¸" if node.warnings else ""
            by_role.setdefault(role, []).append((fname, lr, funcs, warn))

        for role in role_order:
            entries = by_role.get(role, [])
            if not entries:
                continue
            for fname, lr, funcs, warn in entries:
                lr_part = f" [L{lr}]" if lr else ""
                func_part = f"  â†’ {funcs}" if funcs else ""
                lines.append(f"  {role:<8}{fname}{lr_part}{warn}{func_part}")

        if tree.call_graph:
            lines.append("")
            lines.append("CALL_GRAPH (key chains):")
            for item in tree.call_graph[:8]:
                lines.append(f"  {item}")

        return "\n".join(lines)

    def to_index(self, tree: CodebaseTree) -> str:
        """
        Level 1 â€” File Skeletons Index.
        Names + signatures + imports only â€” no logic, no conditions.
        Typical cost: ~1-3K tokens for a mid-size project.
        Use for Phase 1 of 2-phase retrieval after repo_map.
        """
        project_name = Path(tree.root_path).name
        lines = [
            f"INDEX:{project_name}  [{tree.file_count} files | ~{tree.total_tokens:,} tokens]",
        ]
        if tree.project_summary:
            lines.append(f"  PROJECT:{tree.project_summary}")
        lines.append("")

        for path, node in sorted(tree.nodes.items()):
            fname = Path(path).name
            lr = f" [L{node.line_range}]" if node.line_range else ""
            role = node.role or ""
            warn = " âš ï¸" if node.warnings else ""
            lines.append(f"FILE:{fname} [{role}{lr}]{warn}")

            # Imports (compressed)
            if node.imports:
                lines.append(f"  IMPORTS:{','.join(node.imports[:8])}")

            # Functions with confidence scores
            if node.main_functions:
                scored = self._score_functions(node)
                func_parts = []
                for fname_f, lr_f, score in scored[:6]:
                    tag = "[HIGH]" if score >= 15 else "[MED]" if score >= 6 else "[LOW]"
                    func_parts.append(f"{fname_f}{tag}")
                lines.append(f"  FUNCTIONS:{', '.join(func_parts)}")

            # Tags
            tags = self._compute_tags(node)
            if tags:
                lines.append(f"  TAGS:{' '.join(tags)}")

            # Connections
            if node.connections:
                conns = [Path(c).stem for c in node.connections[:4]]
                lines.append(f"  USES:{','.join(conns)}")

            # Warnings
            for w in node.warnings:
                lines.append(f"  WARN:{w}")

            lines.append("")

        return "\n".join(lines)

    def to_ai_text(self, tree: CodebaseTree, level: int = 2) -> str:
        """
        Convert tree to text for AI consumption.

        level=0  â†’ Repo map (200-600 tokens)
        level=1  â†’ File index with names + imports (1-3K tokens)
        level=2  â†’ Full skeleton with logic (default, 5-30K tokens)
        level=3  â†’ Same as 2 but caller-aware context header prepended
        """
        if level == 0:
            return self.to_repo_map(tree)
        if level == 1:
            return self.to_index(tree)
        # Level 2 / 3 â€” full detail
        lines = [
            "=== CODEBASE TREE ===",
            "Legend: = PURPOSE | NOTE SECTION | % LIFECYCLE | & STATE UPDATES | @ LOGIC VARS | > CALLS | ? IF | < RETURNS | ! RAISES | ~ async | [N] line",
            f"Files: {tree.file_count} | "
            f"Tokens: ~{tree.total_tokens:,} | "
            f"Compression: {tree.reduction_percent}%",
            "",
        ]

        if level == 3 and tree.project_summary:
            lines.append(f"PROJECT:{tree.project_summary}")
            if tree.core_strategy:
                lines.append(f"STRATEGY:{tree.core_strategy}")
            lines.append("")

        if getattr(tree, "state_summaries", None):
            lines.append("=== STATE SUMMARIES ===")
            for summary in tree.state_summaries:
                lines.append(
                    f"STATE:{summary['class_name']} [{summary['path']}]"
                )
                for item in summary.get("updated_by", [])[:10]:
                    lines.append(f"  %{item}")
                lines.append("")

        if getattr(tree, "call_graph", None):
            lines.append("=== CROSS-FILE CALL GRAPH ===")
            for item in tree.call_graph[:30]:
                lines.append(item)
            lines.append("")

        for path, node in sorted(tree.nodes.items()):
            lines.append(node.skeleton_text)
            lines.append("")  # blank line between files

        return "\n".join(lines)

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    #  SMART RELEVANCE ENGINE
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def search_index(
        self,
        tree: CodebaseTree,
        query: str,
        top_k: int = 5,
        exclude_roles: Optional[Set[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search index with keyword + function-name + tag matching.
        Returns top_k scored results with confidence labels.

        Result dict keys: path, score, confidence, matched_functions, matched_tags, reason
        """
        query_lower = query.lower().strip()
        # Build query tokens: camelCase split + snake_case split
        import re as _re
        raw_tokens = _re.split(r'[\s_\-/]+', query_lower)
        camel_split = []
        for tok in raw_tokens:
            # split camelCase â†’ ['rate', 'limit'] etc
            camel_split.extend(t.lower() for t in _re.sub(r'([A-Z])', r' \1', tok).split())

        query_tokens = [t for t in (raw_tokens + camel_split) if t]
        meaningful_tokens = [t for t in query_tokens if t not in STOPWORDS]
        # Fallback: if query is entirely generic, keep original tokens.
        if meaningful_tokens:
            query_tokens = meaningful_tokens

        query_token_set = set(query_tokens)

        results: List[Dict[str, Any]] = []

        blocked_roles = {r.upper() for r in (exclude_roles or set())}

        for path, node in tree.nodes.items():
            if (node.role or "").upper() in blocked_roles:
                continue
            score = 0.0
            matched_functions: List[str] = []
            matched_tags: List[str] = []
            reasons: List[str] = []

            fname = Path(path).name.lower()
            stem = Path(path).stem.lower()

            # --- file/path match (high weight) ---
            for tok in query_token_set:
                if tok in stem:
                    score += 4.0
                    reasons.append(f"filename:{tok}")

            # --- function name match ---
            for func_entry in node.main_functions or []:
                func_name = func_entry.split("[")[0].lower()
                for tok in query_token_set:
                    if tok in func_name:
                        score += 3.0
                        if func_entry not in matched_functions:
                            matched_functions.append(func_entry)
                        reasons.append(f"func:{func_name}")

            # --- skeleton text match ---
            skel = node.skeleton_text.lower()
            for tok in query_token_set:
                cnt = skel.count(tok)
                if cnt:
                    score += cnt * 0.8
                    reasons.append(f"text:{tok}Ã—{cnt}")

            # --- tag match ---
            tags = self._compute_tags(node)
            for tag in tags:
                tag_clean = tag.lstrip("#").lower()
                for tok in query_token_set:
                    if tok in tag_clean:
                        score += 2.0
                        matched_tags.append(tag)

            # --- role bonus ---
            if node.role in ("ENTRY", "CORE"):
                score += 1.0

            # De-prioritize non-production roles.
            score *= ROLE_MULTIPLIERS.get(node.role or "", 1.0)

            if score <= 0:
                continue

            confidence = "HIGH" if score >= 12 else "MED" if score >= 5 else "LOW"
            reason_str = " | ".join(dict.fromkeys(reasons[:5]))  # dedup, top 5

            results.append({
                "path": path,
                "score": round(score, 2),
                "confidence": confidence,
                "role": node.role,
                "matched_functions": matched_functions[:4],
                "matched_tags": matched_tags[:4],
                "reason": reason_str,
                "token_estimate": node.token_estimate,
            })

        results.sort(key=lambda r: -r["score"])

        # Confidence labels are based on adjusted (role-aware) score.
        for item in results:
            score = item["score"]
            item["confidence"] = "HIGH" if score >= 12 else "MED" if score >= 5 else "LOW"

        return results[:top_k]

    def get_targeted_tree(
        self,
        tree: CodebaseTree,
        seed_files: List[str],
        depth: int = 1,
        level: int = 2,
        auto_exclude_legacy: bool = False,
    ) -> str:
        """
        Phase 2 targeted retrieval: build a subgraph around seed files.

        seed_files  â€” file paths (or stems) to start from
        depth=0     â€” seed files only
        depth=1     â€” seed + direct imports/importers (default)
        depth=2     â€” depth-1 + their imports

        level       â€” output detail level (2=full skeleton, 1=index, 0=map)
        auto_exclude_legacy â€” ignore LEGACY during expansion unless explicitly seeded
        """
        # Resolve seeds to known paths
        resolved: Set[str] = set()
        for seed in seed_files:
            seed_lower = seed.lower()
            for path in tree.nodes:
                if path == seed or Path(path).name == seed or Path(path).stem.lower() == seed_lower:
                    resolved.add(path)

        if not resolved:
            return f"No files matched seeds: {seed_files}"

        # BFS expansion up to `depth` hops
        frontier = set(resolved)
        included = set(resolved)
        for _ in range(depth):
            next_frontier: Set[str] = set()
            for path in frontier:
                node = tree.nodes.get(path)
                if not node:
                    continue
                for conn in node.connections:
                    if conn not in included and conn in tree.nodes:
                        if (
                            auto_exclude_legacy
                            and conn not in resolved
                            and tree.nodes[conn].role == "LEGACY"
                        ):
                            continue
                        next_frontier.add(conn)
                for imp_by in node.imported_by:
                    if imp_by not in included and imp_by in tree.nodes:
                        if (
                            auto_exclude_legacy
                            and imp_by not in resolved
                            and tree.nodes[imp_by].role == "LEGACY"
                        ):
                            continue
                        next_frontier.add(imp_by)
            included |= next_frontier
            frontier = next_frontier

        # Build a mini CodebaseTree with only the included nodes
        sub_nodes = {p: tree.nodes[p] for p in included}

        # Re-filter connections so they only reference included nodes
        import copy
        sub_nodes_clean: Dict[str, TreeNode] = {}
        for p, n in sub_nodes.items():
            n2 = copy.copy(n)
            n2.connections = [c for c in n.connections if c in sub_nodes]
            n2.imported_by = [c for c in n.imported_by if c in sub_nodes]
            sub_nodes_clean[p] = n2

        sub_tokens = sum(n.token_estimate for n in sub_nodes_clean.values())
        sub_tree = CodebaseTree(
            root_path=tree.root_path,
            nodes=sub_nodes_clean,
            total_tokens=sub_tokens,
            raw_token_estimate=tree.raw_token_estimate,
            file_count=len(sub_nodes_clean),
            reduction_percent=tree.reduction_percent,
            entry_files=[p for p in tree.entry_files if p in sub_nodes_clean],
            orphan_files=[p for p in tree.orphan_files if p in sub_nodes_clean],
            state_summaries=[
                s for s in tree.state_summaries
                if s.get("path") in sub_nodes_clean
            ],
            project_summary=tree.project_summary,
            core_strategy=tree.core_strategy,
            state_management=tree.state_management,
            call_graph=[
                line for line in tree.call_graph
                if any(Path(p).stem in line for p in included)
            ],
        )

        header_lines = [
            f"=== TARGETED TREE (depth={depth}) ===",
            f"Seeds: {', '.join(Path(s).name for s in resolved)}",
            f"Files included: {len(sub_nodes_clean)} | Tokens: ~{sub_tokens:,}",
            f"Legacy auto-exclude: {'ON' if auto_exclude_legacy else 'OFF'}",
            "",
        ]
        return "\n".join(header_lines) + self.to_ai_text(sub_tree, level=level)

    def get_impact_preview(
        self,
        tree: CodebaseTree,
        function_name: str,
        file_hint: Optional[str] = None,
        depth: int = 2,
        include_dataflow: bool = False,
        show_paths: bool = False,
    ) -> str:
        """
        Impact preview before editing a function.
        Shows all files + lines that call this function (from call_graph + connections).

        function_name â€” exact name, e.g. 'execute_trade'
        file_hint     â€” optional file stem to narrow down (e.g. 'trade_executor')
        """
        fn_lower = function_name.lower().strip()
        depth = max(1, min(depth, 5))

        caller_lines, caller_meta = self._collect_direct_callers(tree, fn_lower, file_hint)
        impacted_files = self._expand_indirect_file_impact(tree, caller_meta, depth=depth)

        direct_files = {meta["caller_file"] for meta in caller_meta if meta.get("caller_file")}
        indirect_files = [p for p, hop in impacted_files.items() if hop >= 2]

        # Infer potential target file(s) for clearer direct-caller classification.
        target_files: Set[str] = set()
        for entry in tree.call_graph:
            if " -> " not in entry:
                continue
            _, targets_str = entry.split(" -> ", 1)
            for target in targets_str.split(", "):
                t_stem, _, t_func = target.partition(".")
                if t_func.lower() != fn_lower:
                    continue
                if file_hint and file_hint.lower() not in t_stem.lower():
                    continue
                resolved = self._resolve_tree_file_by_stem(tree, t_stem)
                if resolved:
                    target_files.add(resolved)

        if not target_files and file_hint:
            for path in tree.nodes:
                if file_hint.lower() in Path(path).name.lower():
                    target_files.add(path)

        lines = [f"IMPACT PREVIEW: {function_name}()"]
        if file_hint:
            lines.append(f"  Defined in: {file_hint}")

        if caller_meta:
            cross_file_callers: List[str] = []
            same_file_callers: List[str] = []
            symbol_mentions: List[str] = []
            for meta in caller_meta:
                caller_file = meta.get("caller_file", "")
                caller_symbol = meta.get("caller_symbol", "callsite")
                confidence = meta.get("confidence", "LOW")
                if not caller_file:
                    continue
                line_range = self._lookup_symbol_line_range(tree, caller_file, caller_symbol)
                suffix = f" [L{line_range}]" if line_range and caller_symbol != "mention" else ""
                row = f"  - {Path(caller_file).name} -> {caller_symbol}(){suffix} [{confidence}]"
                if caller_symbol == "mention":
                    symbol_mentions.append(f"  - {Path(caller_file).name} (symbol mention) [LOW]")
                elif target_files and caller_file not in target_files:
                    cross_file_callers.append(row)
                else:
                    same_file_callers.append(row)

            total_direct = len(cross_file_callers) + len(same_file_callers)
            lines.append(f"  Direct callers ({total_direct}):")
            lines.append(f"  - Cross-file direct: {len(cross_file_callers)}")
            if cross_file_callers:
                lines.extend(cross_file_callers[:8])
            lines.append(f"  - Same-file direct: {len(same_file_callers)}")
            if same_file_callers:
                lines.extend(same_file_callers[:8])
            if symbol_mentions:
                lines.append(f"  - Symbol mentions: {len(symbol_mentions)}")
                lines.extend(symbol_mentions[:6])
        else:
            lines.append("  Direct callers: none detected in current index")

        lines.append("")
        lines.append(f"  Indirect callers (up to {depth} hops):")
        if indirect_files:
            for path in sorted(indirect_files)[:16]:
                hops = impacted_files[path]
                conf = "MED" if hops <= 3 else "LOW"
                lines.append(f"  - {Path(path).name} ({hops} hops, {conf})")
        else:
            lines.append("  - none")

        sidefx: List[str] = []
        if include_dataflow:
            dataflow = self._build_dataflow_summary(tree, fn_lower, file_hint)
            sidefx = self._detect_side_effects(tree, fn_lower, file_hint)

            lines.append("")
            lines.append("  Data flow:")
            if dataflow:
                for row in dataflow[:12]:
                    lines.append(f"  - {row}")
            else:
                lines.append("  - No strong dataflow hints found")

            lines.append("")
            lines.append("  Side effects:")
            if sidefx:
                for row in sidefx:
                    lines.append(f"  - {row}")
            else:
                lines.append("  - No explicit side effects detected")

        if show_paths:
            call_paths = self._build_call_paths(tree, fn_lower, file_hint, depth=depth)
            lines.append("")
            lines.append("  Call paths to this function:")
            if call_paths:
                for i, path in enumerate(call_paths[:8], 1):
                    lines.append(f"    {i}. {path}")
            else:
                lines.append("    No call paths found")

        # Calculate high-impact and keep summary counts aligned with side-effects output.
        high_impact_files: Set[str] = set()
        risk_domains: Set[str] = set()
        side_effect_files: Set[str] = set()

        if include_dataflow:
            for sfx in sidefx:
                file_part = sfx.split(":", 1)[0].strip()
                if file_part:
                    side_effect_files.add(file_part)
                if "(HIGH)" in sfx:
                    high_impact_files.add(file_part)

                # Dynamic domain inference from detected side-effect labels.
                for label in self._extract_side_effect_labels(sfx):
                    risk_domains.add(self._normalize_risk_domain(label))
            high_impact = len(high_impact_files)
        else:
            high_impact = sum(1 for m in caller_meta if m.get("confidence") == "HIGH")

        all_affected_paths = set(direct_files).union(set(impacted_files.keys()))
        all_affected_names = {Path(p).name for p in all_affected_paths if p}
        files_affected = len(all_affected_names.union(side_effect_files)) if include_dataflow else len(all_affected_names)
        potential_breaks = files_affected

        lines.append("")
        
        # Build intelligent summary with context
        if risk_domains:
            domain_str = " + ".join(sorted(risk_domains))
            summary_line = f"Summary: {files_affected} files | {high_impact} \033[92mHIGH IMPACT\033[0m | {domain_str} at \033[92mrisk\033[0m"
            risk_msg = f"[!] \033[92mHIGH RISK\033[0m: Changing \033[94m{function_name}\033[0m() can break {domain_str.lower()}."
        else:
            summary_line = f"Summary: {files_affected} files affected | {high_impact} high impact | {potential_breaks} potential breaks"
            risk_msg = f"[!] Changing \033[94m{function_name}\033[0m() may break downstream behavior."

        # Explicit production-risk classification for safer release decisions.
        domain_count = len(risk_domains)
        risk_tier = "LOW"
        if high_impact >= 8 or (high_impact >= 6 and files_affected >= 10):
            risk_tier = "PRODUCTION-CRITICAL"
        elif high_impact >= 4 or domain_count >= 3:
            risk_tier = "HIGH"
        elif high_impact >= 1 or domain_count >= 1:
            risk_tier = "MEDIUM"
        
        lines.append(summary_line)
        lines.append(f"Risk Tier: {risk_tier}")

        if potential_breaks > 0:
            lines.append(risk_msg)
        else:
            lines.append("No callers found in index; likely low-risk signature change.")

        return "\n".join(lines)

    def _collect_direct_callers(
        self,
        tree: CodebaseTree,
        function_lower: str,
        file_hint: Optional[str],
    ) -> Tuple[List[str], List[Dict[str, str]]]:
        caller_lines: List[str] = []
        caller_meta: List[Dict[str, str]] = []
        seen: Set[str] = set()

        # High confidence: from call_graph edges.
        for entry in tree.call_graph:
            if " -> " not in entry:
                continue
            src, targets_str = entry.split(" -> ", 1)
            src_stem, _, src_func = src.partition(".")
            for target in targets_str.split(", "):
                t_stem, _, t_func = target.partition(".")
                if t_func.lower() != function_lower:
                    continue
                if file_hint and file_hint.lower() not in t_stem.lower():
                    continue

                src_path = self._resolve_tree_file_by_stem(tree, src_stem)
                if not src_path:
                    continue
                line_range = self._lookup_symbol_line_range(tree, src_path, src_func)
                suffix = f" [L{line_range}]" if line_range else ""
                key = f"{src_path}:{src_func}"
                if key in seen:
                    continue
                seen.add(key)
                caller_lines.append(
                    f"  - {Path(src_path).name} -> {src_func}(){suffix} [HIGH]"
                )
                caller_meta.append(
                    {
                        "caller_file": src_path,
                        "caller_symbol": src_func,
                        "confidence": "HIGH",
                    }
                )

        # Medium confidence: reverse call lines from skeleton text.
        reverse_calls = self._build_reverse_call_graph(tree)
        for label in reverse_calls.get(function_lower, []):
            clean = label.strip()
            # format: file.py -> symbol() [Lx-y]
            if "->" in clean:
                left, right = [p.strip() for p in clean.split("->", 1)]
                file_name = left
                symbol = right.split("(", 1)[0].strip()
            else:
                file_name = clean.split()[0]
                symbol = "callsite"

            src_path = self._resolve_tree_file_by_name(tree, file_name)
            if not src_path:
                continue
            if file_hint and file_hint.lower() not in file_name.lower():
                # file_hint points to callee file, not caller; keep this row.
                pass
            key = f"{src_path}:{symbol}"
            if key in seen:
                continue
            seen.add(key)
            caller_lines.append(f"  - {Path(src_path).name} -> {symbol}() [MED]")
            caller_meta.append(
                {
                    "caller_file": src_path,
                    "caller_symbol": symbol,
                    "confidence": "MED",
                }
            )

        # Low confidence: mention scan fallback.
        for path, node in tree.nodes.items():
            if function_lower not in node.skeleton_text.lower():
                continue
            key = f"{path}:mention"
            if key in seen:
                continue
            seen.add(key)
            caller_lines.append(f"  - {Path(path).name} (symbol mention) [LOW]")
            caller_meta.append(
                {
                    "caller_file": path,
                    "caller_symbol": "mention",
                    "confidence": "LOW",
                }
            )

        return caller_lines, caller_meta

    def _expand_indirect_file_impact(
        self,
        tree: CodebaseTree,
        caller_meta: List[Dict[str, str]],
        depth: int,
    ) -> Dict[str, int]:
        impacted_hops: Dict[str, int] = {}
        frontier: Set[str] = {m["caller_file"] for m in caller_meta if m.get("caller_file") in tree.nodes}
        for src in frontier:
            impacted_hops[src] = 1

        for hop in range(2, depth + 1):
            next_frontier: Set[str] = set()
            for file_path in frontier:
                node = tree.nodes.get(file_path)
                if not node:
                    continue
                neighbors = set(node.imported_by or []) | set(node.connections or [])
                for nxt in neighbors:
                    if nxt not in tree.nodes or nxt in impacted_hops:
                        continue
                    impacted_hops[nxt] = hop
                    next_frontier.add(nxt)
            frontier = next_frontier
            if not frontier:
                break

        return impacted_hops

    def _build_dataflow_summary(
        self,
        tree: CodebaseTree,
        function_lower: str,
        file_hint: Optional[str],
    ) -> List[str]:
        import re as _re

        rows: List[str] = []
        for path, node in tree.nodes.items():
            text = node.skeleton_text
            if function_lower not in text.lower() and (file_hint and file_hint.lower() not in path.lower()):
                continue

            configs = _re.findall(r"CONST:([A-Z][A-Z0-9_]{2,})", text)
            classes = _re.findall(r"CLASS:([A-Za-z_][A-Za-z0-9_]*)", text)
            state_writes = _re.findall(r"\b(?:state|self)\.([A-Za-z_][A-Za-z0-9_]*)", text)

            parts: List[str] = []
            if configs:
                parts.append("configs=" + ",".join(list(dict.fromkeys(configs))[:4]))
            if classes:
                parts.append("classes=" + ",".join(list(dict.fromkeys(classes))[:4]))
            if state_writes:
                parts.append("state=" + ",".join(list(dict.fromkeys(state_writes))[:6]))
            if parts:
                rows.append(f"{Path(path).name}: " + " | ".join(parts))

        return rows

    def _detect_side_effects(
        self,
        tree: CodebaseTree,
        function_lower: str,
        file_hint: Optional[str],
    ) -> List[str]:
        effects: List[str] = []
        checks = self._load_side_effect_rules(tree.root_path)

        for path, node in tree.nodes.items():
            text = node.skeleton_text.lower()
            if function_lower not in text and (file_hint and file_hint.lower() not in path.lower()):
                continue
            matched = []
            for label, needles in checks:
                if any(n in text for n in needles):
                    matched.append(label)
            if matched:
                conf = "HIGH" if len(matched) >= 2 else "MED"
                effects.append(f"{Path(path).name}: {', '.join(matched)} ({conf})")

        return effects

    def _load_side_effect_rules(self, root_path: str) -> List[Tuple[str, Tuple[str, ...]]]:
        """Load side-effect detection rules from config with sane defaults.

        Optional file: .contexly/risk_rules.json
        Shape:
            {
              "effect_rules": [
                {"label": "queue", "keywords": ["kafka", "rabbitmq"]}
              ]
            }
        """
        default_rules: List[Tuple[str, Tuple[str, ...]]] = [
            ("database", ("db.", "sqlite", "postgres", "mysql", "mongodb")),
            ("api", ("aiohttp", "requests", "httpx", "fetch(", "websocket", "api")),
            ("telegram", ("telegram", "send_telegram", "notify_")),
            ("file-write", ("open(", "write(", "json.dump", "path(", "to_csv")),
            ("blockchain", ("web3", "contract", "tx", "polygon", "nonce")),
        ]

        cfg_path = Path(root_path) / ".contexly" / "risk_rules.json"
        if not cfg_path.exists():
            return default_rules

        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
            rows = data.get("effect_rules", [])
            loaded: List[Tuple[str, Tuple[str, ...]]] = []
            for row in rows:
                label = str(row.get("label", "")).strip().lower()
                kws = row.get("keywords", [])
                if not label or not isinstance(kws, list):
                    continue
                keywords = tuple(str(k).strip().lower() for k in kws if str(k).strip())
                if keywords:
                    loaded.append((label, keywords))
            return loaded or default_rules
        except Exception:
            return default_rules

    def _extract_side_effect_labels(self, sidefx_row: str) -> List[str]:
        """Parse labels from a side-effect output row.

        Example row: "trade_executor.py: api, blockchain (HIGH)"
        Returns: ["api", "blockchain"]
        """
        if ":" not in sidefx_row:
            return []
        _, rhs = sidefx_row.split(":", 1)
        rhs = rhs.rsplit("(", 1)[0].strip()
        return [p.strip().lower() for p in rhs.split(",") if p.strip()]

    def _normalize_risk_domain(self, label: str) -> str:
        """Normalize effect label into display-friendly risk domain."""
        cleaned = label.replace("_", " ").replace("-", " ").strip()
        if not cleaned:
            return "Unknown"
        return " ".join(part.capitalize() for part in cleaned.split())

    def _build_call_paths(
        self,
        tree: CodebaseTree,
        target_function: str,
        file_hint: Optional[str],
        depth: int = 2,
    ) -> List[str]:
        """Build complete call chains to the target function from entry points.
        
        Returns list of call paths like: "main.py:main() -> round_manager.py:run_round() -> run_coin_round()"
        """
        paths = []
        visited_chains = set()
        
        # Get direct callers
        caller_lines, caller_meta = self._collect_direct_callers(tree, target_function, file_hint)
        
        if not caller_meta:
            return paths
        
        # Determine target file from file_hint or first caller's file
        if file_hint:
            target_file = Path(file_hint).name
        else:
            # Try to find the target file from caller files - usually all callers are in same file
            target_files = {Path(meta["caller_file"]).name for meta in caller_meta if meta.get("caller_file")}
            target_file = list(target_files)[0] if target_files else "unknown"
        
        # For each direct caller, trace back to entry points
        for meta in caller_meta[:4]:  # Limit to top 4 callers
            caller_file = meta.get("caller_file", "").strip()
            caller_func = meta.get("caller_symbol", "").strip()
            if not caller_func:
                continue
            
            file_name = Path(caller_file).name if caller_file else "unknown"
            
            # Find who calls this caller
            parents = self._find_caller_chain(tree, caller_func, max_depth=2)
            
            # Build chains from parents
            if parents:
                for parent_chain in parents[:2]:
                    # parent_chain format: "file.py:func()"
                    full_chain = f"{parent_chain} -> {file_name}:{caller_func}() -> {target_file}:{target_function}()"
                    if full_chain not in visited_chains:
                        visited_chains.add(full_chain)
                        paths.append(full_chain)
            else:
                # No parent found, direct call
                chain = f"{file_name}:{caller_func}() -> {target_file}:{target_function}()"
                if chain not in visited_chains:
                    visited_chains.add(chain)
                    paths.append(chain)
        
        return paths

    def _find_caller_chain(self, tree: CodebaseTree, func_name: str, max_depth: int = 2) -> List[str]:
        """Find caller chains for a function."""
        chains = []
        func_lower = func_name.lower().strip()
        
        # Look in call_graph for who calls this function
        direct_callers = []
        for entry in tree.call_graph:
            if " -> " not in entry:
                continue
            src, targets_str = entry.split(" -> ", 1)
            src_stem, _, src_func = src.partition(".")
            
            for target in targets_str.split(", "):
                t_stem, _, t_func = target.partition(".")
                if t_func.lower() == func_lower:
                    # Find full path for src_stem
                    src_path = self._resolve_tree_file_by_stem(tree, src_stem)
                    if src_path:
                        src_file = Path(src_path).name
                        direct_callers.append((src_file, src_func))
        
        if not direct_callers:
            return []
        
        # Return first direct caller as chain starter
        src_file, src_func = direct_callers[0]
        chain = f"{src_file}:{src_func}()"
        chains.append(chain)
        
        return chains

    def _resolve_tree_file_by_stem(self, tree: CodebaseTree, stem: str) -> str:
        for path in tree.nodes:
            if Path(path).stem == stem:
                return path
        return ""

    def _resolve_tree_file_by_name(self, tree: CodebaseTree, name: str) -> str:
        for path in tree.nodes:
            if Path(path).name == name:
                return path
        return ""

    def _build_reverse_call_graph(self, tree: CodebaseTree) -> Dict[str, List[str]]:
        """
        Build reverse caller map from skeleton text lines.

        Output shape:
            {
                "execute_trade": [
                    "  round_manager.py -> run_coin_round()",
                ]
            }
        """
        reverse: Dict[str, List[str]] = {}

        for path, node in tree.nodes.items():
            current_symbol: Optional[str] = None
            current_line_range: str = ""
            for raw_line in node.skeleton_text.splitlines():
                line = raw_line.strip()
                if not line:
                    continue

                # Function header lines look like:
                #   run_round()[120-180]
                #   ~run_coin_round()[40-90]
                if line.endswith("]") and "(" in line and ")[" in line:
                    head = line.split("(", 1)[0].lstrip("~").strip()
                    if head and not head.startswith((">", "?", "<", "!", "=", "NOTE", "&", "@", "%")):
                        current_symbol = head
                        range_part = line.split("[", 1)[1][:-1] if "[" in line else ""
                        current_line_range = range_part
                    continue

                if not line.startswith(">"):
                    continue

                call_expr = line[1:].strip()
                called = call_expr.split("(", 1)[0].split(".")[-1].strip().lower()
                if not called:
                    continue

                caller_file = Path(path).name
                if current_symbol:
                    line_suffix = f" [L{current_line_range}]" if current_line_range else ""
                    caller_label = f"  {caller_file} -> {current_symbol}(){line_suffix}"
                else:
                    caller_label = f"  {caller_file} (callsite)"

                bucket = reverse.setdefault(called, [])
                if caller_label not in bucket:
                    bucket.append(caller_label)

        return reverse

    def _lookup_symbol_line_range(
        self,
        tree: CodebaseTree,
        file_name: str,
        symbol_name: str,
    ) -> str:
        """Find line range for a symbol from node.main_functions."""
        node = None
        for path, n in tree.nodes.items():
            if Path(path).name == file_name or Path(path).stem == Path(file_name).stem:
                node = n
                break
        if not node:
            return ""

        for entry in node.main_functions or []:
            name = entry.split("[", 1)[0]
            if name == symbol_name and "[" in entry and entry.endswith("]"):
                return entry.split("[", 1)[1][:-1]
        return ""

    def _score_functions(self, node: "TreeNode") -> List[tuple]:
        """Return (func_name, line_range, score) sorted by score desc."""
        scored = []
        for entry in node.main_functions or []:
            name = entry.split("[")[0]
            lr = entry[len(name):]
            skel_lower = node.skeleton_text.lower()
            score = (
                skel_lower.count(name.lower()) * 3
                + (5 if "async" in skel_lower[:skel_lower.find(name.lower()) + 50] else 0)
                + (3 if "state" in name.lower() or "execute" in name.lower() else 0)
            )
            scored.append((name, lr, score))
        scored.sort(key=lambda x: -x[2])
        return scored

    def _node_strength_score(self, node: "TreeNode") -> float:
        """Compute a lightweight strength score used by --min-score tree filtering."""
        score = 0.0
        score += min(len(node.main_functions or []), 5) * 0.8
        score += min(len(node.connections or []), 5) * 0.5
        score += min(len(node.imported_by or []), 5) * 0.5

        tags = self._compute_tags(node)
        if "#complex" in tags:
            score += 1.2
        if "#state-heavy" in tags:
            score += 1.0
        if "#api-call" in tags or "#blockchain" in tags:
            score += 0.8
        if node.role in ("ENTRY", "CORE"):
            score += 0.8
        return round(score, 2)

    def filter_by_min_score(self, tree: CodebaseTree, min_score: float) -> CodebaseTree:
        """Return a filtered tree keeping files with score >= min_score."""
        if min_score <= 0:
            return tree

        keep_paths = {
            path
            for path, node in tree.nodes.items()
            if self._node_strength_score(node) >= min_score or node.role == "ENTRY"
        }
        if not keep_paths:
            keep_paths = set(tree.entry_files[:1]) or set(list(tree.nodes.keys())[:1])

        filtered_nodes: Dict[str, TreeNode] = {}
        import copy
        for path in keep_paths:
            if path not in tree.nodes:
                continue
            n = copy.copy(tree.nodes[path])
            n.connections = [c for c in n.connections if c in keep_paths]
            n.imported_by = [i for i in n.imported_by if i in keep_paths]
            filtered_nodes[path] = n

        return CodebaseTree(
            root_path=tree.root_path,
            nodes=filtered_nodes,
            total_tokens=sum(n.token_estimate for n in filtered_nodes.values()),
            raw_token_estimate=tree.raw_token_estimate,
            file_count=len(filtered_nodes),
            reduction_percent=tree.reduction_percent,
            entry_files=[p for p in tree.entry_files if p in filtered_nodes],
            orphan_files=[p for p in tree.orphan_files if p in filtered_nodes],
            state_summaries=[s for s in tree.state_summaries if s.get("path") in filtered_nodes],
            project_summary=tree.project_summary,
            core_strategy=tree.core_strategy,
            state_management=tree.state_management,
            call_graph=tree.call_graph,
        )

    def _compute_tags(self, node: "TreeNode") -> List[str]:
        """Derive searchable tags from skeleton content and node metadata."""
        tags: List[str] = []
        skel = node.skeleton_text.lower()
        if "async def" in skel or "asyncio" in skel:
            tags.append("#async")
        if "aiohttp" in skel or "requests" in skel or "httpx" in skel:
            tags.append("#api-call")
        if "rate_limit" in skel or "ratelimit" in skel or "retry" in skel:
            tags.append("#rate-limit")
        if "clob" in skel:
            tags.append("#clob")
        if "polymarket" in skel:
            tags.append("#polymarket")
        if "hedge" in skel or "hedging" in skel or "pivot" in skel:
            tags.append("#hedging")
        if "webhook" in skel:
            tags.append("#webhook")
        if "telegram" in skel or "send_telegram" in skel or "notify_" in skel:
            tags.append("#telegram")
        if "state." in skel or "self.state" in skel:
            tags.append("#state-heavy")
        if "web3" in skel or "contract" in skel or "polygon" in skel:
            tags.append("#blockchain")
        if "class=" in skel or "id=" in skel or "data-" in skel:
            tags.append("#frontend")
        if "html_role_hints" in skel or "external_libs" in skel:
            tags.append("#frontend")
        if any(token in skel for token in ("three.js", "gsap", "canvas", "graph", "renderer", "particle")):
            tags.append("#visualization")
        if any(token in skel for token in ("modal", "dialog", "drawer", "sidebar", "panel", "widget")):
            tags.append("#ui-shell")
        if any(token in skel for token in ("onclick", "oninput", "onchange", "event listener", "addEventListener")):
            tags.append("#interactive")
        if "tailwind" in skel or "bg-" in skel or "text-" in skel or "px-" in skel:
            tags.append("#tailwind")
        if "css" in skel or "selector" in skel or "style" in skel:
            tags.append("#css")
        if "&decisions:" in skel:
            cond_count = skel.count("â€¢ ")
            if cond_count >= 10:
                tags.append("#complex")
            elif cond_count >= 5:
                tags.append("#moderate")
        if node.role == "LEGACY":
            tags.append("#legacy")
        if node.warnings:
            tags.append("#has-warnings")
        return list(dict.fromkeys(tags))

    def get_relevant_chunk(
        self,
        tree: CodebaseTree,
        query: str,
        max_tokens: int = 8000,
        level: int = 2,
    ) -> str:
        """
        Get only the relevant subset of the tree for a given query.
        Uses search_index() for scoring, then builds targeted tree.

        level controls output detail (0=map, 1=index, 2=full skeleton).
        """
        scored = self.search_index(tree, query, top_k=10)
        seed_files = [r["path"] for r in scored if r["confidence"] in ("HIGH", "MED")]

        if not seed_files and scored:
            seed_files = [scored[0]["path"]]

        if not seed_files:
            return f"No relevant files found for query: {query}"

        # Use targeted_tree to auto-expand via connections
        targeted = self.get_targeted_tree(tree, seed_files, depth=1, level=level)

        # Prepend search summary
        header_lines = [
            f"=== RELEVANT CHUNK: '{query}' ===",
            "Top matches:",
        ]
        for r in scored[:5]:
            fname = Path(r["path"]).name
            funcs = ", ".join(r["matched_functions"][:3]) if r["matched_functions"] else "â€”"
            tags = " ".join(r["matched_tags"][:3]) if r["matched_tags"] else ""
            header_lines.append(
                f"  {r['confidence']:<4} {fname:<40} score={r['score']} funcs=[{funcs}] {tags}"
            )
        header_lines.append("")

        return "\n".join(header_lines) + targeted

    def _find_connections(
        self,
        imports: List[str],
        all_paths: List[str],
        current_path: Optional[str] = None,
        aliases: Optional[Dict[str, str]] = None,
    ) -> List[str]:
        """
        Find which other project files this file imports.

        Supports:
        - Python imports: from x import y / import x
        - JS/TS imports: import ... from "...", import "...", require("...")
        - Relative module paths: ./foo, ../bar/baz
        """
        from pathlib import Path as _Path

        def _norm(path: str) -> str:
            return path.replace("\\", "/")

        # Build normalized path indexes for exact/suffix matching.
        norm_to_orig: Dict[str, str] = {}
        stem_map: Dict[str, str] = {}
        for path in all_paths:
            npath = _norm(path)
            norm_to_orig[npath] = path
            stem = _Path(npath).stem
            stem_map[stem] = path

        supported_exts = (".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".go")
        aliases = aliases or {}

        current_norm = _norm(current_path) if current_path else None
        current_dir = _Path(current_norm).parent.as_posix() if current_norm else ""

        def _resolve_module(module_spec: str) -> Optional[str]:
            module_spec = module_spec.strip().strip(";\"").strip("'")
            if not module_spec:
                return None

            base_candidates: List[str] = []

            if module_spec.startswith(".") and current_dir:
                rel = os.path.normpath(os.path.join(current_dir, module_spec)).replace("\\", "/")
                base_candidates.append(rel)
            else:
                # Alias rewrite (tsconfig/vite): '@/x' -> 'src/x'
                aliased = module_spec
                for alias, target in sorted(aliases.items(), key=lambda kv: -len(kv[0])):
                    if module_spec == alias or module_spec.startswith(alias + "/"):
                        suffix = module_spec[len(alias):].lstrip("/")
                        aliased = f"{target.rstrip('/')}/{suffix}" if suffix else target.rstrip("/")
                        break
                if aliased != module_spec:
                    base_candidates.append(aliased)
                base_candidates.append(module_spec)
                base_candidates.append(module_spec.replace(".", "/"))

            # Prefer exact/relative file resolution.
            for base in base_candidates:
                path_candidates = [base]
                if not base.endswith(supported_exts):
                    path_candidates.extend([f"{base}{ext}" for ext in supported_exts])
                    path_candidates.extend([f"{base}/index{ext}" for ext in supported_exts])

                for cand in path_candidates:
                    cand_norm = _norm(cand)
                    if cand_norm in norm_to_orig:
                        return norm_to_orig[cand_norm]
                    for npath, orig in norm_to_orig.items():
                        if npath.endswith(f"/{cand_norm}"):
                            return orig

            # Fallback: exact stem match (legacy behavior).
            leaf = module_spec.replace(".", "/").split("/")[-1]
            if leaf in stem_map:
                return stem_map[leaf]

            return None

        connections = []
        seen_paths: Set[str] = set()

        for imp in imports:
            imp = imp.strip()
            module = None

            if imp.startswith("from "):
                parts = imp.split()
                if len(parts) >= 2:
                    # Python style: from pkg.module import x
                    module = parts[1]
            elif imp.startswith("import "):
                # Python-style only (exclude JS/TS forms like: import x from '...').
                if " from " not in imp and "'" not in imp and '"' not in imp:
                    rest = imp[7:]  # strip "import "
                    # Python: import a.b as c / import a, b
                    module = rest.split(" as ")[0].split(",")[0].strip()

            # JS/TS style imports and requires.
            if not module:
                m = re.search(r"export\s+.*?from\s+['\"]([^'\"]+)['\"]", imp)
                if not m:
                    m = re.search(r"export\s*\{[^}]*\}\s*from\s+['\"]([^'\"]+)['\"]", imp)
                if not m:
                    m = re.search(r"from\s+['\"]([^'\"]+)['\"]", imp)
                if not m:
                    m = re.search(r"import\s+['\"]([^'\"]+)['\"]", imp)
                if not m:
                    m = re.search(r"require\(\s*['\"]([^'\"]+)['\"]\s*\)", imp)
                if m:
                    module = m.group(1)

            resolved = _resolve_module(module) if module else None
            if resolved and resolved not in seen_paths:
                connections.append(resolved)
                seen_paths.add(resolved)

        return connections

    def _load_module_aliases(self, root_path: str) -> Dict[str, str]:
        """Load module aliases from tsconfig.json and vite.config.ts/js when present."""
        aliases: Dict[str, str] = {}
        root = Path(root_path)

        def norm_rel(path_str: str) -> str:
            path_str = path_str.replace("\\", "/").strip()
            path_str = path_str.strip('"\'')
            path_str = path_str.replace("./", "")
            return path_str.rstrip("/")

        # tsconfig paths
        tsconfig = root / "tsconfig.json"
        if tsconfig.exists():
            try:
                raw = tsconfig.read_text(encoding="utf-8", errors="ignore")
                raw = re.sub(r"/\*.*?\*/", "", raw, flags=re.S)
                raw = re.sub(r"(^|\s)//.*", "", raw)
                data = json.loads(raw)
                compiler = data.get("compilerOptions", {})
                base_url = norm_rel(str(compiler.get("baseUrl", "")))
                for key, targets in compiler.get("paths", {}).items():
                    if not targets:
                        continue
                    alias_key = key.replace("/*", "").rstrip("/")
                    target = str(targets[0]).replace("/*", "")
                    target = norm_rel(target)
                    if base_url and not target.startswith(base_url):
                        target = f"{base_url}/{target}".strip("/")
                    aliases[alias_key] = target.strip("/")
            except Exception:
                pass

        # vite alias (best-effort regex)
        for vite_name in ("vite.config.ts", "vite.config.js"):
            vite_cfg = root / vite_name
            if not vite_cfg.exists():
                continue
            try:
                raw = vite_cfg.read_text(encoding="utf-8", errors="ignore")
                # Object style: '@': '/src' or '@': './src'
                for m in re.finditer(r"['\"](@[^'\"]*)['\"]\s*:\s*['\"]([^'\"]+)['\"]", raw):
                    aliases[m.group(1)] = norm_rel(m.group(2))
                # Array style: { find: '@', replacement: '/src' }
                for m in re.finditer(r"find\s*:\s*['\"](@[^'\"]*)['\"].*?replacement\s*:\s*['\"]([^'\"]+)['\"]", raw, flags=re.S):
                    aliases[m.group(1)] = norm_rel(m.group(2))
                # path.resolve(__dirname, './src')
                for m in re.finditer(r"find\s*:\s*['\"](@[^'\"]*)['\"].*?replacement\s*:\s*path\.resolve\(__dirname,\s*['\"]([^'\"]+)['\"]\)", raw, flags=re.S):
                    aliases[m.group(1)] = norm_rel(m.group(2))
            except Exception:
                pass

        # Safe defaults for common setups.
        if "@" not in aliases and (root / "src").exists():
            aliases["@"] = "src"

        return aliases

    def save(self, tree: CodebaseTree, output_path: str):
        """Save tree to JSON file for persistence."""
        data = {
            "root_path": tree.root_path,
            "file_count": tree.file_count,
            "total_tokens": tree.total_tokens,
            "raw_token_estimate": tree.raw_token_estimate,
            "reduction_percent": tree.reduction_percent,
            "entry_files": tree.entry_files,
            "orphan_files": tree.orphan_files,
            "state_summaries": getattr(tree, "state_summaries", []),
            "project_summary": getattr(tree, "project_summary", ""),
            "core_strategy": getattr(tree, "core_strategy", ""),
            "state_management": getattr(tree, "state_management", ""),
            "call_graph": getattr(tree, "call_graph", []),
            "nodes": {
                path: {
                    "path": node.path,
                    "language": node.language,
                    "skeleton_text": node.skeleton_text,
                    "token_estimate": node.token_estimate,
                    "line_range": getattr(node, "line_range", ""),
                    "main_functions": getattr(node, "main_functions", []),
                    "connections": node.connections,
                    "role": node.role,
                    "imported_by": node.imported_by,
                    "is_entry_point": node.is_entry_point,
                    "has_duplicate_funcs": node.has_duplicate_funcs,
                    "warnings": getattr(node, "warnings", []),
                }
                for path, node in tree.nodes.items()
            },
        }
        Path(output_path).write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls, json_path: str) -> CodebaseTree:
        """Load tree from saved JSON file."""
        data = json.loads(Path(json_path).read_text())
        nodes = {
            path: TreeNode(
                path=nd["path"],
                language=nd["language"],
                skeleton_text=nd["skeleton_text"],
                token_estimate=nd["token_estimate"],
                imports=[],
                connections=nd.get("connections", []),
                role=nd.get("role", "UNKNOWN"),
                imported_by=nd.get("imported_by", []),
                is_entry_point=nd.get("is_entry_point", False),
                has_duplicate_funcs=nd.get("has_duplicate_funcs", []),
                line_range=nd.get("line_range", ""),
                main_functions=nd.get("main_functions", []),
                warnings=nd.get("warnings", []),
            )
            for path, nd in data["nodes"].items()
        }
        return CodebaseTree(
            root_path=data["root_path"],
            nodes=nodes,
            total_tokens=data["total_tokens"],
            raw_token_estimate=data["raw_token_estimate"],
            file_count=data["file_count"],
            reduction_percent=data["reduction_percent"],
            entry_files=data.get("entry_files", []),
            orphan_files=data.get("orphan_files", []),
            state_summaries=data.get("state_summaries", []),
            project_summary=data.get("project_summary", ""),
            core_strategy=data.get("core_strategy", ""),
            state_management=data.get("state_management", ""),
            call_graph=data.get("call_graph", []),
        )

