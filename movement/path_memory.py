# Directions are relative, since we have one sensor
# This is NOT a map — it is experience-based memory

blocked_directions = {
    "forward": False,
    "left": False,
    "right": False
}

def mark_blocked(direction):
    blocked_directions[direction] = True
    print(f"⚠️ Marked {direction} as blocked")

def clear_direction(direction):
    blocked_directions[direction] = False

def choose_direction():
    # Prefer forward if safe
    if not blocked_directions["forward"]:
        return "forward"

    # Try turning
    if not blocked_directions["left"]:
        return "left"

    if not blocked_directions["right"]:
        return "right"

    # Everything blocked → reset memory
    print("🔄 All directions blocked, resetting memory")
    for d in blocked_directions:
        blocked_directions[d] = False
    return "backward"
