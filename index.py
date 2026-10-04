"""Vercel entrypoint. The app lives in src/fixturefeed (src layout), which
Vercel's Python runtime doesn't put on the import path by itself."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from fixturefeed.web import app  # noqa: E402, F401
