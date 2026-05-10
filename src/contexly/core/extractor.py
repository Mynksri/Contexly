"""
SkeletonExtractor â€” Core extraction engine.

Uses tree-sitter to parse source files and extract ONLY the logic skeleton:
- Function signatures (not bodies)
- Import statements  
- If/elif conditions (decision points)
- Function calls within functions
- Return statements and raises
- Class definitions with method signatures

EXCLUDES: print statements, comments, docstrings, variable assignments,
          logging calls, raw string values, test boilerplate.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from contexly.core.languages import get_config_for_file, LanguageConfig

try:
    import tree_sitter_python as tspython
    import tree_sitter_javascript as tsjavascript
    import tree_sitter_typescript as tstypescript
    from tree_sitter import Language, Parser, Node
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False

try:
    import tree_sitter_go as tsgo
    TREE_SITTER_GO_AVAILABLE = True
except ImportError:
    TREE_SITTER_GO_AVAILABLE = False


@dataclass
class FunctionSkeleton:
    """Represents one function's logic skeleton."""
    name: str
    line_start: int
    line_end: int
    is_async: bool
    is_method: bool                     # inside a class?
    class_name: Optional[str]           # which class (if method)
    parameters: List[str]               # param names only, no types/defaults
    calls: List[str]                    # functions this function calls
    conditions: List[str]               # if/elif conditions as strings
    returns: List[str]                  # return value descriptions
    raises: List[str]                   # exception types raised
    decorators: List[str]               # decorator names
    logic_vars: List[str]               # key local variables (threshold tables etc.)
    purpose: str                        # why this function exists
    sections: List[str]                 # key in-function section comments
    state_writes: List[str]             # important state/self attribute updates


@dataclass
class ClassSkeleton:
    """Represents one class's skeleton."""
    name: str
    line_start: int
    bases: List[str]                    # parent classes
    methods: List[FunctionSkeleton]     # all methods
    fields: List[str]                   # dataclass/class-level fields
    purpose: str                        # class role / summary


@dataclass
class FileSkeleton:
    """Complete skeleton for one file."""
    filepath: str
    language: str
    imports: List[str]                  # what is imported
    functions: List[FunctionSkeleton]   # top-level functions
    classes: List[ClassSkeleton]        # classes with their methods
    constants: List[str]                # module-level constants (NAME = value)
    has_main_guard: bool                # has if __name__ == '__main__'
    is_entry_point: bool                # has main() or asyncio.run() at top-level
    total_lines: int
    skeleton_lines: int                 # how many lines the skeleton is
    token_estimate: int                 # rough token count of skeleton


