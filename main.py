"""Punto de entrada para ``python main.py``."""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from cvformfiller.cli import app  # noqa: E402

if __name__ == "__main__":
    app()
