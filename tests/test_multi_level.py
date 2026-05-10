"""Tests for multi-level indexing and smart relevance engine."""

import tempfile
import os
import pytest
from pathlib import Path
from contexly.core.tree_builder import TreeBuilder, CodebaseTree, TreeNode


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  Helpers
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _make_tree(tmp_dir: str) -> "CodebaseTree":
    """Build a small tree from synthetic Python files for testing."""
    # entry: main.py
    (Path(tmp_dir) / "main.py").write_text(
        "import asyncio\nfrom round_manager import run_round\n\n"
        "async def main():\n    await run_round()\n\n"
        "if __name__ == '__main__':\n    asyncio.run(main())\n"
    )
    # core: round_manager.py
    (Path(tmp_dir) / "round_manager.py").write_text(
        "from trade_executor import execute_trade\nfrom config import SETTINGS\n\n"
        "async def run_round():\n    signal = compute_signal()\n"
        "    if signal > 0:\n        await execute_trade('BUY')\n"
        "    elif signal < 0:\n        await execute_trade('SELL')\n\n"
        "def compute_signal():\n    return 1\n"
    )
    # core: trade_executor.py
    (Path(tmp_dir) / "trade_executor.py").write_text(
        "from config import SETTINGS\n\n"
        "async def execute_trade(side):\n    if side not in ('BUY', 'SELL'):\n"
        "        raise ValueError('bad side')\n    return True\n"
    )
    # util: config.py
    (Path(tmp_dir) / "config.py").write_text(
        "SETTINGS = {'rpc': 'http://localhost', 'rate_limit': 10}\n"
        "POLYGON_RPC = 'https://polygon.io'\n"
    )
    builder = TreeBuilder()
    return builder.build(tmp_dir, exclude_roles=[])


def _make_ts_tree(tmp_dir: str) -> "CodebaseTree":
    """Build a small TS tree to verify relative import resolution."""
    (Path(tmp_dir) / "main.ts").write_text(
        "import { helper } from './utils/helper'\n\n"
        "export function run(): number {\n"
        "    return helper()\n"
        "}\n"
    )
    os.makedirs(Path(tmp_dir) / "utils", exist_ok=True)
    (Path(tmp_dir) / "utils" / "helper.ts").write_text(
        "export function helper(): number {\n"
        "    return 1\n"
        "}\n"
    )
    builder = TreeBuilder()
    return builder.build(tmp_dir)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  Level 0 â€” Repo Map
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestRepoMap:
    def test_returns_string(self, tmp_path):
        tree = _make_tree(str(tmp_path))
        builder = TreeBuilder()
        result = builder.to_repo_map(tree)
        assert isinstance(result, str)
        assert len(result) > 50

    def test_contains_repo_name(self, tmp_path):
        tree = _make_tree(str(tmp_path))
        builder = TreeBuilder()
        result = builder.to_repo_map(tree)
        assert tmp_path.name in result

    def test_contains_file_names(self, tmp_path):
        tree = _make_tree(str(tmp_path))
        builder = TreeBuilder()
        result = builder.to_repo_map(tree)
        assert "main.py" in result
        assert "config.py" in result

    def test_contains_role_labels(self, tmp_path):
        tree = _make_tree(str(tmp_path))
        builder = TreeBuilder()
        result = builder.to_repo_map(tree)
        # At least one role label must appear
        assert any(r in result for r in ("ENTRY", "CORE", "UTIL", "ORPHAN"))

    def test_shorter_than_full_tree(self, tmp_path):
        tree = _make_tree(str(tmp_path))
        builder = TreeBuilder()
        map_text = builder.to_repo_map(tree)
        full_text = builder.to_ai_text(tree, level=2)
        assert len(map_text) < len(full_text)


