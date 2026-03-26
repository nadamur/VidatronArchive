#!/usr/bin/env python3
"""
Legacy launcher name — same app as root main.py.

The previous ScreenManager + ui/screens Homescreen stack is not used here anymore;
the canonical UI is ai/test_ui.py (VidatronRoot).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_AI = ROOT / "ai"
if str(_AI) not in sys.path:
    sys.path.insert(0, str(_AI))

from test_ui import VidatronApp, VidatronEngine  # noqa: E402


def main():
    VidatronApp(engine=VidatronEngine()).run()


if __name__ == "__main__":
    main()
