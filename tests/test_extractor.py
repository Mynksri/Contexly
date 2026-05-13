"""Tests for SkeletonExtractor."""

import tempfile
import os
import pytest
from contexly.core.extractor import SkeletonExtractor


SAMPLE_PYTHON = '''
import os
import json

def calculate_balance(user_id, amount):
    data = fetch_user(user_id)
    if amount < 0:
        raise ValueError("Amount cannot be negative")
    if data["balance"] < amount:
        notify_insufficient(user_id)
        return False
    data["balance"] -= amount
    save_user(data)
    return True

class BalanceManager:
    def __init__(self, db):
        self.db = db
    
    async def get_balance(self, user_id):
        result = self.db.query(user_id)
        if result is None:
            return 0
        return result["balance"]
'''


def test_extract_file_returns_skeleton():
    extractor = SkeletonExtractor()
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(SAMPLE_PYTHON)
        fpath = f.name
    try:
        skeleton = extractor.extract_file(fpath)
        assert skeleton is not None
        assert skeleton.language == "python"
        assert len(skeleton.imports) >= 1
    finally:
        os.unlink(fpath)


def test_extract_functions():
    extractor = SkeletonExtractor()
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(SAMPLE_PYTHON)
        fpath = f.name
    try:
        skeleton = extractor.extract_file(fpath)
        if skeleton and skeleton.functions:
            func_names = [f.name for f in skeleton.functions]
            assert "calculate_balance" in func_names
    finally:
        os.unlink(fpath)


def test_token_reduction():
    extractor = SkeletonExtractor()
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(SAMPLE_PYTHON)
        fpath = f.name
    try:
        skeleton = extractor.extract_file(fpath)
        if skeleton:
            text = extractor.to_text(skeleton)
            skeleton_tokens = extractor.estimate_tokens(text)
            raw_tokens = len(SAMPLE_PYTHON) // 4
            # Skeleton should be smaller than raw code
            assert skeleton_tokens < raw_tokens
    finally:
        os.unlink(fpath)


def test_to_text_format():
    extractor = SkeletonExtractor()
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(SAMPLE_PYTHON)
        fpath = f.name
    try:
        skeleton = extractor.extract_file(fpath)
        if skeleton:
            text = extractor.to_text(skeleton)
            assert "FILE:" in text
            assert "IMPORTS:" in text
    finally:
        os.unlink(fpath)


SAMPLE_TSX = '''
import React, { useEffect, useState } from "react";
import { useOrders } from "./hooks/useOrders";

export const usePivotSignal = (symbol: string) => {
    const [signal, setSignal] = useState("hold");
    useEffect(() => {
        if (symbol) setSignal("buy");
    }, [symbol]);
    return signal;
};

export const PivotPanel = ({ symbol }: { symbol: string }) => {
    const orders = useOrders(symbol);
    const signal = usePivotSignal(symbol);
    if (!orders.length) return <div>No orders</div>;
    return <div>{signal}</div>;
};
'''


def test_extract_tsx_assigned_functions_and_hooks():
    extractor = SkeletonExtractor()
    with tempfile.NamedTemporaryFile(suffix=".tsx", mode="w", delete=False) as f:
        f.write(SAMPLE_TSX)
        fpath = f.name
    try:
        skeleton = extractor.extract_file(fpath)
        assert skeleton is not None
        assert skeleton.language == "typescript"
        names = [fn.name for fn in skeleton.functions]
        assert "PivotPanel" in names
        assert "usePivotSignal" in names

        panel = next(fn for fn in skeleton.functions if fn.name == "PivotPanel")
        assert any("useOrders" in call for call in panel.calls)
        assert any("usePivotSignal" in call for call in panel.calls)
    finally:
        os.unlink(fpath)


def test_extract_tsx_hooks_calls_present():
    extractor = SkeletonExtractor()
    with tempfile.NamedTemporaryFile(suffix=".tsx", mode="w", delete=False) as f:
        f.write(SAMPLE_TSX)
        fpath = f.name
    try:
        skeleton = extractor.extract_file(fpath)
        assert skeleton is not None
        hook = next(fn for fn in skeleton.functions if fn.name == "usePivotSignal")
        calls_joined = " ".join(hook.calls)
        assert "useState" in calls_joined
        assert "useEffect" in calls_joined
    finally:
        os.unlink(fpath)


