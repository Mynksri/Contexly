"""
Contexly - Codebase Context Engine
Extracts logic skeletons from codebases and manages AI context efficiently.
"""

__version__ = "0.1.0"
__author__ = "Contexly"

from contexly.core.extractor import SkeletonExtractor
from contexly.core.tree_builder import TreeBuilder
from contexly.agent.context_manager import ContextManager
from contexly.agent.todo_engine import TodoEngine

__all__ = [
    "SkeletonExtractor",
    "TreeBuilder", 
    "ContextManager",
    "TodoEngine",
]

