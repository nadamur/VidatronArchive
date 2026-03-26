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
        """Add default reminders if they haven't been added yet, or update intervals if they exist."""
        reminders = self.config.get("reminders", [])
        
        # Check if default reminders already exist
        drink_water_exists = False
        stretch_exists = False
        for reminder in reminders:
            if reminder.get("text") == "Drink water":
                drink_water_exists = True
                # Update interval to 1 minute for testing
                reminder["interval_minutes"] = 1
            elif reminder.get("text") == "Get up and stretch":
                stretch_exists = True
                # Update interval to 2 minutes for testing
                reminder["interval_minutes"] = 2
        
        # Add missing default reminders
        default_reminders = []
        if not drink_water_exists:
            default_reminders.append({
                "id": str(uuid.uuid4()),
                "text": "Drink water",
                "action": "drink",  # Kivy-drawn stick figure (no image file needed)
                "icon": None,
                "icon_path": "assets/icons/drink_water.png",  # Optional fallback if file exists
                "face_expression": None,
                "trigger_type": "Every X Minutes",
                "trigger_time": None,
                "interval_minutes": 1,  # Every 1 minute (for testing)
                "repeat_settings": "daily",
                "is_active": True,
                "accent": [0.10, 0.90, 1.00, 1.0],  # Blue
                "mood": "happy",
                "description": "Stay hydrated!"
            })
        if not stretch_exists:
            default_reminders.append({
                "id": str(uuid.uuid4()),
                "text": "Get up and stretch",
                "action": "stretch",  # Kivy-drawn stick figure (no image file needed)
                "icon": None,
                "icon_path": "assets/icons/stretch.png",  # Optional fallback if file exists
                "face_expression": None,
                "trigger_type": "Every X Minutes",
                "trigger_time": None,
                "interval_minutes": 2,  # Every 2 minutes (for testing)
                "repeat_settings": "daily",
                "is_active": True,
                "accent": [0.15, 1.00, 0.55, 1.0],  # Green
                "mood": "calm",
                "description": "Take a break and move around"
            })
        
        if default_reminders:
            reminders.extend(default_reminders)
            self.config["reminders"] = reminders
            self.config["default_reminders_added"] = True
            self.save_config()
        elif drink_water_exists or stretch_exists:
            # Updated existing reminders - save the changes
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
