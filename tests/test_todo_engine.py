"""Tests for TodoEngine."""

import tempfile
import pytest
from contexly.agent.todo_engine import TodoEngine, TodoStatus


def test_add_and_retrieve():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = TodoEngine(session_id="test", persist_dir=tmpdir)
        todo_id = engine.add("Fix the login bug", file_hint="auth.py", line_hint=42)
        assert todo_id is not None
        assert len(engine.items) == 1
        assert engine.items[0].description == "Fix the login bug"


def test_start_and_complete():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = TodoEngine(session_id="test", persist_dir=tmpdir)
        todo_id = engine.add("Write tests")
        engine.start_item(todo_id)
        assert engine.get_current() is not None
        assert engine.get_current().id == todo_id

        engine.complete_item(todo_id)
        assert engine.get_current() is None
        assert len(engine.get_done()) == 1


def test_to_ai_text_format():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = TodoEngine(session_id="test", persist_dir=tmpdir)
        engine.add("Task one")
        engine.add("Task two")
        text = engine.to_ai_text()
        assert "TODO LIST" in text
        assert "Task one" in text


def test_subtasks():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = TodoEngine(session_id="test", persist_dir=tmpdir)
        todo_id = engine.add(
            "Refactor auth",
            subtasks=["Update login", "Update logout", "Add tests"]
        )
        item = engine.items[0]
        assert len(item.subtasks) == 3


def test_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine1 = TodoEngine(session_id="test", persist_dir=tmpdir)
        engine1.add("Persistent task")

        engine2 = TodoEngine(session_id="test", persist_dir=tmpdir)
        assert len(engine2.items) == 1
        assert engine2.items[0].description == "Persistent task"

