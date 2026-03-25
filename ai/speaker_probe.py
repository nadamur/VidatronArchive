#!/usr/bin/env python3
"""
Isolate the speaker path from Vidatron (no Kivy, no mic, no wake word, no cancel).

Generates a ~4 s test tone WAV, plays it via the same SubprocessWavPlayer used by
the UI. If this sounds complete, the hardware/ALSA chain is fine and cutoffs in
the app are likely logic (e.g. request-id cancellation), not the speaker.

Usage (from ai/ or with PYTHONPATH):
  python speaker_probe.py
  VIDATRON_SPEAKER_ALSA=plughw:1,0 python speaker_probe.py
"""

from __future__ import annotations

import importlib.util
import math
import os
import struct
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# Load subprocess_playback without importing audio/__init__.py (avoids sounddevice, etc.).
_sp = ROOT / "audio" / "subprocess_playback.py"
_spec = importlib.util.spec_from_file_location("vidatron_subprocess_playback", _sp)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
SubprocessWavPlayer = _mod.SubprocessWavPlayer


def _write_tone_wav(path: str, duration_s: float = 4.0, sr: int = 48000) -> int:
    """Return frame count. Stereo-safe: mono int16."""
    n = int(sr * duration_s)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        for i in range(n):
            t = i / sr
            # Two beeps + quiet tail so clipping is obvious if truncated
            s = 0.2 * math.sin(2 * math.pi * 440 * t)
            s += 0.15 * math.sin(2 * math.pi * 880 * t)
            if t > 2.0:
                s *= max(0.0, 1.0 - (t - 2.0) / 2.0)
            v = int(max(-32768, min(32767, s * 28000)))
            w.writeframes(struct.pack("<h", v))
    return n


def main() -> int:
    fd, wav = tempfile.mkstemp(suffix="_probe.wav")
    os.close(fd)
    try:
        frames = _write_tone_wav(wav, duration_s=4.0, sr=48000)
        dur = frames / 48000.0
        size = os.path.getsize(wav)
        print(f"Wrote {wav}")
        print(f"  Duration ~{dur:.2f}s, {size} bytes, 48 kHz mono S16")
        hint = os.environ.get("VIDATRON_SPEAKER_ALSA", "").strip() or None
        print("  Playing (no cancel, normalize=off)...")
        player = SubprocessWavPlayer()
        ok = player.play(wav, plughw_hint=hint, cancel_check=None, normalize=False)
        print(f"  Result: {'OK' if ok else 'FAILED'}")
        return 0 if ok else 1
    finally:
        try:
            os.unlink(wav)
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
