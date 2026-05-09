"""Tests for Session markdown tracker and context builder."""

from pathlib import Path

from contexly.agent.session import Session
from contexly.core.tree_builder import CodebaseTree, TreeNode


def _sample_tree(root: Path) -> CodebaseTree:
    node = TreeNode(
        path="balance_manager.py",
        language="python",
        skeleton_text=(
            "FILE:balance_manager.py [python]\n"
            "~fetch_usdc_balance()[1-10]\n"
            "  >fetch_usdc_balance()\n"
        ),
        token_estimate=80,
        imports=[],
        connections=[],
        role="CORE",
        imported_by=[],
        is_entry_point=False,
        has_duplicate_funcs=[],
        line_range="1-10",
        main_functions=["fetch_usdc_balance[1-10]"],
        warnings=[],
    )
    return CodebaseTree(
        root_path=str(root),
        nodes={"balance_manager.py": node},
        total_tokens=80,
        raw_token_estimate=320,
        file_count=1,
        reduction_percent=75.0,
        entry_files=[],
        orphan_files=[],
        state_summaries=[],
        project_summary="",
        core_strategy="",
        state_management="",
        call_graph=[],
    )


def test_create_and_update_session(tmp_path):
    sess = Session(str(tmp_path))
    sess.create("Fix Bot")
    sess.update("done", "balance_manager.py fixed")
    sess.update("todo", "Fix trade executor")
    sess.update("in_progress", "market_discovery timeout")

    text = (tmp_path / ".contexly" / "session.md").read_text(encoding="utf-8")
    assert "# Session: Fix Bot" in text
    assert "- DONE: balance_manager.py fixed" in text
    assert "- TODO: Fix trade executor" in text
    assert "- IN_PROGRESS: market_discovery timeout" in text


def test_complete_step_uses_short_rolling_summaries(tmp_path):
    sess = Session(str(tmp_path))
    sess.create("Fix Bot")

    long_summary = "A" * 200
    sess.complete_step(long_summary, "Implement retry and timeout guard for quote fetch")

    text = (tmp_path / ".contexly" / "session.md").read_text(encoding="utf-8")
    assert "- DONE: " in text
    assert ("A" * 130) not in text
    assert "- IN_PROGRESS: Implement retry and timeout guard for quote fetch" in text


def test_build_context_sends_tree_only_once(tmp_path):
    sess = Session(str(tmp_path))
    sess.create("Fix Bot")
    tree = _sample_tree(tmp_path)

    first = sess.build_context(tree, "fix usdc balance")
    second = sess.build_context(tree, "fix usdc balance")

    marker = "=== CODEBASE TREE (FIRST SEND ONLY) ==="
    assert marker in first
    assert marker not in second

    session_text = (tmp_path / ".contexly" / "session.md").read_text(encoding="utf-8")
    assert "tree_sent_once:true" in session_text


def test_build_context_writes_chunk_file(tmp_path):
    sess = Session(str(tmp_path))
    sess.create("Fix Bot")
    tree = _sample_tree(tmp_path)

    _ = sess.build_context(tree, "balance calculation")

    chunks_dir = tmp_path / ".contexly" / "chunks"
    chunk_files = list(chunks_dir.glob("*_chunk.md"))
    assert len(chunk_files) == 1
    assert "balance_calculation_chunk.md" == chunk_files[0].name
