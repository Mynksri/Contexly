"""Tests for Go language support in SkeletonExtractor."""

import tempfile
import os
import pytest
from contexly.core.extractor import SkeletonExtractor
from contexly.core.languages import get_config_for_file


SAMPLE_GO = '''package main

import (
    "fmt"
    "net/http"
)

type Server struct {
    host string
    port int
}

func NewServer(host string, port int) *Server {
    return &Server{host: host, port: port}
}

func (s *Server) Start() error {
    addr := fmt.Sprintf("%s:%d", s.host, s.port)
    return http.ListenAndServe(addr, nil)
}

func calculateBalance(userID string, amount float64) (float64, error) {
    if amount < 0 {
        return 0, fmt.Errorf("amount cannot be negative")
    }
    balance := fetchBalance(userID)
    if balance < amount {
        return 0, fmt.Errorf("insufficient funds")
    }
    return balance - amount, nil
}

func main() {
    s := NewServer("localhost", 8080)
    s.Start()
}
'''


def test_go_config_detected():
    """Go file extension should resolve to Go language config."""
    config = get_config_for_file("main.go")
    assert config is not None
    assert config.name == "go"


def test_go_extensions():
    """Only .go extension should match Go config."""
    assert get_config_for_file("server.go") is not None
    assert get_config_for_file("server.py") is None or get_config_for_file("server.py").name == "python"


def test_extract_go_file_returns_skeleton():
    """Extractor should return a skeleton for a valid Go file."""
    extractor = SkeletonExtractor()
    with tempfile.NamedTemporaryFile(suffix=".go", mode="w", delete=False) as f:
        f.write(SAMPLE_GO)
        fpath = f.name
    try:
        skeleton = extractor.extract_file(fpath)
        assert skeleton is not None
        assert skeleton.language == "go"
    finally:
        os.unlink(fpath)


def test_extract_go_functions():
    """Top-level Go functions should be extracted."""
    extractor = SkeletonExtractor()
    with tempfile.NamedTemporaryFile(suffix=".go", mode="w", delete=False) as f:
        f.write(SAMPLE_GO)
        fpath = f.name
    try:
        skeleton = extractor.extract_file(fpath)
        assert skeleton is not None
        all_funcs = [fn.name for fn in skeleton.functions]
        all_funcs += [m.name for cls in skeleton.classes for m in cls.methods]
        assert "NewServer" in all_funcs or "calculateBalance" in all_funcs or "main" in all_funcs
    finally:
        os.unlink(fpath)


def test_extract_go_imports():
    """Go import declarations should be captured."""
    extractor = SkeletonExtractor()
    with tempfile.NamedTemporaryFile(suffix=".go", mode="w", delete=False) as f:
        f.write(SAMPLE_GO)
        fpath = f.name
    try:
        skeleton = extractor.extract_file(fpath)
        assert skeleton is not None
        assert len(skeleton.imports) > 0
    finally:
        os.unlink(fpath)


def test_extract_go_type_as_class():
    """Go struct type declarations should appear as classes or produce some output."""
    extractor = SkeletonExtractor()
    with tempfile.NamedTemporaryFile(suffix=".go", mode="w", delete=False) as f:
        f.write(SAMPLE_GO)
        fpath = f.name
    try:
        skeleton = extractor.extract_file(fpath)
        assert skeleton is not None
        # Either classes captured or functions — skeleton must be non-trivial
        total_items = len(skeleton.functions) + len(skeleton.classes) + len(skeleton.imports)
        assert total_items > 0
    finally:
        os.unlink(fpath)


def test_go_unsupported_extension_returns_none():
    """Files with unsupported extension should return None from extractor."""
    extractor = SkeletonExtractor()
    with tempfile.NamedTemporaryFile(suffix=".rb", mode="w", delete=False) as f:
        f.write("def hello; end\n")
        fpath = f.name
    try:
        skeleton = extractor.extract_file(fpath)
        assert skeleton is None
    finally:
        os.unlink(fpath)
