# movement/main.py

import random
import time

from movement.movement import (
    backward,
    forward,
    forward_arc_left,
    forward_arc_right,
    gentle_left,
    gentle_right,
    left,
    right,
    stop,
)
from movement.path_memory import mark_blocked, choose_direction
from movement.config import (
    FIRST_MOVE_DELAY_MAX_SEC,
    FIRST_MOVE_DELAY_MIN_SEC,
    IDLE_BETWEEN_MOVES_MAX_SEC,
    IDLE_BETWEEN_MOVES_MIN_SEC,
    MAX_DISTANCE_CM,
    SAFE_DISTANCE_CM,
)
from movement.ultrasonic import drop_detected, get_distance_cm, pause_triggered

# Set to True to enable drop / edge detection in the autonomy loop.
ENABLE_DROP_DETECTOR = False


def _sync_voice_paused(paused: bool) -> None:
    """Expose pause state to voice_commands so the AI only queues moves while paused."""
    try:
        from movement.voice_commands import set_robot_paused

        set_robot_paused(paused)
    except ImportError:
        pass


def _natural_wander_move():
    """Pick a varied maneuver when the path ahead is clear (not straight-only)."""
    r = random.random()
    if r < 0.34:
        forward(duration=random.uniform(0.42, 0.62))
    elif r < 0.52:
        forward_arc_left(duration=random.uniform(0.5, 0.75))
    elif r < 0.70:
        forward_arc_right(duration=random.uniform(0.5, 0.75))
    elif r < 0.84:
        gentle_left()
    elif r < 0.94:
        gentle_right()
    else:
        # Occasional short straight then a nudge (feels like glancing / exploring)
        forward(duration=random.uniform(0.35, 0.5))
        if random.random() < 0.6:
            gentle_left() if random.random() < 0.5 else gentle_right()


def robot_loop():
    try:
        _robot_loop_impl()
    except PermissionError:
        print(
            "⛔ Autonomous mode stopped: motor I2C not accessible. "
            "Fix permissions (see message above), then restart."
        )


def _robot_loop_impl():
    print("🤖 Autonomous robot starting (paused by default)...")
    if not ENABLE_DROP_DETECTOR:
        print("ℹ️ Drop detector disabled (set ENABLE_DROP_DETECTOR = True to enable)")
    stop()
    time.sleep(2)

    paused = True
    _sync_voice_paused(True)
    print("⏸️ PAUSED — waiting for pause sensor toggle to resume")
    pause_latched = False
    next_allowed_move_time = time.time() + random.uniform(
        FIRST_MOVE_DELAY_MIN_SEC, FIRST_MOVE_DELAY_MAX_SEC
    )

    while True:
        # -------- PAUSE SENSOR CHECK --------
        if pause_triggered():
            if not pause_latched:
                paused = not paused
                pause_latched = True

                if paused:
                    print("⏸️ PAUSED — motors stopped")
                    stop()
                else:
                    print("▶️ RESUMED")
                _sync_voice_paused(paused)
        else:
            pause_latched = False

        # -------- IF PAUSED --------
        if paused:
            stop()
            try:
                from movement.voice_commands import wait_motion_command
            except ImportError:
                time.sleep(0.25)
                continue
            cmd = wait_motion_command(0.3)
            if cmd is None:
                continue
            try:
                if cmd in ("left", "right"):
                    burst = 1.0
                    scale = 1.0
                    print(f"🎮 Voice drive: {cmd} ({burst:.1f}s, full turn torque)")
                    if cmd == "left":
                        left(duration=burst, speed_scale=scale)
                    else:
                        right(duration=burst, speed_scale=scale)
                elif cmd in ("spin", "spin_left", "spin_right"):
                    burst = 1.0
                    scale = 0.65
                    print(f"🎮 Voice drive: {cmd} ({burst:.1f}s @ {int(scale * 100)}% throttle)")
                    if cmd == "spin_right":
                        right(duration=burst, speed_scale=scale)
                    else:
                        left(duration=burst, speed_scale=scale)
                elif cmd == "forward":
                    burst = random.uniform(1.0, 2.0)
                    print(f"🎮 Voice drive: {cmd} ({burst:.1f}s)")
                    forward(duration=burst)
                elif cmd == "back":
                    burst = random.uniform(1.0, 2.0)
                    print(f"🎮 Voice drive: {cmd} ({burst:.1f}s)")
                    backward(duration=burst)
            except Exception as e:
                print(f"  Motion error: {e}")
            stop()
            continue

        # -------- DROP DETECTION --------
        if ENABLE_DROP_DETECTOR and drop_detected():
            print("⚠️ DROP DETECTED! Avoiding edge...")

            stop()
            time.sleep(0.1)

            # Mark forward as unsafe (like obstacle)
            mark_blocked("forward")

            # Back up slightly
            backward()
            time.sleep(0.4)
            stop()
            time.sleep(0.1)

            # Choose new direction intelligently
            direction = choose_direction()
            print(f"🧠 New direction after drop: {direction}")

            if direction == "left":
                left()
            elif direction == "right":
                right()
            elif direction == "backward":
                backward()

            time.sleep(0.3)
            stop()
            continue

        # -------- NORMAL AUTONOMY --------
        stop()
        distance = get_distance_cm()

        if distance is None:
            print("⚠️ No distance reading")
            time.sleep(0.2)
            continue

        print(f"📏 Distance ahead: {distance:.1f} cm")

        if distance < MAX_DISTANCE_CM:
            print(f"🚨 Object detected at {distance:.1f} cm")

            if distance <= SAFE_DISTANCE_CM:
                print("🛑 Too close! Emergency avoidance")
                mark_blocked("forward")
                backward()
                # Use same planner as normal avoidance: prefers left before right when
                # forward is blocked, and skips right if path_memory marked it blocked (etc.).
                direction = choose_direction()
                print(f"➡️ Emergency avoidance turn: {direction}")
                if direction == "left":
                    left()
                elif direction == "right":
                    right()
                else:
                    backward()
                continue

            mark_blocked("forward")
            direction = choose_direction()
            print(f"➡️ Choosing direction: {direction}")

            if direction == "left":
                left()
            elif direction == "right":
                right()
            elif direction == "backward":
                backward()

        else:
            print("✅ Path clear")
            if time.time() < next_allowed_move_time:
                # Stay stopped between maneuvers — reads as "paused / looking" not constant crawl
                time.sleep(0.25)
                continue
            _natural_wander_move()
            next_allowed_move_time = time.time() + random.uniform(
                IDLE_BETWEEN_MOVES_MIN_SEC, IDLE_BETWEEN_MOVES_MAX_SEC
            )

        time.sleep(0.3)


if __name__ == "__main__":
    robot_loop()