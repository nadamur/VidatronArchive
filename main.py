# main.py (root)

import threading

from movement.main import robot_loop
from smart_ui.main import SmartUIApp


def main():
    print("🚀 Starting Vidatron system...")

    # Start movement in background
    movement_thread = threading.Thread(
        target=robot_loop,
        daemon=True,
    )
    movement_thread.start()

    # Run Smart UI + AI on main thread
    app = SmartUIApp()
    app.run()


if __name__ == "__main__":
    main()