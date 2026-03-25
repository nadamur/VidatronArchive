#!/usr/bin/env python3
"""
Run each HC-SR04 until a *change* is detected, logging every sample.

**Change detection (default):** After collecting a few valid readings, the baseline is
their median. Sampling stops when a valid reading differs from that baseline by at
least CHANGE_THRESHOLD_CM (e.g. move a hand / obstacle).

Uses partial=True and queue_len=1 so reads return quickly.

Stop other programs that use these GPIOs first (e.g. the Vidatron app).

From repo root:
  python3 movement/test_ultrasonic_sensors.py

With the project venv:
  ./movement/venv/bin/python3 movement/test_ultrasonic_sensors.py
"""

from __future__ import annotations

import time
import warnings
from datetime import datetime

from gpiozero import DistanceSensor
from gpiozero.exc import DistanceSensorNoEcho

# Same pins as movement/ultrasonic.py
SENSORS: list[tuple[str, int, int]] = [
    ("pause / resume", 12, 25),
    ("front obstacle", 24, 23),
    ("drop / edge", 26, 16),
]

# --- tuning ---
DELAY_BETWEEN_READS_SEC = 0.08

# Valid readings used to compute baseline median (scene before you move)
BASELINE_VALID_SAMPLES = 5

# Stop when |reading - baseline| >= this (cm) on a valid echo
CHANGE_THRESHOLD_CM = 8.0

# Safety cap so a noisy/stuck sensor cannot loop forever
MAX_SECONDS_PER_SENSOR = 180.0
MAX_TOTAL_READS_PER_SENSOR = 5000


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="milliseconds")


def _median(values: list[float]) -> float:
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


def _read_cm(sensor: DistanceSensor) -> tuple[float, bool]:
    """Return (cm, echo_failed)."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        d = sensor.distance
        cm = d * 100.0
    echo_failed = any(
        isinstance(w.category, type) and issubclass(w.category, DistanceSensorNoEcho)
        for w in caught
    )
    return cm, echo_failed


def test_one_until_change(name: str, echo: int, trigger: int) -> None:
    print("\n" + "=" * 60)
    print(f"{name}")
    print(f"  echo=GPIO{echo}  trigger=GPIO{trigger}")
    print(
        f"  Logging until a valid reading differs from baseline by ≥ {CHANGE_THRESHOLD_CM} cm "
        f"(baseline = median of first {BASELINE_VALID_SAMPLES} valid samples)."
    )
    print(f"  Safety: max {MAX_SECONDS_PER_SENSOR:.0f} s or {MAX_TOTAL_READS_PER_SENSOR} reads.")
    print("=" * 60)

    sensor = DistanceSensor(
        echo=echo,
        trigger=trigger,
        queue_len=1,
        partial=True,
    )
    t0 = time.monotonic()
    baseline_vals: list[float] = []
    baseline: float | None = None
    last_valid: float | None = None
    total_reads = 0
    valid_count = 0

    try:
        time.sleep(0.05)
        while True:
            if time.monotonic() - t0 > MAX_SECONDS_PER_SENSOR:
                print(f"  {_now_iso()}  STOP (timeout {MAX_SECONDS_PER_SENSOR:.0f}s)")
                break
            if total_reads >= MAX_TOTAL_READS_PER_SENSOR:
                print(f"  {_now_iso()}  STOP (max reads {MAX_TOTAL_READS_PER_SENSOR})")
                break

            total_reads += 1
            cm, echo_failed = _read_cm(sensor)

            if echo_failed:
                print(
                    f"  {_now_iso()}  #{total_reads}  no-echo  (reported {cm:.1f} cm)",
                    flush=True,
                )
                time.sleep(DELAY_BETWEEN_READS_SEC)
                continue

            valid_count += 1
            delta_prev = (
                f"{cm - last_valid:+.1f} vs last"
                if last_valid is not None
                else "—"
            )
            delta_base = (
                f"{cm - baseline:+.1f} vs baseline"
                if baseline is not None
                else "—"
            )

            print(
                f"  {_now_iso()}  #{total_reads}  valid  {cm:6.1f} cm  "
                f"{delta_prev:>18}  {delta_base:>22}",
                flush=True,
            )

            if baseline is None:
                baseline_vals.append(cm)
                if len(baseline_vals) >= BASELINE_VALID_SAMPLES:
                    baseline = _median(baseline_vals)
                    print(
                        f"  {_now_iso()}  --- baseline set to {baseline:.1f} cm "
                        f"(from {BASELINE_VALID_SAMPLES} samples) — move obstacle / hand to test ---",
                        flush=True,
                    )
            else:
                if abs(cm - baseline) >= CHANGE_THRESHOLD_CM:
                    print(
                        f"  {_now_iso()}  >>> CHANGE DETECTED: |{cm:.1f} - {baseline:.1f}| = "
                        f"{abs(cm - baseline):.1f} cm ≥ {CHANGE_THRESHOLD_CM} cm",
                        flush=True,
                    )
                    break

            last_valid = cm
            time.sleep(DELAY_BETWEEN_READS_SEC)

    finally:
        sensor.close()
        print(f"  {_now_iso()}  (sensor closed)  valid_echo_samples={valid_count}")


def main() -> None:
    print(
        "Each sensor runs until a change from baseline or safety limit.\n"
        "If you see GPIO busy, stop the main robot/UI first.\n"
    )
    for name, echo, trigger in SENSORS:
        test_one_until_change(name, echo, trigger)
    print("\nFinished all sensors.")


if __name__ == "__main__":
    main()