class TestBuildRegressions:
    def test_default_build_keeps_script_or_orphan_files(self, tmp_path):
        (tmp_path / "standalone.js").write_text("console.log('ok')\n")
        builder = TreeBuilder()
        tree = builder.build(str(tmp_path))
        assert tree.file_count >= 1
        assert any(p.endswith("standalone.js") for p in tree.nodes)

    def test_ts_relative_import_connections_resolve(self, tmp_path):
        tree = _make_ts_tree(str(tmp_path))
        assert tree.file_count >= 2

        main_path = next(p for p in tree.nodes if p.endswith("main.ts"))
        helper_path = next(p for p in tree.nodes if p.endswith("helper.ts"))

        assert helper_path in tree.nodes[main_path].connections


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  Level 1 â€” File Index
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestFileIndex:
    def test_returns_string(self, tmp_path):
        tree = _make_tree(str(tmp_path))
        builder = TreeBuilder()
        result = builder.to_index(tree)
        assert isinstance(result, str)

    def test_contains_file_headers(self, tmp_path):
        tree = _make_tree(str(tmp_path))
        builder = TreeBuilder()
        result = builder.to_index(tree)
        assert "FILE:main.py" in result or "main.py" in result

    def test_contains_imports_line(self, tmp_path):
        tree = _make_tree(str(tmp_path))
        builder = TreeBuilder()
        result = builder.to_index(tree)
        assert "IMPORTS:" in result

    def test_no_detailed_conditions(self, tmp_path):
        tree = _make_tree(str(tmp_path))
        builder = TreeBuilder()
        result = builder.to_index(tree)
        # Should NOT include condition details like &DECISIONS
        assert "&DECISIONS" not in result

    def test_shorter_than_level2(self, tmp_path):
        tree = _make_tree(str(tmp_path))
        builder = TreeBuilder()
        index_text = builder.to_index(tree)
        full_text = builder.to_ai_text(tree, level=2)
        assert len(index_text) < len(full_text)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  to_ai_text level dispatch
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestToAiTextLevels:
    def test_level0_calls_repo_map(self, tmp_path):
        tree = _make_tree(str(tmp_path))
        builder = TreeBuilder()
        assert builder.to_ai_text(tree, level=0) == builder.to_repo_map(tree)

    def test_level1_calls_index(self, tmp_path):
        tree = _make_tree(str(tmp_path))
        builder = TreeBuilder()
        assert builder.to_ai_text(tree, level=1) == builder.to_index(tree)

    def test_level2_contains_legend(self, tmp_path):
        tree = _make_tree(str(tmp_path))
        builder = TreeBuilder()
        result = builder.to_ai_text(tree, level=2)
        assert "Legend:" in result

    def test_level3_contains_project_context(self, tmp_path):
        tree = _make_tree(str(tmp_path))
        tree.project_summary = "Test project description"
        builder = TreeBuilder()
        result = builder.to_ai_text(tree, level=3)
        assert "Test project description" in result


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  Search Index
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestSearchIndex:
    def test_returns_list(self, tmp_path):
        tree = _make_tree(str(tmp_path))
        builder = TreeBuilder()
        results = builder.search_index(tree, "execute trade")
        assert isinstance(results, list)

    def test_top_k_respected(self, tmp_path):
        tree = _make_tree(str(tmp_path))
        builder = TreeBuilder()
        results = builder.search_index(tree, "config settings", top_k=2)
        assert len(results) <= 2

    def test_result_has_required_keys(self, tmp_path):
        tree = _make_tree(str(tmp_path))
        builder = TreeBuilder()
        results = builder.search_index(tree, "execute trade")
        if results:
            r = results[0]
            assert "path" in r
            assert "score" in r
            assert "confidence" in r
            assert r["confidence"] in ("HIGH", "MED", "LOW")

    def test_trade_executor_scores_high_for_execute(self, tmp_path):
        tree = _make_tree(str(tmp_path))
        builder = TreeBuilder()
        results = builder.search_index(tree, "execute trade", top_k=5)
        paths = [Path(r["path"]).name for r in results]
        assert any("trade" in p or "executor" in p for p in paths)

    def test_config_scores_high_for_rate_limit(self, tmp_path):
        tree = _make_tree(str(tmp_path))
        builder = TreeBuilder()
        results = builder.search_index(tree, "rate limit settings", top_k=5)
        paths = [Path(r["path"]).name for r in results]
        assert "config.py" in paths

    def test_empty_query_returns_results(self, tmp_path):
        tree = _make_tree(str(tmp_path))
        builder = TreeBuilder()
        results = builder.search_index(tree, "", top_k=5)
        # Empty query may return 0 results â€” should not raise
        assert isinstance(results, list)

    def test_results_sorted_by_score_desc(self, tmp_path):
        tree = _make_tree(str(tmp_path))
        builder = TreeBuilder()
        results = builder.search_index(tree, "trade execute round", top_k=5)
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_stopwords_filtered(self, tmp_path):
        tree = _make_tree(str(tmp_path))
        builder = TreeBuilder()
        noisy = builder.search_index(tree, "fix trade execution not working", top_k=5)
        clean = builder.search_index(tree, "trade execution", top_k=5)
        assert noisy
        assert clean
        assert noisy[0]["path"] == clean[0]["path"]

    def test_legacy_role_penalty(self):
        builder = TreeBuilder()
        core_node = TreeNode(
            path="core.py",
            language="python",
            skeleton_text="FILE:core.py\nexecute_trade()[1-10]\n  >execute_trade()",
            token_estimate=30,
            imports=[],
            connections=[],
            role="CORE",
            imported_by=[],
            is_entry_point=False,
            has_duplicate_funcs=[],
            main_functions=["execute_trade[1-10]"],
        )
        legacy_node = TreeNode(
            path="legacy.py",
            language="python",
            skeleton_text="FILE:legacy.py\nexecute_trade()[1-10]\n  >execute_trade()",
            token_estimate=30,
            imports=[],
            connections=[],
            role="LEGACY",
            imported_by=[],
            is_entry_point=False,
            has_duplicate_funcs=[],
            main_functions=["execute_trade[1-10]"],
        )
        tree = CodebaseTree(
            root_path=".",
            nodes={"core.py": core_node, "legacy.py": legacy_node},
            total_tokens=60,
            raw_token_estimate=120,
            file_count=2,
            reduction_percent=50.0,
            entry_files=[],
            orphan_files=[],
        )

        results = builder.search_index(tree, "execute trade", top_k=2)
        assert results[0]["path"] == "core.py"


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  Targeted Tree
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestGetTargetedTree:
    def test_returns_string(self, tmp_path):
        tree = _make_tree(str(tmp_path))
        builder = TreeBuilder()
        result = builder.get_targeted_tree(tree, ["main.py"], depth=0)
        assert isinstance(result, str)

    def test_depth0_only_seed(self, tmp_path):
        tree = _make_tree(str(tmp_path))
        builder = TreeBuilder()
        result = builder.get_targeted_tree(tree, ["config.py"], depth=0)
        assert "config.py" in result
        # At depth=0, round_manager should NOT be included
        assert "round_manager.py" not in result

    def test_depth1_expands_connections(self, tmp_path):
        tree = _make_tree(str(tmp_path))
        builder = TreeBuilder()
        result = builder.get_targeted_tree(tree, ["main.py"], depth=1)
        # main.py imports round_manager â†’ should appear
        assert "round_manager" in result

    def test_unknown_seed_returns_error(self, tmp_path):
        tree = _make_tree(str(tmp_path))
        builder = TreeBuilder()
        result = builder.get_targeted_tree(tree, ["nonexistent.py"], depth=1)
        assert "No files matched" in result

    def test_stem_matching_works(self, tmp_path):
        """Seeds can be given as stem (no extension)."""
        tree = _make_tree(str(tmp_path))
        builder = TreeBuilder()
        result = builder.get_targeted_tree(tree, ["config"], depth=0)
        assert "config" in result

    def test_header_shows_depth(self, tmp_path):
        tree = _make_tree(str(tmp_path))
        builder = TreeBuilder()
        result = builder.get_targeted_tree(tree, ["main.py"], depth=2)
        assert "depth=2" in result

    def test_auto_exclude_legacy_during_expansion(self):
        builder = TreeBuilder()
        entry = TreeNode(
            path="main.py",
            language="python",
            skeleton_text="FILE:main.py\nmain()[1-10]",
            token_estimate=20,
            imports=[],
            connections=["legacy.py"],
            role="ENTRY",
            imported_by=[],
            is_entry_point=True,
            has_duplicate_funcs=[],
            main_functions=["main[1-10]"],
        )
        legacy = TreeNode(
            path="legacy.py",
            language="python",
            skeleton_text="FILE:legacy.py\nold_flow()[1-10]",
            token_estimate=20,
            imports=[],
            connections=[],
            role="LEGACY",
            imported_by=["main.py"],
            is_entry_point=False,
            has_duplicate_funcs=[],
            main_functions=["old_flow[1-10]"],
        )
        tree = CodebaseTree(
            root_path=".",
            nodes={"main.py": entry, "legacy.py": legacy},
            total_tokens=40,
            raw_token_estimate=80,
            file_count=2,
            reduction_percent=50.0,
            entry_files=["main.py"],
            orphan_files=[],
        )

        result = builder.get_targeted_tree(
            tree,
            ["main.py"],
            depth=1,
            level=1,
            auto_exclude_legacy=True,
        )
        assert "legacy.py" not in result


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  Impact Preview
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestGetImpactPreview:
    def test_returns_string(self, tmp_path):
        tree = _make_tree(str(tmp_path))
        builder = TreeBuilder()
        result = builder.get_impact_preview(tree, "execute_trade")
        assert isinstance(result, str)

    def test_header_contains_function_name(self, tmp_path):
        tree = _make_tree(str(tmp_path))
        builder = TreeBuilder()
        result = builder.get_impact_preview(tree, "execute_trade")
        assert "execute_trade" in result

    def test_unknown_function_safe_message(self, tmp_path):
        tree = _make_tree(str(tmp_path))
        builder = TreeBuilder()
        result = builder.get_impact_preview(tree, "totally_nonexistent_func_xyz")
        assert "No callers found" in result or "safe to modify" in result

    def test_file_hint_respected(self, tmp_path):
        tree = _make_tree(str(tmp_path))
        builder = TreeBuilder()
        result = builder.get_impact_preview(tree, "execute_trade", file_hint="trade_executor")
        assert "execute_trade" in result

    def test_reverse_call_graph_detects_callers(self):
        builder = TreeBuilder()
        caller = TreeNode(
            path="caller.py",
            language="python",
            skeleton_text="FILE:caller.py\nrun_round()[1-10]\n  >calculate_balance()",
            token_estimate=20,
            imports=[],
            connections=[],
            role="CORE",
            imported_by=[],
            is_entry_point=False,
            has_duplicate_funcs=[],
            main_functions=["run_round[1-10]"],
        )
        callee = TreeNode(
            path="balance.py",
            language="python",
            skeleton_text="FILE:balance.py\ncalculate_balance()[1-10]",
            token_estimate=20,
            imports=[],
            connections=[],
            role="CORE",
            imported_by=[],
            is_entry_point=False,
            has_duplicate_funcs=[],
            main_functions=["calculate_balance[1-10]"],
        )
        tree = CodebaseTree(
            root_path=".",
            nodes={"caller.py": caller, "balance.py": callee},
            total_tokens=40,
            raw_token_estimate=80,
            file_count=2,
            reduction_percent=50.0,
            entry_files=[],
            orphan_files=[],
            call_graph=[],
        )

        result = builder.get_impact_preview(tree, "calculate_balance")
        assert "caller.py" in result

    def test_impact_includes_line_hints_from_call_graph(self):
        builder = TreeBuilder()
        caller = TreeNode(
            path="round_manager.py",
            language="python",
            skeleton_text="FILE:round_manager.py\nrun_round()[10-20]\n  >execute_trade()",
            token_estimate=20,
            imports=[],
            connections=[],
            role="CORE",
            imported_by=[],
            is_entry_point=False,
            has_duplicate_funcs=[],
            line_range="10-20",
            main_functions=["run_round[10-20]"],
        )
        callee = TreeNode(
            path="trade_executor.py",
            language="python",
            skeleton_text="FILE:trade_executor.py\nexecute_trade()[1-5]",
            token_estimate=20,
            imports=[],
            connections=[],
            role="CORE",
            imported_by=[],
            is_entry_point=False,
            has_duplicate_funcs=[],
            line_range="1-5",
            main_functions=["execute_trade[1-5]"],
        )
        tree = CodebaseTree(
            root_path=".",
            nodes={"round_manager.py": caller, "trade_executor.py": callee},
            total_tokens=40,
            raw_token_estimate=80,
            file_count=2,
            reduction_percent=50.0,
            entry_files=[],
            orphan_files=[],
            call_graph=["round_manager.run_round -> trade_executor.execute_trade"],
        )

        result = builder.get_impact_preview(tree, "execute_trade")
        assert "[L10-20]" in result


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  Compute Tags helper
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestComputeTags:
    def test_async_tag(self, tmp_path):
        tree = _make_tree(str(tmp_path))
        builder = TreeBuilder()
        for path, node in tree.nodes.items():
            if "async def" in node.skeleton_text:
                tags = builder._compute_tags(node)
                assert "#async" in tags
                break

    def test_no_crash_on_empty_skeleton(self):
        builder = TreeBuilder()
        node = TreeNode(
            path="x.py", language="python", skeleton_text="", token_estimate=0,
            imports=[], connections=[], role="UTIL", imported_by=[],
            is_entry_point=False, has_duplicate_funcs=[],
        )
        tags = builder._compute_tags(node)
        assert isinstance(tags, list)