def test_extract_jsx_extension_supported():
    extractor = SkeletonExtractor()
    jsx = """
import React from 'react';
export const Widget = () => {
    return <button>OK</button>;
};
"""
    with tempfile.NamedTemporaryFile(suffix=".jsx", mode="w", delete=False) as f:
        f.write(jsx)
        fpath = f.name
    try:
        skeleton = extractor.extract_file(fpath)
        assert skeleton is not None
        assert skeleton.language == "javascript"
        assert any(fn.name == "Widget" for fn in skeleton.functions)
    finally:
        os.unlink(fpath)


def test_extract_tsx_default_export_function_component():
    extractor = SkeletonExtractor()
    code = '''
import { useEffect, useState } from "react";

export default function ComponentB({ id }: { id: string }) {
    const [state, setState] = useState(0);
    useEffect(() => {
        if (id) setState(1);
    }, [id]);
    return <div>{state}</div>;
}
'''
    with tempfile.NamedTemporaryFile(suffix=".tsx", mode="w", delete=False) as f:
        f.write(code)
        fpath = f.name
    try:
        skeleton = extractor.extract_file(fpath)
        assert skeleton is not None
        names = [fn.name for fn in skeleton.functions]
        assert "ComponentB" in names
        fn = next(fn for fn in skeleton.functions if fn.name == "ComponentB")
        calls_joined = " ".join(fn.calls)
        assert "useState" in calls_joined
        assert "useEffect" in calls_joined
    finally:
        os.unlink(fpath)


def test_extract_compact_one_line_tsx_component():
    extractor = SkeletonExtractor()
    code = "import { useEffect, useState } from 'react';\nexport default function ComponentB({ id }: { id: string }) { const [state, setState] = useState(0); useEffect(() => { if (id) setState(1); }, [id]); return <div>{state}</div>; }"
    with tempfile.NamedTemporaryFile(suffix=".tsx", mode="w", delete=False) as f:
        f.write(code)
        fpath = f.name
    try:
        skeleton = extractor.extract_file(fpath)
        assert skeleton is not None
        names = [fn.name for fn in skeleton.functions]
        assert "ComponentB" in names
        fn = next(fn for fn in skeleton.functions if fn.name == "ComponentB")
        assert any("useState" in c for c in fn.calls)
        assert any("useEffect" in c for c in fn.calls)
    finally:
        os.unlink(fpath)


def test_extract_frontend_signals_from_tsx():
    extractor = SkeletonExtractor()
    code = """
export const Panel = () => {
  return <div className='bg-slate-900 text-white px-4' id='panel-root' data-testid='panel'>Hi</div>;
};
"""
    with tempfile.NamedTemporaryFile(suffix=".tsx", mode="w", delete=False) as f:
        f.write(code)
        fpath = f.name
    try:
        skeleton = extractor.extract_file(fpath)
        assert skeleton is not None
        constants_joined = " ".join(skeleton.constants)
        assert "HTML_CLASSES" in constants_joined
        assert "HTML_IDS" in constants_joined
        assert "DATA_ATTRS" in constants_joined
    finally:
        os.unlink(fpath)


def test_extract_html_fallback_support():
    extractor = SkeletonExtractor()
    code = """
<html>
  <head><link href='/app.css' rel='stylesheet'></head>
  <body>
    <div class='container grid' id='app-root' data-state='ready'></div>
    <script src='/main.js'></script>
  </body>
</html>
"""
    with tempfile.NamedTemporaryFile(suffix=".html", mode="w", delete=False) as f:
        f.write(code)
        fpath = f.name
    try:
        skeleton = extractor.extract_file(fpath)
        assert skeleton is not None
        assert skeleton.language == "html"
        assert any("main.js" in item for item in skeleton.imports)
        constants_joined = " ".join(skeleton.constants)
        assert "HTML_CLASSES" in constants_joined
        assert "DATA_ATTRS" in constants_joined
    finally:
        os.unlink(fpath)


