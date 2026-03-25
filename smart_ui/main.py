#!/usr/bin/env python3
"""
Smart UI launcher:
- Uses AI assistant logic from ../ai/test_ui.py
- Uses Kivy UI screens from ../ui
"""

from __future__ import annotations

import os
import sys
import threading
from functools import partial
from pathlib import Path
import importlib

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
AI_DIR = PROJECT_ROOT / "ai"
UI_DIR = PROJECT_ROOT / "ui"

# Import AI engine first (it mutates sys.path to AI_DIR internally).
sys.path.insert(0, str(PROJECT_ROOT))
from ai.test_ui import State, VidatronEngine, _on_keyboard  # type: ignore  # noqa: E402

# Normalize sys.path so UI's local imports (config/widgets/screens) resolve from ui/.
sys.path[:] = [p for p in sys.path if p != str(AI_DIR)]
if str(UI_DIR) not in sys.path:
    sys.path.insert(0, str(UI_DIR))

# ai/test_ui imports ai/config.py as module name "config". Ensure UI imports
# do not reuse that cached module.
for mod_name in ("config", "screens", "widgets"):
    sys.modules.pop(mod_name, None)

ui_config = importlib.import_module("config")
ui_screens = importlib.import_module("screens")

config_manager = ui_config.config_manager
WelcomeScreen = ui_screens.WelcomeScreen
SetupFaceScreen = ui_screens.SetupFaceScreen
SetupFontScreen = ui_screens.SetupFontScreen
SetupColorsScreen = ui_screens.SetupColorsScreen
Homescreen = ui_screens.Homescreen
SettingsScreen = ui_screens.SettingsScreen
RemindersScreen = ui_screens.RemindersScreen


class SmartUIApp(App):
    title = "Smart UI - Vidatron"
    STARTUP_GREETING = (
        'Hi, I am Veedatron, your healthy lifestyle assistant. '
        'Say "Hey Veedatron" if you want to ask me a question.'
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.engine = VidatronEngine()
        self._keyboard_cb = None
        self._face_sync_event = None
        self._last_face_signature = None

    def build(self):
        Window.size = (800, 480)
        Window.minimum_width, Window.minimum_height = 800, 480

        # Force default visual profile at boot and skip first-time setup flow.
        config_manager.set("face_customization.selected_eyes", "Round")
        config_manager.set("face_customization.selected_mouth", "Curved")
        config_manager.set("default_colors.primary", [0.10, 0.90, 1.00, 1.0])
        config_manager.set("font_settings.style", "Roboto")
        config_manager.set("font_settings.size", 30)
        config_manager.set("first_time_setup_complete", True)

        sm = ScreenManager()
        sm.add_widget(WelcomeScreen(name="welcome"))
        sm.add_widget(SetupFaceScreen(name="setup_face"))
        sm.add_widget(SetupFontScreen(name="setup_font"))
        sm.add_widget(SetupColorsScreen(name="setup_colors"))
        sm.add_widget(Homescreen(name="homescreen"))
        sm.add_widget(SettingsScreen(name="settings"))
        sm.add_widget(RemindersScreen(name="reminders"))

        sm.current = "homescreen"
        return sm

    def on_start(self):
        self._keyboard_cb = partial(_on_keyboard, self.engine)
        Window.bind(on_keyboard=self._keyboard_cb)

        if not self.engine.manual_terminal_mode:
            self.engine._open_mic_stream()
            print(f"  Audio stream started at {self.engine.mic_sample_rate}Hz")
        else:
            self.engine.stream = None
            print("  Audio stream disabled (manual terminal mode)")

        self.engine.start_terminal_prompt_loop()
        self._face_sync_event = Clock.schedule_interval(self._sync_homescreen_face, 0.12)
        Clock.schedule_once(self._speak_startup_greeting, 0.8)

    def _speak_startup_greeting(self, _dt):
        def worker():
            wav_file = None
            try:
                wav_file = self.engine.tts.synthesize(self.STARTUP_GREETING)

                def start_speaking():
                    self.engine.bot_response = self.STARTUP_GREETING
                    self.engine.status_message = "Speaking introduction..."
                    self.engine._set_state(State.SPEAKING)

                self.engine._main_thread_sync(start_speaking, timeout=5.0)
                self.engine._play_wav_blocking(wav_file, cancel_id=None)
            except Exception as exc:
                print(f"Startup greeting failed: {exc}")
            finally:
                if wav_file:
                    try:
                        os.unlink(wav_file)
                    except OSError:
                        pass

                def back_to_waiting():
                    self.engine._set_state(State.WAITING)
                    self.engine.status_message = "Ready. Say 'Hey Veedatron' to begin."

                self.engine._main_thread(back_to_waiting)

        threading.Thread(target=worker, daemon=True).start()

    def _sync_homescreen_face(self, _dt):
        # Keep menu/navigation under user control; do not force screen switches.
        root = self.root
        display_state = str(getattr(self.engine, "display_state", "waiting"))
        conversation_active = display_state in ("listening", "thinking", "speaking", "follow_up")

        # Only drive the home face from AI state when homescreen is visible.
        if root is None or root.current != "homescreen":
            self._last_face_signature = None
            return

        home = root.get_screen("homescreen")
        if not hasattr(home, "face"):
            return

        # If user starts talking to Vidatron while a reminder card is displayed,
        # dismiss the reminder overlay immediately so conversational face states show.
        if conversation_active and getattr(home, "triggered_reminder_showing", False):
            home.triggered_reminder_showing = False
            home.cycling_paused_until = None
            home._return_screen = "homescreen"
            home.load_reminders()
            self._last_face_signature = None

        if display_state == "speaking":
            mood = "speaking"
        elif display_state == "thinking":
            mood = "thinking"
        elif display_state in ("listening", "follow_up"):
            mood = "focused"
        else:
            mood = "happy"

        accent = config_manager.get("default_colors.primary", [0.10, 0.90, 1.00, 1.0])
        if isinstance(accent, list):
            accent = tuple(accent)
        signature = (display_state, mood, accent)
        if signature == self._last_face_signature:
            return

        home.face.set_style(accent, mood)
        self._last_face_signature = signature

    def on_stop(self):
        if self._face_sync_event is not None:
            self._face_sync_event.cancel()
            self._face_sync_event = None
        if self._keyboard_cb is not None:
            Window.unbind(on_keyboard=self._keyboard_cb)
            self._keyboard_cb = None
        self.engine.running = False
        if self.engine.stream:
            self.engine.stream.stop()
            self.engine.stream.close()
            self.engine.stream = None
        self.engine._stop_playback()


def main():
    SmartUIApp().run()


if __name__ == "__main__":
    main()
