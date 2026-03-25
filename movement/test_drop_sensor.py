#!/usr/bin/env python3
"""
Continuous drop sensor test logger.

Run:
    python test_drop_sensor.py
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime

from gpiozero import DistanceSensor

from config import DROP_IGNORE_DISTANCE_CM, DROP_IGNORE_DISTANCE_CM_TOLERANCE


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _is_ignored_sentinel(cm: float) -> bool:
    return abs(cm - DROP_IGNORE_DISTANCE_CM) <= DROP_IGNORE_DISTANCE_CM_TOLERANCE


def main() -> None:
    parser = argparse.ArgumentParser(description="Continuously test and log drop sensor readings.")
    parser.add_argument("--trigger", type=int, default=16, help="GPIO trigger pin (default: 16)")
    parser.add_argument("--echo", type=int, default=26, help="GPIO echo pin (default: 26)")
    parser.add_argument("--interval", type=float, default=0.2, help="Seconds between samples (default: 0.2)")
    parser.add_argument(
        "--threshold",
        type=float,
        default=40.0,
        help="Drop threshold in cm (default: 40.0). Above means drop risk.",
    )
    args = parser.parse_args()

    sensor = DistanceSensor(echo=args.echo, trigger=args.trigger)
    print(f"[{_now()}] Drop sensor test started (trigger={args.trigger}, echo={args.echo})")
    print(f"[{_now()}] Ignore sentinel: ~{DROP_IGNORE_DISTANCE_CM}cm (+/-{DROP_IGNORE_DISTANCE_CM_TOLERANCE})")
    print(f"[{_now()}] Threshold: {args.threshold}cm | Interval: {args.interval}s")
    print(f"[{_now()}] Press Ctrl+C to stop.\n")

    try:
        while True:
            try:
                cm = float(sensor.distance * 100.0)
                ignored = _is_ignored_sentinel(cm)
                state = "DROP_RISK" if (cm > args.threshold and not ignored) else "SAFE"
                note = "IGNORED_SENTINEL" if ignored else ""
                print(f"[{_now()}] distance={cm:7.2f} cm | state={state:<9} {note}".rstrip())
            except Exception as exc:
                print(f"[{_now()}] read_error={exc}")
            time.sleep(max(0.01, args.interval))
    except KeyboardInterrupt:
        print(f"\n[{_now()}] Drop sensor test stopped.")


if __name__ == "__main__":
    main()
