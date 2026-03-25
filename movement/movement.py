from adafruit_motorkit import MotorKit
import time

from movement.config import MOTION_DEBUG_PRINTS, PWM_FREQUENCY_HZ

_kit = None


def _motion_log(msg: str) -> None:
    if MOTION_DEBUG_PRINTS:
        print(msg)


def _get_kit():
    """Lazily open I2C / MotorKit so importing this module does not require /dev/i2c access."""
    global _kit
    if _kit is None:
        try:
            _kit = MotorKit(pwm_frequency=PWM_FREQUENCY_HZ)
        except PermissionError as e:
            if e.errno == 13 and "i2c" in str(e).lower():
                print(
                    "\nMotor driver: cannot open I2C bus (permission denied).\n"
                    "  sudo usermod -aG i2c $USER\n"
                    "Then log out and log back in (or reboot), and confirm: groups | grep i2c\n"
                )
            raise
    return _kit

SPEED = 0.4
# Below ~0.22–0.25 many DC gearmotors stall on pivot (forward/back still work at full SPEED).
MIN_PIVOT_THROTTLE = 0.26
MOVE_TIME = 0.7
TURN_TIME = 0.45
# Curved forward: inner wheel slower for smooth arcs
ARC_INNER_RATIO = 0.58
# Gentle nudges — shorter than full turns
GENTLE_TURN_TIME = 0.28


def stop():
   k = _get_kit()
   k.motor3.throttle = 0
   k.motor4.throttle = 0
   _motion_log("Stop")


# ---- MOVEMENT FUNCTIONS ----

def forward(duration=0.4):
   """Drive straight forward. If duration is None, uses MOVE_TIME."""
   t = MOVE_TIME if duration is None else duration
   _motion_log("Forward")
   k = _get_kit()
   k.motor3.throttle = SPEED
   k.motor4.throttle = SPEED
   time.sleep(t)
   stop()


def forward_arc_left(duration=0.4):
   """Forward with a gentle left bias (natural arc)."""
   t = MOVE_TIME * 0.85 if duration is None else duration
   _motion_log("Forward arc left")
   k = _get_kit()
   k.motor3.throttle = SPEED * ARC_INNER_RATIO
   k.motor4.throttle = SPEED
   time.sleep(t)
   stop()


def forward_arc_right(duration=0.4):
   """Forward with a gentle right bias (natural arc)."""
   t = MOVE_TIME * 0.85 if duration is None else duration
   _motion_log("Forward arc right")
   k = _get_kit()
   k.motor3.throttle = SPEED
   k.motor4.throttle = SPEED * ARC_INNER_RATIO
   time.sleep(t)
   stop()


def gentle_left():
   """Small heading change without a full pivot."""
   _motion_log("Gentle left")
   k = _get_kit()
   k.motor3.throttle = -SPEED
   k.motor4.throttle = SPEED
   time.sleep(GENTLE_TURN_TIME)
   stop()


def gentle_right():
   """Small heading change without a full pivot."""
   _motion_log("Gentle right")
   k = _get_kit()
   k.motor3.throttle = SPEED
   k.motor4.throttle = -SPEED
   time.sleep(GENTLE_TURN_TIME)
   stop()


def backward(duration=0.4):
   """Drive straight backward. If duration is None, uses MOVE_TIME."""
   t = MOVE_TIME if duration is None else duration
   _motion_log("Backward")
   k = _get_kit()
   k.motor3.throttle = -SPEED
   k.motor4.throttle = -SPEED
   time.sleep(t)
   stop()


def left(duration=0.4, speed_scale: float = 1.0):
   """Pivot left. If duration is None, uses TURN_TIME. speed_scale scales motor throttle (0–1)."""
   t = TURN_TIME if duration is None else duration
   s = max(0.15, min(1.0, float(speed_scale))) * SPEED
   s = max(MIN_PIVOT_THROTTLE, min(SPEED, s))
   _motion_log("Left turn")
   k = _get_kit()
   k.motor3.throttle = -s
   k.motor4.throttle = s
   time.sleep(t)
   stop()


def right(duration=0.4, speed_scale: float = 1.0):
   """Pivot right. If duration is None, uses TURN_TIME. speed_scale scales motor throttle (0–1)."""
   t = TURN_TIME if duration is None else duration
   s = max(0.15, min(1.0, float(speed_scale))) * SPEED
   s = max(MIN_PIVOT_THROTTLE, min(SPEED, s))
   _motion_log("Right turn")
   k = _get_kit()
   k.motor3.throttle = s
   k.motor4.throttle = -s
   time.sleep(t)
   stop()


# def square():
#    print("Starting square motion")
#    for i in range(4):
#        print(f"Side {i+1}")
#        forward()
#        right()
#    print("Square complete")


# # ---- MAIN ----
# print("Motor test starting...")
# time.sleep(1)

# forward()
# forward()
# forward()
# forward()
# forward()
# forward()

# # forward()
# # stop()
# # backward()
# # stop()
# # left()
# # forward()
# # stop()
# # backward()
# # stop()
# # right()
# # forward()


# # #square
# # left()
# # forward()
# # left()
# # forward()
# # left()
# # forward()
# # left()