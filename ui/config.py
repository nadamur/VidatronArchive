"""
Configuration Management
=======================
Handles saving and loading application configuration.
"""

import json
import os
import sys
import types
import uuid


def get_config_path():
    """
    Get absolute path to configuration file.
    Uses vidatron_config.json in the project directory.
    """
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, "vidatron_config.json")


CONFIG_FILE = get_config_path()


def deep_merge(default, loaded):
    """
    Deep merge two dictionaries, preserving nested structure.
    Values from 'loaded' override 'default', but missing nested keys are preserved.
    """
    result = default.copy()
    for key, value in loaded.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class ConfigManager:
    """
    Manages application configuration persistence.
    Handles saving and loading user preferences, setup state, and reminders.
    """
    
    def __init__(self):
        """Initialize the config manager and load existing configuration."""
        self.config = self.load_config()
    
    def load_config(self):
        """
        Load configuration from JSON file with deep merging.
        Returns default configuration if file doesn't exist.
        """
        default_config = {
            "first_time_setup_complete": False,
            "face_customization": {
                "selected_eyes": None,      # nullable - can be None or a string identifier
                "selected_mouth": None       # nullable - can be None or a string identifier
            },
            "font_settings": {
                "style": "Roboto",           # default font style
                "size": 30                   # default font size in sp
            },
            "default_colors": {
                "primary": [0.10, 0.90, 1.00, 1.0],    # default accent color
                "background": [0.02, 0.02, 0.04, 1.0]   # default background color
            },
            "voice_reminders_enabled": True,        # audibly speak reminders on trigger
            "reminders": [],                 # list of reminder objects
            "last_fired": {},                # reminder_id -> "YYYY-MM-DD HH:MM" for trigger tracking
            "default_reminders_added": False  # track if default reminders have been added
        }
        
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    loaded = json.load(f)
                    # Deep merge to preserve nested defaults
                    merged = deep_merge(default_config, loaded)
                    # Ensure None values are preserved (JSON null becomes None in Python)
                    # Convert string "None" to actual None if it exists
                    if isinstance(merged.get("face_customization", {}).get("selected_eyes"), str):
                        if merged["face_customization"]["selected_eyes"] == "None":
                            merged["face_customization"]["selected_eyes"] = None
                    if isinstance(merged.get("face_customization", {}).get("selected_mouth"), str):
                        if merged["face_customization"]["selected_mouth"] == "None":
                            merged["face_customization"]["selected_mouth"] = None
                    return merged
            except Exception as e:
                print(f"Error loading config: {e}")
                return default_config
        return default_config
    
    def save_config(self):
        """Save current configuration to JSON file."""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def get(self, key, default=None):
        """Get a configuration value by key path (supports nested keys)."""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def set(self, key, value):
        """Set a configuration value by key path (supports nested keys)."""
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        self.save_config()
    
    def ensure_default_reminders(self):
        """
        Seed missing built-in reminders without clobbering user settings.

        What we do:
        - If a built-in reminder is missing, add it with default wording.
        - If a built-in reminder exists, only migrate wording/action/icon fields.
          We DO NOT overwrite interval minutes / trigger time / active state, so
          user changes persist across restarts.
        """
        reminders = self.config.get("reminders", [])
        if not isinstance(reminders, list):
            reminders = []
        # Only seed missing built-ins once. After first-time setup, user deletions
        # should persist across restarts (do not recreate deleted reminders).
        allow_add_missing = not bool(self.config.get("default_reminders_added", False))

        def _norm(s):
            return (s or "").strip().lower()

        def _is_drink(r):
            t = _norm(r.get("text"))
            a = _norm(r.get("action"))
            ip = _norm(r.get("icon_path"))
            return (
                a == "drink"
                or "drink" in t
                or "water" in t
                or "hydration" in t
                or ip.endswith("drink_water.png")
            )

        def _is_stretch(r):
            t = _norm(r.get("text"))
            a = _norm(r.get("action"))
            ip = _norm(r.get("icon_path"))
            return (
                (a == "stretch" and ip.endswith("stretch.png"))
                or "stretch" in t
                or "get up" in t
                or "yoga" in t
            )

        def _is_posture(r):
            t = _norm(r.get("text"))
            a = _norm(r.get("action"))
            ip = _norm(r.get("icon_path"))
            return (a == "stretch" and (not ip or ip in ("none", "")) and "posture" in t)

        def _is_short_break(r):
            t = _norm(r.get("text"))
            a = _norm(r.get("action"))
            return a == "walk" or ("short" in t and "break" in t)

        def _is_gratitude(r):
            t = _norm(r.get("text"))
            a = _norm(r.get("action"))
            return a == "think" or "grateful" in t or "gratitude" in t or "thank" in t

        # Target wording (fix punctuation/spelling)
        drink_default = {
            "text": "Drink water",
            "action": "drink",
            "icon": None,
            "icon_path": "assets/icons/drink_water.png",
            "face_expression": None,
            "trigger_type": "Every X Minutes",
            "trigger_time": None,
            "interval_minutes": 5,
            "repeat_settings": "daily",
            "is_active": True,
            "accent": [0.10, 0.65, 1.00, 1.0],
            "mood": "happy",
            "description": "Stay hydrated!",
        }

        stretch_default = {
            "text": "Get up and stretch",
            "action": "stretch",
            "icon": None,
            "icon_path": "assets/icons/stretch.png",
            "face_expression": None,
            "trigger_type": "Every X Minutes",
            "trigger_time": None,
            "interval_minutes": 10,
            "repeat_settings": "daily",
            "is_active": True,
            "accent": [1.00, 0.82, 0.20, 1.0],
            "mood": "calm",
            "description": "Take a break and move around.",
        }

        posture_default = {
            "text": "Fix your posture",
            "action": "stretch",
            "icon": None,
            "icon_path": None,
            "face_expression": None,
            "trigger_type": "Every X Minutes",
            "trigger_time": None,
            "interval_minutes": 15,
            "repeat_settings": "daily",
            "is_active": True,
            "accent": [0.20, 0.85, 0.40, 1.0],
            "mood": "calm",
            "description": "Sit tall and relax your shoulders.",
        }

        short_break_default = {
            "text": "Take a short break",
            "action": "walk",
            "icon": None,
            "icon_path": None,
            "face_expression": None,
            "trigger_type": "Every X Minutes",
            "trigger_time": None,
            "interval_minutes": 20,
            "repeat_settings": "daily",
            "is_active": True,
            "accent": [0.68, 0.45, 1.00, 1.0],
            "mood": "happy",
            "description": "Stand up, breathe, and reset.",
        }

        gratitude_default = {
            "text": "Think about something you're grateful for",
            "action": "think",
            "icon": None,
            "icon_path": None,
            "face_expression": None,
            "trigger_type": "Every X Minutes",
            "trigger_time": None,
            "interval_minutes": 30,
            "repeat_settings": "daily",
            "is_active": True,
            "accent": [1.00, 0.41, 0.71, 1.0],
            "mood": "happy",
            "description": "Name one thing you're grateful for.",
        }

        # Track which built-ins exist.
        found = {
            "drink": False,
            "stretch": False,
            "posture": False,
            "short_break": False,
            "gratitude": False,
        }

        def _migrate_existing(existing: dict, target: dict) -> bool:
            """Migrate wording/action/icon fields. Returns True if anything changed."""
            changed = False
            for k in (
                "text",
                "action",
                "icon",
                "icon_path",
                "mood",
                "accent",
                "description",
                "face_expression",
            ):
                if existing.get(k) != target.get(k):
                    existing[k] = target.get(k)
                    changed = True
            return changed

        changed_any = False
        for r in reminders:
            if not isinstance(r, dict):
                continue

            if _is_drink(r) and not found["drink"]:
                found["drink"] = True
                changed_any = _migrate_existing(r, drink_default) or changed_any
            elif _is_posture(r) and not found["posture"]:
                found["posture"] = True
                changed_any = _migrate_existing(r, posture_default) or changed_any
            elif _is_short_break(r) and not found["short_break"]:
                found["short_break"] = True
                changed_any = _migrate_existing(r, short_break_default) or changed_any
            elif _is_gratitude(r) and not found["gratitude"]:
                found["gratitude"] = True
                changed_any = _migrate_existing(r, gratitude_default) or changed_any
            elif _is_stretch(r) and not found["stretch"]:
                found["stretch"] = True
                changed_any = _migrate_existing(r, stretch_default) or changed_any

        # Add any missing built-ins (first-time setup only).
        default_reminders = []
        if allow_add_missing and not found["drink"]:
            default_reminders.append({"id": str(uuid.uuid4()), **drink_default})
        if allow_add_missing and not found["stretch"]:
            default_reminders.append({"id": str(uuid.uuid4()), **stretch_default})
        if allow_add_missing and not found["posture"]:
            default_reminders.append({"id": str(uuid.uuid4()), **posture_default})
        if allow_add_missing and not found["short_break"]:
            default_reminders.append({"id": str(uuid.uuid4()), **short_break_default})
        if allow_add_missing and not found["gratitude"]:
            default_reminders.append({"id": str(uuid.uuid4()), **gratitude_default})

        if default_reminders:
            reminders.extend(default_reminders)
            self.config["reminders"] = reminders
            self.config["default_reminders_added"] = True
            self.save_config()
            return

        if changed_any:
            self.config["reminders"] = reminders
            self.save_config()


def _process_wide_config_manager():
    """
    Single ConfigManager for the whole process.

    This module is often loaded twice (importlib + different fake module names from
    ``screens.py`` and ``ai/test_ui.py``). A plain ``config_manager = ConfigManager()``
    would create two instances: UI saves would update one while the voice screen's
    ``_refresh_ui`` would keep overwriting face/theme from a stale copy.
    """
    key = "vidatron._shared_config_manager"
    mod = sys.modules.get(key)
    if mod is None:
        mod = types.ModuleType(key)
        mod.config_manager = ConfigManager()
        sys.modules[key] = mod
    return mod.config_manager


config_manager = _process_wide_config_manager()
