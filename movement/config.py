MAX_DISTANCE_CM = 50    # 1 meter radius
SAFE_DISTANCE_CM = 25   # too close = emergency avoidance

# Drop sensor only: ignore ~100 cm readings (common max-range sentinel from gpiozero)
DROP_IGNORE_DISTANCE_CM = 100.0
DROP_IGNORE_DISTANCE_CM_TOLERANCE = 0.35

MOVE_DELAY = 0.3

# Motor HAT (PCA9685) PWM: default library frequency is ~1.6 kHz, which is audible
# (often sounds like a buzz/beep from the motors/driver). Valid range is roughly
# 24 Hz–1526 Hz. Try 400–1000 Hz for a lower, less “beepy” tone, or ~1526 Hz max.
PWM_FREQUENCY_HZ = 800.0

# Set True to print each move (Forward, Stop, …) to the console
MOTION_DEBUG_PRINTS = False

# Natural wander: stay stopped until first move, then pause between maneuvers
FIRST_MOVE_DELAY_MIN_SEC = 2.0
FIRST_MOVE_DELAY_MAX_SEC = 4.5
IDLE_BETWEEN_MOVES_MIN_SEC = 0.35
IDLE_BETWEEN_MOVES_MAX_SEC = 1.4