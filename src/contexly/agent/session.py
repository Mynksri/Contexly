"""Session manager for token-efficient multi-turn agent workflows."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from contexly.core.tree_builder import CodebaseTree, TreeBuilder


class Session:
    """
    Maintains a human-readable progress file and builds compact AI context.

    Files created under the target project:
            .contexly/session.md
            .contexly/chunks/*.md
    """

    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path).resolve()
        self.ctx_dir = self.project_path / ".contexly"
        self.session_file = self.ctx_dir / "session.md"
        self.chunks_dir = self.ctx_dir / "chunks"

    def create(self, task: str):
        """Create a new markdown session tracker with a standard template."""
        self.ctx_dir.mkdir(parents=True, exist_ok=True)
        self.chunks_dir.mkdir(parents=True, exist_ok=True)
        started = datetime.now().strftime("%Y-%m-%d %H:%M")
        template = (
            f"# Session: {task}\n"
            f"Started: {started}\n"
            "<!-- tree_sent_once:false -->\n"
            "\n"
            "## COMPLETED\n"
            "\n"
            "## IN PROGRESS\n"
            "- IN_PROGRESS: Not started\n"
            "\n"
            "## TODO\n"
            "\n"
            "## CODEBASE\n"
            "- Tree source: contexly tree output\n"
            "- Key files: (fill as needed)\n"
        )
        self.session_file.write_text(template, encoding="utf-8")

    @staticmethod
    def _short_summary(text: str, max_len: int = 120) -> str:
        clean = " ".join(text.strip().split())
        if len(clean) <= max_len:
            return clean
        return clean[: max_len - 3].rstrip() + "..."

    def update(self, status: str, summary: str):
        """
        Update session sections.

        status values:
          - done
          - in_progress
          - todo
        """
        if not self.session_file.exists():
            self.create("General Session")

        content = self.session_file.read_text(encoding="utf-8")
        status_key = status.strip().lower()

        if status_key == "done":
            line = f"- DONE: {self._short_summary(summary)}"
            content = self._append_under_heading(content, "## COMPLETED", line)
        elif status_key == "in_progress":
            line = f"- IN_PROGRESS: {self._short_summary(summary)}"
            content = self._replace_section_lines(content, "## IN PROGRESS", [line])
        elif status_key == "todo":
            line = f"- TODO: {self._short_summary(summary)}"
            content = self._append_under_heading(content, "## TODO", line)
        else:
            raise ValueError("status must be one of: done, in_progress, todo")

        self.session_file.write_text(content, encoding="utf-8")

    def complete_step(self, done_summary: str, next_in_progress: str = ""):
        """Append short completion note and optionally update current in-progress line."""
        self.update("done", done_summary)
        if next_in_progress.strip():
            self.update("in_progress", next_in_progress)

    def build_context(self, tree: CodebaseTree, query: str) -> str:
        """
        Build context payload for AI.

        First call for a session includes full tree + session + chunk.
        Later calls include session + chunk only (tree omitted).
        """
        if not self.session_file.exists():
            self.create(query or "General Session")

        session_text = self.session_file.read_text(encoding="utf-8")
        tree_sent_once = self._tree_was_sent(session_text)
        builder = TreeBuilder()

        chunk_text = builder.get_relevant_chunk(tree, query=query, max_tokens=3000, level=2)
        chunk_file = self.chunks_dir / f"{self._slug(query)}_chunk.md"
        chunk_file.write_text(chunk_text, encoding="utf-8")

        parts = [
            "=== SESSION ===",
            session_text,
            "",
            f"=== RELEVANT CHUNK: {query} ===",
            chunk_text,
        ]

        if not tree_sent_once:
            parts.extend([
                "",
                "=== CODEBASE TREE (FIRST SEND ONLY) ===",
                builder.to_ai_text(tree, level=2),
            ])
            updated = self._set_tree_sent_once(session_text, sent=True)
            self.session_file.write_text(updated, encoding="utf-8")

        return "\n".join(parts)

    def read_status(self) -> str:
        """Return current session markdown for CLI display."""
        if not self.session_file.exists():
            return "No session found. Run: contexly session new \"<task>\""
        return self.session_file.read_text(encoding="utf-8")

    @staticmethod
    def _slug(text: str) -> str:
        text = text.strip().lower()
        text = re.sub(r"[^a-z0-9]+", "_", text)
        text = text.strip("_")
        return text[:40] or "query"

    @staticmethod
    def _tree_was_sent(content: str) -> bool:
        m = re.search(r"<!--\s*tree_sent_once:(true|false)\s*-->", content, re.IGNORECASE)
        if not m:
            return False
        return m.group(1).lower() == "true"

    @staticmethod
    def _set_tree_sent_once(content: str, sent: bool) -> str:
        value = "true" if sent else "false"
        if re.search(r"<!--\s*tree_sent_once:(true|false)\s*-->", content, re.IGNORECASE):
            return re.sub(
                r"<!--\s*tree_sent_once:(true|false)\s*-->",
                f"<!-- tree_sent_once:{value} -->",
                content,
                count=1,
                flags=re.IGNORECASE,
            )
        return f"<!-- tree_sent_once:{value} -->\n" + content

    @staticmethod
    def _find_section_bounds(content: str, heading: str) -> Optional[tuple[int, int]]:
        lines = content.splitlines()
        start = None
        for i, line in enumerate(lines):
            if line.strip() == heading:
                start = i
                break
        if start is None:
            return None

        end = len(lines)
        for j in range(start + 1, len(lines)):
            if lines[j].startswith("## "):
                end = j
                break
        return start, end

    def _append_under_heading(self, content: str, heading: str, line_to_add: str) -> str:
        bounds = self._find_section_bounds(content, heading)
        if bounds is None:
            content = content.rstrip() + f"\n\n{heading}\n"
            bounds = self._find_section_bounds(content, heading)
            if bounds is None:
                return content

        lines = content.splitlines()
        start, end = bounds
        body = [ln for ln in lines[start + 1:end] if ln.strip()]
        body.append(line_to_add)

        rebuilt = lines[:start + 1] + [""] + body + [""] + lines[end:]
        return "\n".join(rebuilt).rstrip() + "\n"

    def _replace_section_lines(self, content: str, heading: str, new_lines: list[str]) -> str:
        bounds = self._find_section_bounds(content, heading)
        if bounds is None:
            content = content.rstrip() + f"\n\n{heading}\n"
            bounds = self._find_section_bounds(content, heading)
            if bounds is None:
                return content

        lines = content.splitlines()
        start, end = bounds
        rebuilt = lines[:start + 1] + [""] + new_lines + [""] + lines[end:]
        return "\n".join(rebuilt).rstrip() + "\n"
