#!/usr/bin/env python3
"""
Test microphone + speaker on Raspberry Pi (ALSA).

SETUP (do once on the Pi)
-------------------------
1. Plug in USB audio and/or TRRS jack devices, then reboot if the OS does not see them.

2. Install ALSA tools if needed:
     sudo apt update && sudo apt install -y alsa-utils

3. List devices:
     aplay -l          # playback (speakers/HDMI/USB DAC)
     arecord -l         # capture (microphones)

   Note card numbers (e.g. card 1) and device numbers (e.g. device 0).

4. Default output (3.5 mm vs HDMI vs USB):
     - Raspberry Pi OS: sudo raspi-config → System Options → Audio
     - Or: wpctl status   (PipeWire)   /   pactl info   (PulseAudio)

5. Volume / mute:
     alsamixer
     (F6 to pick card; unmute with M where needed.)

6. Optional: force a default in ~/.asoundrc, e.g. USB mic as default capture:
     defaults.ctl.card 1
     defaults.pcm.card 1
   (Use your card index from arecord -l / aplay -l.)

RUN THIS TEST
-------------
  python3 scripts/test_audio.py

  Record 3 s from the default mic, then play back through the default speaker:
  python3 scripts/test_audio.py --seconds 3

  If the wrong devices are used, pass ALSA names from `arecord -l` / `aplay -l`:
  python3 scripts/test_audio.py --record-device plughw:1,0 --play-device plughw:1,0

SPEAKER-ONLY QUICK CHECK (no Python)
--------------------------------------
  speaker-test -t wav -c 2
  (Ctrl+C to stop; uses default output.)
"""

from __future__ import annotations

import argparse
import math
import os
import subprocess
import sys
import tempfile


def _run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def main() -> int:
    p = argparse.ArgumentParser(description="Record then play back to test mic + speaker.")
    p.add_argument(
        "--seconds",
        type=float,
        default=3.0,
        help="Recording length; rounded up to whole seconds for arecord (default: 3)",
    )
    p.add_argument(
        "--record-device",
        default="default",
        metavar="ALSA",
        help="ALSA device for recording (default: default). Example: plughw:1,0",
    )
    p.add_argument(
        "--play-device",
        default="default",
        metavar="ALSA",
        help="ALSA device for playback (default: default). Example: plughw:1,0",
    )
    args = p.parse_args()

    for exe in ("arecord", "aplay"):
        if subprocess.run(["which", exe], capture_output=True).returncode != 0:
            print(
                f"Missing `{exe}`. Install: sudo apt install alsa-utils",
                file=sys.stderr,
            )
            return 1

    fd, wav_path = tempfile.mkstemp(suffix=".wav", prefix="audio_test_")
    os.close(fd)

    try:
        # arecord -d only accepts whole seconds on many builds (rejects "3.0")
        duration_sec = max(1, math.ceil(float(args.seconds)))
        print(
            f"\nRecording {duration_sec} s from '{args.record_device}' — speak now.\n",
            flush=True,
        )
        _run(
            [
                "arecord",
                "-D",
                args.record_device,
                "-f",
                "S16_LE",
                "-r",
                "44100",
                "-c",
                "1",
                "-d",
                str(duration_sec),
                wav_path,
            ]
        )
        print(f"\nPlaying back through '{args.play_device}'...\n", flush=True)
        _run(["aplay", "-D", args.play_device, wav_path])
        print("\nDone. If you heard your voice, mic + speaker routing works.\n", flush=True)
    except subprocess.CalledProcessError as e:
        print(f"\nCommand failed (exit {e.returncode}). Check devices with arecord -l / aplay -l.\n", file=sys.stderr)
        return e.returncode or 1
    finally:
        try:
            os.unlink(wav_path)
        except OSError:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