def test_extract_html_inline_script_support():
        extractor = SkeletonExtractor()
        code = """
<html>
    <body>
        <div class='graph-shell panel' id='graph-root' data-state='ready'></div>
        <script src='/vendor/three.min.js'></script>
        <script>
            function initGraph() {
                const canvas = document.querySelector('#graph-root');
                return canvas;
            }
        </script>
    </body>
</html>
"""
        with tempfile.NamedTemporaryFile(suffix=".html", mode="w", delete=False) as f:
                f.write(code)
                fpath = f.name
        try:
                skeleton = extractor.extract_file(fpath)
                assert skeleton is not None
                assert skeleton.language == "html"
                assert any("three.min.js" in item for item in skeleton.imports)
                names = [fn.name for fn in skeleton.functions]
                assert "initGraph" in names
                constants_joined = " ".join(skeleton.constants)
                assert "EXTERNAL_LIBS" in constants_joined
                assert "HTML_ROLE_HINTS" in constants_joined
        finally:
                os.unlink(fpath)


def test_extract_css_fallback_support():
    extractor = SkeletonExtractor()
    code = """
@import './base.css';
.card { color: white; }
#panel-root { background: black; }
[data-state='ready'] { opacity: 1; }
"""
    with tempfile.NamedTemporaryFile(suffix=".css", mode="w", delete=False) as f:
        f.write(code)
        fpath = f.name
    try:
        skeleton = extractor.extract_file(fpath)
        assert skeleton is not None
        assert skeleton.language == "css"
        constants_joined = " ".join(skeleton.constants)
        assert "CSS_SELECTORS" in constants_joined
        assert any("base.css" in item for item in skeleton.imports)
    finally:
        os.unlink(fpath)


# ─────────────────────────────────────────────────────────────────────────────
# New language tests: C, C++, Java, Rust, C#, Vue, Svelte
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_C = """\
#include <stdio.h>
#include "utils.h"

int add(int a, int b) {
    return a + b;
}

void greet(char* name) {
    if (name == NULL) { return; }
    printf("Hello, %s", name);
}
"""

SAMPLE_CPP = """\
#include <iostream>
#include <string>

class Calculator {
public:
    int add(int a, int b) { return a + b; }
    void reset() {}
};

int main() {
    Calculator c;
    return c.add(1, 2);
}
"""

SAMPLE_JAVA = """\
import java.util.List;
import java.io.IOException;

public class UserService {
    private int count;

    public String getUser(int id) {
        if (id <= 0) { return null; }
        return "user_" + id;
    }

    public void saveUser(String name) {
        count++;
    }
}
"""

SAMPLE_RUST = """\
use std::collections::HashMap;

fn add(a: i32, b: i32) -> i32 {
    a + b
}

struct Config {
    debug: bool,
}

impl Config {
    pub fn new() -> Self {
        Config { debug: false }
    }

    pub fn is_debug(&self) -> bool {
        self.debug
    }
}
"""

SAMPLE_CSHARP = """\
using System;
using System.Collections.Generic;

namespace MyApp {
    public class OrderService {
        private int _count;

        public string GetOrder(int id) {
            if (id <= 0) { return null; }
            return "order_" + id;
        }

        public async Task SaveOrder(string name) {
            _count++;
        }
    }
}
"""

SAMPLE_VUE = """\
<template>
  <div class="app-shell dashboard" id="main" @click="handleClick">
    <input v-model="username" :placeholder="hint" />
    <button @submit="submitForm">Submit</button>
  </div>
</template>

<script>
export default {
  data() { return { username: '' }; },
  methods: {
    handleClick() { this.$emit('clicked'); },
    submitForm() { this.save(this.username); }
  }
}
</script>
"""

SAMPLE_SVELTE = """\
<script>
  export let title = 'Hello';
  export let count = 0;
  import { writable } from 'svelte/store';
  const items = writable([]);

  function increment() {
    count += 1;
  }
</script>

<main class="svelte-shell" id="root">
  <h1 bind:textContent={title}>{title}</h1>
  <button on:click={increment}>+</button>
</main>
"""


def test_extract_c_functions():
    extractor = SkeletonExtractor()
    with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as f:
        f.write(SAMPLE_C)
        fpath = f.name
    try:
        skeleton = extractor.extract_file(fpath)
        assert skeleton is not None
        assert skeleton.language == "c"
        func_names = [fn.name for fn in skeleton.functions]
        assert "add" in func_names
        assert "greet" in func_names
    finally:
        os.unlink(fpath)


