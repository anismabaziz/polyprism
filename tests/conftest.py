"""Shared pytest fixtures and helpers."""

from __future__ import annotations

import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    """Load a recorded JSON fixture by filename."""
    path = FIXTURES_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))
