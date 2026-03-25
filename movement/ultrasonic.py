from gpiozero import DistanceSensor
import time

from movement.config import DROP_IGNORE_DISTANCE_CM, DROP_IGNORE_DISTANCE_CM_TOLERANCE


def _drop_ignores_reading_cm(cm: float) -> bool:
    """Drop sensor only: skip ~100 cm (max-range sentinel)."""
    return abs(cm - DROP_IGNORE_DISTANCE_CM) <= DROP_IGNORE_DISTANCE_CM_TOLERANCE


# pause / resume sensor
pause_sensor = DistanceSensor(echo=12, trigger=25)

# object detection sensor
front_sensor = DistanceSensor(echo=24, trigger=23)

# drop detecion sensor
drop_sensor = DistanceSensor(echo=26, trigger=16)

def get_distance_cm(samples=3):
    readings = []
    for _ in range(samples):
        d = front_sensor.distance * 100
        if d > 0:
            readings.append(d)
        time.sleep(0.05)

    if not readings:
        return None

    return sum(readings) / len(readings)

def pause_triggered(threshold_cm=20):
    d = pause_sensor.distance * 100
    if d > 0 and d <= threshold_cm:
        return True
    return False

def drop_detected(threshold_cm=40, samples=3):
    readings = []

    for _ in range(samples):
        d = drop_sensor.distance * 100
        print(f"Drop sensor distance: {d} cm")
        if d > 0 and not _drop_ignores_reading_cm(d):
            readings.append(d)
        time.sleep(0.02)

    if not readings:
        return False

    avg = sum(readings) / len(readings)
    return avg > threshold_cm
    return True