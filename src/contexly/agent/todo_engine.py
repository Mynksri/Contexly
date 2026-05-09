"""
TodoEngine — Automatic TODO generation and tracking.

Generates structured task lists from AI conversations.
Ensures AI never loses track of what was done and what is pending.
"""

import json
import time
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass
from enum import Enum


class TodoStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"


@dataclass
class TodoItem:
    id: str
    description: str
    status: TodoStatus
    file_hint: Optional[str]        # which file this relates to
    line_hint: Optional[int]        # which line
    created_at: float
    completed_at: Optional[float]
    subtasks: List["TodoItem"]


class TodoEngine:
    """
    Manages TODO list for an AI coding session.
    
    Usage:
        todos = TodoEngine(session_id="my_project")
        todos.add("Fix balance calculation", file_hint="balance_manager.py", line_hint=47)
        todos.start_item(todo_id)
        todos.complete_item(todo_id)
        
        # Get formatted list for AI injection
        text = todos.to_ai_text()
    """

    def __init__(self, session_id: str, persist_dir: str = ".contexly"):
        self.session_id = session_id
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(exist_ok=True)
        self.todo_file = self.persist_dir / f"{session_id}_todos.json"
        self.items: List[TodoItem] = []
        self._load()

    def add(
        self,
        description: str,
        file_hint: Optional[str] = None,
        line_hint: Optional[int] = None,
        subtasks: Optional[List[str]] = None,
    ) -> str:
        """Add a new TODO item. Returns item ID."""
        todo_id = f"todo_{int(time.time() * 1000)}"
        sub_items = []
        if subtasks:
            for i, sub in enumerate(subtasks):
                sub_items.append(TodoItem(
                    id=f"{todo_id}_sub_{i}",
                    description=sub,
                    status=TodoStatus.PENDING,
                    file_hint=None,
                    line_hint=None,
                    created_at=time.time(),
                    completed_at=None,
                    subtasks=[],
                ))

        item = TodoItem(
            id=todo_id,
            description=description,
            status=TodoStatus.PENDING,
            file_hint=file_hint,
            line_hint=line_hint,
            created_at=time.time(),
            completed_at=None,
            subtasks=sub_items,
        )
        self.items.append(item)
        self._save()
        return todo_id

    def start_item(self, todo_id: str):
        """Mark a TODO as in progress."""
        item = self._find(todo_id)
        if item:
            item.status = TodoStatus.IN_PROGRESS
            self._save()

    def complete_item(self, todo_id: str):
        """Mark a TODO as done."""
        item = self._find(todo_id)
        if item:
            item.status = TodoStatus.DONE
            item.completed_at = time.time()
            self._save()

    def block_item(self, todo_id: str):
        """Mark a TODO as blocked."""
        item = self._find(todo_id)
        if item:
            item.status = TodoStatus.BLOCKED
            self._save()

    def get_current(self) -> Optional[TodoItem]:
        """Get the currently in-progress item."""
        for item in self.items:
            if item.status == TodoStatus.IN_PROGRESS:
                return item
        return None

    def get_pending(self) -> List[TodoItem]:
        return [i for i in self.items if i.status == TodoStatus.PENDING]

    def get_done(self) -> List[TodoItem]:
        return [i for i in self.items if i.status == TodoStatus.DONE]

    def to_ai_text(self) -> str:
        """Format TODO list for injection into AI context."""
        lines = ["=== TODO LIST ==="]

        done = self.get_done()
        if done:
            lines.append("COMPLETED:")
            for item in done[-3:]:  # show last 3 completed
                hint = f" [{item.file_hint}:{item.line_hint}]" if item.file_hint else ""
                lines.append(f"  ✅ {item.description}{hint}")

        current = self.get_current()
        if current:
            hint = f" [{current.file_hint}:{current.line_hint}]" if current.file_hint else ""
            lines.append(f"IN PROGRESS:")
            lines.append(f"  🔄 {current.description}{hint}")
            for sub in current.subtasks:
                status_icon = "✅" if sub.status == TodoStatus.DONE else "⏳"
                lines.append(f"    {status_icon} {sub.description}")

        pending = self.get_pending()
        if pending:
            lines.append("PENDING:")
            for item in pending[:5]:  # show max 5 pending
                lines.append(f"  ⏳ {item.description}")

        return "\n".join(lines)

    def clear_done(self):
        """Remove completed items to keep list clean."""
        self.items = [i for i in self.items if i.status != TodoStatus.DONE]
        self._save()

    def _find(self, todo_id: str) -> Optional[TodoItem]:
        return next((i for i in self.items if i.id == todo_id), None)

    def _save(self):
        def item_to_dict(item: TodoItem) -> dict:
            return {
                "id": item.id,
                "description": item.description,
                "status": item.status.value,
                "file_hint": item.file_hint,
                "line_hint": item.line_hint,
                "created_at": item.created_at,
                "completed_at": item.completed_at,
                "subtasks": [item_to_dict(s) for s in item.subtasks],
            }
        data = {"items": [item_to_dict(i) for i in self.items]}
        self.todo_file.write_text(json.dumps(data, indent=2))

    def _load(self):
        if not self.todo_file.exists():
            return
        try:
            data = json.loads(self.todo_file.read_text())

            def dict_to_item(d: dict) -> TodoItem:
                return TodoItem(
                    id=d["id"],
                    description=d["description"],
                    status=TodoStatus(d["status"]),
                    file_hint=d.get("file_hint"),
                    line_hint=d.get("line_hint"),
                    created_at=d["created_at"],
                    completed_at=d.get("completed_at"),
                    subtasks=[dict_to_item(s) for s in d.get("subtasks", [])],
                )

            self.items = [dict_to_item(i) for i in data.get("items", [])]
        except Exception:
            pass
