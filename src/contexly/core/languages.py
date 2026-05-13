"""
Language configurations for tree-sitter parsing.
Defines which node types to extract per language.
"""

from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class LanguageConfig:
    name: str
    extensions: List[str]
    function_types: List[str]      # node types that are functions
    class_types: List[str]         # node types that are classes
    import_types: List[str]        # node types that are imports
    call_types: List[str]          # node types that are function calls
    condition_types: List[str]     # node types that are conditions (if/elif)
    return_types: List[str]        # node types that are returns
    async_markers: List[str]       # keywords that mark async functions


LANGUAGE_CONFIGS: Dict[str, LanguageConfig] = {
    "python": LanguageConfig(
        name="python",
        extensions=[".py"],
        function_types=["function_definition", "async_function_definition"],
        class_types=["class_definition"],
        import_types=["import_statement", "import_from_statement"],
        call_types=["call"],
        condition_types=["if_statement", "elif_clause"],
        return_types=["return_statement"],
        async_markers=["async"],
    ),
    "javascript": LanguageConfig(
        name="javascript",
        extensions=[".js", ".mjs", ".jsx"],
        function_types=[
            "function_declaration", "arrow_function",
            "function_expression", "method_definition"
        ],
        class_types=["class_declaration"],
        import_types=["import_statement", "import_declaration"],
        call_types=["call_expression"],
        condition_types=["if_statement", "else_clause"],
        return_types=["return_statement"],
        async_markers=["async"],
    ),
    "typescript": LanguageConfig(
        name="typescript",
        extensions=[".ts", ".tsx"],
        function_types=[
            "function_declaration", "arrow_function",
            "function_expression", "method_definition",
            "method_signature"
        ],
        class_types=["class_declaration", "interface_declaration"],
        import_types=["import_statement"],
        call_types=["call_expression"],
        condition_types=["if_statement", "else_clause"],
        return_types=["return_statement"],
        async_markers=["async"],
    ),
    "go": LanguageConfig(
        name="go",
        extensions=[".go"],
        function_types=["function_declaration", "method_declaration", "func_literal"],
        class_types=["type_declaration"],
        import_types=["import_declaration"],
        call_types=["call_expression"],
        condition_types=["if_statement"],
        return_types=["return_statement"],
        async_markers=[],
    ),
    "html": LanguageConfig(
        name="html",
        extensions=[".html", ".htm"],
        function_types=[],
        class_types=[],
        import_types=[],
        call_types=[],
        condition_types=[],
        return_types=[],
        async_markers=[],
    ),
    "css": LanguageConfig(
        name="css",
        extensions=[".css", ".scss", ".sass", ".less"],
        function_types=[],
        class_types=[],
        import_types=[],
        call_types=[],
        condition_types=[],
        return_types=[],
        async_markers=[],
    ),
    "c": LanguageConfig(
        name="c",
        extensions=[".c", ".h"],
        function_types=["function_definition"],
        class_types=["struct_specifier"],
        import_types=["preproc_include"],
        call_types=["call_expression"],
        condition_types=["if_statement"],
        return_types=["return_statement"],
        async_markers=[],
    ),
    "cpp": LanguageConfig(
        name="cpp",
        extensions=[".cpp", ".hpp", ".cc", ".hh", ".cxx"],
        function_types=["function_definition"],
        class_types=["class_specifier", "struct_specifier"],
        import_types=["preproc_include"],
        call_types=["call_expression"],
        condition_types=["if_statement"],
        return_types=["return_statement"],
        async_markers=[],
    ),
    "java": LanguageConfig(
        name="java",
        extensions=[".java"],
        function_types=["method_declaration"],
        class_types=["class_declaration", "interface_declaration"],
        import_types=["import_declaration"],
        call_types=["method_invocation"],
        condition_types=["if_statement"],
        return_types=["return_statement"],
        async_markers=[],
    ),
    "rust": LanguageConfig(
        name="rust",
        extensions=[".rs"],
        function_types=["function_item"],
        class_types=["impl_item", "struct_item"],
        import_types=["use_declaration"],
        call_types=["call_expression"],
        condition_types=["if_expression"],
        return_types=["return_expression"],
        async_markers=["async"],
    ),
    "csharp": LanguageConfig(
        name="csharp",
        extensions=[".cs"],
        function_types=["method_declaration"],
        class_types=["class_declaration", "interface_declaration"],
        import_types=["using_directive"],
        call_types=["invocation_expression"],
        condition_types=["if_statement"],
        return_types=["return_statement"],
        async_markers=["async"],
    ),
    "vue": LanguageConfig(
        name="vue",
        extensions=[".vue"],
        function_types=[],
        class_types=[],
        import_types=[],
        call_types=[],
        condition_types=[],
        return_types=[],
        async_markers=[],
    ),
    "svelte": LanguageConfig(
        name="svelte",
        extensions=[".svelte"],
        function_types=[],
        class_types=[],
        import_types=[],
        call_types=[],
        condition_types=[],
        return_types=[],
        async_markers=[],
    ),
}


def get_config_for_file(filepath: str) -> LanguageConfig | None:
    """Return language config based on file extension."""
    for lang, config in LANGUAGE_CONFIGS.items():
        for ext in config.extensions:
            if filepath.endswith(ext):
                return config
    return None
