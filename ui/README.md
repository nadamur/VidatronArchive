# Vidatron – Personal Robot Assistant

Vidatron is a fully functioning personal robot assistant with an on-device UI, movement system, sensors, and power system. The robot is operational end-to-end; some behaviors and integrations remain open for tweaks and future refinement.

---

## 1. Feature Overview (Increments)

### UI & Display (This Repository – Vidatron UI)

- **First-time setup**
  - Welcome screen with: Go with Default, Customize, or View Settings.
  - Optional wizard: customize robot face (eyes, mouth), font (style and size), and accent/primary color.
  - Setup state is persisted; on later power-on the device boots directly to the homescreen.

- **Homescreen & reminders**
  - Homescreen shows the robot face (or reminder card when a reminder is active), current time, and a bottom bar with accent color.
  - Time-based reminders (e.g. “Every X minutes” or at specific times) with optional default reminders: “Drink water” and “Get up and stretch.”
  - When a reminder triggers, the UI switches to the homescreen and shows the reminder card for 1 minute, then returns to the previous view or default homescreen.

- **Reminder actions & icons**
  - Each reminder can have an **action** (e.g. `drink`, `stretch`) or an optional **icon image**.
  - Kivy-drawn **stick-figure icons** represent the action (e.g. person drinking, person stretching) with the same colored background as the robot face (accent-based), so the card is never plain black.
  - Default reminders use built-in stick-figure icons; custom reminders can use file-based icons or the same action-based icons.

- **Settings & tools**
  - Settings: face customization, font, colors.
  - Reminders list: add, edit, delete, toggle active; set trigger type, interval or time, accent, mood, and optional per-reminder face expression.
  - “Test in 10 seconds” for reminders; keyboard shortcuts (e.g. `h` home, `s` settings, `r` reminders, `d` dismiss, `n` next) for testing without hardware.

- **Persistence**
  - All preferences and reminders are stored in `vidatron_config.json` (deep-merge with defaults so new options don’t overwrite existing data).

### Robot Systems (Movement, Sensors, Power)

- **Movement system**
  - Robot movement has been added and integrated so the platform can move as required by the assistant behavior (e.g. orienting toward the user or moving to a position).

- **Sensors**
  - Sensors are applied and used to support context-aware behavior and interaction (e.g. for reminders or environment awareness).

- **Power system**
  - Power system is implemented so the robot can run on its intended power source and operate reliably during use.

The combination of UI, movement, sensors, and power makes the robot **fully functioning** as a single system, with room for further tweaks and enhancements.

---

## 2. End-to-End Flow (Example)

An example of how the pieces work together:

1. **Power on**
   - Power system supplies the device; UI and robot systems boot.
   - If first-time setup is not complete → user sees the welcome screen and can run the setup wizard (face, font, colors) or go with defaults.
   - If setup is complete → device goes directly to the homescreen with the robot face and reminder count.

2. **Daily use**
   - User sees the homescreen (robot face, time, reminder count). Sensors and movement can be used in the background for context and positioning.
   - When a reminder’s time is reached (e.g. “Drink water” every hour, “Get up and stretch” every 90 minutes), the UI automatically switches to the homescreen and shows the reminder card.

3. **Reminder card**
   - The card shows the **action icon** (stick figure for “drink” or “stretch”) on the same colored background as the robot theme (not black), plus the reminder text and description.
   - User can dismiss the card or wait; after about 1 minute the view returns to the default homescreen (or previous screen). Feedback from interaction can be used for future tweaks (e.g. reminder timing or content).

4. **Customization**
   - From the homescreen, user can open Settings to change face, font, and colors, or open Reminders to add/edit reminders, set intervals or specific times, and assign actions or icon paths.
   - All changes are saved to `vidatron_config.json` and persist across power cycles.

5. **Testing without hardware**
   - On desktop, keyboard shortcuts simulate navigation (e.g. `h` home, `s` settings, `r` reminders, `d` dismiss, `n` next card). Reminders can be tested with “Test in 10 seconds” in the reminder edit screen.

---

## 3. Running the UI (This Repo) & Download / Executable

If you just cloned the repo, follow the steps below to run the UI from source.

### Prerequisites

- **Python 3.8+**
- **pip** (usually included with Python)

### Run from source (after cloning the repo)

From the **Vidatron** repo root, do the following.

**1. Go to the UI project folder**

```bash
cd src/prototypes/updatedui
```

**2. Create a virtual environment**

```bash
python3 -m venv venv
```

**3. Activate the virtual environment**

- **macOS / Linux:** `source venv/bin/activate`
- **Windows:** `venv\Scripts\activate`

**4. Install dependencies**

```bash
pip install -r requirements.txt
```

This installs Kivy 2.x and its dependencies.

**5. Run the application**

- **macOS / Linux:** `./run.sh`  
  (uses the venv automatically if the `venv` folder exists)
- **Windows or if `run.sh` doesn’t work:** with the venv still activated, run  
  `python main.py`

**Summary (copy-paste, macOS/Linux):**

```bash
cd src/prototypes/updatedui
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
./run.sh
```

**Summary (copy-paste, Windows):**

```cmd
cd src\prototypes\updatedui
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

- Default window size is **800×480** (e.g. for a small display or embedded use).
- Config and reminders are stored in `vidatron_config.json` in this directory (created on first run).

### Compiled / executable and host URL

- **Executable / packaged app**  
  To distribute a standalone executable (e.g. for Windows/macOS/Linux or for the robot’s onboard computer), you can use:
  - **Desktop:** [PyInstaller](https://pyinstaller.org/) or [briefcase](https://briefcase.readthedocs.io/) with Kivy.
  - **Mobile/embedded:** [Buildozer](https://buildozer.readthedocs.io/) (Kivy’s tool for Android, etc.).

  *(Replace this bullet with a direct link to your built installer or package once you have one, e.g. “Download the latest build: [link].”)*

- **Host URL (if applicable)**  
  If the UI or any part of Vidatron is later served over the web (e.g. a dashboard or remote control), add the URL here, for example:

  ```text
  Host URL: https://your-vidatron-dashboard.example.com
  ```

  *(Remove this line if you do not have a hosted version.)*

---

## 4. Project structure (UI repo)

| Path               | Purpose |
|--------------------|--------|
| `main.py`          | App entry point, screen manager, first-time vs normal boot, keyboard shortcuts |
| `config.py`        | Config load/save, defaults, default reminders (Drink water, Get up and stretch) |
| `screens.py`       | All screens: Welcome, Setup (face/font/colors), Homescreen, Settings, Reminders, Reminder edit |
| `widgets.py`       | Robot face widget, stick-figure icon widget (action-based icons and colored background) |
| `vidatron_config.json` | Persisted user settings and reminders (created at first run) |
| `assets/icons/`    | Optional icon images for reminders; built-in actions use Kivy-drawn stick figures |
| `ICONS_README.md`  | Icon system and reminder icon behavior |

---

## 5. Status and tweaks

The robot is **fully functioning** with UI, movement, sensors, and power integrated. Ongoing work may include:

- Fine-tuning reminder intervals and content.
- Refining movement and sensor behavior for different environments.
- Power management and battery behavior.
- Adding more reminder actions or icon options in the UI.

---

*Vidatron – Your Personal Robot Assistant*
