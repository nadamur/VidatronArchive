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
import math
import random
import uuid
import numpy as np
from pathlib import Path
from datetime import datetime
from enum import Enum
from collections import deque
from functools import partial
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))
_UI_PKG = Path(__file__).resolve().parent.parent / "ui"
if str(_UI_PKG) not in sys.path:
    sys.path.append(str(_UI_PKG))
from face_customization import normalize_eye_choice, normalize_mouth_choice
from widgets import StickFigureIcon


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
from kivy.graphics import Color, Ellipse, Line, Mesh, RoundedRectangle
from kivy.metrics import dp
from kivy.lang import Builder
from kivy.properties import (
    BooleanProperty,
    ListProperty,
    NumericProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen, ScreenManager, SlideTransition
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


class UIColors:
    """Blue screen background; accent colors for UI chrome elsewhere."""
    BG = (0.38, 0.58, 0.88, 1)
    BG_BLOB_A = (0.48, 0.72, 0.95, 0.35)
    BG_BLOB_B = (0.28, 0.42, 0.78, 0.4)
    PANEL = (1.0, 0.995, 1.0, 1)
    PANEL_BOT = (0.99, 0.98, 0.99, 1)
    ACCENT = (0.28, 0.55, 0.82, 1)
    ACCENT_DIM = (0.48, 0.62, 0.82, 1)
    PINK = (0.94, 0.48, 0.58, 1)
    MINT = (0.45, 0.78, 0.68, 1)
    TEXT = (0.16, 0.19, 0.24, 1)
    TEXT_DIM = (0.44, 0.47, 0.52, 1)
    SUCCESS = (0.34, 0.72, 0.52, 1)
    ERROR = (0.92, 0.45, 0.52, 1)
    ORANGE = (0.96, 0.62, 0.38, 1)
    PURPLE = (0.62, 0.5, 0.9, 1)
    CARD_BORDER = (0.86, 0.9, 0.94, 1)
    WAVE_BG = (0.93, 0.96, 0.99, 1)
    FACE_RING = (0.88, 0.92, 0.98, 1)


def _ease_in_quad(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t


def _ease_out_quad(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * (2.0 - t)


_UI_CM = None


def _get_ui_config_manager():
    """Load ui/vidatron_config.json (avoids clashing with ai ``config`` on sys.path)."""
    global _UI_CM
    if _UI_CM is None:
        import importlib.util

        p = Path(__file__).resolve().parent.parent / "ui" / "config.py"
        spec = importlib.util.spec_from_file_location("vidatron_ui_cfg", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _UI_CM = mod.config_manager
    return _UI_CM


def _voice_repeat_allows(repeat_settings: str, now: datetime) -> bool:
    if repeat_settings == "once":
        return True
    if repeat_settings == "daily":
        return True
    if repeat_settings == "weekdays":
        return now.weekday() < 5
    if repeat_settings == "weekends":
        return now.weekday() >= 5
    if repeat_settings == "weekly":
        return True
    return True


def _voice_normalize_trigger_time(time_str: str) -> str:
    if not time_str or not isinstance(time_str, str):
        return ""
    parts = time_str.strip().split(":")
    if len(parts) != 2:
        return ""
    try:
        h, m = int(parts[0]), int(parts[1])
        if h < 0 or h > 23 or m < 0 or m > 59:
            return ""
        return f"{h:02d}:{m:02d}"
    except (ValueError, TypeError):
        return ""


def _reminder_stick_action(reminder: dict) -> str:
    """Map a reminder to a stick-figure animation id."""
    a = (reminder.get("action") or "").strip().lower()
    if a in ("drink", "stretch", "walk", "think", "wave"):
        return a
    t = (reminder.get("text") or "").lower()
    ip = (reminder.get("icon_path") or "").lower()
    if "drink" in t or "water" in t or "hydrat" in t or "drink_water" in ip:
        return "drink"
    if any(k in t for k in ("grateful", "gratitude", "reflect", "thankful", "think about")):
        return "think"
    if any(k in t for k in ("short break", "walk", "stroll", "step away")):
        return "walk"
    if (
        "stretch" in t
        or "yoga" in t
        or any(k in t for k in ("stand", "break", "exercise", "jog"))
        or "get up" in t
    ):
        return "stretch"
    if "stretch" in ip or "stretch.png" in ip:
        return "stretch"
    if "drink" in ip or "water" in ip:
        return "drink"
    return "wave"


def _voice_seed_interval_last_fired(cm) -> None:
    reminders = cm.get("reminders", [])
    last_fired = dict(cm.get("last_fired", {}))
    now_ts = datetime.now().timestamp()
    updated = False
    for reminder in reminders:
        if not reminder.get("is_active", True):
            continue
        if reminder.get("trigger_type", "Specific Time") != "Every X Minutes":
            continue
        rid = reminder.get("id")
        if not rid:
            continue
        last_fired[rid] = now_ts
        updated = True
    if updated:
        cm.set("last_fired", last_fired)


def voice_reminder_tick(_dt: float) -> None:
    app = App.get_running_app()
    if not app or not getattr(app, "engine", None):
        return
    eng = app.engine
    if eng.reminder_show:
        return
    sm = app.root
    if not isinstance(sm, ScreenManager):
        return

    now = datetime.now()
    current_time = now.strftime("%H:%M")
    current_date = now.strftime("%Y-%m-%d")
    current_minute = f"{current_date} {current_time}"
    current_timestamp = now.timestamp()

    cm = _get_ui_config_manager()
    reminders = cm.get("reminders", [])
    last_fired = dict(cm.get("last_fired", {}))

    for reminder in reminders:
        if not reminder.get("is_active", True):
            continue
        rid = reminder.get("id")
        if not rid:
            rid = str(uuid.uuid4())
            reminder["id"] = rid
            cm.set("reminders", reminders)

        trigger_type = reminder.get("trigger_type", "Specific Time")
        should_trigger = False

        if trigger_type == "Every X Minutes":
            interval_minutes = reminder.get("interval_minutes", 5)
            last_fired_time = last_fired.get(rid)
            if last_fired_time is None:
                last_fired[rid] = current_timestamp
                cm.set("last_fired", last_fired)
                continue
            try:
                if isinstance(last_fired_time, str):
                    last_dt = datetime.strptime(last_fired_time, "%Y-%m-%d %H:%M")
                else:
                    last_dt = datetime.fromtimestamp(last_fired_time)
                minutes_passed = (now - last_dt).total_seconds() / 60.0
                if minutes_passed >= interval_minutes:
                    should_trigger = True
            except (ValueError, TypeError):
                should_trigger = True
        else:
            raw_trigger = reminder.get("trigger_time", "")
            trigger_time = _voice_normalize_trigger_time(raw_trigger)
            if not trigger_time or trigger_time != current_time:
                continue
            if last_fired.get(rid) == current_minute:
                continue
            should_trigger = True

        if not should_trigger:
            continue

        if trigger_type == "Specific Time":
            repeat_settings = reminder.get("repeat_settings", "once")
            if not _voice_repeat_allows(repeat_settings, now):
                continue

        if sm.current != "voice":
            sm.current = "voice"
        eng.fire_reminder_display(reminder, return_screen=None)

        if trigger_type == "Every X Minutes":
            last_fired[rid] = current_timestamp
        else:
            last_fired[rid] = current_minute
        cm.set("last_fired", last_fired)

        if trigger_type == "Specific Time" and reminder.get("repeat_settings") == "once":
            reminder["is_active"] = False
            cm.set("reminders", reminders)
        break


class CuteMascotWidget(Widget):
    """Large-eyed vector mascot with realistic blink timing and speech-shaped mouth motion."""

    engine = ObjectProperty(None, allownone=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        now = time.monotonic()
        self._blink_phase = 0
        self._blink_t0 = now
        self._next_blink_at = now + random.uniform(2.2, 4.2)
        self._blink_amount = 0.0
        self._chained_second_blink = False
        Clock.schedule_interval(self._tick, 1 / 60.0)

    def _advance_blink(self, now: float) -> None:
        """Finite-state blink: quick close, short hold, smooth open; random intervals + rare double-blink."""
        if self._blink_phase == 0:
            if now >= self._next_blink_at:
                self._blink_phase = 1
                self._blink_t0 = now
            return

        if self._blink_phase == 1:
            u = (now - self._blink_t0) / 0.048
            self._blink_amount = _ease_in_quad(min(1.0, u))
            if u >= 1.0:
                self._blink_phase = 2
                self._blink_t0 = now
            return

        if self._blink_phase == 2:
            self._blink_amount = 1.0
            if now - self._blink_t0 > 0.042:
                self._blink_phase = 3
                self._blink_t0 = now
            return

        if self._blink_phase == 3:
            u = (now - self._blink_t0) / 0.085
            self._blink_amount = 1.0 - _ease_out_quad(min(1.0, u))
            if u >= 1.0:
                self._blink_phase = 0
                self._blink_amount = 0.0
                if self._chained_second_blink:
                    self._chained_second_blink = False
                    self._next_blink_at = now + random.uniform(2.6, 4.8)
                elif random.random() < 0.13:
                    self._chained_second_blink = True
                    self._next_blink_at = now + 0.11
                else:
                    self._next_blink_at = now + random.uniform(2.6, 4.8)

    def _mouth_speaking(self, af: float) -> tuple[float, float]:
        """Jaw 0..1 + mouth width factor — layered sines (syllable + ripple + micro) like earlier viseme motion."""
        t = af * 0.028
        syllable = 0.5 + 0.5 * math.sin(t)
        ripple = 0.2 * math.sin(t * 2.65 + 0.4)
        micro = 0.07 * math.sin(t * 5.1)
        jaw = max(0.06, min(1.0, 0.15 + 0.74 * syllable + ripple + micro))
        width = 0.9 + 0.16 * abs(math.sin(t * 1.85 + 0.2))
        return jaw, width

    def _tick(self, _dt):
        self._advance_blink(time.monotonic())
        if self.engine:
            self.engine.animation_frame = self.engine.animation_frame + 1
        self._draw()

    def _draw(self):
        self.canvas.after.clear()
        if not self.width or not self.height:
            return
        eng = self.engine
        if not eng:
            return
        st = eng.display_state
        af = float(eng.animation_frame)
        cx = self.x + self.width / 2
        cy = self.y + self.height / 2
        r = min(self.width, self.height) * 0.53
        cy_f = cy - r * 0.12
        blink = self._blink_amount
        is_thinking = st == "thinking"
        think_t = af * 0.065

        eye_shape = normalize_eye_choice(getattr(eng, "selected_eyes", None))
        mouth_shape = normalize_mouth_choice(getattr(eng, "selected_mouth", None))

        ex = r * 0.42
        ey = r * 0.1
        eye_d = r * 0.56
        eye_scale_w = 1.0
        eye_scale_h = 1.0
        eye_off_y = 0.0
        iris_mul = 1.0
        pupil_mul = 1.0
        if eye_shape == "Round":
            pass
        elif eye_shape == "Narrow":
            eye_scale_w = 0.54
            eye_scale_h = 1.14
            ex *= 0.93
            eye_off_y = -r * 0.02
            iris_mul = 0.9
            pupil_mul = 0.88
        elif eye_shape == "Wide":
            eye_scale_w = 1.48
            eye_scale_h = 0.84
            ex *= 1.09
            eye_off_y = -r * 0.04
            iris_mul = 1.1
            pupil_mul = 1.06
        elif eye_shape == "Small":
            eye_scale_w = 0.68
            eye_scale_h = 0.68
            ex *= 0.91
            iris_mul = 0.76
            pupil_mul = 0.74

        listen_wide = 1.04 if st == "listening" else 1.0
        think_squint = 0.88 if is_thinking else 1.0
        squish = max(0.06, 1.0 - blink)
        d_full = eye_d * listen_wide * think_squint
        ew = d_full * eye_scale_w
        eh = d_full * squish * eye_scale_h
        eye_y0 = ey + eye_off_y

        with self.canvas.after:
            # rosy cheeks (no head circle — floating face on blue)
            cheek_boost = 0.1 * math.sin(af * 0.2) if st == "speaking" else 0.0
            Color(1.0, 0.62 + cheek_boost * 0.12, 0.72 + cheek_boost * 0.08, 0.5 + cheek_boost * 0.1)
            Ellipse(pos=(cx - r * 0.9, cy_f - r * 0.22), size=(r * 0.38, r * 0.24))
            Ellipse(pos=(cx + r * 0.54, cy_f - r * 0.22), size=(r * 0.38, r * 0.24))

            # Thought bubbles first (under eyes) — beside top of right eye
            if is_thinking:
                bob = math.sin(think_t * 1.1) * r * 0.028
                bx0 = cx + ex + d_full * 0.32
                by0 = cy_f + eye_y0 + d_full * 0.92 + bob
                Color(0.93, 0.94, 0.98, 0.58)
                Ellipse(pos=(bx0 - r * 0.08, by0 - r * 0.06), size=(r * 0.16, r * 0.11))
                Color(1, 1, 1, 0.92)
                Ellipse(pos=(bx0 + r * 0.14, by0 + r * 0.1), size=(r * 0.26, r * 0.2))
                Ellipse(pos=(bx0 + r * 0.42, by0 + r * 0.2), size=(r * 0.16, r * 0.14))
                Color(0.88, 0.9, 0.95, 0.88)
                Line(circle=(bx0 + r * 0.28, by0 + r * 0.14, r * 0.13), width=1.45)
                Line(circle=(bx0 + r * 0.52, by0 + r * 0.25, r * 0.08), width=1.35)

            # --- Eyes: shape from Round / Narrow / Wide / Small ---
            gaze_up = r * 0.1 * math.sin(think_t * 0.88) if is_thinking else 0.0
            gaze_x = r * 0.04 * math.cos(think_t * 0.52) if is_thinking else r * 0.015 * math.sin(af * 0.04)
            off_x = gaze_x
            px_shift = gaze_x * 1.2
            px_left = px_shift
            px_right = px_shift
            Color(1, 1, 1, 1)
            Ellipse(
                pos=(cx - ex - ew / 2 + off_x, cy_f + eye_y0 + (d_full - eh) / 2),
                size=(ew, eh),
            )
            Ellipse(
                pos=(cx + ex - ew / 2 + off_x, cy_f + eye_y0 + (d_full - eh) / 2),
                size=(ew, eh),
            )

            # eyebrows — thinking: gentle inner tilt (very thick strokes)
            brow_y = cy_f + eye_y0 + d_full * 0.88
            if is_thinking:
                Color(0.52, 0.4, 0.42, 0.92)
                Line(
                    points=[cx - ex - ew * 0.48, brow_y, cx - ex + ew * 0.12, brow_y + r * 0.05],
                    width=8.4,
                )
                Line(
                    points=[cx + ex + ew * 0.48, brow_y, cx + ex - ew * 0.12, brow_y + r * 0.05],
                    width=8.4,
                )
            elif st == "listening":
                bo = r * 0.018
                bi = r * 0.052
                Color(0.5, 0.4, 0.44, 0.9)
                Line(
                    points=[
                        cx - ex - ew * 0.5,
                        brow_y - bo,
                        cx - ex + ew * 0.1,
                        brow_y + bi,
                    ],
                    width=6.0,
                )
                Line(
                    points=[
                        cx + ex + ew * 0.5,
                        brow_y - bo,
                        cx + ex - ew * 0.1,
                        brow_y + bi,
                    ],
                    width=6.0,
                )

            iris = r * 0.34 * (0.38 + 0.62 * squish) * iris_mul
            pupil = r * 0.26 * (0.35 + 0.65 * squish) * pupil_mul
            py = cy_f + eye_y0 + d_full * 0.5 - gaze_up
            if squish > 0.12:
                Color(0.32, 0.55, 0.78, 1)
                Ellipse(
                    pos=(cx - ex - iris / 2 + off_x + px_left, py - iris / 2),
                    size=(iris, iris),
                )
                Ellipse(
                    pos=(cx + ex - iris / 2 + off_x + px_right, py - iris / 2),
                    size=(iris, iris),
                )
                Color(0.12, 0.14, 0.2, 1)
                Ellipse(
                    pos=(cx - ex - pupil / 2 + off_x + px_left, py - pupil / 2),
                    size=(pupil, pupil),
                )
                Ellipse(
                    pos=(cx + ex - pupil / 2 + off_x + px_right, py - pupil / 2),
                    size=(pupil, pupil),
                )
                Color(1, 1, 1, 0.95)
                hi = r * 0.048
                Ellipse(
                    pos=(cx - ex - iris * 0.35 + off_x + px_left, py + iris * 0.15),
                    size=(hi, hi),
                )
                Ellipse(
                    pos=(cx + ex - iris * 0.15 + off_x + px_right, py + iris * 0.12),
                    size=(hi * 0.85, hi * 0.85),
                )

            if 0.15 < blink < 0.92:
                Color(0.42, 0.52, 0.68, 0.75)
                lw = 2.4
                lx = cx - ex + off_x
                Line(
                    points=self._lid_pts(lx, cy_f + eye_y0 + d_full * 0.35, ew * 0.42, blink),
                    width=lw,
                )
                lx = cx + ex + off_x
                Line(
                    points=self._lid_pts(lx, cy_f + eye_y0 + d_full * 0.35, ew * 0.42, blink),
                    width=lw,
                )

            # sparkles — idle / follow-up (not while thinking)
            if st in ("waiting", "follow_up"):
                Color(1, 0.94, 0.55, 0.82)
                Ellipse(pos=(cx - r * 0.92, cy_f + r * 0.52), size=(r * 0.11, r * 0.11))
                Ellipse(pos=(cx + r * 0.78, cy_f + r * 0.48), size=(r * 0.09, r * 0.09))

            # --- Mouth: Small / Wide / Neutral ---
            mouth_w_mul = 1.0
            idle_line_w = 3.15
            smile_b = -0.12
            if mouth_shape == "Wide":
                mouth_w_mul = 1.26
                idle_line_w = 3.75
                smile_b = -0.16
            elif mouth_shape == "Small":
                mouth_w_mul = 0.74
                idle_line_w = 2.55
                smile_b = -0.078
            else:
                # Neutral
                mouth_w_mul = 1.0
                idle_line_w = 2.95

            mouth_cy = cy_f + r * 0.09
            smile_w = r * 0.52 * mouth_w_mul
            mouth_y = mouth_cy + r * 0.02

            if st == "speaking":
                mouth_speak_cy = mouth_cy - r * 0.055
                jaw, wfac = self._mouth_speaking(af)
                w_m = r * (0.36 + 0.14 * wfac) * mouth_w_mul
                gap = r * (0.02 + 0.12 * jaw)
                if mouth_shape == "Neutral":
                    gap *= 0.72
                du = gap * 0.42
                dl = gap * 0.58
                lip_u, lip_lo = self._speaking_lip_pts(cx, mouth_speak_cy, w_m, du, dl)
                fill_v = self._speaking_lip_fill_vertices(lip_u, lip_lo)
                Color(0.42, 0.14, 0.24, 0.94)
                Mesh(vertices=fill_v, indices=list(range(len(fill_v) // 4)), mode="triangle_strip")
                Color(0.78, 0.42, 0.52, 1)
                Line(points=lip_u, width=3.0)
                Color(0.52, 0.26, 0.36, 1)
                Line(points=lip_lo, width=2.7)
            elif st == "listening":
                Color(0.92, 0.55, 0.68, 1)
                if mouth_shape == "Neutral":
                    lw = r * 0.41 * mouth_w_mul
                    Line(points=[cx - lw, mouth_y, cx + lw, mouth_y], width=2.05)
                else:
                    Line(
                        points=self._smile_pts(cx, mouth_cy, r * 0.4 * mouth_w_mul, bulge=-0.034),
                        width=1.55,
                    )
            elif is_thinking:
                hmm = 0.5 + 0.5 * math.sin(think_t * 1.2)
                wobble = 0.04 * math.sin(think_t * 2.1)
                th_mul = 0.88 if mouth_shape == "Small" else 1.12 if mouth_shape == "Wide" else 1.0
                oh = r * (0.065 + 0.062 * hmm) * mouth_w_mul**0.5 * th_mul
                ow = r * (0.16 + 0.048 * hmm) * mouth_w_mul * th_mul
                if mouth_shape == "Neutral":
                    oh *= 0.85
                    ow *= 0.88
                Color(0.5, 0.34, 0.4, 1)
                Ellipse(pos=(cx - ow / 2 + r * wobble, mouth_cy - oh / 2), size=(ow, oh))
                Color(0.2, 0.1, 0.12, 0.35)
                Ellipse(
                    pos=(cx - ow * 0.22 + r * wobble * 0.9, mouth_cy - oh * 0.25),
                    size=(ow * 0.44, oh * 0.45),
                )
            else:
                Color(0.95, 0.52, 0.65, 1)
                if mouth_shape == "Neutral":
                    lw = smile_w * 0.48
                    Line(points=[cx - lw, mouth_y, cx + lw, mouth_y], width=idle_line_w)
                else:
                    Line(
                        points=self._smile_pts(cx, mouth_y, smile_w, bulge=smile_b),
                        width=idle_line_w,
                    )

    @staticmethod
    def _speaking_lip_pts(
        cx: float, y_corner: float, width: float, upper_span: float, lower_span: float
    ) -> tuple[list[float], list[float]]:
        """Upper/lower lip polylines with identical (x,y) at both ends — mouth opens at center only."""
        lip_u: list[float] = []
        lip_lo: list[float] = []
        for i in range(17):
            t = -1.0 + (i / 16.0) * 2.0
            x = cx + t * 0.55 * width
            fac = 1.0 - t * t
            lip_u.extend([x, y_corner + upper_span * fac])
            lip_lo.extend([x, y_corner - lower_span * fac])
        return lip_u, lip_lo

    @staticmethod
    def _speaking_lip_fill_vertices(lip_u: list[float], lip_lo: list[float]) -> list[float]:
        """Triangle strip for Mesh: x,y,u,v per vertex; alternates upper then lower along the mouth."""
        out: list[float] = []
        n = len(lip_u) // 2
        for i in range(n):
            out.extend(
                [lip_u[2 * i], lip_u[2 * i + 1], 0.0, 0.0, lip_lo[2 * i], lip_lo[2 * i + 1], 0.0, 0.0]
            )
        return out

    @staticmethod
    def _lid_pts(cx: float, cy: float, half_w: float, blink_amt: float) -> list[float]:
        dip = half_w * 0.35 * blink_amt
        return [cx - half_w, cy, cx, cy - dip, cx + half_w, cy]

    @staticmethod
    def _smile_pts(cx: float, cy: float, width: float, bulge: float) -> list:
        """Quad through (-1,1): negative bulge => center dips => corners rise => smile."""
        pts = []
        for i in range(17):
            t = -0.55 + i / 16 * 1.1
            x = cx + t * width
            y = cy + bulge * width * (1 - t * t) * 3
            pts.extend([x, y])
        return pts


Builder.load_string(
    """
<VidatronRoot>:
    canvas.before:
        Color:
            rgba: root.bg_color
        Rectangle:
            pos: self.pos
            size: self.size
        Color:
            rgba: root.blob_color_a
        Ellipse:
            pos: self.x - dp(48), self.top - dp(140)
            size: dp(260), dp(200)
        Color:
            rgba: root.blob_color_b
        Ellipse:
            pos: self.right - dp(120), self.y + dp(8)
            size: dp(220), dp(180)

    orientation: 'vertical'
    padding: 0, 0, 0, 0
    spacing: 0

    FloatLayout:
        size_hint: 1, 1
        CuteMascotWidget:
            id: mascot
            engine: root.engine
            pos_hint: {'x': 0, 'y': 0}
            size_hint: 1, 1
        Image:
            id: face_img
            source: root.face_source
            fit_mode: "contain"
            pos_hint: {'x': 0, 'y': 0}
            size_hint: 1, 1
        StickFigureIcon:
            id: reminder_stick
            pos_hint: {'x': 0, 'y': 0}
            size_hint: 1, 1
            opacity: 0
        BoxLayout:
            orientation: 'vertical'
            padding: dp(14)
            spacing: dp(6)
            size_hint: 0.94, None
            height: dp(118)
            pos_hint: {'center_x': 0.5, 'y': 0.035}
            opacity: 1 if root.engine and root.engine.reminder_show else 0
            disabled: not (root.engine and root.engine.reminder_show)
            canvas.before:
                Color:
                    rgba: 0.11, 0.14, 0.22, 0.94
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(14),]
            Label:
                text: root.engine.reminder_caption if root.engine else ''
                color: 1, 1, 1, 1
                font_size: '18sp'
                bold: True
                size_hint_y: None
                height: max(dp(26), self.texture_size[1])
                text_size: self.width - dp(8), None
                halign: 'center'
                valign: 'middle'
            Label:
                text: root.engine.reminder_detail if root.engine else ''
                color: 0.92, 0.94, 0.98, 1
                font_size: '15sp'
                size_hint_y: None
                height: max(dp(36), self.texture_size[1])
                text_size: self.width - dp(8), None
                halign: 'center'
                valign: 'top'
"""
)


class VidatronRoot(BoxLayout):
    engine = ObjectProperty(None, allownone=True)

    bg_color = ListProperty([*UIColors.BG])
    blob_color_a = ListProperty([*UIColors.BG_BLOB_A])
    blob_color_b = ListProperty([*UIColors.BG_BLOB_B])
    face_source = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Clock.schedule_interval(self._refresh_ui, 1 / 15.0)

    def _refresh_ui(self, _dt):
        eng = self.engine
        if not eng:
            return
        self.face_source = eng.face_source
        reminding = bool(getattr(eng, "reminder_show", False))
        has_face = bool(
            getattr(eng, "face_source", "") and Path(str(eng.face_source)).exists()
        )
        if getattr(eng, "face_use_vector", False):
            has_face = False
        if hasattr(self.ids, "reminder_stick"):
            rs = self.ids.reminder_stick
            if reminding:
                rs.action = getattr(eng, "reminder_stick_action", "wave") or "wave"
                rs.accent = list(getattr(eng, "reminder_stick_accent", [0.1, 0.9, 1.0, 1.0]))
                rs.opacity = 1.0
        else:
                rs.opacity = 0.0
        if hasattr(self.ids, "face_img"):
            self.ids.face_img.opacity = 0.0 if reminding else (1.0 if has_face else 0.0)
        if hasattr(self.ids, "mascot"):
            self.ids.mascot.opacity = 0.0 if reminding or has_face else 1.0
        try:
            cm = _get_ui_config_manager()
            eng.selected_eyes = normalize_eye_choice(cm.get("face_customization.selected_eyes"))
            eng.selected_mouth = normalize_mouth_choice(cm.get("face_customization.selected_mouth"))
            bg = cm.get("default_colors.background", [0.38, 0.58, 0.88, 1.0])
            prim = cm.get("default_colors.primary", [0.28, 0.55, 0.82, 1.0])
            if isinstance(bg, list) and len(bg) >= 3:
                self.bg_color = [float(bg[0]), float(bg[1]), float(bg[2]), float(bg[3] if len(bg) > 3 else 1.0)]
            if isinstance(prim, list) and len(prim) >= 3:
                pr = [float(prim[0]), float(prim[1]), float(prim[2])]
                self.blob_color_a = [
                    pr[0] * 0.55 + 0.2,
                    pr[1] * 0.55 + 0.2,
                    pr[2] * 0.55 + 0.2,
                    0.38,
                ]
                self.blob_color_b = [
                    pr[0] * 0.35 + 0.08,
                    pr[1] * 0.35 + 0.08,
                    pr[2] * 0.35 + 0.15,
                    0.42,
                ]
            Window.clearcolor = (self.bg_color[0], self.bg_color[1], self.bg_color[2], 1.0)
        except (OSError, ValueError, TypeError, AttributeError):
            pass


class VidatronEngine(EventDispatcher):
    status_message = StringProperty("Say Hey Veedatron when you're ready…")
    wake_word_confidence = NumericProperty(0.0)
    audio_level = NumericProperty(0.0)
    animation_frame = NumericProperty(0)
    display_state = StringProperty("waiting")
    badge_text = StringProperty("")
    badge_color_rgba = ListProperty([*UIColors.ACCENT_DIM])
    face_source = StringProperty("")
    wake_meter_label = StringProperty("Wake word: 0%")
    playback_active = BooleanProperty(False)
    selected_eyes = StringProperty("Round")
    selected_mouth = StringProperty("Neutral")
    reminder_show = BooleanProperty(False)
    reminder_title = StringProperty("")
    reminder_detail = StringProperty("")
    reminder_caption = StringProperty("")
    reminder_stick_action = StringProperty("wave")
    reminder_stick_accent = ListProperty([0.10, 0.90, 1.00, 1.0])

    def __init__(self):
        super().__init__()
        self._reminder_return_screen: str | None = None
        self._reminder_clear_ev = None
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

        self.config = AppConfig.load()
        self.face_use_vector = bool(getattr(self.config, "face_use_vector", False))
        self._face_paths = self._build_face_paths()
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

    def fire_reminder_display(self, reminder: dict, return_screen: str | None = None) -> None:
        """Show full-screen stick-figure reminder animation on the voice UI (auto-dismiss)."""
        self._reminder_return_screen = return_screen

        # If the reminder provides `text_variants`, rotate caption text so it isn't repetitive.
        # We persist the chosen index in ui/vidatron_config.json so the UI and speech stay correlated.
        tv = reminder.get("text_variants")
        rid = reminder.get("id")
        if isinstance(tv, list) and len(tv) > 0 and rid:
            try:
                cm = _get_ui_config_manager()
                idx_map = cm.get("reminder_text_variant_index", {})
                if not isinstance(idx_map, dict):
                    idx_map = {}
                cur_idx = idx_map.get(rid, -1)
                next_idx = (int(cur_idx) + 1) % len(tv)
                idx_map[rid] = next_idx
                cm.set("reminder_text_variant_index", idx_map)

                chosen = str(tv[next_idx]).strip() or str(reminder.get("text") or "Reminder")
                reminder = dict(reminder)
                reminder["text"] = chosen
            except Exception as e:
                print(f"  Reminder variant selection failed: {e}")

        self.reminder_stick_action = _reminder_stick_action(reminder)
        # Force deterministic reminder accent colors for the built-in habits.
        # This keeps each reminder visually distinct even if old saved reminders
        # were created with different `accent` values.
        rem_text = (reminder.get("text") or "").strip().lower()
        act_hint = (reminder.get("action") or "").strip().lower()
        if (
            ("water" in rem_text)
            or ("hydration" in rem_text)
            or (act_hint == "drink")
        ):
            accent = [0.10, 0.65, 1.00, 1.0]
        elif "posture" in rem_text or (act_hint == "stretch" and "posture" in rem_text):
            accent = [0.20, 0.85, 0.40, 1.0]
        elif act_hint == "walk" or ("short" in rem_text and "break" in rem_text):
            accent = [0.68, 0.45, 1.00, 1.0]
        elif (
            "grateful" in rem_text
            or "gratitude" in rem_text
            or "thank" in rem_text
            or act_hint == "think"
        ):
            accent = [1.00, 0.41, 0.71, 1.0]
        elif act_hint == "stretch" or "stretch" in rem_text or "get up" in rem_text:
            accent = [1.00, 0.82, 0.20, 1.0]
        else:
            accent = reminder.get("accent")
        if isinstance(accent, list) and len(accent) >= 3:
            self.reminder_stick_accent = [
                float(accent[0]),
                float(accent[1]),
                float(accent[2]),
                float(accent[3] if len(accent) > 3 else 1.0),
            ]
        else:
            try:
                cm = _get_ui_config_manager()
                prim = cm.get("default_colors.primary", [0.10, 0.90, 1.00, 1.0])
                if isinstance(prim, list) and len(prim) >= 3:
                    self.reminder_stick_accent = [
                        float(prim[0]),
                        float(prim[1]),
                        float(prim[2]),
                        float(prim[3] if len(prim) > 3 else 1.0),
                    ]
            except (OSError, ValueError, TypeError, AttributeError):
                pass
        title = (reminder.get("text") or "Reminder").strip() or "Reminder"
        friendly_caption = f"Friendly reminder to {title.lower()}" if title else "Friendly reminder"
        self.reminder_title = f"[b]{friendly_caption}[/b]"
        self.reminder_caption = friendly_caption

        desc = (reminder.get("description") or "").strip()
        if desc and title and desc.lower() == title.lower():
            t = title.lower()
            if "drink" in t or "water" in t or "hydration" in t:
                desc = "Stay hydrated!"
            elif "posture" in t:
                desc = "Sit tall and relax your shoulders."
            elif "short break" in t or ("break" in t and "short" in t):
                desc = "Stand up, breathe, and reset."
            elif "grateful" in t or "gratitude" in t or "think about" in t or "thank" in t:
                desc = "Name one thing you're grateful for."
            elif "stretch" in t or "get up" in t or "yoga" in t:
                desc = "Relax your body, move gently."
            else:
                desc = "Take a brief pause and focus on your habit."
        self.reminder_detail = desc if desc else ""
        self.reminder_show = True
        if self._reminder_clear_ev is not None:
            self._reminder_clear_ev.cancel()
        self._reminder_clear_ev = Clock.schedule_once(self._clear_reminder_display, 60.0)

        # Optional audible reminder (respects ui/config.py voice_reminders_enabled).
        try:
            cm = _get_ui_config_manager()
            voice_enabled = bool(cm.get("voice_reminders_enabled", True))
        except Exception:
            voice_enabled = True

        if voice_enabled and self.state == State.WAITING:
            speak_text = friendly_caption
            my_request_id = self.current_request_id

            def _speak():
                wav_file = None
                try:
                    wav_file = self.tts.synthesize(speak_text)
                    self._play_wav_blocking(wav_file, cancel_id=my_request_id)
                except Exception as exc:
                    print(f"  Reminder speech error: {exc}")
                finally:
                    if wav_file:
                        try:
                            os.unlink(wav_file)
                        except OSError:
                            pass
                    # Playback closes mic stream; reopen if we're still waiting for wake word.
                    try:
                        if (not self.manual_terminal_mode) and self.state == State.WAITING:
                            self._open_mic_stream()
                    except Exception:
                        pass

            threading.Thread(target=_speak, daemon=True).start()

    def _clear_reminder_display(self, _dt: float) -> None:
        self.reminder_show = False
        self.reminder_title = ""
        self.reminder_detail = ""
        self.reminder_caption = ""
        self._reminder_clear_ev = None
        rs = self._reminder_return_screen
        self._reminder_return_screen = None
        if rs and rs != "voice":
            app = App.get_running_app()
            sm = getattr(app, "root", None) if app else None
            if sm is not None and hasattr(sm, "has_screen") and sm.has_screen(rs):
                sm.current = rs

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
        base = Path(self.config.assets_path)
        theme = (getattr(self.config, "face_theme", "") or "").strip()
        if theme:
            base = base / theme
        custom = getattr(self.config, "face_images", None) or {}
        if not isinstance(custom, dict):
            custom = {}
        default_names = {
            State.WAITING: "happy.png",
            State.LISTENING: "thinking.png",
            State.THINKING: "thinking.png",
            State.SPEAKING: "happy_eye_glistening.png",
            State.FOLLOW_UP: "happy.png",
        }
        out: dict[State, str] = {}
        for st, default_fn in default_names.items():
            key = st.value
            fn = custom.get(key) or custom.get(st.name) or default_fn
            if not isinstance(fn, str):
                fn = default_fn
            p = base / fn
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
            State.WAITING: ("Say Hey Veedatron when you're ready", UIColors.ACCENT_DIM),
            State.LISTENING: ("Listening — take your time", UIColors.ERROR),
            State.THINKING: ("Thinking it over...", UIColors.PURPLE),
            State.SPEAKING: ("Talking to you...", UIColors.SUCCESS),
            State.FOLLOW_UP: ("Go ahead — follow-up?", UIColors.ORANGE),
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
        return "…"

    def _format_bot_panel(self) -> str:
        if self.bot_response:
            return self.bot_response
        if self.state == State.THINKING:
            dots = "." * (1 + (int(self.animation_frame) // 10) % 3)
            return f"Generating response{dots}"
        return "…"

    def compute_hint_text(self) -> str:
        if self.manual_terminal_mode:
            return "Type at You> in the terminal • Esc to exit"
        if self.state == State.WAITING:
            return "Say Hey Veedatron, or type at You> • Esc to exit"
        if self.state == State.LISTENING:
            return "Speak naturally — I'll listen until you pause"
        if self.state == State.FOLLOW_UP:
            remaining = max(0, self.follow_up_timeout - (time.time() - self.follow_up_start_time))
            return f"Ask another question, or wait {remaining:.0f}s to return to idle"
        return "Esc to exit"

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
        # Wake word should always bring UI back to the face (voice screen),
        # dismissing any reminder overlay that may still be visible.
        if self._reminder_clear_ev is not None:
            self._reminder_clear_ev.cancel()
            self._reminder_clear_ev = None
        self.reminder_show = False
        self.reminder_title = ""
        self.reminder_detail = ""
        self.reminder_caption = ""
        self._reminder_return_screen = None
        app = App.get_running_app()
        sm = getattr(app, "root", None) if app else None
        if sm is not None and hasattr(sm, "has_screen") and sm.has_screen("voice"):
            sm.current = "voice"
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


class VoiceScreen(Screen):
    """Main voice assistant view (wrapped for :class:`ScreenManager`)."""

    def __init__(self, engine: VidatronEngine, **kwargs):
        super().__init__(**kwargs)
        self.add_widget(VidatronRoot(engine=engine))


class VidatronApp(App):
    title = "Vidatron"

    def __init__(self, engine: VidatronEngine, **kwargs):
        super().__init__(**kwargs)
        self.engine = engine
        self._keyboard_cb = None
        self._touch_ud_token: str = "vidatron_swipe"

    def build(self):
        sm = ScreenManager(transition=SlideTransition())
        sm.add_widget(VoiceScreen(name="voice", engine=self.engine))
        ui_dir = Path(__file__).resolve().parent.parent / "ui"
        if str(ui_dir) not in sys.path:
            sys.path.append(str(ui_dir))
        from screens import (  # noqa: WPS433 — loaded after ui/ on path
            SetupColorsScreen,
            SetupFaceScreen,
            RemindersScreen,
        )

        sm.add_widget(SetupFaceScreen(name="setup_face"))
        sm.add_widget(SetupColorsScreen(name="setup_colors"))
        sm.add_widget(RemindersScreen(name="reminders"))
        sm.current = "voice"
        self._screen_manager = sm
        return sm

    def on_start(self):
        Window.clearcolor = (*UIColors.BG[:3], 1)
        eng = self.engine
        try:
            cm = _get_ui_config_manager()
            cm.ensure_default_reminders()
            _voice_seed_interval_last_fired(cm)
        except (OSError, ValueError, TypeError, AttributeError) as e:
            print(f"  Reminder config warmup: {e}")
        self._keyboard_cb = partial(_on_keyboard, eng)
        Window.bind(on_keyboard=self._keyboard_cb)
        Window.bind(on_touch_down=self._on_window_touch_down, on_touch_up=self._on_window_touch_up)
        Clock.schedule_interval(voice_reminder_tick, 1.0)
        # Do not pre-open speaker stream here — it holds plughw open and breaks aplay.
        if not eng.manual_terminal_mode:
            eng._open_mic_stream()
            print(f"  Audio stream started at {eng.mic_sample_rate}Hz")
        else:
            eng.stream = None
            print("  Audio stream disabled (manual terminal mode)")
        eng.start_terminal_prompt_loop()

    def _on_window_touch_down(self, window, touch):
        # touch.profile is a list of capability names (e.g. ['pos', 'button']), not a dict.
        if "button" in touch.profile:
            btn = getattr(touch, "button", None)
            if btn and str(btn).startswith("scroll"):
                return False
        touch.ud[self._touch_ud_token] = (touch.x, touch.y)
        return False

    def _on_window_touch_up(self, window, touch):
        start = touch.ud.pop(self._touch_ud_token, None)
        if start is None:
            return False
        sm = self.root
        if not isinstance(sm, ScreenManager) or sm.current != "voice":
            return False
        dx = touch.x - start[0]
        dy = touch.y - start[1]
        if abs(dx) >= dp(72) and abs(dx) > abs(dy) * 1.25:
            sm.current = "setup_face"
            return False
        return False

    def on_stop(self):
        if self._keyboard_cb is not None:
            Window.unbind(on_keyboard=self._keyboard_cb)
            self._keyboard_cb = None
        Window.unbind(on_touch_down=self._on_window_touch_down, on_touch_up=self._on_window_touch_up)
        Clock.unschedule(voice_reminder_tick)
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
    print("  • Swipe horizontally on the window to customize face, colours & reminders")
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
