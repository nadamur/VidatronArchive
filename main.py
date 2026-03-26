# main.py (root)
#
# Launches the voice assistant UI from ai/test_ui.py (VidatronRoot + CuteMascotWidget).
# The older ScreenManager flow (ui/screens.py + smart_ui) is no longer the default entry.

import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
_AI = ROOT / "ai"
if str(_AI) not in sys.path:
    sys.path.insert(0, str(_AI))

from movement.main import robot_loop  # noqa: E402
from test_ui import VidatronApp, VidatronEngine  # noqa: E402


def main():
    print("🚀 Starting Vidatron system…")

    movement_thread = threading.Thread(
        target=robot_loop,
        daemon=True,
    )
    movement_thread.start()

    engine = VidatronEngine()
    VidatronApp(engine=engine).run()


if __name__ == "__main__":
    main()
