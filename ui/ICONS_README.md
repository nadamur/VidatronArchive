# Icon System Implementation

## Summary

Added icon support for reminders with default reminders ("Drink water" and "Get up and stretch") that users can toggle active/inactive.

## Files Changed

### 1. `config.py`
- Added `uuid` import
- Added `default_reminders_added` flag to track if defaults have been initialized
- Added `ensure_default_reminders()` method that creates two default reminders:
  - **"Drink water"** - triggers every 60 minutes (hourly)
  - **"Get up and stretch"** - triggers every 90 minutes
- Both reminders are **active by default** and can be toggled on/off by the user

### 2. `screens.py`
- Added `Image` widget import from `kivy.uix.image`
- Added `os` import for path handling
- **Homescreen (`apply_card` method):**
  - Added `icon_image` widget to display reminder icons
  - Icon displays above the reminder text when a reminder is triggered
  - Gracefully handles missing icon files (falls back to text-only display)
  - Icon is hidden in default view (`show_default_view`)
- **ReminderEditScreen:**
  - Replaced simple text icon input with dropdown + custom path input
  - Dropdown options: "None", "Drink Water", "Stretch", "Custom Path"
  - When "Custom Path" selected, user can enter any icon file path
  - Updated `setup_for_new()` and `setup_for_edit()` to handle icon_path
  - Updated `save()` to save `icon_path` field (relative paths preferred)
- **Default reminders initialization:**
  - Called `config_manager.ensure_default_reminders()` when Homescreen initializes
  - Default reminders are only added once (tracked by `default_reminders_added` flag)

### 3. `assets/icons/` directory
- Created directory structure: `assets/icons/`
- Added `README.md` with instructions for icon placement
- Expected icon files:
  - `drink_water.png` - Icon for "Drink water" reminder
  - `stretch.png` - Icon for "Get up and stretch" reminder

## Icon File Placement

Place icon image files in: **`assets/icons/`**

### Required Default Icons
- `assets/icons/drink_water.png` - Person drinking water (128x128 to 256x256 recommended)
- `assets/icons/stretch.png` - Person stretching (128x128 to 256x256 recommended)

### Custom Icons
You can add any custom icon files and reference them using:
- Relative path: `assets/icons/your_icon.png`
- Absolute path: `/full/path/to/icon.png` (less portable)

## Data Structure

Each reminder now has:
- `icon` (nullable) - Text icon for backward compatibility
- `icon_path` (nullable) - Path to image file (relative paths preferred, e.g., `"assets/icons/drink_water.png"`)

## Behavior

1. **Default Reminders:**
   - Added automatically when app first runs (or when Homescreen loads if not already added)
   - Both are **active by default** (`is_active: true`)
   - Users can toggle them on/off in the Reminders list screen
   - Users can edit them like any other reminder

2. **Icon Display:**
   - When a reminder triggers, if `icon_path` exists and file is found → Image widget displays the icon
   - If icon file missing → Falls back to text icon (or no icon)
   - Icon appears centered above the reminder text on the homescreen
   - Icon is hidden when showing default view (reminder count)

3. **Icon Selection:**
   - In Reminder Edit screen, users can:
     - Select "None" (no icon)
     - Select "Drink Water" or "Stretch" (predefined icons)
     - Select "Custom Path" and enter any icon file path

## Fallback Behavior

- If icon file doesn't exist → No crash, icon image hidden, text-only reminder shown
- If icon file is corrupted → Exception caught, icon hidden, text-only reminder shown
- Backward compatible: Reminders without `icon_path` still work (use text `icon` field or no icon)
