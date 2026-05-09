"""Tests for ContextManager."""

import tempfile
import os
import pytest
from contexly.agent.context_manager import ContextManager, ChunkStatus


def test_add_message_creates_chunk():
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = ContextManager(session_id="test", persist_dir=tmpdir)
        mgr.add_message("user", "Hello")
        assert mgr.current_chunk is not None
        assert len(mgr.current_chunk.messages) == 1


def test_complete_chunk_moves_to_done():
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = ContextManager(session_id="test", persist_dir=tmpdir)
        mgr.add_message("user", "Fix the bug")
        mgr.add_message("assistant", "Fixed it")
        mgr.complete_current_chunk("Fixed the bug in main.py")
        assert mgr.current_chunk is None
        assert len(mgr.chunks) == 1
        assert mgr.chunks[0].status == ChunkStatus.DONE


def test_get_context_for_ai_contains_task():
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = ContextManager(session_id="test", persist_dir=tmpdir)
        mgr.start_task("Fix balance calculation")
        mgr.add_message("user", "The balance is wrong")
        context = mgr.get_context_for_ai()
        assert "Fix balance calculation" in context


def test_session_persists_across_instances():
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr1 = ContextManager(session_id="test", persist_dir=tmpdir)
        mgr1.add_message("user", "Hello world")
        mgr1.complete_current_chunk("Said hello")

        mgr2 = ContextManager(session_id="test", persist_dir=tmpdir)
        assert len(mgr2.chunks) == 1
        assert mgr2.chunks[0].status == ChunkStatus.DONE


def test_export_for_new_ai():
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = ContextManager(session_id="test", persist_dir=tmpdir)
        mgr.start_task("Refactor auth module")
        mgr.add_message("user", "Refactor the auth")
        exported = mgr.export_for_new_ai()
        assert exported["current_task"] == "Refactor auth module"
        assert "recent_messages" in exported

