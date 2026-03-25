"""
Guaranteed WAV playback: serialized, subprocess-only, optional ffmpeg normalize.

Designed so the main process never opens PortAudio for output; mic can be fully
closed before play to avoid ALSA conflicts on USB combo devices.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import wave
from math import gcd
from typing import Callable

import numpy as np
from scipy import signal as scipy_signal

# Serialize all playback — avoids overlap and USB/ALSA races.
_PLAYBACK_SERIAL = threading.Lock()

TARGET_RATE = 48000


def _aplay_cmd(path: str, device: str | None = None) -> list[str]:
    """Larger buffer (-B) reduces USB gadget underrun pops/crackle after speech."""
    buf = os.environ.get("VIDATRON_APLAY_BUFFER_US", "2000000").strip()
    cmd = ["aplay", "-q"]
    if buf and buf != "0":
        cmd.extend(["-B", buf])
    if device is not None:
        cmd.extend(["-D", device])
    cmd.append(path)
    return cmd


def _usb_hw_from_aplay() -> str | None:
    try:
        r = subprocess.run(
            ["aplay", "-l"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        if r.returncode != 0:
            return None
        for line in r.stdout.splitlines():
            if "UACDemo" not in line:
                continue
            m = re.search(r"card (\d+):.*device (\d+):", line)
            if m:
                return f"{m.group(1)},{m.group(2)}"
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def normalize_wav_for_speaker(src: str) -> tuple[str, bool]:
    """
    Return (path, is_temp). Prefer ffmpeg; else scipy resample to 48 kHz mono S16 WAV.
    """
    if shutil.which("ffmpeg"):
        fd, dst = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        r = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-i",
                src,
                "-af",
                "apad=pad_dur=0.15",
                "-vn",
                "-ac",
                "1",
                "-ar",
                str(TARGET_RATE),
                "-c:a",
                "pcm_s16le",
                "-f",
                "wav",
                dst,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if r.returncode == 0 and os.path.getsize(dst) > 100:
            return dst, True
        try:
            os.unlink(dst)
        except OSError:
            pass

    try:
        with wave.open(src, "rb") as wf:
            nch = wf.getnchannels()
            sw = wf.getsampwidth()
            sr = wf.getframerate()
            nframes = wf.getnframes()
            raw = wf.readframes(nframes)
        if sw != 2:
            return src, False
        data = np.frombuffer(raw, dtype=np.int16).astype(np.float64)
        if nch > 1:
            data = data.reshape(-1, nch).mean(axis=1)
        if sr != TARGET_RATE:
            g = gcd(int(sr), TARGET_RATE)
            up = TARGET_RATE // g
            down = int(sr) // g
            data = scipy_signal.resample_poly(data.astype(np.float32), up, down)
            data = np.clip(data, -32768, 32767).astype(np.int16)
        else:
            data = np.clip(data, -32768, 32767).astype(np.int16)
        fd, dst = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        with wave.open(dst, "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(TARGET_RATE)
            out.writeframes(data.tobytes())
        return dst, True
    except Exception as e:
        print(f"  WAV normalize fallback failed ({e}); using original file.")
        return src, False


def _build_command_list(path: str, plughw_hint: str | None) -> list[list[str]]:
    seen: set[tuple[str, ...]] = set()
    out: list[list[str]] = []

    def add(cmd: list[str]) -> None:
        t = tuple(cmd)
        if t not in seen:
            seen.add(t)
            out.append(cmd)

    # User override first (so pulse/default does not steal the device).
    env_alsa = os.environ.get("VIDATRON_SPEAKER_ALSA", "").strip()
    if env_alsa:
        add(_aplay_cmd(path, device=env_alsa))
    # Prefer aplay to Pulse/default before paplay: on some Pi/ALSA setups paplay
    # exits 0 while audio is truncated or routed to the wrong sink.
    skip_paplay = os.environ.get("VIDATRON_SKIP_PAPLAY", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    for dev in ("pulse", "default", "sysdefault"):
        add(_aplay_cmd(path, device=dev))
    if not skip_paplay and shutil.which("paplay"):
        add(["paplay", path])
    if plughw_hint:
        add(_aplay_cmd(path, device=plughw_hint))
    hw = _usb_hw_from_aplay()
    if hw:
        add(_aplay_cmd(path, device=f"plughw:{hw}"))
    add(_aplay_cmd(path))
    return out


class SubprocessWavPlayer:
    """Subprocess-only playback; single global lock; optional normalize step."""

    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()

    def stop(self) -> None:
        with self._lock:
            p = self._proc
            self._proc = None
        if p is None:
            return
        if p.poll() is None:
            try:
                p.terminate()
                p.wait(timeout=2.0)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass

    def play(
        self,
        path: str,
        *,
        plughw_hint: str | None = None,
        cancel_check: Callable[[], bool] | None = None,
        normalize: bool = True,
    ) -> bool:
        """
        Slow path: normalize WAV, then try paplay/aplay under a process-wide lock.
        """
        self.stop()
        with _PLAYBACK_SERIAL:
            time.sleep(0.08)
            play_path = path
            tmp_norm: str | None = None
            if normalize:
                play_path, is_tmp = normalize_wav_for_speaker(path)
                if is_tmp:
                    tmp_norm = play_path
            cmds = _build_command_list(play_path, plughw_hint)
            child_env = os.environ.copy()
            child_env.pop("DISPLAY", None)
            last_err = ""
            try:
                for cmd in cmds:
                    binname = cmd[0]
                    if shutil.which(binname) is None and binname != "aplay":
                        continue
                    try:
                        # No cancel: block until the player exits (full clip, no poll races).
                        if cancel_check is None:
                            with self._lock:
                                self._proc = None
                            r = subprocess.run(
                                cmd,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                env=child_env,
                                timeout=7200,
                            )
                            if r.returncode == 0:
                                time.sleep(0.05)
                                return True
                            last_err = f"exit {r.returncode} cmd={' '.join(cmd)}"
                            continue
                        # stderr=DEVNULL: PIPE can fill on long clips and deadlock aplay.
                        with self._lock:
                            self._proc = subprocess.Popen(
                                cmd,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                env=child_env,
                            )
                            proc = self._proc
                        while proc.poll() is None:
                            if cancel_check and cancel_check():
                                self.stop()
                                return False
                            time.sleep(0.04)
                        rc = proc.returncode or 0
                        with self._lock:
                            if self._proc is proc:
                                self._proc = None
                        if rc == 0:
                            time.sleep(0.05)
                            return True
                        last_err = f"exit {rc} cmd={' '.join(cmd)}"
                    except FileNotFoundError:
                        continue
                if last_err:
                    print(f"  All playback routes failed. Last stderr: {last_err[:350]}")
                else:
                    print("  All playback routes failed (paplay/aplay missing or unusable).")
                return False
            finally:
                if tmp_norm and os.path.isfile(tmp_norm):
                    try:
                        os.unlink(tmp_norm)
                    except OSError:
                        pass
