#!/usr/bin/env python3
"""
Read each ultrasonic once and report which (if any) raises DistanceSensorNoEcho.

Stop any other process using these GPIOs first (e.g. quit the main robot app).

Run from repo root:
  python3 -m movement.diagnose_ultrasonic
"""

from __future__ import annotations

import warnings

# Uses the same sensor objects and pins as movement/ultrasonic.py
from movement.ultrasonic import drop_sensor, front_sensor, pause_sensor


def _read_named(name: str, sensor) -> None:
    print(f"\n--- {name} ---")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        d = sensor.distance
        cm = d * 100.0
    if caught:
        for w in caught:
            print(f"  WARNING: {w.message!s}")
        print(f"  Last distance read ≈ {cm:.1f} cm (may be unreliable)")
    else:
        print(f"  OK — distance ≈ {cm:.1f} cm")


def main() -> None:
    print(
        "Testing pause → front → drop. The section whose read shows WARNING is the problem sensor.\n"
        "Pins: pause echo=12 trigger=25 | front echo=24 trigger=23 | drop echo=26 trigger=16\n"
    )
    _read_named("pause / resume (echo=12, trigger=25)", pause_sensor)
    _read_named("front obstacle (echo=24, trigger=23)", front_sensor)
    _read_named("drop / edge (echo=26, trigger=16)", drop_sensor)
    print("\nDone.")


if __name__ == "__main__":
    main()