class SkeletonExtractor:
    """
    Extracts logic skeleton from source files using tree-sitter.
    
    Usage:
        extractor = SkeletonExtractor()
        skeleton = extractor.extract_file("path/to/file.py")
        text = extractor.to_text(skeleton)     # for AI consumption
        tokens = extractor.estimate_tokens(text)
    """

    # Function calls to EXCLUDE (not useful for AI context)
    EXCLUDED_CALL_PREFIXES = [
        "print", "logger.", "logging.", "log.", "console.log",
        "console.error", "console.warn", "pytest.", "unittest.",
        "self.log", "self.logger", "sys.stdout", "sys.stderr",
    ]

    # Secret patterns to redact from constants
    _SECRET_PATTERNS = [
        # Ethereum/polygon private key (64 hex chars)
        (r'[0-9a-fA-F]{48,}', '***HEX_KEY***'),
        # Telegram bot token: digits:alphanum35+
        (r'\d{8,10}:[A-Za-z0-9_-]{30,}', '***BOT_TOKEN***'),
        # Ethereum wallet address 0x...
        (r'0x[0-9a-fA-F]{40}\b', '***WALLET***'),
        # Long base64-like secrets
        (r'[A-Za-z0-9+/]{40,}={0,2}', '***SECRET***'),
    ]

    def _redact(self, text: str) -> str:
        """Replace sensitive values with redacted placeholders."""
        import re
        for pattern, replacement in self._SECRET_PATTERNS:
            text = re.sub(pattern, replacement, text)
        return text

    def __init__(self):
        self._parsers: Dict[str, Any] = {}
        self._setup_parsers()

    def _setup_parsers(self):
        """Initialize tree-sitter parsers for each language."""
        if not TREE_SITTER_AVAILABLE:
            return
        try:
            PY_LANGUAGE = Language(tspython.language())
            self._parsers["python"] = Parser(PY_LANGUAGE)
        except Exception:
            pass
        try:
            JS_LANGUAGE = Language(tsjavascript.language())
            self._parsers["javascript"] = Parser(JS_LANGUAGE)
        except Exception:
            pass
        try:
            TS_LANGUAGE = Language(tstypescript.language_typescript())
            self._parsers["typescript"] = Parser(TS_LANGUAGE)
        except Exception:
            pass
        if TREE_SITTER_GO_AVAILABLE:
            try:
                GO_LANGUAGE = Language(tsgo.language())
                self._parsers["go"] = Parser(GO_LANGUAGE)
            except Exception:
                pass

    def extract_file(self, filepath: str) -> Optional[FileSkeleton]:
        """
        Extract skeleton from a single file.
        Returns None if file cannot be parsed.
        """
        path = Path(filepath)
        if not path.exists() or not path.is_file():
            return None

        lang_config = get_config_for_file(filepath)
        if lang_config is None:
            return None

        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return None

        total_lines = source.count("\n") + 1

        if lang_config.name in self._parsers and TREE_SITTER_AVAILABLE:
            skeleton = self._extract_with_tree_sitter(
                source, filepath, lang_config
            )
        else:
            skeleton = self._extract_with_fallback(
                source, filepath, lang_config
            )

        if skeleton:
            text = self.to_text(skeleton)
            skeleton.skeleton_lines = text.count("\n") + 1
            skeleton.token_estimate = self.estimate_tokens(text)
            skeleton.total_lines = total_lines

        return skeleton

    def extract_directory(
        self,
        dirpath: str,
        exclude_dirs: List[str] = None,
        exclude_file_patterns: List[str] = None,
        max_files: int = 5000,
    ) -> Dict[str, FileSkeleton]:
        """
        Extract skeletons from all supported files in a directory.
        Returns dict of {filepath: FileSkeleton}
        """
        exclude_dirs = exclude_dirs or [
            ".git", "node_modules", "__pycache__", ".venv", "venv",
            "env", "dist", "build", ".next", ".nuxt", "coverage",
            ".pytest_cache", ".mypy_cache", "migrations",
        ]
        exclude_file_patterns = exclude_file_patterns or [
            "_graphify_*", "debug_*", "analyze_*",
        ]

        results = {}
        dirpath = Path(dirpath)

        for root, dirs, files in os.walk(dirpath):
            # Remove excluded dirs in-place to prevent walking into them
            dirs[:] = [d for d in dirs if d not in exclude_dirs]

            for filename in files:
                if any(Path(filename).match(pat) for pat in exclude_file_patterns):
                    continue
                filepath = os.path.join(root, filename)
                lang_config = get_config_for_file(filepath)
                if lang_config is None:
                    continue

                skeleton = self.extract_file(filepath)
                if skeleton:
                    rel_path = os.path.relpath(filepath, dirpath)
                    results[rel_path] = skeleton

                if len(results) >= max_files:
                    break

        return results

    def _extract_with_tree_sitter(
        self,
        source: str,
        filepath: str,
        config: LanguageConfig,
    ) -> FileSkeleton:
        """Full extraction using tree-sitter parser."""
        parser = self._parsers[config.name]
        tree = parser.parse(bytes(source, "utf-8"))
        root = tree.root_node
        lines = source.split("\n")

        imports = self._extract_imports(root, lines, config)
        functions = []
        classes = []

        for node in root.children:
            if node.type in config.class_types:
                cls = self._extract_class(node, lines, config)
                if cls:
                    classes.append(cls)
            elif node.type in config.function_types:
                func = self._extract_function(node, lines, config)
                if func:
                    functions.append(func)
            elif node.type == "decorated_definition":
                # @dataclass class Foo or @staticmethod def bar
                for child in node.children:
                    if child.type in config.class_types:
                        cls = self._extract_class(child, lines, config)
                        if cls:
                            # Mark it as decorated (e.g. dataclass)
                            for deco_child in node.children:
                                if deco_child.type == "decorator":
                                    dec_text = lines[deco_child.start_point[0]].strip()
                                    if dec_text not in cls.fields:
                                        cls.fields.insert(0, dec_text)
                            classes.append(cls)
                    elif child.type in config.function_types:
                        func = self._extract_function(child, lines, config)
                        if func:
                            functions.append(func)

        constants = self._extract_constants(root, lines, config)
        has_main_guard = self._has_main_guard(source)
        is_entry_point = self._is_entry_point(source, functions)

        return FileSkeleton(
            filepath=filepath,
            language=config.name,
            imports=imports,
            functions=functions,
            classes=classes,
            constants=constants,
            has_main_guard=has_main_guard,
            is_entry_point=is_entry_point,
            total_lines=len(lines),
            skeleton_lines=0,
            token_estimate=0,
        )

    def _extract_imports(
        self, root: "Node", lines: List[str], config: LanguageConfig
    ) -> List[str]:
        """Extract import statements as clean strings."""
        imports = []
        for node in root.children:
            if node.type in config.import_types:
                line = lines[node.start_point[0]].strip()
                # Clean up long import lines
                if len(line) > 80:
                    line = line[:77] + "..."
                imports.append(line)
        return imports

    def _extract_function(
        self,
        node: "Node",
        lines: List[str],
        config: LanguageConfig,
        class_name: Optional[str] = None,
    ) -> Optional[FunctionSkeleton]:
        """Extract a single function's skeleton."""
        name = ""
        is_async = False
        parameters = []
        decorators = []

        # Get function name
        for child in node.children:
            if child.type == "identifier":
                name = child.text.decode("utf-8")
                break
            if child.type == "async":
                is_async = True
            if child.type == "decorator":
                dec_text = lines[child.start_point[0]].strip()
                decorators.append(dec_text)

        if not name or name.startswith("_test") or name == "test":
            return None  # skip test functions

        # Get parameters
        for child in node.children:
            if child.type in ("parameters", "formal_parameters"):
                for param in child.children:
                    if param.type == "identifier":
                        pname = param.text.decode("utf-8")
                        if pname != "self" and pname != "cls":
                            parameters.append(pname)

        # Get function body details
        body_node = None
        for child in node.children:
            if child.type == "block" or child.type == "statement_block":
                body_node = child
                break

        calls = []
        conditions = []
        returns = []
        raises = []
        logic_vars = []
        sections = []
        state_writes = []

        if body_node:
            calls = self._extract_calls(body_node, config)
            conditions = self._extract_conditions(body_node, lines, config)
            returns = self._extract_returns(body_node, lines, config)
            raises = self._extract_raises(body_node, lines)
            logic_vars = self._extract_logic_vars(body_node, lines)
            sections = self._extract_sections(node, lines)
            state_writes = self._extract_state_writes(body_node)

        line_start = node.start_point[0] + 1  # 1-indexed
        line_end = node.end_point[0] + 1
        purpose = self._extract_symbol_purpose(
            node=node,
            lines=lines,
            name=name,
            calls=calls,
            conditions=conditions,
            returns=returns,
            state_writes=state_writes,
            is_async=is_async,
            kind="function",
        )

        return FunctionSkeleton(
            name=name,
            line_start=line_start,
            line_end=line_end,
            is_async=is_async,
            is_method=class_name is not None,
            class_name=class_name,
            parameters=parameters,
            calls=calls,
            conditions=conditions,
            returns=returns,
            raises=raises,
            decorators=decorators,
            logic_vars=logic_vars,
            purpose=purpose,
            sections=sections,
            state_writes=state_writes,
        )

    def _extract_sections(self, node: "Node", lines: List[str]) -> List[str]:
        """Extract concise section notes from inside a function/class body."""
        import re
        sections = []
        seen_norm = set()
        start = node.start_point[0] + 1
        end = node.end_point[0]
        for index in range(start, min(end + 1, len(lines))):
            stripped = lines[index].strip()
            if not stripped.startswith("#"):
                continue
            content = stripped.lstrip("#").strip(" -=\t")
            if len(content) < 6 or not re.search(r'[A-Za-z]', content):
                continue
            content = re.sub(r'\s+', ' ', content)
            content = re.sub(r'\b(V\d+(?:\.\d+)?)\b', lambda m: m.group(1).lower(), content)
            content = content[:92].rstrip(' ,;:.')
            norm = content.lower()
            if norm not in seen_norm:
                sections.append(content)
                seen_norm.add(norm)
        return sections[:4]

    def _extract_state_writes(self, body_node: "Node") -> List[str]:
        """Extract important attribute updates like state.foo = ... or self.bar = ...."""
        writes = []

        def target_name(target: "Node") -> Optional[str]:
            if target.type == "identifier":
                return target.text.decode("utf-8", errors="ignore")
            if target.type == "attribute":
                text = target.text.decode("utf-8", errors="ignore")
                return text if "." in text else None
            return None

        def walk(n):
            if n.type in ("assignment", "augmented_assignment") and n.children:
                lhs = n.children[0]
                name = target_name(lhs)
                if name and (name.startswith("state.") or name.startswith("self.")):
                    writes.append(name)
            for child in n.children:
                walk(child)

        walk(body_node)
        deduped = []
        seen = set()
        for item in writes:
            if item not in seen:
                deduped.append(item)
                seen.add(item)
        return deduped[:10]

    def _extract_symbol_purpose(
        self,
        node: "Node",
        lines: List[str],
        name: str,
        calls: List[str],
        conditions: List[str],
        returns: List[str],
        state_writes: List[str],
        is_async: bool,
        kind: str,
    ) -> str:
        """Extract a concise purpose from docstrings/comments, else infer one."""
        inferred = self._infer_class_purpose(name, state_writes, calls, returns) \
            if kind == "class" else self._infer_function_purpose(
                name=name,
                calls=calls,
                conditions=conditions,
                returns=returns,
                state_writes=state_writes,
                is_async=is_async,
            )

        docstring = self._extract_docstring_text(node, lines)
        if docstring:
            return self._merge_purpose(docstring, inferred)

        leading = self._extract_leading_comment_text(node, lines)
        if leading:
            return self._merge_purpose(leading, inferred)

        return inferred

    def _safe_trim(self, text: str, limit: int = 170) -> str:
        """Trim text without breaking mid-word, preserving readability."""
        text = " ".join(text.split())
        if len(text) <= limit:
            return text
        head = text[:limit]
        last_space = head.rfind(" ")
        if last_space > 40:
            head = head[:last_space]
        return head.rstrip(" ,;:") + "..."

    def _merge_purpose(self, primary: str, fallback: str) -> str:
        """Keep explicit summaries, but add inferred detail when they are too short."""
        primary = self._safe_trim(primary.strip().rstrip(".:"), 170)
        fallback = self._safe_trim(fallback.strip().rstrip(".:"), 150)
        if not primary:
            return fallback
        if len(primary) >= 48 or not fallback:
            return primary
        fallback_tail = fallback.split("; ", 1)[1] if "; " in fallback else fallback
        if fallback_tail and fallback_tail.lower() not in primary.lower():
            return f"{primary}; {fallback_tail}"
        return primary

    def _extract_docstring_text(self, node: "Node", lines: List[str]) -> str:
        """Get the first docstring sentence from a function/class body when present."""
        import re
        start = node.start_point[0] + 1
        limit = min(node.end_point[0] + 1, start + 8, len(lines))
        for index in range(start, limit):
            stripped = lines[index].strip()
            if not stripped:
                continue
            if stripped.startswith(("'''", '"""')):
                quote = stripped[:3]
                text = stripped[3:]
                collected = [text]
                if quote in text:
                    collected = [text.split(quote)[0]]
                else:
                    for inner_index in range(index + 1, limit):
                        inner = lines[inner_index].strip()
                        if quote in inner:
                            collected.append(inner.split(quote)[0])
                            break
                        collected.append(inner)
                normalized = re.sub(r'\s+', ' ', ' '.join(collected)).strip(' "\'')
                # Prefer complete first sentence, but avoid splitting numbered lists (1. 2. 3.).
                if re.search(r'\b\d+\.', normalized):
                    return self._safe_trim(normalized, 170)
                sentence = re.split(r'(?<=[.!?])\s+', normalized, maxsplit=1)[0]
                return self._safe_trim(sentence or normalized, 170)
            break
        return ""

    def _extract_leading_comment_text(self, node: "Node", lines: List[str]) -> str:
        """Get a concise leading comment block directly above a symbol."""
        import re
        comments = []
        index = node.start_point[0] - 1
        while index >= 0:
            stripped = lines[index].strip()
            if not stripped:
                if comments:
                    break
                index -= 1
                continue
            if not stripped.startswith("#"):
                break
            content = stripped.lstrip("#").strip(" -=\t")
            if re.search(r'[A-Za-z]', content):
                comments.append(content)
            index -= 1
        comments.reverse()
        if not comments:
            return ""
        return self._safe_trim(' '.join(comments), 170)

    def _compress_constant_value(self, name: str, value: str) -> str:
        """Compress long literal constants (especially ABI dict/list blobs)."""
        value = value.strip()
        if len(value) <= 60:
            return value
        if value.startswith("["):
            if name.endswith("_ABI"):
                return f"[{name}_SPEC]"
            return "[LIST_SPEC]"
        if value.startswith("{"):
            return "{DICT_SPEC}"
        return value[:60] + "..."

    def _infer_function_purpose(
        self,
        name: str,
        calls: List[str],
        conditions: List[str],
        returns: List[str],
        state_writes: List[str],
        is_async: bool,
    ) -> str:
        """Infer a compact purpose line when no docstring/comment exists."""
        action = name.replace("_", " ")
        parts = []
        if state_writes:
            parts.append("updates " + ", ".join(state_writes[:4]))
        if returns:
            parts.append("returns " + ", ".join(r.replace("return ", "") for r in returns[:3]))
        elif conditions:
            parts.append("decision-heavy logic")
        if calls:
            parts.append("uses " + ", ".join(calls[:3]))
        prefix = "async " if is_async else ""
        detail = " | ".join(parts[:3])
        return f"{prefix}{action}" + (f"; {detail}" if detail else "")

    def _infer_class_purpose(
        self,
        name: str,
        state_writes: List[str],
        calls: List[str],
        returns: List[str],
    ) -> str:
        """Infer a compact class purpose when no explicit summary exists."""
        label = name.replace("_", " ")
        if name.lower().endswith("state"):
            return f"state container for {label}"
        if calls:
            return f"class for {label}; uses {', '.join(calls[:2])}"
        if returns:
            return f"class for {label}; returns {', '.join(returns[:2])}"
        if state_writes:
            return f"class for {label}; updates {', '.join(state_writes[:2])}"
        return f"class for {label}"

    def _build_class_lifecycle(self, skeleton: FileSkeleton, cls: ClassSkeleton) -> List[str]:
        """Summarize where a state-heavy class gets updated across the file."""
        import re

        field_names = []
        for field_line in cls.fields:
            match = re.match(r'^@?([A-Za-z_][A-Za-z0-9_]*)\s*:', field_line)
            if match:
                field_names.append(match.group(1))

        if len(field_names) < 6:
            return []

        updater_map: Dict[str, List[str]] = {}

        def add_updates(func_name: str, writes: List[str], allowed_prefixes: tuple[str, ...]):
            touched = []
            for write in writes:
                if not write.startswith(allowed_prefixes):
                    continue
                attr = write.split(".", 1)[1]
                if attr in field_names and attr not in touched:
                    touched.append(attr)
            if touched:
                updater_map[func_name] = touched

        for func in skeleton.functions:
            add_updates(func.name, func.state_writes, ("state.",))
        for method in cls.methods:
            add_updates(method.name, method.state_writes, ("self.", "state."))

        lifecycle_lines = []
        for func_name, touched in sorted(
            updater_map.items(), key=lambda item: (-len(item[1]), item[0])
        ):
            summary = ", ".join(touched[:8])
            if len(touched) > 8:
                summary += ", ..."
            lifecycle_lines.append(f"{func_name} -> {summary}")

        return lifecycle_lines[:8]

    def _extract_calls(
        self, node: "Node", config: LanguageConfig
    ) -> List[str]:
        """Extract function calls, excluding noise (print, log, etc.)."""
        calls = []
        seen = set()

        def walk(n):
            if n.type in config.call_types:
                call_text = n.text.decode("utf-8", errors="ignore")
                call_name = call_text.split("(")[0].strip()
                excluded = any(
                    call_name.startswith(prefix)
                    for prefix in self.EXCLUDED_CALL_PREFIXES
                )
                if not excluded and call_name not in seen and len(call_name) < 80:
                    calls.append(call_name)
                    seen.add(call_name)
            for child in n.children:
                walk(child)

        walk(node)
        return calls[:15]  # raised from 10

    def _extract_conditions(
        self, node: "Node", lines: List[str], config: LanguageConfig
    ) -> List[str]:
        """Extract if/elif conditions as readable strings."""
        conditions = []

        def walk(n):
            if n.type in config.condition_types:
                line = lines[n.start_point[0]].strip()
                if line.startswith("if ") or line.startswith("elif "):
                    cond = line.split("#", 1)[0].rstrip(":").strip()
                    if len(cond) > 140:
                        cond = cond[:137] + "..."
                    conditions.append(cond)
            for child in n.children:
                walk(child)

        walk(node)

        deduped_conditions = []
        seen_conditions = set()
        for cond in conditions:
            if cond not in seen_conditions:
                deduped_conditions.append(cond)
                seen_conditions.add(cond)

        def score_condition(cond: str, index: int) -> tuple:
            """
            Prefer conditions that carry more decision detail:
            equality/inequality checks, string/enum comparisons, membership,
            multi-part logic, and later branch conditions that are often the
            actual action dispatch after guard clauses.
            """
            score = 0
            if "==" in cond or "!=" in cond:
                score += 4
            if '"' in cond or "'" in cond:
                score += 3
            if " in " in cond or " not in " in cond:
                score += 2
            if " and " in cond or " or " in cond:
                score += 2
            if any(ch.isupper() for ch in cond):
                score += 1
            if len(cond) >= 40:
                score += 1
            return (score, index)

        if len(deduped_conditions) <= 22:
            return deduped_conditions

        ranked = sorted(
            enumerate(deduped_conditions),
            key=lambda item: score_condition(item[1], item[0]),
            reverse=True,
        )
        selected_indexes = {index for index, _ in ranked[:22]}
        return [
            cond
            for index, cond in enumerate(deduped_conditions)
            if index in selected_indexes
        ]

    def _extract_returns(
        self, node: "Node", lines: List[str], config: LanguageConfig
    ) -> List[str]:
        """Extract return values."""
        import re
        returns = []

        def normalize_return(line: str, node_text: str) -> Optional[str]:
            if line == "return":
                return None
            if line.startswith("return {"):
                keys = re.findall(r'["\']([A-Za-z_][A-Za-z0-9_]*)["\']\s*:', node_text)
                if keys:
                    summary = ",".join(keys[:10])
                    if len(keys) > 10:
                        summary += ",..."
                    return f"return dict[{summary}]"
                return "return dict"
            if len(line) > 80:
                return line[:77] + "..."
            return line

        def walk(n):
            if n.type in config.return_types:
                line = lines[n.start_point[0]].strip()
                node_text = n.text.decode("utf-8", errors="ignore").strip()
                normalized = normalize_return(line, node_text)
                if normalized:
                    returns.append(normalized)
            for child in n.children:
                walk(child)

        walk(node)
        deduped_returns = []
        seen_returns = set()
        for ret in returns:
            if ret not in seen_returns:
                deduped_returns.append(ret)
                seen_returns.add(ret)

        def score_return(ret: str, index: int) -> tuple:
            score = 0
            if '"' in ret or "'" in ret:
                score += 4
            if "dict[" in ret:
                score += 3
            if len(ret) >= 18:
                score += 1
            return (score, -index)

        ranked = sorted(
            enumerate(deduped_returns),
            key=lambda item: score_return(item[1], item[0]),
            reverse=True,
        )
        selected_indexes = {index for index, _ in ranked[:6]}
        return [
            ret
            for index, ret in enumerate(deduped_returns)
            if index in selected_indexes
        ]

    def _extract_raises(
        self, node: "Node", lines: List[str]
    ) -> List[str]:
        """Extract raised exceptions."""
        raises = []

        def walk(n):
            if n.type == "raise_statement":
                line = lines[n.start_point[0]].strip()
                raises.append(line)
            for child in n.children:
                walk(child)

        walk(node)
        return raises[:3]

    def _extract_constants(
        self, root: "Node", lines: List[str], config: LanguageConfig
    ) -> List[str]:
        """
        Extract module-level constants (ALL_CAPS = value), redacting secrets.
        Priority order:
          1. Mode flags first (SIMULATION_MODE, DEBUG_MODE) â€” most important
          2. Numeric/bool trading params
          3. Everything else
        Secret values are redacted but still shown (key name is valuable).
        """
        import re
        raw: List[str] = []
        for node in root.children:
            if node.type in ("expression_statement", "assignment"):
                node_text = node.text.decode("utf-8", errors="ignore").strip()
                normalized = re.sub(r'\s+', ' ', node_text)
                if re.match(r'^[A-Z][A-Z0-9_]{2,}\s*=', normalized):
                    name, _, value = normalized.partition("=")
                    name = name.strip()
                    value = self._compress_constant_value(name, value)
                    compact = f"{name} = {value}"
                    raw.append(self._redact(compact))

        MODE_WORDS = ("MODE", "ENABLED", "DISABLED", "FLAG", "DEBUG",
                      "SIMULATION", "LIVE", "TEST")
        NUMERIC_RE = re.compile(r'=\s*[-\d.]+\b')

        def score_constant(line: str, index: int) -> tuple:
            name, _, value = line.partition('=')
            name = name.strip()
            value = value.strip()
            score = 0
            if any(word in name for word in MODE_WORDS):
                score += 7
            if NUMERIC_RE.search(line):
                score += 4
            if value.startswith(("{", "[")):
                score += 3
            if "http" in value.lower():
                score += 3
            if any(word in name for word in ("TOKEN", "RPC", "API", "ADDRESS")):
                score += 2
            if any(word in name for word in ("COIN", "SLUG", "CHAT")):
                score += 2
            if len(line) >= 40:
                score += 1
            return (score, -index)

        ranked = sorted(
            enumerate(raw),
            key=lambda item: score_constant(item[1], item[0]),
            reverse=True,
        )
        selected_indexes = {index for index, _ in ranked[:30]}
        return [line for index, line in enumerate(raw) if index in selected_indexes]

    def _extract_logic_vars(self, body_node: "Node", lines: List[str]) -> List[str]:
        """
        Extract key local variables from a function body:
        1. Literal list/tuple/dict of numbers (threshold tables, quotas, etc.)
        2. Direct numeric assignments used as caps/limits (e.g. goal_profit = losing_costs * 2.0)
        3. Named inline constants (e.g. MAX_CAP = 9.9)
        """
        import re
        NUMERIC_CONTAINER = re.compile(
            r'^[\[\({]'
            r'[\d\s.,\-\'":\w]*'
            r'[\]\)}]$'
        )
        PLAIN_NUMBER = re.compile(r'^-?\d+\.?\d*$')
        PLAIN_BOOL = re.compile(r'^(True|False)$')
        NUMERIC_EXPR = re.compile(
            r'^[\w.]+\s*[\*\/\+\-]\s*[\d.]+$|^[\d.]+\s*[\*\/\+\-]\s*[\w.]+$'
        )
        SKIP_NAMES = {"i", "j", "k", "n", "x", "y", "e", "ex", "err",
                      "idx", "len", "tmp", "res", "ret", "val",
                      "result", "response", "data", "msg", "text",
                      "url", "params", "headers", "body", "row"}
        vars_found = []

        def walk(n, depth=0):
            if depth > 12:
                return
            if n.type == "assignment":
                children = list(n.children)
                lhs_node = children[0] if children else None
                rhs_node = children[-1] if len(children) >= 3 else None
                if lhs_node and rhs_node and lhs_node.type == "identifier":
                    name = lhs_node.text.decode("utf-8")
                    rhs_text = rhs_node.text.decode("utf-8", errors="ignore").strip()
                    is_numeric_like = bool(
                        re.search(r'\d', rhs_text)
                        and (
                            NUMERIC_CONTAINER.match(rhs_text)
                            or PLAIN_NUMBER.match(rhs_text)
                            or NUMERIC_EXPR.match(rhs_text)
                        )
                    )
                    is_bool_like = bool(PLAIN_BOOL.match(rhs_text))
                    if (
                        name not in SKIP_NAMES
                        and len(name) > 2
                        and len(rhs_text) < 70
                        and (is_bool_like or is_numeric_like)
                    ):
                        vars_found.append(f"{name}={rhs_text}")
            for child in n.children:
                walk(child, depth + 1)

        walk(body_node)
        deduped_vars = []
        seen_vars = set()
        for item in vars_found:
            if item not in seen_vars:
                deduped_vars.append(item)
                seen_vars.add(item)
        return deduped_vars[:8]  # max 8 logic vars per function

    def _has_main_guard(self, source: str) -> bool:
        """Check if file has if __name__ == '__main__' guard."""
        return "__name__" in source and "__main__" in source

    def _is_entry_point(self, source: str, functions: list) -> bool:
        """Check if file is an entry point (has main() or asyncio.run)."""
        has_main_fn = any(f.name == "main" for f in functions)
        has_asyncio_run = "asyncio.run(" in source
        return has_main_fn or has_asyncio_run or self._has_main_guard(source)

    def _extract_class(
        self,
        node: "Node",
        lines: List[str],
        config: LanguageConfig,
    ) -> Optional[ClassSkeleton]:
        """Extract class skeleton with all methods."""
        import re
        name = ""
        bases = []
        methods = []
        fields = []

        for child in node.children:
            if child.type == "identifier":
                name = child.text.decode("utf-8")
            elif child.type == "argument_list" or child.type == "base_clause":
                for base in child.children:
                    if base.type == "identifier":
                        bases.append(base.text.decode("utf-8"))

        if not name:
            return None

        # Extract methods and fields from class body
        for child in node.children:
            if child.type == "block":
                for item in child.children:
                    if item.type in config.function_types:
                        method = self._extract_function(
                            item, lines, config, class_name=name
                        )
                        if method:
                            methods.append(method)
                    elif item.type in ("expression_statement", "assignment"):
                        line = lines[item.start_point[0]].strip()
                        # Dataclass field pattern: name: type or name: type = default
                        if re.match(r'^\w+\s*:', line) and not line.startswith('#'):
                            fields.append(line[:60])

        purpose = self._extract_symbol_purpose(
            node=node,
            lines=lines,
            name=name,
            calls=[m.name for m in methods],
            conditions=[],
            returns=[],
            state_writes=fields,
            is_async=False,
            kind="class",
        )

        return ClassSkeleton(
            name=name,
            line_start=node.start_point[0] + 1,
            bases=bases,
            methods=methods,
            fields=fields,
            purpose=purpose,
        )

    def _extract_with_fallback(
        self,
        source: str,
        filepath: str,
        config: LanguageConfig,
    ) -> FileSkeleton:
        """
        Fallback extraction using regex when tree-sitter is not available.
        Less accurate but works without tree-sitter bindings.
        """
        import re
        lines = source.split("\n")
        imports = []
        functions = []

        for i, line in enumerate(lines):
            stripped = line.strip()
            # Imports
            if stripped.startswith("import ") or stripped.startswith("from "):
                imports.append(stripped[:80])
            # Function definitions (Python)
            elif re.match(r"^(async\s+)?def\s+\w+", stripped):
                match = re.match(
                    r"^(async\s+)?def\s+(\w+)\s*\(([^)]*)\)", stripped
                )
                if match:
                    is_async = bool(match.group(1))
                    fname = match.group(2)
                    params_raw = match.group(3)
                    params = [
                        p.strip().split(":")[0].split("=")[0].strip()
                        for p in params_raw.split(",")
                        if p.strip() and p.strip() not in ("self", "cls")
                    ]
                    functions.append(FunctionSkeleton(
                        name=fname,
                        line_start=i + 1,
                        line_end=i + 1,
                        is_async=is_async,
                        is_method=False,
                        class_name=None,
                        parameters=params,
                        calls=[],
                        conditions=[],
                        returns=[],
                        raises=[],
                        decorators=[],
                        logic_vars=[],
                        purpose="",
                        sections=[],
                        state_writes=[],
                    ))

        has_main_guard = "__name__" in source and "__main__" in source
        is_entry_point = (
            any(f.name == "main" for f in functions)
            or "asyncio.run(" in source
            or has_main_guard
        )
        # Simple constant extraction for fallback â€” with redaction and prioritization
        import re as _re
        MODE_WORDS = ("MODE", "ENABLED", "DISABLED", "FLAG", "DEBUG", "SIMULATION", "LIVE")
        NUMERIC_RE = _re.compile(r'=\s*[-\d.]+\b')
        raw_consts = [
            self._redact(line.strip()[:90]) for line in lines
            if _re.match(r'^[A-Z][A-Z0-9_]{2,}\s*=', line.strip())
        ]
        compressed_consts = []
        for line in raw_consts:
            name, _, value = line.partition("=")
            name = name.strip()
            value = self._compress_constant_value(name, value)
            compressed_consts.append(f"{name} = {value}")
        raw_consts = compressed_consts
        priority_c = [c for c in raw_consts if any(w in c.split('=')[0] for w in MODE_WORDS)]
        trading_c  = [c for c in raw_consts if c not in priority_c and NUMERIC_RE.search(c)]
        rest_c     = [c for c in raw_consts if c not in priority_c and c not in trading_c]
        constants  = (priority_c + trading_c + rest_c)[:30]

        # Fallback class extraction
        classes = []
        i = 0
        while i < len(lines):
            stripped = lines[i].strip()
            cls_match = re.match(r'^class\s+(\w+)\s*(?:\(([^)]*)\))?\s*:', stripped)
            if cls_match:
                cls_name = cls_match.group(1)
                bases_raw = cls_match.group(2) or ""
                bases = [b.strip() for b in bases_raw.split(",") if b.strip()]
                cls_line = i + 1
                cls_methods = []
                cls_fields = []
                # Scan class body (next indented lines)
                j = i + 1
                while j < len(lines) and j < i + 200:
                    body_line = lines[j]
                    body_stripped = body_line.strip()
                    if body_stripped and not body_line.startswith((" ", "\t")):
                        break  # back to module level
                    fn_match = re.match(r'^\s+(async\s+)?def\s+(\w+)\s*\(([^)]*)\)', body_line)
                    if fn_match:
                        m_async = bool(fn_match.group(1))
                        m_name = fn_match.group(2)
                        m_params_raw = fn_match.group(3)
                        m_params = [
                            p.strip().split(":")[0].split("=")[0].strip()
                            for p in m_params_raw.split(",")
                            if p.strip() and p.strip() not in ("self", "cls")
                        ]
                        cls_methods.append(FunctionSkeleton(
                            name=m_name, line_start=j + 1, line_end=j + 1,
                            is_async=m_async, is_method=True, class_name=cls_name,
                            parameters=m_params, calls=[], conditions=[],
                            returns=[], raises=[], decorators=[], logic_vars=[],
                            purpose="", sections=[], state_writes=[],
                        ))
                    # Dataclass fields
                    field_match = re.match(r'^\s+(\w+)\s*:', body_stripped)
                    if field_match and not body_stripped.startswith('#') and 'def ' not in body_stripped:
                        cls_fields.append(body_stripped[:60])
                    j += 1
                classes.append(ClassSkeleton(
                    name=cls_name, line_start=cls_line,
                    bases=bases, methods=cls_methods, fields=cls_fields,
                    purpose=f"class for {cls_name.replace('_', ' ')}",
                ))
            i += 1

        return FileSkeleton(
            filepath=filepath,
            language=config.name,
            imports=imports,
            functions=functions,
            classes=classes,
            constants=constants,
            has_main_guard=has_main_guard,
            is_entry_point=is_entry_point,
            total_lines=len(lines),
            skeleton_lines=0,
            token_estimate=0,
        )

    def to_text(self, skeleton: FileSkeleton) -> str:
        """
        Convert skeleton to compressed text format for AI consumption.
        
        Format legend (also sent to AI in system prompt):
        > = CALLS    ? = IF condition    < = RETURNS
        ! = RAISES   ~ = async           [N] = line number
        """
        lines = []
        fname = os.path.basename(skeleton.filepath)
        lines.append(f"FILE:{fname} [{skeleton.language}]")

        if skeleton.is_entry_point:
            lines.append("ENTRY_POINT:yes")

        if skeleton.imports:
            import_names = []
            for imp in skeleton.imports:
                # Extract just the module names for brevity
                if imp.startswith("from "):
                    parts = imp.split()
                    if len(parts) >= 2:
                        import_names.append(parts[1])
                elif imp.startswith("import "):
                    names = imp.replace("import ", "").split(",")
                    import_names.extend([n.strip() for n in names])
            if import_names:
                lines.append(f"IMPORTS:{','.join(import_names[:12])}")

        # Constants (top 30 â€” scored for operational importance)
        if skeleton.constants:
            for const in skeleton.constants[:30]:
                lines.append(f"CONST:{const}")

        # Top-level functions
        for func in skeleton.functions:
            lines.extend(self._func_to_lines(func))

        # Classes
        for cls in skeleton.classes:
            bases_str = f"({','.join(cls.bases)})" if cls.bases else ""
            lines.append(f"CLASS:{cls.name}{bases_str}[{cls.line_start}]")
            if cls.purpose and (len(cls.fields) >= 8 or len(cls.methods) >= 3):
                lines.append(f"  ={cls.purpose}")
            lifecycle = self._build_class_lifecycle(skeleton, cls)
            for item in lifecycle:
                lines.append(f"  %{item}")
            # Dataclass fields
            for field_line in cls.fields[:30]:
                lines.append(f"  .{field_line}")
            for method in cls.methods:
                method_lines = self._func_to_lines(method, indent="  ")
                lines.extend(method_lines)

        return "\n".join(lines)

    def _func_to_lines(
        self, func: FunctionSkeleton, indent: str = ""
    ) -> List[str]:
        """Convert one function skeleton to compressed text lines with enhanced format."""
        lines = []
        show_rich_detail = (
            len(func.conditions) >= 4
            or len(func.logic_vars) >= 2
            or len(func.state_writes) >= 3
            or len(func.calls) >= 6
            or len(func.sections) >= 2
        )
        async_marker = "~" if func.is_async else ""
        params = f"({','.join(func.parameters)})" if func.parameters else "()"
        
        # Enhanced header with line range
        lines.append(
            f"{indent}{async_marker}{func.name}{params}[{func.line_start}-{func.line_end}]"
        )
        
        if show_rich_detail and func.purpose:
            lines.append(f"{indent}  ={func.purpose}")
        
        if show_rich_detail and func.sections:
            compact_note = " | ".join(func.sections[:3])
            lines.append(f"{indent}  NOTE:{compact_note}")
        
        # New: Enhanced subsections for complex functions
        if show_rich_detail:
            # STATE CHANGES subsection
            if func.state_writes:
                lines.append(f"{indent}  &STATE CHANGES:")
                for write in func.state_writes[:6]:
                    lines.append(f"{indent}    â€¢ {write}")
                if len(func.state_writes) > 6:
                    lines.append(f"{indent}    â€¢ ... ({len(func.state_writes) - 6} more)")
            
            # DECISIONS subsection (from key conditions and returns)
            if func.conditions or func.returns:
                lines.append(f"{indent}  &DECISIONS:")
                if func.calls:
                    lines.append(f"{indent}    â€¢ driver: {func.calls[0]}()")
                for ret in func.returns[:2]:
                    lines.append(f"{indent}      â†’ {ret.replace('return ', '')}")
                if func.conditions and not func.returns:
                    lines.append(f"{indent}    â€¢ branches: {len(func.conditions)}")
            
            # RISK_GUARDS subsection (from important conditions)
            if len(func.conditions) >= 2:
                lines.append(f"{indent}  &RISK_GUARDS:")
                important_conds = []
                for cond in func.conditions[:4]:
                    # Extract guard keywords
                    if any(kw in cond.lower() for kw in ["budget", "cap", "limit", "max", "min", "threshold", "cooldown", "time", "guard", "check", "verify"]):
                        important_conds.append(cond)
                if not important_conds:
                    important_conds = func.conditions[:2]
                for cond in important_conds:
                    lines.append(f"{indent}    â€¢ {cond}")
        
        # Legacy format items
        for lvar in func.logic_vars:
            lines.append(f"{indent}  @{lvar}")
        call_lines = func.calls if not show_rich_detail else func.calls[:10]
        for call in call_lines:
            lines.append(f"{indent}  >{call}()")
        skip_conds = set()
        if show_rich_detail:
            for cond in func.conditions:
                if any(kw in cond.lower() for kw in ["budget", "cap", "limit", "max", "min", "threshold", "cooldown", "time", "guard", "check", "verify"]):
                    skip_conds.add(cond)
            cond_lines = [c for c in func.conditions if c not in skip_conds][:10]
        else:
            cond_lines = func.conditions
        for cond in cond_lines:
            lines.append(f"{indent}  ?{cond}")
        for ret in func.returns:
            clean = ret.replace("return ", "")
            lines.append(f"{indent}  <{clean}")
        for exc in func.raises:
            clean = exc.replace("raise ", "")
            lines.append(f"{indent}  !{clean}")
        return lines

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation: chars / 4."""
        return len(text) // 4

    def get_stats(self, skeletons: Dict[str, FileSkeleton]) -> dict:
        """Return compression statistics for a set of skeletons."""
        total_lines = sum(s.total_lines for s in skeletons.values())
        total_skeleton_tokens = sum(s.token_estimate for s in skeletons.values())
        raw_token_estimate = total_lines * 38  # avg 38 tokens per raw line

        return {
            "files": len(skeletons),
            "total_lines": total_lines,
            "raw_token_estimate": raw_token_estimate,
            "skeleton_token_estimate": total_skeleton_tokens,
            "reduction_percent": round(
                (1 - total_skeleton_tokens / max(raw_token_estimate, 1)) * 100, 1
            ),
            "compression_ratio": round(
                raw_token_estimate / max(total_skeleton_tokens, 1), 1
            ),
        }

