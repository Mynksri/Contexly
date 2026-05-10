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

