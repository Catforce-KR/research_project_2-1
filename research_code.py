"""Compatibility wrapper for the legacy single-file import path.

The implementation now lives under ``src/helical_propeller``. This module
keeps existing ``import research_code`` users working.
"""

from pathlib import Path
import sys


_SRC_DIR = Path(__file__).resolve().parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from helical_propeller import *  # noqa: F401,F403,E402


if __name__ == "__main__":
    from helical_propeller.cli import main

    main()
