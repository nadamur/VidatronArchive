"""
Voice / text drive commands while the robot is paused (see movement.main).

Uses a thread-safe queue consumed only when the movement loop is in paused mode.
"""

from __future__ import annotations

import queue
import re
import threading

_CMD_QUEUE: queue.Queue[str] = queue.Queue(maxsize=16)

# Set by movement.main when pause state changes.
_ROBOT_PAUSED = threading.Event()


def set_robot_paused(paused: bool) -> None:
    """Call from movement loop whenever pause state changes."""
    if paused:
        _ROBOT_PAUSED.set()
    else:
        _ROBOT_PAUSED.clear()
        while True:
            try:
                _CMD_QUEUE.get_nowait()
            except queue.Empty:
                break


def is_robot_paused_for_voice() -> bool:
    return _ROBOT_PAUSED.is_set()


def parse_motion_command(text: str) -> str | None:
    """
    Map user text to left | right | forward | back | spin | spin_left | spin_right, or None.
    """
    t = (text or "").lower()
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return None

    # Spin (check before plain left/right so "spin left" wins over "left")
    if any(p in t for p in ("spin right", "rotate right")):
        return "spin_right"
    if any(p in t for p in ("spin left", "rotate left")):
        return "spin_left"
    if any(
        p in t
        for p in (
            "turn around",
            "spin around",
            "do a spin",
            "do a 360",
            "360 spin",
        )
    ):
        return "spin"
    if re.search(r"\bspin\b", t) or re.search(r"\brotate\b", t) or re.search(r"\bpivot\b", t):
        return "spin"

    if any(p in t for p in ("go left", "turn left", "move left")):
        return "left"
    if any(p in t for p in ("go right", "turn right", "move right")):
        return "right"
    if any(p in t for p in ("go forward", "move forward", "go straight")):
        return "forward"
    if any(
        p in t
        for p in (
            "go back",
            "move back",
            "go backward",
            "move backward",
            "reverse",
        )
    ):
        return "back"

    one_word = {
        "left": "left",
        "right": "right",
        "forward": "forward",
        "back": "back",
        "spin": "spin",
        "rotate": "spin",
        "pivot": "spin",
    }
    if t in one_word:
        return one_word[t]
    return None


def try_enqueue_motion_command(text: str) -> str | None:
    """
    If the robot is paused and text is a drive command, enqueue it.

    Returns a short spoken ack phrase, or None if this is not a drive command
    or the robot is not paused (caller should use normal AI routing).
    """
    if not is_robot_paused_for_voice():
        return None
    cmd = parse_motion_command(text)
    if not cmd:
        return None
    try:
        _CMD_QUEUE.put_nowait(cmd)
    except queue.Full:
        return "Please wait, a move is already in progress."
    return {
        "left": "Moving left.",
        "right": "Moving right.",
        "forward": "Moving forward.",
        "back": "Moving backward.",
        "spin": "Spinning.",
        "spin_left": "Spinning left.",
        "spin_right": "Spinning right.",
    }[cmd]


def wait_motion_command(timeout: float = 0.25) -> str | None:
    """Blocking wait for a drive command (used by movement loop when paused)."""
    try:
        return _CMD_QUEUE.get(timeout=timeout)
    except queue.Empty:
        return None
