"""Pytest setup: put the `py/` package root on sys.path.

Run from the repo root with:  python -m pytest   (after: pip install pytest)
The library modules import as `lib.*`, matching how the workflows import them.
"""

import sys
from pathlib import Path

PY_ROOT = Path(__file__).resolve().parent.parent / "py"
if str(PY_ROOT) not in sys.path:
    sys.path.insert(0, str(PY_ROOT))