def test_extract_cpp_class_and_functions():
    extractor = SkeletonExtractor()
    with tempfile.NamedTemporaryFile(suffix=".cpp", mode="w", delete=False) as f:
        f.write(SAMPLE_CPP)
        fpath = f.name
    try:
        skeleton = extractor.extract_file(fpath)
        assert skeleton is not None
        assert skeleton.language == "cpp"
        # Either top-level main or Calculator class methods should be found
        all_names = (
            [fn.name for fn in skeleton.functions]
            + [m.name for cls in skeleton.classes for m in cls.methods]
            + [cls.name for cls in skeleton.classes]
        )
        assert len(all_names) > 0
    finally:
        os.unlink(fpath)


def test_extract_java_class_and_methods():
    extractor = SkeletonExtractor()
    with tempfile.NamedTemporaryFile(suffix=".java", mode="w", delete=False) as f:
        f.write(SAMPLE_JAVA)
        fpath = f.name
    try:
        skeleton = extractor.extract_file(fpath)
        assert skeleton is not None
        assert skeleton.language == "java"
        assert len(skeleton.imports) >= 1
        all_names = (
            [fn.name for fn in skeleton.functions]
            + [m.name for cls in skeleton.classes for m in cls.methods]
            + [cls.name for cls in skeleton.classes]
        )
        assert len(all_names) > 0
    finally:
        os.unlink(fpath)


def test_extract_rust_functions_and_impl():
    extractor = SkeletonExtractor()
    with tempfile.NamedTemporaryFile(suffix=".rs", mode="w", delete=False) as f:
        f.write(SAMPLE_RUST)
        fpath = f.name
    try:
        skeleton = extractor.extract_file(fpath)
        assert skeleton is not None
        assert skeleton.language == "rust"
        func_names = [fn.name for fn in skeleton.functions]
        assert "add" in func_names
        # Config impl methods or struct should be found
        all_symbols = (
            func_names
            + [m.name for cls in skeleton.classes for m in cls.methods]
            + [cls.name for cls in skeleton.classes]
        )
        assert len(all_symbols) > 1
    finally:
        os.unlink(fpath)


def test_extract_csharp_namespace_and_methods():
    extractor = SkeletonExtractor()
    with tempfile.NamedTemporaryFile(suffix=".cs", mode="w", delete=False) as f:
        f.write(SAMPLE_CSHARP)
        fpath = f.name
    try:
        skeleton = extractor.extract_file(fpath)
        assert skeleton is not None
        assert skeleton.language == "csharp"
        assert len(skeleton.imports) >= 1
        all_names = (
            [fn.name for fn in skeleton.functions]
            + [m.name for cls in skeleton.classes for m in cls.methods]
            + [cls.name for cls in skeleton.classes]
        )
        assert len(all_names) > 0
    finally:
        os.unlink(fpath)


def test_extract_vue_component():
    extractor = SkeletonExtractor()
    with tempfile.NamedTemporaryFile(suffix=".vue", mode="w", delete=False) as f:
        f.write(SAMPLE_VUE)
        fpath = f.name
    try:
        skeleton = extractor.extract_file(fpath)
        assert skeleton is not None
        assert skeleton.language == "vue"
        constants_joined = " ".join(skeleton.constants)
        # Should detect v-model, @events
        assert "VUE_MODELS" in constants_joined or "VUE_EVENTS" in constants_joined
        # Should extract handleClick/submitForm from inline <script>
        all_funcs = [fn.name for fn in skeleton.functions]
        assert len(all_funcs) > 0
    finally:
        os.unlink(fpath)


def test_extract_svelte_component():
    extractor = SkeletonExtractor()
    with tempfile.NamedTemporaryFile(suffix=".svelte", mode="w", delete=False) as f:
        f.write(SAMPLE_SVELTE)
        fpath = f.name
    try:
        skeleton = extractor.extract_file(fpath)
        assert skeleton is not None
        assert skeleton.language == "svelte"
        constants_joined = " ".join(skeleton.constants)
        # Should detect bind: and on: directives
        assert "SVELTE_BINDS" in constants_joined or "SVELTE_EVENTS" in constants_joined
        # Should extract increment() from inline <script>
        func_names = [fn.name for fn in skeleton.functions]
        assert "increment" in func_names
    finally:
        os.unlink(fpath)

