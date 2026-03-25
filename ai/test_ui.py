#!/usr/bin/env python3
"""
Test UI for Vidatron - Wake word activated with automatic silence detection.
Say "Hey Veedatron" to activate, then speak your command!

UI: Kivy. Mic: sounddevice InputStream. Speaker: external paplay/aplay only (see audio.subprocess_playback).
"""

from __future__ import annotations

import sys
import os
import threading
import time
import tempfile
import subprocess
import re
import wave
import random
import numpy as np
from pathlib import Path
from enum import Enum
from dataclasses import dataclass
from collections import deque
from functools import partial
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


def _display_size() -> tuple[int, int]:
    import json

    cfg_path = PROJECT_ROOT / "config" / "config.json"
    if cfg_path.exists():
        try:
            with open(cfg_path) as f:
                d = json.load(f)
            return int(d.get("display_width", 900)), int(d.get("display_height", 700))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
    return 900, 700


_dw, _dh = _display_size()
from kivy.config import Config

Config.set("graphics", "width", str(_dw))
Config.set("graphics", "height", str(_dh))
Config.set("input", "mouse", "mouse,multitouch_on_demand")

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.event import EventDispatcher
from kivy.graphics import Color, RoundedRectangle
from kivy.lang import Builder
from kivy.properties import (
    BooleanProperty,
    ListProperty,
    NumericProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

import sounddevice as sd

from config import Config as AppConfig
from brain.ollama_client import OllamaClient
from brain.router import Router, ToolType
from brain.tools.time_tool import get_current_time
from brain.tools.system_tool import get_system_status
from brain.tools.joke_tool import get_joke
from brain.tools.weather_tool import WeatherTool
from brain.tools.news_tool import NewsTool
from brain.tools.spotify_tool import SpotifyError, SpotifyTool
from brain.groq_client import GroqClient
from brain.chat_history import ChatHistoryStore
from audio.subprocess_playback import SubprocessWavPlayer
from audio.stt_engine import sanitize_whisper_output
from audio.tts_engine import PiperTTS
from openwakeword.model import Model as WakeWordModel
from openwakeword_setup import ensure_openwakeword_resources


class State(Enum):
    WAITING = "waiting"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    FOLLOW_UP = "follow_up"


@dataclass
class UIColors:
    BG = (15 / 255, 15 / 255, 25 / 255, 1)
    PANEL = (25 / 255, 28 / 255, 40 / 255, 1)
    ACCENT = (0, 1, 200 / 255, 1)
    ACCENT_DIM = (0, 150 / 255, 120 / 255, 1)
    PINK = (1, 50 / 255, 150 / 255, 1)
    TEXT = (240 / 255, 240 / 255, 250 / 255, 1)
    TEXT_DIM = (140 / 255, 145 / 255, 165 / 255, 1)
    SUCCESS = (50 / 255, 1, 120 / 255, 1)
    ERROR = (1, 80 / 255, 80 / 255, 1)
    ORANGE = (1, 150 / 255, 50 / 255, 1)
    PURPLE = (150 / 255, 50 / 255, 1, 1)


Builder.load_string(
    """
<VidatronRoot>:
    canvas.before:
        Color:
            rgba: root.bg_color
        Rectangle:
            pos: self.pos
            size: self.size

    orientation: 'vertical'
    padding: dp(12)
    spacing: dp(6)

    Label:
        text: 'Vidatron'
        font_size: dp(28)
        bold: True
        color: root.accent_color
        size_hint_y: None
        height: dp(40)

    WaveformWidget:
        id: waveform
        engine: root.engine
        size_hint_y: None
        height: dp(70)

    Label:
        id: badge
        text: root.badge_text
        color: root.badge_color
        font_size: dp(16)
        size_hint_y: None
        height: dp(32)
        canvas.before:
            Color:
                rgba: root.badge_bg_color
            RoundedRectangle:
                pos: self.x - dp(12), self.y - dp(4)
                size: self.width + dp(24), self.height + dp(8)
                radius: [dp(16),]

    AnchorLayout:
        size_hint_y: None
        height: dp(210)
        Image:
            id: face_img
            source: root.face_source
            fit_mode: "contain"
            size_hint: None, None
            size: dp(200), dp(200)

    Label:
        text: 'You said:'
        font_size: dp(13)
        color: root.accent_color
        size_hint_y: None
        height: dp(20)
        halign: 'left'
        text_size: self.size

    ScrollView:
        size_hint_y: None
        height: dp(88)
        bar_width: dp(6)
        Label:
            text: root.user_panel_text
            font_size: dp(15)
            color: root.text_color
            size_hint_y: None
            height: self.texture_size[1]
            text_size: self.width, None
            halign: 'left'
            valign: 'top'
            padding: dp(8), dp(8)
            canvas.before:
                Color:
                    rgba: root.user_panel_bg
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(10),]

    Label:
        text: 'Vidatron:'
        font_size: dp(13)
        color: root.pink_color
        size_hint_y: None
        height: dp(20)
        halign: 'left'
        text_size: self.size

    ScrollView:
        size_hint_y: None
        height: dp(118)
        bar_width: dp(6)
        Label:
            text: root.bot_panel_text
            font_size: dp(15)
            color: root.text_color
            size_hint_y: None
            height: self.texture_size[1]
            text_size: self.width, None
            halign: 'left'
            valign: 'top'
            padding: dp(8), dp(8)
            canvas.before:
                Color:
                    rgba: root.bot_panel_bg
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(10),]

    BoxLayout:
        orientation: 'vertical'
        size_hint_y: None
        height: dp(52)
        opacity: 1 if root.show_wake_meter else 0
        Label:
            text: root.wake_meter_label
            font_size: dp(12)
            color: root.text_dim_color
            size_hint_y: None
            height: dp(18)
            halign: 'left'
        ProgressBar:
            id: wake_pb
            max: 1
            value: 0
            size_hint_y: None
            height: dp(14)

    Widget:
        size_hint_y: 1

    Label:
        text: root.status_message
        font_size: dp(12)
        color: root.text_dim_color
        size_hint_y: None
        height: dp(22)

    Label:
        text: root.hint_text
        font_size: dp(11)
        color: root.text_dim_color
        size_hint_y: None
        height: dp(36)
        text_size: self.width, None
"""
)


class WaveformWidget(Widget):
    engine = ObjectProperty(None, allownone=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._pulse = 0.0
        Clock.schedule_interval(self._tick, 1 / 30.0)

    def _tick(self, _dt):
        if self.engine:
            if getattr(self.engine, "playback_active", False):
                return
            self.engine.animation_frame = self.engine.animation_frame + 1
        self._pulse += 0.08
        self._draw()

    def _draw(self):
        self.canvas.after.clear()
        if not self.width or not self.height:
            return
        eng = self.engine
        if not eng:
            return
        st = eng.display_state
        af = int(eng.animation_frame)
        al = eng.audio_level
        wc = eng.wake_word_confidence

        num_bars = 15
        bar_w = 8
        spacing = 12
        total_w = num_bars * spacing
        start_x = self.x + (self.width - total_w) / 2
        cy = self.y + self.height / 2

        for i in range(num_bars):
            if st == "listening":
                wave = np.sin(af * 0.15 + i * 0.5)
                h = max(4, int(5 + al * 40 * (0.5 + 0.5 * abs(wave))))
                rgba = UIColors.ERROR
            elif st == "speaking":
                wave = np.sin(af * 0.2 + i * 0.4)
                h = max(8, int(10 + 25 * (0.5 + 0.5 * abs(wave))))
                rgba = UIColors.SUCCESS
            elif st == "thinking":
                wave = np.sin(af * 0.1 + i * 0.3)
                h = max(6, int(5 + 15 * (0.5 + 0.5 * abs(wave))))
                rgba = UIColors.PURPLE
            elif st == "follow_up":
                wave = np.sin(af * 0.12 + i * 0.4)
                h = max(6, int(8 + al * 30 * (0.5 + 0.5 * abs(wave))))
                rgba = UIColors.ORANGE
            else:
                pulse = 0.3 + 0.7 * wc
                h = max(4, int(3 + 8 * pulse * abs(np.sin(af * 0.05 + i * 0.2))))
                rgba = UIColors.ACCENT_DIM

            bx = start_x + i * spacing
            by = cy - h / 2
            with self.canvas.after:
                Color(*rgba)
                RoundedRectangle(pos=(bx, by), size=(bar_w, h), radius=[3,])


class VidatronRoot(BoxLayout):
    engine = ObjectProperty(None, allownone=True)

    bg_color = ListProperty([15 / 255, 15 / 255, 25 / 255, 1])
    accent_color = ListProperty([0, 1, 200 / 255, 1])
    pink_color = ListProperty([1, 50 / 255, 150 / 255, 1])
    text_color = ListProperty([240 / 255, 240 / 255, 250 / 255, 1])
    text_dim_color = ListProperty([140 / 255, 145 / 255, 165 / 255, 1])
    user_panel_bg = ListProperty([25 / 255, 28 / 255, 40 / 255, 1])
    bot_panel_bg = ListProperty([25 / 255, 28 / 255, 40 / 255, 1])
    badge_bg_color = ListProperty([25 / 255, 28 / 255, 40 / 255, 1])
    badge_color = ListProperty([0, 150 / 255, 120 / 255, 1])
    badge_text = StringProperty("")
    face_source = StringProperty("")
    user_panel_text = StringProperty("")
    bot_panel_text = StringProperty("")
    status_message = StringProperty("")
    hint_text = StringProperty("")
    show_wake_meter = BooleanProperty(False)
    wake_meter_label = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Clock.schedule_interval(self._refresh_ui, 1 / 30.0)

    def on_engine(self, _inst, eng):
        if eng:
            eng.fbind("wake_word_confidence", self._sync_wake_bar)

    def _sync_wake_bar(self, *args):
        if self.engine:
            self.ids.wake_pb.value = min(1.0, float(self.engine.wake_word_confidence))

    def _refresh_ui(self, _dt):
        eng = self.engine
        if not eng:
            return
        if eng.playback_active:
            # Keep only essential status updates while speaker has exclusive mode.
            self.status_message = eng.status_message
            self.hint_text = eng.compute_hint_text()
            return
        self.hint_text = eng.compute_hint_text()
        self.status_message = eng.status_message
        self.user_panel_text = eng._format_user_panel()
        self.bot_panel_text = eng._format_bot_panel()
        self.badge_text = eng.badge_text
        self.badge_color = eng.badge_color_rgba
        self.face_source = eng.face_source
        self.show_wake_meter = eng.display_state == "waiting"
        self.wake_meter_label = eng.wake_meter_label
        if eng.display_state == "waiting":
            self.user_panel_bg = [*UIColors.PANEL[:3], 1]
        else:
            self.user_panel_bg = [*UIColors.PANEL[:3], 1]


class VidatronEngine(EventDispatcher):
    status_message = StringProperty("Say 'Hey Veedatron' to activate...")
    wake_word_confidence = NumericProperty(0.0)
    audio_level = NumericProperty(0.0)
    animation_frame = NumericProperty(0)
    display_state = StringProperty("waiting")
    badge_text = StringProperty("")
    badge_color_rgba = ListProperty([0, 150 / 255, 120 / 255, 1])
    face_source = StringProperty("")
    wake_meter_label = StringProperty("Wake word: 0%")
    playback_active = BooleanProperty(False)

    def __init__(self):
        super().__init__()
        # Set VIDATRON_MANUAL_TERMINAL=1 to disable mic and use terminal typing instead.
        self.manual_terminal_mode = os.environ.get("VIDATRON_MANUAL_TERMINAL", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        self.state = State.WAITING
        self.user_text = ""
        self.bot_response = ""
        self.silence_counter = 0
        self.animation_frame = 0
        self.pulse_value = 0.0

        self.mic_sample_rate = 16000
        self.target_sample_rate = 16000
        self.channels = 1
        self.chunk_size = 1280
        # Voice activity detection thresholds (adaptive for quiet mics)
        self.silence_threshold = 0.00035
        self.speech_start_multiplier = 2.0
        self.noise_floor_ema = 0.0002
        self.noise_floor_alpha = 0.08
        self.silence_duration = 1.5
        self.min_speech_duration = 0.5
        self.max_speech_duration = 10.0
        self.follow_up_timeout = 8.0
        self.follow_up_start_time = 0
        self.current_request_id = 0
        self.audio_buffer = deque(maxlen=100)
        self.recording_buffer = []
        self.speech_started = False
        self.speech_start_time = 0
        self.loud_counter = 0
        self.running = True
        self.processing = False
        self._last_listen_debug_log = 0.0
        self._mic_enabled = True
        self._silence_triggered = False
        self.enable_filler_audio = False
        self.speaker_device = self._find_playback_device()
        self.speaker_sample_rate = self._get_speaker_sample_rate(self.speaker_device)
        self.speaker_aplay_device = self._resolve_speaker_aplay()
        self._wav_player = SubprocessWavPlayer()

        self._face_paths = self._build_face_paths()
        self.config = AppConfig.load()
        self.chat_history = ChatHistoryStore(
            self.config.chat_history_path,
            max_stored_messages=self.config.chat_history_max_stored,
            max_context_messages=self.config.chat_history_max_context,
        )
        print(f"  Chat history file: {self.config.chat_history_path}")

        print("Initializing AI components...")
        print(f"  Loading Ollama ({self.config.chat_model})...")
        self.ollama = OllamaClient(model=self.config.chat_model)
        self.router = Router(self.ollama)
        print("  Warming up local model...")
        try:
            self.ollama.ensure_model_loaded()
        except Exception:
            pass

        self.cloud = None
        if self.config.groq_api_key:
            print("  Loading Cloud AI (Groq)...")
            try:
                self.cloud = GroqClient(
                    api_key=self.config.groq_api_key,
                    model=self.config.groq_model or None,
                    soul_path=self.config.cloud_soul_path,
                )
                print("  ✓ Cloud AI ready!")
            except Exception as e:
                print(f"  Warning: Cloud AI unavailable: {e}")
        else:
            print("  ℹ Cloud AI not configured (set GROQ_API_KEY for complex questions)")

        self.weather = None
        if self.config.openweather_api_key:
            print("  Loading Weather API...")
            try:
                self.weather = WeatherTool(api_key=self.config.openweather_api_key)
                print("  ✓ Weather API ready!")
            except Exception as e:
                print(f"  Warning: Weather unavailable: {e}")
        else:
            print("  ℹ Weather not configured (set OPENWEATHER_API_KEY)")

        self.news = None
        if self.config.newsapi_key:
            print("  Loading News API...")
            try:
                self.news = NewsTool(api_key=self.config.newsapi_key)
                print("  ✓ News API ready!")
            except Exception as e:
                print(f"  Warning: News unavailable: {e}")
        else:
            print("  ℹ News not configured (set NEWSAPI_KEY)")

        self.spotify = None
        if (
            self.config.spotify_client_id
            and self.config.spotify_client_secret
            and self.config.spotify_refresh_token
        ):
            print("  Loading Spotify...")
            try:
                self.spotify = SpotifyTool(
                    client_id=self.config.spotify_client_id,
                    client_secret=self.config.spotify_client_secret,
                    refresh_token=self.config.spotify_refresh_token,
                    device_id=self.config.spotify_device_id or "",
                )
                print("  ✓ Spotify ready!")
            except Exception as e:
                print(f"  Warning: Spotify unavailable: {e}")
        else:
            print("  ℹ Spotify not configured (set SPOTIFY_* in .env; see setup_spotify_token.py)")

        print("  Loading TTS...")
        self.tts = PiperTTS(model_path=self.config.piper_voice)
        if not self.manual_terminal_mode:
            print("  Loading wake word model...")
            ensure_openwakeword_resources()
            self.wake_word_model = WakeWordModel(
                wakeword_models=[self.config.wake_word_model],
                inference_framework="onnx",
            )
            self.wake_word_threshold = self.config.wake_word_threshold
        else:
            self.wake_word_model = None
            self.wake_word_threshold = 1.0

        print("  Loading filler audio...")
        self.filler_sounds = []
        fillers_dir = PROJECT_ROOT / "assets" / "fillers"
        for i in range(5):
            filler_path = fillers_dir / f"filler_{i}.wav"
            if filler_path.exists():
                self.filler_sounds.append(str(filler_path))
        print(f"  ✓ Loaded {len(self.filler_sounds)} filler phrases")
        if self.speaker_device is not None:
            try:
                dev = sd.query_devices(self.speaker_device)
                print(f"  ✓ Speaker device: {self.speaker_device} ({dev['name']})")
            except Exception:
                print(f"  ✓ Speaker device index: {self.speaker_device}")
            print(f"  ✓ Speaker sample rate: {int(self.speaker_sample_rate)} Hz")
            if self.speaker_aplay_device:
                print(f"  ✓ Speaker ALSA route: {self.speaker_aplay_device}")
        else:
            print("  ⚠ Using default output device (no dedicated speaker device selected)")

        self.stream: sd.InputStream | None = None
        self._sync_ui_state()
        print("✓ UI Ready!")

    def _ollama_messages_cloud_fallback(self, user_text: str) -> list:
        """Ollama path when Groq is unavailable: system + saved chat + current user."""
        base = (
            "You are Vidatron, a healthy lifestyle robot and AI assistant. "
            "Give a concise answer in 1-3 sentences."
        )
        msgs = [{"role": "system", "content": base}]
        msgs.extend(self.chat_history.messages_for_api())
        msgs.append({"role": "user", "content": user_text})
        return msgs

    def start_terminal_prompt_loop(self):
        """Background thread: type prompts at You> (alongside wake word + mic when enabled)."""
        def _worker():
            if self.manual_terminal_mode:
                print("\nManual prompt mode — microphone disabled.")
            else:
                print("\nTerminal — type prompts at You> anytime (same pipeline as voice).")
            print("Press Enter after your line. Type 'exit' or 'quit' to close the app.\n")
            while self.running:
                try:
                    text = input("You> ").strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if not text:
                    continue
                if text.lower() in {"exit", "quit"}:
                    App.get_running_app().stop()
                    break
                self._process_text_prompt(text)

        threading.Thread(target=_worker, daemon=True).start()

    def _process_text_prompt(self, text: str):
        """Process a manually-typed prompt (no microphone path)."""
        if self._is_farewell_thanks(text):
            self.current_request_id += 1

            def goodbye():
                self.user_text = text
                self.bot_response = ""
                self._set_state(State.WAITING)
                self.status_message = (
                    "Say 'Hey Veedatron' to activate..."
                    if not self.manual_terminal_mode
                    else "Type another prompt at You>, or 'thank you' to stay idle."
                )
                if self.wake_word_model is not None:
                    self.wake_word_model.reset()

            self._main_thread(goodbye)
            print("  Farewell — back to waiting for wake word.")
            return

        ack = self._paused_motion_ack_or_none(text)
        if ack is not None:
            my_request_id = self.current_request_id + 1
            self.current_request_id = my_request_id
            print(f"  [motion] {ack}")
            self._handle_voice_drive_ack(text, ack, my_request_id, from_voice=False)
            return

        my_request_id = self.current_request_id + 1
        self.current_request_id = my_request_id

        def set_user():
            self.user_text = text
            self.status_message = "Generating response..."
            self._set_state(State.THINKING)

        self._main_thread(set_user)
        print(f"  You typed: {text}")

        try:
            result_rt = self.router.route(text)
            print(f"  Router selected: {result_rt.tool.name} (args: {result_rt.arguments})")

            if result_rt.tool == ToolType.NONE:
                response = result_rt.response
            elif result_rt.tool == ToolType.TIME:
                response = get_current_time()
            elif result_rt.tool == ToolType.SYSTEM_STATUS:
                response = get_system_status()
            elif result_rt.tool == ToolType.JOKE:
                response = get_joke()
            elif result_rt.tool == ToolType.WEATHER:
                if self.weather:
                    loc = result_rt.arguments.get("location") or self.config.local_location or "New York"
                    response = self.weather.get_weather(loc)
                else:
                    response = "Weather lookup isn't configured. Add OPENWEATHER_API_KEY to enable it."
            elif result_rt.tool == ToolType.NEWS:
                if self.news:
                    category = result_rt.arguments.get("category", "")
                    response = self.news.get_news(category)
                else:
                    response = "News lookup isn't configured. Add NEWSAPI_KEY to enable it."
            elif result_rt.tool == ToolType.SPOTIFY_PLAY:
                if self.spotify:
                    q = (result_rt.arguments.get("query") or "").strip() or text
                    try:
                        response = self.spotify.play_search(q)
                    except SpotifyError as e:
                        response = str(e)
                else:
                    response = (
                        "Spotify is not configured. Add SPOTIFY_CLIENT_ID, "
                        "SPOTIFY_CLIENT_SECRET, and SPOTIFY_REFRESH_TOKEN to your .env file."
                    )
            elif result_rt.tool == ToolType.SPOTIFY_PAUSE:
                if self.spotify:
                    try:
                        self.spotify.pause()
                        response = "Okay, I paused Spotify."
                    except SpotifyError as e:
                        response = str(e)
                else:
                    response = "Spotify is not configured, so I cannot pause playback."
            elif result_rt.tool == ToolType.CLOUD:
                if self.cloud:
                    query = result_rt.arguments.get("query", text)
                    response = self.cloud.chat(
                        query,
                        stream=False,
                        history=self.chat_history.messages_for_api(),
                    )
                else:
                    query = result_rt.arguments.get("query", text)
                    messages = self._ollama_messages_cloud_fallback(query)
                    local_response = self.ollama.chat(messages, tools=None)
                    response = local_response.content or "I'm not sure about that."
            else:
                response = result_rt.response or "I'm not sure how to respond to that."

            if result_rt.tool == ToolType.CLOUD and response:
                self.chat_history.append_exchange(
                    result_rt.arguments.get("query", text),
                    response,
                )

            print(f"  Bot: {response[:80]}...")

            def set_bot():
                self.bot_response = response
                self._set_state(State.SPEAKING)
                self.status_message = "Speaking response..."

            self._main_thread_sync(set_bot, timeout=5.0)

            wav_file = self.tts.synthesize(response)
            self._play_wav_blocking(wav_file, cancel_id=my_request_id)
            try:
                os.unlink(wav_file)
            except OSError:
                pass

            def done():
                self._set_state(State.WAITING)
                self.status_message = (
                    "Type at You> or say 'Hey Veedatron'..."
                    if not self.manual_terminal_mode
                    else "Type another prompt in terminal..."
                )

            self._main_thread(done)
        except Exception as e:
            print(f"  Manual prompt error: {e}")

    def _build_face_paths(self) -> dict:
        face_dir = PROJECT_ROOT / "assets" / "face"
        mapping = {
            State.WAITING: "happy.png",
            State.LISTENING: "thinking.png",
            State.THINKING: "thinking.png",
            State.SPEAKING: "happy_eye_glistening.png",
            State.FOLLOW_UP: "happy.png",
        }
        out = {}
        for st, fn in mapping.items():
            p = face_dir / fn
            out[st] = str(p) if p.exists() else ""
        return out

    def _usb_hw_from_aplay(self) -> str | None:
        """Return 'card,device' (e.g. '1,0') if a USB UACDemo speaker is listed by aplay -l."""
        try:
            r = subprocess.run(
                ["aplay", "-l"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if r.returncode != 0:
                return None
            for line in r.stdout.splitlines():
                if "UACDemo" not in line:
                    continue
                m = re.search(r"card (\d+):.*device (\d+):", line)
                if m:
                    return f"{m.group(1)},{m.group(2)}"
        except Exception:
            pass
        return None

    def _find_playback_device(self) -> int | None:
        """Prefer dedicated USB speaker (UACDemo), not Pulse/default, when possible."""
        env_idx = os.environ.get("VIDRATON_SPEAKER_DEVICE_INDEX", "").strip()
        if env_idx.isdigit():
            try:
                idx = int(env_idx)
                devices = sd.query_devices()
                if 0 <= idx < len(devices) and int(devices[idx].get("max_output_channels", 0)) > 0:
                    return idx
            except Exception:
                pass

        try:
            devices = sd.query_devices()
        except Exception:
            return None

        hw = self._usb_hw_from_aplay()
        if hw:
            needle = f"hw:{hw}"
            for i, d in enumerate(devices):
                if int(d.get("max_output_channels", 0)) <= 0:
                    continue
                if needle in str(d.get("name", "")):
                    return i

        preferred_tokens = (
            "uacdemo",
            "uacdemov1.0",
            "usb audio",
            "usb pnp sound device",
        )
        for i, d in enumerate(devices):
            if int(d.get("max_output_channels", 0)) <= 0:
                continue
            name = str(d.get("name", "")).lower()
            if any(tok in name for tok in preferred_tokens):
                return i
        try:
            default_out = sd.default.device[1]
            if default_out is not None and default_out >= 0:
                return int(default_out)
        except Exception:
            pass
        return None

    def _resolve_speaker_aplay(self) -> str | None:
        """ALSA device for aplay fallback: env override > plughw from PortAudio name > aplay card."""
        env = os.environ.get("VIDATRON_SPEAKER_ALSA", "").strip()
        if env:
            return env
        pl = self._alsa_plughw_from_device(self.speaker_device)
        if pl:
            return pl
        hw = self._usb_hw_from_aplay()
        if hw:
            return f"plughw:{hw}"
        return None

    def _get_speaker_sample_rate(self, device: int | None) -> float:
        """Return a safe output sample rate for the selected playback device."""
        try:
            if device is not None:
                d = sd.query_devices(device)
                sr = float(d.get("default_samplerate", 0) or 0)
                if sr > 0:
                    return sr
        except Exception:
            pass
        # Most USB speaker devices on Pi are happiest at 48k.
        return 48000.0

    def _alsa_plughw_from_device(self, device: int | None) -> str | None:
        """Map sounddevice device name containing (hw:X,Y) to ALSA plughw:X,Y."""
        if device is None:
            return None
        try:
            d = sd.query_devices(device)
            name = str(d.get("name", ""))
            m = re.search(r"hw:(\d+),(\d+)", name)
            if m:
                return f"plughw:{m.group(1)},{m.group(2)}"
        except Exception:
            pass
        return None

    def _main_thread(self, fn, *args, **kwargs):
        Clock.schedule_once(lambda dt: fn(*args, **kwargs), 0)

    def _main_thread_sync(self, fn, *args, timeout: float = 2.0, **kwargs):
        """Run fn on the Kivy thread and block until done (for ordering vs background workers)."""
        ev = threading.Event()
        err: list[BaseException | None] = [None]

        def run(_dt):
            try:
                fn(*args, **kwargs)
            except BaseException as e:
                err[0] = e
            finally:
                ev.set()

        Clock.schedule_once(run, 0)
        ev.wait(timeout=timeout)
        if err[0] is not None:
            raise err[0]

    def _hard_close_mic_stream(self) -> None:
        """Stop and close the InputStream so ALSA releases the USB audio device for aplay/paplay."""
        if self.stream is None:
            return
        try:
            self.stream.stop()
        except Exception:
            pass
        try:
            self.stream.close()
        except Exception as e:
            print(f"  Mic stream close: {e}")
        self.stream = None

    def _open_mic_stream(self) -> None:
        """Create or restart capture when the mic should be active."""
        if self.manual_terminal_mode:
            return
        if self.stream is not None:
            try:
                if not self.stream.active:
                    self.stream.start()
            except Exception as e:
                print(f"  Mic stream start: {e}")
            return
        self.stream = sd.InputStream(
            samplerate=self.mic_sample_rate,
            channels=self.channels,
            blocksize=self.chunk_size,
            callback=self._audio_callback,
            dtype="float32",
        )
        self.stream.start()

    def _set_mic_enabled(self, enabled: bool, hardware: bool = False):
        """Logically enable/disable mic; when hardware=True, close stream when off, reopen when on."""
        self._mic_enabled = bool(enabled)
        if not hardware or self.manual_terminal_mode:
            return
        if enabled:
            self._open_mic_stream()
        else:
            self._hard_close_mic_stream()

    @staticmethod
    def _is_farewell_thanks(text: str) -> bool:
        """True if the user is ending the session (thanks / goodbye — no follow-up question)."""
        t = (text or "").lower()
        t = re.sub(r"[^\w\s]", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        if not t:
            return False
        bare = {
            "thank you",
            "thanks",
            "thank you vidatron",
            "thank you veedatron",
            "thanks vidatron",
            "thanks veedatron",
            "thank you so much",
            "thanks a lot",
            "thanks so much",
            "many thanks",
            "thank you very much",
            "much appreciated",
            "appreciate it",
            "thx",
            "ty",
            # Goodbye / end conversation
            "goodbye",
            "bye",
            "good bye",
            "bye bye",
            "see you",
            "see ya",
            "farewell",
            "goodnight",
            "good night",
            "goodbye vidatron",
            "goodbye veedatron",
            "bye vidatron",
            "bye veedatron",
            "see you later",
            "talk to you later",
            "have a good one",
        }
        if t in bare:
            return True
        # Short goodbye tails (e.g. "goodbye for now", "bye for now")
        if t.startswith("goodbye "):
            rest = t[len("goodbye ") :].strip()
            if len(rest) < 36 and (
                not rest
                or rest in ("for now", "thanks", "thank you", "have a good day")
                or rest.split()[0]
                in ("vidatron", "veedatron", "for", "and", "everyone", "thanks")
            ):
                return True
        if t.startswith("bye ") and len(t) < 40:
            rest = t[len("bye ") :].strip()
            if (
                not rest
                or rest in ("for now", "bye", "vidatron", "veedatron", "everyone")
                or (
                    rest.split()[0]
                    in ("vidatron", "veedatron", "for", "now", "everyone")
                    and len(rest) < 32
                )
            ):
                return True
        # Short trailing thanks only (e.g. "thank you again", "thanks bye")
        if t.startswith("thank you "):
            rest = t[len("thank you ") :].strip()
            if len(rest) < 28 and (
                not rest
                or rest in ("so much", "a lot", "again", "bye", "goodbye", "very much")
                or rest.split()[0] in ("again", "bye", "goodbye", "vidatron", "veedatron")
            ):
                return True
        if t.startswith("thanks ") and len(t) < 30:
            rest = t[len("thanks ") :].strip()
            if not rest or rest.split()[0] in ("again", "bye", "goodbye", "a", "so", "vidatron", "veedatron"):
                return True
        return False

    def _paused_motion_ack_or_none(self, text: str) -> str | None:
        """If robot is paused and text is a drive command, queue move and return spoken ack."""
        try:
            from movement.voice_commands import try_enqueue_motion_command
        except ImportError:
            return None
        return try_enqueue_motion_command(text)

    def _handle_voice_drive_ack(
        self,
        user_text: str,
        ack: str,
        my_request_id: int,
        *,
        from_voice: bool,
    ) -> None:
        """Speak a short ack for a queued drive command (voice may enter follow-up)."""

        def prep():
            self.user_text = user_text
            self.bot_response = ack

        self._main_thread(prep)

        def start_sp():
            self.bot_response = ack
            self._set_state(State.SPEAKING)
            self.status_message = "Speaking..."

        self._main_thread_sync(start_sp, timeout=5.0)
        wav_file = self.tts.synthesize(ack)
        if from_voice and my_request_id != self.current_request_id:
            try:
                os.unlink(wav_file)
            except OSError:
                pass
            self._main_thread(lambda: setattr(self, "processing", False))
            return
        try:
            played = self._play_wav_blocking(
                wav_file,
                cancel_id=my_request_id if from_voice else None,
            )
        finally:
            try:
                os.unlink(wav_file)
            except OSError:
                pass
        if from_voice and my_request_id != self.current_request_id:
            self._main_thread(lambda: setattr(self, "processing", False))
            return
        if from_voice:
            if played:

                def follow():
                    self._set_state(State.FOLLOW_UP)
                    self.follow_up_start_time = time.time()
                    self.status_message = "Ask a follow-up question..."
                    self.processing = False

                self._main_thread(follow)
            else:
                self._main_thread(lambda: setattr(self, "processing", False))
        else:

            def done():
                self._set_state(State.WAITING)
                self.status_message = (
                    "Type at You> or say 'Hey Veedatron'..."
                    if not self.manual_terminal_mode
                    else "Type another prompt in terminal..."
                )

            self._main_thread(done)

    def _set_state(self, new_state: State):
        # Enforce IO separation:
        # - speaking => mic off
        # - listening => speaker off
        if new_state == State.SPEAKING:
            self._set_mic_enabled(False, hardware=True)
        elif new_state == State.LISTENING:
            self._stop_playback()
            self._set_mic_enabled(True, hardware=True)
        else:
            # Re-enable mic for waiting/follow-up/thinking.
            self._set_mic_enabled(True, hardware=True)
        self.state = new_state
        self.display_state = new_state.value
        self._sync_ui_state()

    def _sync_ui_state(self):
        cfg = {
            State.WAITING: ("Waiting for 'Hey Veedatron'", UIColors.ACCENT_DIM),
            State.LISTENING: ("Listening... (speak now!)", UIColors.ERROR),
            State.THINKING: ("Thinking...", UIColors.PURPLE),
            State.SPEAKING: ("Speaking...", UIColors.SUCCESS),
            State.FOLLOW_UP: ("Listening for follow-up...", UIColors.ORANGE),
        }
        text, col = cfg.get(self.state, ("", UIColors.TEXT_DIM))
        self.badge_text = text
        self.badge_color_rgba = list(col)
        self.face_source = self._face_paths.get(self.state, "")
        self.wake_meter_label = f"Wake word: {self.wake_word_confidence:.1%}"

    def _format_user_panel(self) -> str:
        if self.user_text:
            return self.user_text
        if self.state == State.LISTENING:
            dots = "." * (1 + (int(self.animation_frame) // 15) % 3)
            return f"Recording{dots}"
        return "(waiting for speech...)"

    def _format_bot_panel(self) -> str:
        if self.bot_response:
            return self.bot_response
        if self.state == State.THINKING:
            dots = "." * (1 + (int(self.animation_frame) // 10) % 3)
            return f"Generating response{dots}"
        return "(waiting for response...)"

    def compute_hint_text(self) -> str:
        if self.manual_terminal_mode:
            return "Mic disabled. Type prompts in terminal (You> ...) • Press Esc to exit"
        if self.state == State.WAITING:
            return "Say 'Hey Veedatron' or type at You> in the terminal • Press Esc to exit"
        if self.state == State.LISTENING:
            return "Speak now! Will auto-detect when you stop talking"
        if self.state == State.FOLLOW_UP:
            remaining = max(0, self.follow_up_timeout - (time.time() - self.follow_up_start_time))
            return f"Ask a follow-up or wait {remaining:.0f}s to exit conversation"
        return "Press Esc to exit"

    def _stop_playback(self):
        try:
            sd.stop(ignore_errors=True)
        except TypeError:
            sd.stop()
        self._wav_player.stop()
        self.playback_active = False

    def _play_wav_blocking(self, path: str, cancel_id: int | None = None) -> bool:
        """
        Play WAV only via external paplay/aplay (see audio.subprocess_playback).
        No PortAudio output in this process — avoids pops/underruns vs Kivy + mic.
        Fully closes the mic stream before play so USB combo devices are not busy.
        """
        self._stop_playback()
        self._hard_close_mic_stream()
        time.sleep(0.4)

        def cancel_check():
            if cancel_id is None:
                return False
            if cancel_id != self.current_request_id:
                print("  ⏹ Playback cancelled (request id changed — new input or wake retrigger).")
                return True
            return False

        plughw = self._resolve_speaker_aplay()
        self.playback_active = True
        ok = self._wav_player.play(
            path,
            plughw_hint=plughw,
            cancel_check=cancel_check if cancel_id is not None else None,
        )
        self.playback_active = False
        return ok

    def _play_filler(self):
        if (not self.enable_filler_audio) or (not self.filler_sounds):
            return
        path = random.choice(self.filler_sounds)
        try:
            self._play_wav_blocking(path, cancel_id=None)
        except Exception as e:
            print(f"  Filler error: {e}")

    def _calculate_rms(self, audio_chunk) -> float:
        # Plain float — Kivy NumericProperty rejects numpy scalar types (e.g. np.float32).
        return float(np.sqrt(np.mean(np.asarray(audio_chunk, dtype=np.float64) ** 2)))

    def _audio_callback(self, indata, frames, time_info, status):
        if self.manual_terminal_mode:
            return
        if not self.running:
            return
        if not self._mic_enabled:
            return
        audio = indata[:, 0].copy()
        al = self._calculate_rms(audio)
        self._main_thread(setattr, self, "audio_level", float(al))

        if self.state == State.WAITING:
            audio_int16 = (audio * 32767).astype(np.int16)
            prediction = self.wake_word_model.predict(audio_int16)
            scores = list(prediction.values())
            conf = float(max(scores)) if scores else 0.0
            self._main_thread(self._apply_wake_confidence, conf)

        elif self.state == State.LISTENING:
            self.recording_buffer.append(audio.copy())
            rms = al
            # Track ambient mic floor before speech starts; this adapts for quiet/variable mics.
            if not self.speech_started:
                self.noise_floor_ema = (
                    (1.0 - self.noise_floor_alpha) * self.noise_floor_ema
                    + self.noise_floor_alpha * float(rms)
                )
            adaptive_silence_threshold = max(
                float(self.silence_threshold),
                float(self.noise_floor_ema * 1.35),
            )
            speech_start_threshold = adaptive_silence_threshold * float(self.speech_start_multiplier)
            # Hysteresis: require a stronger signal to reset accumulated silence.
            silence_reset_threshold = speech_start_threshold * 0.9
            frame_seconds = frames / self.mic_sample_rate
            loud_reset_required = 0.24
            now = time.time()
            if now - self._last_listen_debug_log >= 0.25:
                silence_time = self.silence_counter * (frames / self.mic_sample_rate)
                print(
                    "  [mic] rms={:.5f} floor={:.5f} start_th={:.5f} silence_th={:.5f} reset_th={:.5f} loud={:.2f}s speech_started={} silence={:.2f}s/{}s".format(
                        float(rms),
                        float(self.noise_floor_ema),
                        float(speech_start_threshold),
                        float(adaptive_silence_threshold),
                        float(silence_reset_threshold),
                        float(self.loud_counter * frame_seconds),
                        self.speech_started,
                        float(silence_time),
                        float(self.silence_duration),
                    )
                )
                self._last_listen_debug_log = now
            if not self.speech_started and rms > speech_start_threshold:
                self.speech_started = True
                self.speech_start_time = time.time()
                print("  Speech started...")
            if self.speech_started:
                speech_duration = time.time() - self.speech_start_time
                if (not self._silence_triggered) and speech_duration >= self.max_speech_duration:
                    self._silence_triggered = True
                    print(f"  Max speech duration reached ({speech_duration:.1f}s), processing now")
                    self._main_thread(self._on_silence_detected)
                    return
                if rms < adaptive_silence_threshold:
                    self.silence_counter += 1
                    self.loud_counter = 0
                    silence_time = self.silence_counter * (frames / self.mic_sample_rate)
                    if (
                        (not self._silence_triggered)
                        and speech_duration > self.min_speech_duration
                        and silence_time > self.silence_duration
                    ):
                        self._silence_triggered = True
                        print(f"  Silence detected after {speech_duration:.1f}s of speech")
                        self._main_thread(self._on_silence_detected)
                elif rms > silence_reset_threshold:
                    self.loud_counter += 1
                    if (self.loud_counter * frame_seconds) >= loud_reset_required:
                        # Reset silence only on sustained loudness, not one-off spikes.
                        self.silence_counter = 0
                # Between silence_th and reset_th: keep previous counter

        elif self.state == State.FOLLOW_UP:
            rms = al
            if time.time() - self.follow_up_start_time > self.follow_up_timeout:
                print("  Follow-up timeout, returning to wake word mode")

                def back():
                    self._set_state(State.WAITING)
                    self.status_message = "Say 'Hey Veedatron' to activate..."
                    self.wake_word_model.reset()

                self._main_thread(back)
                return
            if rms > self.silence_threshold * 2:
                print("💬 Follow-up detected!")

                def go():
                    self._start_listening_mode()

                self._main_thread(go)

    def _apply_wake_confidence(self, conf: float):
        c = float(conf)
        self.wake_word_confidence = c
        self.wake_meter_label = f"Wake word: {c:.1%}"
        # Only react while waiting; multiple callbacks per second used to fire
        # _on_wake_word repeatedly, bumping current_request_id and aborting TTS mid-play.
        if c >= self.wake_word_threshold:
            if self.state != State.WAITING:
                return
            print("🎤 Wake word detected!")
            self._on_wake_word()

    def _on_wake_word(self):
        """Wake phrase detected: enter listening mode immediately."""
        if self.state != State.WAITING:
            return
        if self.wake_word_model is not None:
            self.wake_word_model.reset()
        self.user_text = "Hey Veedatron"
        self.bot_response = ""
        self._start_listening_mode()
        self.status_message = "Listening... speak your command!"

    def _start_listening_mode(self):
        self.current_request_id += 1
        self._stop_playback()
        self._set_state(State.LISTENING)
        self.recording_buffer = []
        self.speech_started = False
        self.silence_counter = 0
        self.loud_counter = 0
        self._silence_triggered = False
        self._last_listen_debug_log = 0.0
        self.status_message = "Listening... speak now!"

    def _on_silence_detected(self):
        if self.state != State.LISTENING or self.processing:
            return
        self.processing = True
        self._set_state(State.THINKING)
        self.status_message = "Processing your request..."
        threading.Thread(target=self._process_audio, daemon=True).start()

    def _process_audio(self):
        my_request_id = self.current_request_id
        try:
            # Keep this phase strictly compute-only (recording -> STT -> API/LLM -> TTS).
            # We intentionally avoid any speech playback until all work is complete.
            if not self.recording_buffer:

                def fail_empty():
                    self._set_state(State.WAITING)
                    self.status_message = "No audio recorded. Say 'Hey Veedatron' again!"
                    self.processing = False

                self._main_thread(fail_empty)
                return

            audio = np.concatenate(self.recording_buffer)
            duration_sec = len(audio) / self.target_sample_rate
            max_val = float(np.max(np.abs(audio)))
            rms = float(np.sqrt(np.mean(audio**2)))
            print(f"  Recording: {len(audio)} samples = {duration_sec:.2f}s")
            print(f"  Audio stats: max={max_val:.4f}, rms={rms:.4f}")

            if max_val > 0.001:
                audio = audio / max_val * 0.95
            else:
                print("  WARNING: Audio too quiet!")
            audio_rms = float(np.sqrt(np.mean(audio**2)))
            if audio_rms < 0.1:
                gain = min(0.3 / audio_rms, 10.0)
                audio = np.clip(audio * gain, -1.0, 1.0)
                print(f"  Applied gain: {gain:.1f}x")

            audio_int16 = (audio * 32767).astype(np.int16)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                wav_path = f.name
            with wave.open(wav_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.target_sample_rate)
                wf.writeframes(audio_int16.tobytes())

            debug_path = "/tmp/vidatron_last_recording.wav"
            with wave.open(debug_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.target_sample_rate)
                wf.writeframes(audio_int16.tobytes())
            print(f"  Debug WAV saved to: {debug_path}")

            def set_transcribing():
                self.status_message = "Transcribing speech..."

            self._main_thread(set_transcribing)
            print(f"  Transcribing {len(audio)} samples ({len(audio)/self.target_sample_rate:.1f}s)...")

            result = subprocess.run(
                [
                    self.config.whisper_path,
                    "-m",
                    self.config.whisper_model,
                    "-l",
                    "en",
                    "-t",
                    "4",
                    "-np",
                    "-ng",
                    "-nt",
                    wav_path,
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.stderr:
                print(f"  Whisper stderr: {result.stderr[:200]}")

            text = result.stdout.strip()
            text = re.sub(
                r"\[\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}\]\s*",
                "",
                text,
            )
            for marker in [
                "[BLANK_AUDIO]",
                "[MUSIC]",
                "[NOISE]",
                "[SILENCE]",
                "(silence)",
                "[inaudible]",
            ]:
                text = text.replace(marker, "")
            text = text.strip()
            text = sanitize_whisper_output(text)
            os.unlink(wav_path)

            if not text:

                def no_text():
                    self._set_state(State.WAITING)
                    self.status_message = "Couldn't understand. Say 'Hey Veedatron' again!"
                    self.processing = False

                self._main_thread(no_text)
                return

            if self._is_farewell_thanks(text):

                def goodbye():
                    self.user_text = text
                    self.bot_response = ""
                    self._set_state(State.WAITING)
                    self.status_message = "Say 'Hey Veedatron' to activate..."
                    self.processing = False
                    if self.wake_word_model is not None:
                        self.wake_word_model.reset()
                    self.current_request_id += 1

                self._main_thread(goodbye)
                print("  Farewell — back to waiting for 'Hey Veedatron'.")
                return

            ack = self._paused_motion_ack_or_none(text)
            if ack is not None:
                print(f"  [motion] {ack}")
                self._handle_voice_drive_ack(text, ack, my_request_id, from_voice=True)
                return

            def set_user(t):
                self.user_text = t
                self.status_message = "Generating response..."

            self._main_thread(set_user, text)
            print(f"  You said: {text}")

            result_rt = self.router.route(text)
            print(f"  Router selected: {result_rt.tool.name} (args: {result_rt.arguments})")

            if result_rt.tool == ToolType.NONE:
                response = result_rt.response
            elif result_rt.tool == ToolType.TIME:
                response = get_current_time()
            elif result_rt.tool == ToolType.SYSTEM_STATUS:
                response = get_system_status()
            elif result_rt.tool == ToolType.JOKE:
                response = get_joke()
            elif result_rt.tool == ToolType.WEATHER:
                if self.weather:
                    loc = result_rt.arguments.get("location") or self.config.local_location or "New York"
                    print(f"  [weather] Checking weather for {loc}...")
                    try:
                        response = self.weather.get_weather(loc)
                    except Exception as e:
                        print(f"  Weather error: {e}")
                        response = f"Sorry, I couldn't get the weather for {loc} right now."
                else:
                    response = "Weather lookup isn't configured. Add OPENWEATHER_API_KEY to enable it."
            elif result_rt.tool == ToolType.NEWS:
                if self.news:
                    category = result_rt.arguments.get("category", "")
                    print(f"  [news] Fetching headlines{' for ' + category if category else ''}...")
                    try:
                        response = self.news.get_news(category)
                    except Exception as e:
                        print(f"  News error: {e}")
                        response = "Sorry, I couldn't get the news right now."
                else:
                    response = "News lookup isn't configured. Add NEWSAPI_KEY to enable it."
            elif result_rt.tool == ToolType.SPOTIFY_PLAY:
                if self.spotify:
                    q = (result_rt.arguments.get("query") or "").strip() or text
                    print(f"  [spotify] play → {q!r}")
                    try:
                        response = self.spotify.play_search(q)
                    except SpotifyError as e:
                        response = str(e)
                else:
                    response = (
                        "Spotify is not configured. Add SPOTIFY_CLIENT_ID, "
                        "SPOTIFY_CLIENT_SECRET, and SPOTIFY_REFRESH_TOKEN to your .env file."
                    )
            elif result_rt.tool == ToolType.SPOTIFY_PAUSE:
                if self.spotify:
                    print("  [spotify] pause")
                    try:
                        self.spotify.pause()
                        response = "Okay, I paused Spotify."
                    except SpotifyError as e:
                        response = str(e)
                else:
                    response = "Spotify is not configured, so I cannot pause playback."
            elif result_rt.tool == ToolType.CLOUD:
                if self.cloud:
                    print("  [cloud] Sending to Groq...")
                    response = None
                    if my_request_id != self.current_request_id:
                        print("  ⏹ Request cancelled before cloud call")

                        def end():
                            self.processing = False

                        self._main_thread(end)
                        return
                    for attempt in range(2):
                        try:
                            query = result_rt.arguments.get("query", text)
                            response = self.cloud.chat(
                                query,
                                stream=False,
                                history=self.chat_history.messages_for_api(),
                            )
                            break
                        except Exception as e:
                            error_msg = str(e)
                            print(f"  Cloud error (attempt {attempt+1}): {error_msg}")
                            if "429" in error_msg and attempt == 0:
                                if my_request_id != self.current_request_id:
                                    print("  ⏹ Request cancelled during retry wait")

                                    def end2():
                                        self.processing = False

                                    self._main_thread(end2)
                                    return
                                print("  Waiting 3 seconds before retry...")
                                time.sleep(3)
                            else:
                                break
                    if response is None:
                        if my_request_id != self.current_request_id:
                            print("  ⏹ Request cancelled before fallback")

                            def end3():
                                self.processing = False

                            self._main_thread(end3)
                            return
                        print("  [fallback] Using local model...")
                        try:
                            query_fb = result_rt.arguments.get("query", text)
                            messages = self._ollama_messages_cloud_fallback(query_fb)
                            local_response = self.ollama.chat(messages, tools=None)
                            response = local_response.content or "I'm not sure about that."
                        except Exception:
                            response = "Sorry, I'm having trouble thinking right now. Try again in a moment."
                else:
                    print("  [local fallback] No cloud configured...")
                    try:
                        query_fb = result_rt.arguments.get("query", text)
                        messages = self._ollama_messages_cloud_fallback(query_fb)
                        local_response = self.ollama.chat(messages, tools=None)
                        response = local_response.content or "I'm not sure about that."
                    except Exception:
                        response = "That's a complex question. I'm having trouble answering right now."
            else:
                response = result_rt.response or "I'm not sure how to respond to that."

            if result_rt.tool == ToolType.CLOUD and response:
                self.chat_history.append_exchange(
                    result_rt.arguments.get("query", text),
                    response,
                )

            if my_request_id != self.current_request_id:
                print("  ⏹ Request cancelled (new question detected)")

                def end4():
                    self.processing = False

                self._main_thread(end4)
                return

            print(f"  Bot: {response[:50]}...")

            # Finish synthesis before entering SPEAKING so playback is the only active phase.
            wav_file = self.tts.synthesize(response)
            if my_request_id != self.current_request_id:
                print("  ⏹ Request cancelled before playback")
                try:
                    os.unlink(wav_file)
                except OSError:
                    pass

                def end5():
                    self.processing = False

                self._main_thread(end5)
                return

            def start_speaking():
                self.bot_response = response
                self._set_state(State.SPEAKING)
                self.status_message = "Speaking response... (processing complete)"

            self._main_thread_sync(start_speaking, timeout=5.0)

            played = self._play_wav_blocking(wav_file, cancel_id=my_request_id)
            try:
                os.unlink(wav_file)
            except OSError:
                pass

            if my_request_id != self.current_request_id:
                print("  ⏹ Stopping playback (new question)")
                self._main_thread(lambda: setattr(self, "processing", False))
                return

            if played and my_request_id == self.current_request_id:

                def follow():
                    self._set_state(State.FOLLOW_UP)
                    self.follow_up_start_time = time.time()
                    self.status_message = "Ask a follow-up question..."
                    self.processing = False
                    print("💬 Ready for follow-up (or wait 8s to exit conversation)")

                self._main_thread(follow)
            else:
                self._main_thread(lambda: setattr(self, "processing", False))

        except Exception as e:
            print(f"Error: {e}")
            import traceback

            traceback.print_exc()

            err_preview = str(e)[:40]

            def err():
                self._set_state(State.WAITING)
                self.status_message = f"Error: {err_preview}. Try again!"
                self.processing = False

            self._main_thread(err)


class VidatronApp(App):
    title = "Vidatron - Say 'Hey Veedatron'"

    def __init__(self, engine: VidatronEngine, **kwargs):
        super().__init__(**kwargs)
        self.engine = engine
        self._keyboard_cb = None

    def build(self):
        root = VidatronRoot(engine=self.engine)
        self._root = root
        return root

    def on_start(self):
        eng = self.engine
        self._keyboard_cb = partial(_on_keyboard, eng)
        Window.bind(on_keyboard=self._keyboard_cb)
        # Do not pre-open speaker stream here — it holds plughw open and breaks aplay.
        if not eng.manual_terminal_mode:
            eng._open_mic_stream()
            print(f"  Audio stream started at {eng.mic_sample_rate}Hz")
        else:
            eng.stream = None
            print("  Audio stream disabled (manual terminal mode)")
        eng.start_terminal_prompt_loop()

    def on_stop(self):
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
    print("Starting Vidatron Test UI...")
    print("Checking components...")
    cfg = AppConfig.load()
    ollama = OllamaClient(model=cfg.chat_model)
    if not ollama.is_available():
        print("ERROR: Ollama is not running!")
        print("Start it with: ollama serve")
        sys.exit(1)
    print("✓ Ollama connected")
    if os.environ.get("VIDATRON_MANUAL_TERMINAL", "").strip().lower() not in ("1", "true", "yes"):
        if not Path(cfg.wake_word_model).exists():
            print(f"ERROR: Wake word model not found: {cfg.wake_word_model}")
            sys.exit(1)
        print("✓ Wake word model found")
    else:
        print("ℹ Wake word disabled (VIDATRON_MANUAL_TERMINAL)")
    if not Path(cfg.whisper_path).exists():
        print(f"ERROR: Whisper not found: {cfg.whisper_path}")
        sys.exit(1)
    print("✓ Whisper found")
    if not Path(cfg.piper_voice).exists():
        print(f"ERROR: Piper voice not found: {cfg.piper_voice}")
        sys.exit(1)
    print("✓ Piper TTS found")
    print()

    print("\n" + "=" * 55)
    print("  Vidatron Voice Assistant - Test Interface (Kivy)")
    print("=" * 55)
    if os.environ.get("VIDATRON_MANUAL_TERMINAL", "").strip().lower() in ("1", "true", "yes"):
        print("  • Manual terminal mode: mic off, type at You>")
    else:
        print("  • Say 'Hey Veedatron' → starts listening for your command")
        print("  • Type prompts in this terminal at You> (same as speaking after wake)")
        print("  • Space = simulate wake word while waiting")
    print("  • Press Esc to exit")
    print("=" * 55 + "\n")

    engine = VidatronEngine()
    VidatronApp(engine=engine).run()


def _on_keyboard(engine: VidatronEngine, window, key, scancode, codepoint, modifier):
    if key == 27:  # Escape
        App.get_running_app().stop()
        return True
    if key == 32 and engine.state == State.WAITING:  # Space
        engine._main_thread(engine._on_wake_word)
        return True
    return False


if __name__ == "__main__":
    main()
