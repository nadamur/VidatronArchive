"""Allowed face customization values and normalization from legacy config."""

ALLOWED_EYES = frozenset({"Round", "Narrow", "Wide", "Small"})
ALLOWED_MOUTHS = frozenset({"Small", "Wide", "Neutral"})

_LEGACY_EYE = {
    "oval": "Wide",
    "none": "Round",
}
_LEGACY_MOUTH = {
    "curved": "Neutral",
    "smile": "Wide",
    "expressive": "Wide",
    "none": "Neutral",
}


def normalize_eye_choice(value) -> str:
    if value is None:
        return "Round"
    raw = str(value).strip()
    if not raw:
        return "Round"
    low = raw.lower()
    if low in _LEGACY_EYE:
        return _LEGACY_EYE[low]
    t = raw.title()
    if t in ALLOWED_EYES:
        return t
    return "Round"


def normalize_mouth_choice(value) -> str:
    if value is None:
        return "Neutral"
    raw = str(value).strip()
    if not raw:
        return "Neutral"
    low = raw.lower()
    if low in _LEGACY_MOUTH:
        return _LEGACY_MOUTH[low]
    t = raw.title()
    if t in ALLOWED_MOUTHS:
        return t
    return "Neutral"
