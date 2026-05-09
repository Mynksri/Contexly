"""
Updater â€” Real-time file change detection and incremental tree updates.

Watches for file changes and updates only the affected tree nodes.
This ensures AI always has fresh, current codebase state.
"""

import time
import threading
from pathlib import Path
from typing import Dict, Callable, Optional
from contexly.core.extractor import SkeletonExtractor
from contexly.core.tree_builder import CodebaseTree, TreeNode


class FileWatcher:
    """
    Watches a directory for file changes.
    On change: re-extracts that file's skeleton and updates the tree.
    """

    def __init__(
        self,
        tree: CodebaseTree,
        on_update: Optional[Callable[[str, TreeNode], None]] = None,
        poll_interval: float = 1.0,
    ):
        self.tree = tree
        self.on_update = on_update
        self.poll_interval = poll_interval
        self.extractor = SkeletonExtractor()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        # Track last modified times
        self._mtimes: Dict[str, float] = {}
        self._init_mtimes()

    def _init_mtimes(self):
        """Record current modification times for all tracked files."""
        root = Path(self.tree.root_path)
        for rel_path in self.tree.nodes.keys():
            full_path = root / rel_path
            if full_path.exists():
                self._mtimes[rel_path] = full_path.stat().st_mtime

    def start(self):
        """Start watching for changes in background thread."""
        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the file watcher."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def _watch_loop(self):
        """Main polling loop."""
        while self._running:
            self._check_changes()
            time.sleep(self.poll_interval)

    def _check_changes(self):
        """Check all tracked files for modifications."""
        root = Path(self.tree.root_path)

        for rel_path in list(self.tree.nodes.keys()):
            full_path = root / rel_path
            if not full_path.exists():
                continue

            current_mtime = full_path.stat().st_mtime
            last_mtime = self._mtimes.get(rel_path, 0)

            if current_mtime > last_mtime:
                self._mtimes[rel_path] = current_mtime
                self._update_file(rel_path, str(full_path))

    def _update_file(self, rel_path: str, full_path: str):
        """Re-extract skeleton for changed file and update tree."""
        skeleton = self.extractor.extract_file(full_path)
        if not skeleton:
            return

        text = self.extractor.to_text(skeleton)
        tokens = self.extractor.estimate_tokens(text)

        old_node = self.tree.nodes.get(rel_path)
        old_tokens = old_node.token_estimate if old_node else 0

        new_node = TreeNode(
            path=rel_path,
            language=skeleton.language,
            skeleton_text=text,
            token_estimate=tokens,
            imports=skeleton.imports,
            connections=old_node.connections if old_node else [],
        )

        # Update tree in place
        self.tree.nodes[rel_path] = new_node
        self.tree.total_tokens = (
            self.tree.total_tokens - old_tokens + tokens
        )

        # Notify callback
        if self.on_update:
            self.on_update(rel_path, new_node)

    def force_update(self, rel_path: str):
        """Manually trigger update for a specific file."""
        root = Path(self.tree.root_path)
        full_path = str(root / rel_path)
        self._update_file(rel_path, full_path)

