"""
ContextManager — Manages chat history with intelligent chunking.

Solves: AI context window exhaustion in long coding sessions.

Strategy:
- Stores all messages in labeled chunks
- Sends only: last N messages (full) + compressed summaries of older ones
- Persists context across sessions to disk
- Handles cross-AI-tool switching via context export/import
"""

import json
import time
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class ChunkStatus(Enum):
    DONE = "done"               # completed, send only summary
    IN_PROGRESS = "in_progress" # currently active, send full
    PENDING = "pending"         # not started, send as reference
    CONTEXT_ONLY = "context"    # background info, compress heavily


@dataclass
class Message:
    role: str           # "user" or "assistant"
    content: str
    timestamp: float
    tokens_estimate: int


@dataclass
class ContextChunk:
    chunk_id: str
    status: ChunkStatus
    messages: List[Message]
    summary: Optional[str]      # compressed summary when DONE
    task_description: str       # what this chunk is about
    created_at: float
    completed_at: Optional[float]


class ContextManager:
    """
    Manages context across a coding session.
    
    Usage:
        ctx_mgr = ContextManager(session_id="my_project")
        ctx_mgr.add_message("user", "Fix the balance calculation")
        ctx_mgr.add_message("assistant", "I'll fix it...")
        
        # Get context to send to AI
        context = ctx_mgr.get_context_for_ai(max_tokens=20000)
        
        # Mark current task as done
        ctx_mgr.complete_current_chunk("Fixed balance_manager.py line 47")
    """

    RECENT_MESSAGES_COUNT = 3       # always send last N messages in full
    MAX_SUMMARY_LENGTH = 150        # chars per completed chunk summary

    def __init__(
        self,
        session_id: str,
        persist_dir: str = ".contexly",
    ):
        self.session_id = session_id
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(exist_ok=True)
        self.session_file = self.persist_dir / f"{session_id}.json"

        self.chunks: List[ContextChunk] = []
        self.current_chunk: Optional[ContextChunk] = None
        self._load_session()

    def add_message(self, role: str, content: str):
        """Add a message to current active chunk."""
        if self.current_chunk is None:
            self._start_new_chunk("General")

        msg = Message(
            role=role,
            content=content,
            timestamp=time.time(),
            tokens_estimate=len(content) // 4,
        )
        self.current_chunk.messages.append(msg)
        self._save_session()

    def start_task(self, task_description: str):
        """Start a new task chunk."""
        if self.current_chunk and self.current_chunk.messages:
            # Mark previous chunk as pending if not done
            if self.current_chunk.status == ChunkStatus.IN_PROGRESS:
                self.current_chunk.status = ChunkStatus.PENDING
        self._start_new_chunk(task_description)

    def complete_current_chunk(self, summary: str):
        """Mark current chunk as done with a summary."""
        if self.current_chunk:
            self.current_chunk.status = ChunkStatus.DONE
            self.current_chunk.summary = summary[:self.MAX_SUMMARY_LENGTH]
            self.current_chunk.completed_at = time.time()
            self.chunks.append(self.current_chunk)
            self.current_chunk = None
            self._save_session()

    def get_context_for_ai(self, max_tokens: int = 20000) -> str:
        """
        Build context string to send to AI.
        
        Structure:
        1. Completed tasks: summaries only (very compressed)
        2. Pending tasks: task description only
        3. Current chunk: full messages (last N)
        """
        parts = []
        token_budget = max_tokens

        # 1. Completed chunks — summaries only
        done_chunks = [c for c in self.chunks if c.status == ChunkStatus.DONE]
        if done_chunks:
            parts.append("=== COMPLETED TASKS ===")
            for chunk in done_chunks[-5:]:  # last 5 completed only
                summary = chunk.summary or chunk.task_description
                parts.append(f"✅ {summary}")
            token_budget -= len("\n".join(parts)) // 4

        # 2. Pending chunks
        pending = [c for c in self.chunks if c.status == ChunkStatus.PENDING]
        if pending:
            parts.append("\n=== PENDING TASKS ===")
            for chunk in pending:
                parts.append(f"⏳ {chunk.task_description}")
            token_budget -= 200

        # 3. Current in-progress chunk — recent messages in full
        if self.current_chunk and self.current_chunk.messages:
            parts.append("\n=== CURRENT TASK ===")
            parts.append(f"Task: {self.current_chunk.task_description}")

            recent = self.current_chunk.messages[-self.RECENT_MESSAGES_COUNT:]
            for msg in recent:
                role_label = "User" if msg.role == "user" else "AI"
                # Truncate very long messages
                content = msg.content
                if len(content) > 1000:
                    content = content[:500] + "\n...[truncated]...\n" + content[-300:]
                parts.append(f"\n[{role_label}]: {content}")

        return "\n".join(parts)

    def export_for_new_ai(self) -> Dict:
        """
        Export context for switching to a different AI tool.
        Returns a dict that can be injected as first message to new AI.
        """
        return {
            "session_id": self.session_id,
            "completed_tasks": [
                c.summary for c in self.chunks
                if c.status == ChunkStatus.DONE and c.summary
            ],
            "pending_tasks": [
                c.task_description for c in self.chunks
                if c.status == ChunkStatus.PENDING
            ],
            "current_task": (
                self.current_chunk.task_description
                if self.current_chunk else None
            ),
            "recent_messages": [
                {"role": m.role, "content": m.content}
                for m in (self.current_chunk.messages[-3:]
                          if self.current_chunk else [])
            ],
        }

    def _start_new_chunk(self, task_description: str):
        self.current_chunk = ContextChunk(
            chunk_id=f"chunk_{int(time.time())}",
            status=ChunkStatus.IN_PROGRESS,
            messages=[],
            summary=None,
            task_description=task_description,
            created_at=time.time(),
            completed_at=None,
        )

    def _save_session(self):
        """Persist session to disk."""
        all_chunks = self.chunks.copy()
        if self.current_chunk:
            all_chunks.append(self.current_chunk)

        data = {
            "session_id": self.session_id,
            "chunks": [
                {
                    "chunk_id": c.chunk_id,
                    "status": c.status.value,
                    "task_description": c.task_description,
                    "summary": c.summary,
                    "created_at": c.created_at,
                    "completed_at": c.completed_at,
                    "messages": [
                        {
                            "role": m.role,
                            "content": m.content[:2000],  # cap stored content
                            "timestamp": m.timestamp,
                            "tokens_estimate": m.tokens_estimate,
                        }
                        for m in c.messages
                    ],
                }
                for c in all_chunks
            ],
        }
        self.session_file.write_text(json.dumps(data, indent=2))

    def _load_session(self):
        """Load existing session from disk if available."""
        if not self.session_file.exists():
            return

        try:
            data = json.loads(self.session_file.read_text())
            for chunk_data in data.get("chunks", []):
                messages = [
                    Message(
                        role=m["role"],
                        content=m["content"],
                        timestamp=m["timestamp"],
                        tokens_estimate=m["tokens_estimate"],
                    )
                    for m in chunk_data.get("messages", [])
                ]
                chunk = ContextChunk(
                    chunk_id=chunk_data["chunk_id"],
                    status=ChunkStatus(chunk_data["status"]),
                    messages=messages,
                    summary=chunk_data.get("summary"),
                    task_description=chunk_data["task_description"],
                    created_at=chunk_data["created_at"],
                    completed_at=chunk_data.get("completed_at"),
                )
                if chunk.status == ChunkStatus.IN_PROGRESS:
                    self.current_chunk = chunk
                else:
                    self.chunks.append(chunk)
        except Exception:
            pass  # Start fresh if load fails
