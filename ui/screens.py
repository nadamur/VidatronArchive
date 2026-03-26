"""
Screens
=======
All screen classes for the Vidatron application.
"""

import uuid
from datetime import datetime
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.uix.screenmanager import Screen
from kivy.uix.textinput import TextInput
from kivy.uix.dropdown import DropDown
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.metrics import dp
import os

from kivy.app import App
import importlib.util

_ui_dir = os.path.dirname(os.path.abspath(__file__))
_cfg_spec = importlib.util.spec_from_file_location(
    "vidatron_ui_settings", os.path.join(_ui_dir, "config.py")
)
_vidatron_ui_settings = importlib.util.module_from_spec(_cfg_spec)
_cfg_spec.loader.exec_module(_vidatron_ui_settings)
config_manager = _vidatron_ui_settings.config_manager

from face_customization import normalize_eye_choice, normalize_mouth_choice
from widgets import Face, StickFigureIcon


def app_main_nav_screen(sm) -> str:
    """Voice assistant root uses ``voice``; legacy PreviewApp uses ``homescreen``."""
    if sm.has_screen("voice"):
        return "voice"
    return "homescreen"


def sync_voice_engine_face_from_config() -> None:
    """Push saved eye/mouth choices to the running voice UI engine (immediate preview)."""
    try:
        app = App.get_running_app()
        if not app or not getattr(app, "engine", None):
            return
        eng = app.engine
        eng.selected_eyes = normalize_eye_choice(config_manager.get("face_customization.selected_eyes"))
        eng.selected_mouth = normalize_mouth_choice(config_manager.get("face_customization.selected_mouth"))
    except (AttributeError, TypeError):
        pass


# One swatch sets vivid accent (blobs) + soft screen background — see SetupColorsScreen.
SETUP_COLOR_THEMES = (
    ("Blue", (0.10, 0.90, 1.00, 1.0), [0.38, 0.55, 0.82, 1.0]),
    ("Purple", (0.80, 0.35, 1.00, 1.0), [0.52, 0.40, 0.72, 1.0]),
    ("Pink", (1.00, 0.41, 0.71, 1.0), [0.88, 0.55, 0.70, 1.0]),
    ("Orange", (1.00, 0.45, 0.10, 1.0), [0.92, 0.65, 0.42, 1.0]),
    ("Green", (0.15, 1.00, 0.55, 1.0), [0.42, 0.72, 0.55, 1.0]),
)


def _rgba_close(a, b, tol=0.06):
    return all(abs(float(a[i]) - float(b[i])) <= tol for i in range(3))


def sync_voice_theme_from_config() -> None:
    """Apply default_colors from disk to the running voice screen (live preview while in setup)."""
    try:
        app = App.get_running_app()
        if not app:
            return
        root = app.root
        if not root or not getattr(root, "has_screen", None) or not root.has_screen("voice"):
            return
        voice_scr = root.get_screen("voice")
        if not voice_scr.children:
            return
        vr = voice_scr.children[0]
        bg = config_manager.get("default_colors.background", SETUP_COLOR_THEMES[0][2])
        prim = config_manager.get("default_colors.primary", list(SETUP_COLOR_THEMES[0][1]))
        if isinstance(bg, list) and len(bg) >= 3 and hasattr(vr, "bg_color"):
            vr.bg_color = [
                float(bg[0]),
                float(bg[1]),
                float(bg[2]),
                float(bg[3] if len(bg) > 3 else 1.0),
            ]
        if isinstance(prim, list) and len(prim) >= 3 and hasattr(vr, "blob_color_a"):
            pr = [float(prim[0]), float(prim[1]), float(prim[2])]
            vr.blob_color_a = [
                pr[0] * 0.55 + 0.2,
                pr[1] * 0.55 + 0.2,
                pr[2] * 0.55 + 0.2,
                0.38,
            ]
            vr.blob_color_b = [
                pr[0] * 0.35 + 0.08,
                pr[1] * 0.35 + 0.08,
                pr[2] * 0.35 + 0.15,
                0.42,
            ]
        Window.clearcolor = (vr.bg_color[0], vr.bg_color[1], vr.bg_color[2], 1.0)
    except (AttributeError, IndexError, TypeError, ValueError):
        pass


class WelcomeScreen(Screen):
    """
    Welcome/Home screen with navigation options.
    Allows user to choose: Go with Default, Customize, or View Settings.
    """
    
    def __init__(self, **kwargs):
        """Initialize the welcome screen."""
        super().__init__(**kwargs)
        self.setup_ui()
    
    def setup_ui(self):
        """Build the welcome screen UI with navigation icons."""
        # Main layout with background
        main_layout = FloatLayout()
        
        # Background gradient effect
        with main_layout.canvas.before:
            Color(0.05, 0.05, 0.10, 1.0)
            Rectangle(pos=main_layout.pos, size=Window.size)
            Color(0.10, 0.15, 0.25, 0.3)
            RoundedRectangle(pos=(dp(20), dp(20)), size=(Window.width-dp(40), Window.height-dp(40)), radius=[dp(30)])
        
        # Title
        title = Label(
            text="Vidatron",
            font_size="48sp",
            bold=True,
            color=(1, 1, 1, 1),
            halign="center",
            valign="top",
            size_hint=(1, 0.2),
            pos_hint={"x": 0, "y": 0.80}
        )
        main_layout.add_widget(title)
        
        subtitle = Label(
            text="Your Personal Robot Assistant",
            font_size="24sp",
            color=(0.8, 0.8, 1, 1),
            halign="center",
            size_hint=(1, 0.1),
            pos_hint={"x": 0, "y": 0.70}
        )
        main_layout.add_widget(subtitle)
        
        # Navigation buttons in a grid
        nav_grid = GridLayout(
            cols=2,
            spacing=dp(20),
            padding=dp(30),
            size_hint=(0.9, 0.5),
            pos_hint={"center_x": 0.5, "center_y": 0.45}
        )
        
        # Go with Default button
        default_btn = Button(
            text="Go with Default",
            font_size="20sp",
            bold=True,
            size_hint_y=None,
            height=dp(120),
            background_color=(0.2, 0.7, 0.4, 1.0),
            background_normal='',
            background_down=''
        )
        default_btn.bind(on_release=self.go_default)
        nav_grid.add_widget(default_btn)
        
        # Customize button
        customize_btn = Button(
            text="Customize",
            font_size="20sp",
            bold=True,
            size_hint_y=None,
            height=dp(120),
            background_color=(0.3, 0.5, 0.9, 1.0),
            background_normal='',
            background_down=''
        )
        customize_btn.bind(on_release=self.start_customization)
        nav_grid.add_widget(customize_btn)
        
        # Settings button
        settings_btn = Button(
            text="Settings",
            font_size="20sp",
            bold=True,
            size_hint_y=None,
            height=dp(120),
            background_color=(0.7, 0.4, 0.2, 1.0),
            background_normal='',
            background_down=''
        )
        settings_btn.bind(on_release=self.open_settings)
        nav_grid.add_widget(settings_btn)
        
        # Reminders button
        reminders_btn = Button(
            text="Reminders",
            font_size="20sp",
            bold=True,
            size_hint_y=None,
            height=dp(120),
            background_color=(0.8, 0.3, 0.6, 1.0),
            background_normal='',
            background_down=''
        )
        reminders_btn.bind(on_release=self.open_reminders)
        nav_grid.add_widget(reminders_btn)
        
        main_layout.add_widget(nav_grid)
        
        self.add_widget(main_layout)
        
        # Time in a separate overlay so it is always above background/colour (drawn on top of everything)
        welcome_time_overlay = FloatLayout(size_hint=(1, 1))
        self._welcome_time_label = Label(
            text="",
            font_size="20sp",
            color=(0.9, 0.9, 1, 1),
            halign="right",
            valign="top",
            size_hint=(0.32, 0.08),
            pos_hint={"right": 1, "top": 1},
            padding=(dp(16), dp(8))
        )
        self._welcome_time_label.bind(size=lambda lbl, size: setattr(lbl, "text_size", (max(1, size[0] - dp(24)), max(1, size[1] - dp(16)))))
        welcome_time_overlay.add_widget(self._welcome_time_label)
        self.add_widget(welcome_time_overlay)
        self._update_welcome_time()
        Clock.schedule_interval(lambda dt: self._update_welcome_time(), 1.0)
    
    def _update_welcome_time(self):
        """Update time in top right (12-hour with AM/PM)."""
        if hasattr(self, '_welcome_time_label'):
            now = datetime.now()
            h = now.hour % 12 or 12
            m = now.minute
            ampm = "AM" if now.hour < 12 else "PM"
            self._welcome_time_label.text = f"{h}:{m:02d} {ampm}"
    
    def go_default(self, instance):
        """Revert to default settings (blue screen, round eyes, smile) and go to homescreen."""
        # Default: blue accent, Round eyes, Curved mouth (smile)
        config_manager.set("face_customization.selected_eyes", "Round")
        config_manager.set("face_customization.selected_mouth", "Neutral")
        config_manager.set("default_colors.primary", [0.10, 0.90, 1.00, 1.0])
        config_manager.set("font_settings.style", "Roboto")
        config_manager.set("font_settings.size", 30)
        config_manager.set("first_time_setup_complete", True)
        self.manager.current = "homescreen"
    
    def start_customization(self, instance):
        """Start the customization setup process."""
        self.manager.current = "setup_face"
    
    def open_settings(self, instance):
        """Open settings screen."""
        self.manager.current = "settings"
    
    def open_reminders(self, instance):
        """Open reminders screen."""
        self.manager.current = "reminders"


class SetupFaceScreen(Screen):
    """
    First-time setup - Page 1: Face Customization
    Allows user to configure eyes and mouth (both nullable).
    """
    
    def __init__(self, **kwargs):
        """Initialize the face customization setup screen."""
        super().__init__(**kwargs)
        self.selected_eyes = normalize_eye_choice(
            config_manager.get("face_customization.selected_eyes", "Round")
        )
        self.selected_mouth = normalize_mouth_choice(
            config_manager.get("face_customization.selected_mouth", "Neutral")
        )
        self._eyes_btn = None
        self._mouth_btn = None
        self.setup_ui()
    
    def setup_ui(self):
        """Build the UI for face customization."""
        layout = FloatLayout()
        
        # Background
        with layout.canvas.before:
            Color(0.05, 0.05, 0.10, 1.0)
            Rectangle(pos=layout.pos, size=Window.size)
        
        # Title
        title = Label(
            text="Welcome to Vidatron!\nStep 1/2: Face Customization",
            font_size="36sp",
            bold=True,
            color=(1, 1, 1, 1),
            halign="center",
            valign="top",
            size_hint=(1, 0.15),
            pos_hint={"x": 0, "y": 0.85}
        )
        layout.add_widget(title)
        
        # Instructions
        instructions = Label(
            text="Choose eye and mouth shapes",
            font_size="22sp",
            color=(0.8, 0.8, 1, 1),
            halign="center",
            size_hint=(1, 0.08),
            pos_hint={"x": 0, "y": 0.75}
        )
        layout.add_widget(instructions)
        
        # Eyes selection with better spacing
        eyes_label = Label(
            text="Eyes:",
            font_size="24sp",
            color=(0.9, 0.9, 1, 1),
            halign="left",
            size_hint=(0.4, 0.08),
            pos_hint={"x": 0.1, "y": 0.62}
        )
        layout.add_widget(eyes_label)
        
        self.eyes_dropdown = DropDown()
        eyes_btn = Button(
            text=f"Eyes: {self.selected_eyes}",
            size_hint=(0.35, 0.08),
            pos_hint={"x": 0.5, "y": 0.62},
            background_color=(0.3, 0.5, 0.8, 1.0),
            background_normal='',
            background_down=''
        )
        for option in ["Round", "Narrow", "Wide", "Small"]:
            btn = Button(text=option, size_hint_y=None, height=dp(50))
            btn.bind(on_release=lambda b, opt=option: self.select_eyes(opt, eyes_btn))
            self.eyes_dropdown.add_widget(btn)
        eyes_btn.bind(on_release=self.eyes_dropdown.open)
        layout.add_widget(eyes_btn)
        self._eyes_btn = eyes_btn
        
        # Mouth selection with better spacing
        mouth_label = Label(
            text="Mouth:",
            font_size="24sp",
            color=(0.9, 0.9, 1, 1),
            halign="left",
            size_hint=(0.4, 0.08),
            pos_hint={"x": 0.1, "y": 0.50}
        )
        layout.add_widget(mouth_label)
        
        self.mouth_dropdown = DropDown()
        mouth_btn = Button(
            text=f"Mouth: {self.selected_mouth}",
            size_hint=(0.35, 0.08),
            pos_hint={"x": 0.5, "y": 0.50},
            background_color=(0.3, 0.5, 0.8, 1.0),
            background_normal='',
            background_down=''
        )
        for option in ["Small", "Wide", "Neutral"]:
            btn = Button(text=option, size_hint_y=None, height=dp(50))
            btn.bind(on_release=lambda b, opt=option: self.select_mouth(opt, mouth_btn))
            self.mouth_dropdown.add_widget(btn)
        mouth_btn.bind(on_release=self.mouth_dropdown.open)
        layout.add_widget(mouth_btn)
        self._mouth_btn = mouth_btn
        
        # Navigation buttons with better styling
        back_btn = Button(
            text="← Back",
            size_hint=(0.2, 0.10),
            pos_hint={"x": 0.1, "y": 0.15},
            background_color=(0.4, 0.4, 0.4, 1.0),
            background_normal='',
            background_down=''
        )
        back_btn.bind(
            on_release=lambda *_: setattr(
                self.manager,
                "current",
                app_main_nav_screen(self.manager) if self.manager.has_screen("voice") else "welcome",
            )
        )
        layout.add_widget(back_btn)
        
        next_btn = Button(
            text="Next →",
            size_hint=(0.25, 0.10),
            pos_hint={"x": 0.65, "y": 0.15},
            background_color=(0.2, 0.7, 0.4, 1.0),
            background_normal='',
            background_down=''
        )
        next_btn.bind(on_release=self.next_page)
        layout.add_widget(next_btn)
        
        self.add_widget(layout)
    
    def select_eyes(self, option, btn):
        """Handle eyes selection."""
        self.eyes_dropdown.dismiss()
        self.selected_eyes = normalize_eye_choice(option)
        btn.text = f"Eyes: {self.selected_eyes}"
        config_manager.set("face_customization.selected_eyes", self.selected_eyes)
        sync_voice_engine_face_from_config()
    
    def select_mouth(self, option, btn):
        """Handle mouth selection."""
        self.mouth_dropdown.dismiss()
        self.selected_mouth = normalize_mouth_choice(option)
        btn.text = f"Mouth: {self.selected_mouth}"
        config_manager.set("face_customization.selected_mouth", self.selected_mouth)
        sync_voice_engine_face_from_config()
    
    def on_pre_enter(self, *args):
        """Show current saved choices on the buttons and sync the live mascot."""
        self.selected_eyes = normalize_eye_choice(config_manager.get("face_customization.selected_eyes"))
        self.selected_mouth = normalize_mouth_choice(config_manager.get("face_customization.selected_mouth"))
        if self._eyes_btn:
            self._eyes_btn.text = f"Eyes: {self.selected_eyes}"
        if self._mouth_btn:
            self._mouth_btn.text = f"Mouth: {self.selected_mouth}"
        sync_voice_engine_face_from_config()
    
    def next_page(self, instance):
        """Save face customization and go to colours."""
        config_manager.set(
            "face_customization.selected_eyes", normalize_eye_choice(self.selected_eyes)
        )
        config_manager.set(
            "face_customization.selected_mouth", normalize_mouth_choice(self.selected_mouth)
        )
        sync_voice_engine_face_from_config()
        self.manager.current = "setup_colors"


class SetupColorsScreen(Screen):
    """
    First-time setup - Page 2: accent colour and matching main screen background.
    """

    def _sync_theme_from_saved_config(self):
        """Set selected_color / _current_background from JSON (or default theme)."""
        self.selected_color = tuple(SETUP_COLOR_THEMES[0][1])
        self._current_background = list(SETUP_COLOR_THEMES[0][2])
        loaded_bg = config_manager.get("default_colors.background")
        loaded_prim = config_manager.get("default_colors.primary")
        if isinstance(loaded_bg, list) and len(loaded_bg) >= 3:
            lb = [float(loaded_bg[i]) for i in range(min(4, len(loaded_bg)))]
            if len(lb) == 3:
                lb.append(1.0)
            for _name, accent, bg in SETUP_COLOR_THEMES:
                if _rgba_close(lb, bg):
                    self.selected_color = tuple(accent)
                    self._current_background = lb
                    return
            self._current_background = lb
            if isinstance(loaded_prim, list) and len(loaded_prim) >= 3:
                self.selected_color = tuple(
                    float(loaded_prim[i]) for i in range(min(4, len(loaded_prim)))
                )
            return
        if isinstance(loaded_prim, list) and len(loaded_prim) >= 3:
            lp = [float(loaded_prim[i]) for i in range(min(4, len(loaded_prim)))]
            for _name, accent, bg in SETUP_COLOR_THEMES:
                if _rgba_close(lp, list(accent)):
                    self.selected_color = tuple(accent)
                    self._current_background = list(bg)
                    return

    def __init__(self, **kwargs):
        """Initialize the color selection setup screen."""
        super().__init__(**kwargs)
        self._sync_theme_from_saved_config()
        self.setup_ui()

    def on_pre_enter(self, *args):
        """Reload saved theme when opening this screen (e.g. from swipe menu)."""
        self._sync_theme_from_saved_config()
        sync_voice_theme_from_config()
    
    def setup_ui(self):
        """Build the UI for color selection."""
        layout = FloatLayout()
        
        # Title
        title = Label(
            text="Step 2/2: Colours",
            font_size="32sp",
            bold=True,
            color=(1, 1, 1, 1),
            halign="center",
            valign="top",
            size_hint=(1, 0.15),
            pos_hint={"x": 0, "y": 0.85}
        )
        layout.add_widget(title)
        
        # Instructions
        instructions = Label(
            text="Accent colour & background",
            font_size="20sp",
            color=(0.8, 0.8, 1, 1),
            halign="center",
            size_hint=(1, 0.06),
            pos_hint={"x": 0, "y": 0.78}
        )
        layout.add_widget(instructions)

        # One row per theme: sets main screen background + accent (blobs).
        for i, (name, color, _bg) in enumerate(SETUP_COLOR_THEMES):
            row, col = i // 3, i % 3
            btn = Button(
                text=name,
                size_hint=(0.28, 0.11),
                pos_hint={"x": 0.08 + col * 0.32, "y": 0.62 - row * 0.13},
                background_color=(*color[:3], 0.8),
                font_size="18sp"
            )
            btn.bind(
                on_release=lambda b, acc=color, bg=list(_bg): self.apply_color_theme(acc, bg)
            )
            layout.add_widget(btn)

        rem_btn = Button(
            text="Healthy reminders",
            size_hint=(0.45, 0.07),
            pos_hint={"center_x": 0.5, "y": 0.22},
            background_color=(0.55, 0.35, 0.72, 1.0),
            background_normal="",
            background_down="",
            color=(1, 1, 1, 1),
            font_size="17sp",
        )
        rem_btn.bind(on_release=lambda *_: setattr(self.manager, "current", "reminders"))
        layout.add_widget(rem_btn)

        # Navigation buttons
        back_btn = Button(
            text="← Back",
            size_hint=(0.2, 0.09),
            pos_hint={"x": 0.1, "y": 0.075},
            background_color=(0.5, 0.5, 0.5, 1.0)
        )
        back_btn.bind(on_release=lambda *_: setattr(self.manager, "current", "setup_face"))
        layout.add_widget(back_btn)
        
        # Complete Setup Button
        complete_btn = Button(
            text="Save & return",
            size_hint=(0.35, 0.09),
            pos_hint={"x": 0.55, "y": 0.075},
            background_color=(0.2, 0.8, 0.4, 1.0)
        )
        complete_btn.bind(on_release=self.complete_setup)
        layout.add_widget(complete_btn)
        
        self.add_widget(layout)
    
    def apply_color_theme(self, accent, background):
        """Persist accent + matching background and update the voice screen immediately."""
        self.selected_color = accent
        self._current_background = list(background)
        config_manager.set("default_colors.primary", list(accent))
        config_manager.set("default_colors.background", self._current_background)
        sync_voice_theme_from_config()

    def complete_setup(self, instance):
        """Save color settings, mark setup complete, and navigate to homescreen."""
        config_manager.set("default_colors.primary", list(self.selected_color))
        config_manager.set("default_colors.background", list(self._current_background))
        sync_voice_theme_from_config()
        config_manager.set("first_time_setup_complete", True)
        self.manager.current = app_main_nav_screen(self.manager)


class Homescreen(Screen):
    """
    Main homescreen displayed after first-time setup.
    Shows active reminders and provides navigation to settings.
    """
    
    def __init__(self, **kwargs):
        """Initialize the homescreen."""
        super().__init__(**kwargs)
        self.idx = 0  # Current reminder index
        # Ensure default reminders are added if needed
        config_manager.ensure_default_reminders()
        # On app boot, start interval timers from "now" so reminders do not
        # immediately appear due to stale/old last_fired values.
        self._initialize_interval_last_fired()
        self.setup_ui()
        self.load_reminders()

    def _initialize_interval_last_fired(self):
        """Seed interval reminders so they trigger only after one full interval."""
        reminders = config_manager.get("reminders", [])
        last_fired = dict(config_manager.get("last_fired", {}))
        now_ts = datetime.now().timestamp()
        updated = False

        for reminder in reminders:
            if not reminder.get("is_active", True):
                continue
            if reminder.get("trigger_type", "Specific Time") != "Every X Minutes":
                continue
            reminder_id = reminder.get("id")
            if not reminder_id:
                continue
            # Always reset interval timers on boot to avoid immediate card display.
            last_fired[reminder_id] = now_ts
            updated = True

        if updated:
            config_manager.set("last_fired", last_fired)
    
    def setup_ui(self):
        """Build the homescreen UI."""
        layout = FloatLayout()
        
        # Face area (top 72%) - shown by default
        self.face = Face(size_hint=(1, 0.72), pos_hint={"x": 0, "y": 0.28})
        eyes = normalize_eye_choice(config_manager.get("face_customization.selected_eyes"))
        mouth = normalize_mouth_choice(config_manager.get("face_customization.selected_mouth"))
        self.face.set_customization(eyes, mouth)
        
        # Apply saved default color to face
        default_color = config_manager.get("default_colors.primary", [0.10, 0.90, 1.00, 1.0])
        if isinstance(default_color, list):
            default_color = tuple(default_color)
        self.face.set_style(default_color, "happy")
        layout.add_widget(self.face)
        
        # Icon image widget (stick figure from file) - replaces face when reminder has icon_path
        self.icon_image = Image(
            source="",
            size_hint=(1, 0.72),  # Same size as face area
            pos_hint={"x": 0, "y": 0.28},  # Same position as face
            allow_stretch=True,
            keep_ratio=True
        )
        self.icon_image.opacity = 0  # Hidden by default (face shows instead)
        layout.add_widget(self.icon_image)
        # Kivy-drawn stick figure icon (when reminder has action: drink / stretch)
        self.stick_figure_icon = StickFigureIcon(
            action="stretch",
            size_hint=(1, 0.72),
            pos_hint={"x": 0, "y": 0.28}
        )
        self.stick_figure_icon.opacity = 0  # Hidden by default
        layout.add_widget(self.stick_figure_icon)
        
        # Bottom bar
        self.bar = Widget(size_hint=(1, 0.28), pos_hint={"x": 0, "y": 0})
        layout.add_widget(self.bar)
        
        # Title label
        font_size = config_manager.get("font_settings.size", 30)
        font_style = config_manager.get("font_settings.style", "Roboto")
        self.title = Label(
            text="",
            markup=True,
            font_size=f"{font_size}sp",
            font_name=font_style,
            bold=True,
            halign="left",
            valign="top",
            color=(1, 1, 1, 1),
            size_hint=(1, 0.28),
            pos_hint={"x": 0, "y": 0},
            padding=(24, 18)
        )
        self.title.bind(size=lambda lbl, *_: setattr(lbl, "text_size", (lbl.width-40, lbl.height)))
        layout.add_widget(self.title)
        
        # Line label (reminder text)
        self.line = Label(
            text="",
            font_size=f"{int(font_size * 0.73)}sp",
            font_name=font_style,
            halign="left",
            valign="middle",
            color=(0.92, 0.95, 1, 1),
            size_hint=(1, 0.28),
            pos_hint={"x": 0, "y": -0.02},
            padding=(24, 18)
        )
        self.line.bind(size=lambda lbl, *_: setattr(lbl, "text_size", (lbl.width-40, lbl.height)))
        layout.add_widget(self.line)
        
        # Home button only (as requested)
        home_btn = Button(
            text="Home",
            size_hint=(0.15, 0.08),
            pos_hint={"x": 0.82, "y": 0.18},
            background_color=(0.4, 0.4, 0.5, 0.9),
            background_normal='',
            background_down=''
        )
        home_btn.bind(on_release=lambda *_: setattr(self.manager, "current", "welcome"))
        layout.add_widget(home_btn)
        
        self.add_widget(layout)
        
        # Time in a separate overlay so it is always above face/bar/colour (drawn on top of everything)
        time_overlay = FloatLayout(size_hint=(1, 1))
        self.time_label = Label(
            text="",
            font_size="20sp",
            color=(0.9, 0.9, 1, 1),
            halign="right",
            valign="top",
            size_hint=(0.32, 0.08),
            pos_hint={"right": 1, "top": 1},
            padding=(dp(16), dp(8))
        )
        self.time_label.bind(size=lambda lbl, size: setattr(lbl, "text_size", (max(1, size[0] - dp(24)), max(1, size[1] - dp(16)))))
        time_overlay.add_widget(self.time_label)
        self.add_widget(time_overlay)
        self._update_time_label()
        Clock.schedule_interval(lambda dt: self._update_time_label(), 1.0)
        
        # Track if a triggered reminder is currently showing (pause cycling)
        self.triggered_reminder_showing = False
        self.cycling_paused_until = None
        
        # Start reminder scheduler (checks every second for time-triggered reminders)
        Clock.schedule_interval(self.check_reminders, 1.0)
        # No automatic cycling: reminders only show when their set time triggers
    
    def _update_time_label(self):
        """Update the time display in top right (12-hour with AM/PM)."""
        if hasattr(self, 'time_label'):
            now = datetime.now()
            h = now.hour % 12 or 12
            m = now.minute
            ampm = "AM" if now.hour < 12 else "PM"
            self.time_label.text = f"{h}:{m:02d} {ampm}"
    
    def on_pre_enter(self, *args):
        """Refresh reminders and ALL customizations when screen becomes visible."""
        eyes = normalize_eye_choice(config_manager.get("face_customization.selected_eyes"))
        mouth = normalize_mouth_choice(config_manager.get("face_customization.selected_mouth"))
        self.face.set_customization(eyes, mouth)
        
        # Update font settings - CRITICAL: Must update font_size property
        font_size = config_manager.get("font_settings.size", 30)
        font_style = config_manager.get("font_settings.style", "Roboto")
        if hasattr(self, 'title'):
            self.title.font_size = f"{font_size}sp"
            self.title.font_name = font_style
        if hasattr(self, 'line'):
            self.line.font_size = f"{int(font_size * 0.73)}sp"
            self.line.font_name = font_style
        
        # Update default color (apply to face if no reminder showing)
        default_color = config_manager.get("default_colors.primary", [0.10, 0.90, 1.00, 1.0])
        if isinstance(default_color, list):
            default_color = tuple(default_color)
        if not hasattr(self, 'active_reminders') or not self.active_reminders:
            self.face.set_style(default_color, "happy")
            self.draw_bar(default_color)
        
        # Refresh reminders (always show default view with count; never auto-show a reminder card)
        self.load_reminders()
    
    def show_default_view(self):
        """Show the default homescreen: user's face, default color, and reminder count (no reminder card).
        Per-reminder face customizations are never applied here; they only apply when a reminder is triggered (apply_card).
        """
        eyes = normalize_eye_choice(config_manager.get("face_customization.selected_eyes"))
        mouth = normalize_mouth_choice(config_manager.get("face_customization.selected_mouth"))
        self.face.set_customization(eyes, mouth)
        default_color = config_manager.get("default_colors.primary", [0.10, 0.90, 1.00, 1.0])
        if isinstance(default_color, list):
            default_color = tuple(default_color)
        self.face.set_style(default_color, "happy")
        self.draw_bar(default_color)
        # Hide icon image and stick figure; show robot face in default view
        if hasattr(self, 'icon_image'):
            self.icon_image.opacity = 0
        if hasattr(self, 'stick_figure_icon'):
            self.stick_figure_icon.opacity = 0
        if hasattr(self, 'face'):
            self.face.opacity = 1.0  # Show robot face (stick figure hidden)
        n = len(getattr(self, "active_reminders", []))
        if n == 0:
            self.title.text = "[b]No Reminders[/b]"
            self.line.text = "Add reminders in the Tools section"
        elif n == 1:
            self.title.text = "[b]Reminders[/b]"
            self.line.text = "1 reminder"
        else:
            self.title.text = "[b]Reminders[/b]"
            self.line.text = f"{n} reminders"
    
    def load_reminders(self):
        """Load reminders and show default view (count only). Never auto-show a reminder card until its time."""
        reminders = config_manager.get("reminders", [])
        self.active_reminders = [r for r in reminders if r.get("is_active", True)]
        self.show_default_view()
    
    def draw_bar(self, accent):
        """Draw the bottom bar with accent color."""
        self.bar.canvas.before.clear()
        r, g, b, a = accent
        with self.bar.canvas.before:
            Color(r, g, b, 0.95)
            RoundedRectangle(
                pos=(10, 10),
                size=(Window.width-20, Window.height*0.28-20),
                radius=[18]
            )
            Color(0.02, 0.02, 0.04, 0.92)
            RoundedRectangle(
                pos=(16, 16),
                size=(Window.width-32, Window.height*0.28-32),
                radius=[14]
            )
    
    def apply_card(self, reminder):
        """
        Apply a reminder card to the display. Only called when a reminder is actually shown
        (time-triggered, test-in-10, or manual next). Per-reminder face customizations
        are applied here only, not on the default view.
        """
        # Get accent color from reminder or use default
        accent = reminder.get("accent", config_manager.get("default_colors.primary", [0.10, 0.90, 1.00, 1.0]))
        if isinstance(accent, list):
            accent = tuple(accent)
        
        # Get face expression from reminder (nullable)
        # Constraint: face_expression must have eyes and/or mouth defined within it
        face_expression = reminder.get("face_expression")
        if face_expression and isinstance(face_expression, dict):
            # Check constraint: face_expression must have eyes OR mouth defined
            expr_eyes = face_expression.get("eyes")
            expr_mouth = face_expression.get("mouth")
            if expr_eyes is None and expr_mouth is None:
                # Constraint violation - face_expression requires eyes or mouth
                face_expression = None
        
        # Use face expression mood if valid, otherwise use reminder mood
        if face_expression and isinstance(face_expression, dict):
            mood = face_expression.get("mood", reminder.get("mood", "happy"))
            # Apply face expression customization to face widget
            expr_eyes = face_expression.get("eyes")
            expr_mouth = face_expression.get("mouth")
            if expr_eyes is not None:
                expr_eyes = normalize_eye_choice(expr_eyes)
            if expr_mouth is not None:
                expr_mouth = normalize_mouth_choice(expr_mouth)
            self.face.set_customization(expr_eyes, expr_mouth)
        else:
            mood = reminder.get("mood", "happy")
            eyes = normalize_eye_choice(config_manager.get("face_customization.selected_eyes"))
            mouth = normalize_mouth_choice(config_manager.get("face_customization.selected_mouth"))
            self.face.set_customization(eyes, mouth)
        
        # Display reminder icon (stick figure modeling the action) - replaces face when shown
        action = reminder.get("action")  # "drink" | "stretch" for Kivy-drawn icon
        if not action and reminder.get("text"):
            # Infer action from text for default reminders saved before "action" existed
            t = reminder["text"].lower()
            if "drink" in t or "water" in t:
                action = "drink"
            elif "stretch" in t:
                action = "stretch"
        icon_path = reminder.get("icon_path")
        icon_text = reminder.get("icon", "")
        
        icon_shown = False
        # Prefer Kivy-drawn stick figure when reminder has action (no image file needed)
        if action in ("drink", "stretch") and hasattr(self, "stick_figure_icon"):
            self.stick_figure_icon.accent = tuple(accent) if isinstance(accent, (list, tuple)) else (0.10, 0.90, 1.00, 1.0)
            self.stick_figure_icon.action = action
            self.stick_figure_icon.opacity = 1.0
            self.icon_image.opacity = 0.0
            self.face.opacity = 0.0
            icon_shown = True
        elif icon_path:
            if not os.path.isabs(icon_path):
                script_dir = os.path.dirname(os.path.abspath(__file__))
                icon_path_abs = os.path.join(script_dir, icon_path)
            else:
                icon_path_abs = icon_path
            
            if os.path.exists(icon_path_abs):
                try:
                    self.icon_image.source = icon_path_abs
                    self.icon_image.opacity = 1.0
                    if hasattr(self, "stick_figure_icon"):
                        self.stick_figure_icon.opacity = 0.0
                    self.face.opacity = 0.0
                    icon_shown = True
                except Exception as e:
                    print(f"Error loading icon {icon_path_abs}: {e}")
                    self.icon_image.opacity = 0.0
                    if hasattr(self, "stick_figure_icon"):
                        self.stick_figure_icon.opacity = 0.0
                    self.face.opacity = 1.0
                    icon_text = icon_text or ""
            else:
                if hasattr(self, "stick_figure_icon"):
                    self.stick_figure_icon.opacity = 0.0
                self.icon_image.opacity = 0.0
                self.face.opacity = 1.0
                if not icon_text:
                    icon_text = ""
        else:
            if hasattr(self, "stick_figure_icon"):
                self.stick_figure_icon.opacity = 0.0
            self.icon_image.opacity = 0.0
            self.face.opacity = 1.0
            if not icon_text:
                icon_text = ""
        
        # Apply face style and bar (even if face is hidden, bar still shows)
        self.face.set_style(accent, mood)
        self.draw_bar(accent)
        
        # Display reminder text (nullable)
        title = reminder.get("text", "Reminder")
        self.title.text = f"[b]{icon_text} {title}[/b]" if icon_text else f"[b]{title}[/b]"
        # Use description if available, otherwise use text as line
        description = reminder.get("description")
        if description:
            self.line.text = description
        else:
            # Fallback: show text in line if no description
            self.line.text = reminder.get("text", "")
    
    def dismiss(self):
        """Dismiss current reminder overlay."""
        self.line.text = "Dismissed!"
    
    def _normalize_trigger_time(self, time_str):
        """Normalize stored trigger time to HH:MM for reliable comparison."""
        if not time_str or not isinstance(time_str, str):
            return ""
        parts = time_str.strip().split(":")
        if len(parts) != 2:
            return ""
        try:
            h, m = int(parts[0]), int(parts[1])
            if h < 0 or h > 23 or m < 0 or m > 59:
                return ""
            return f"{h:02d}:{m:02d}"
        except (ValueError, TypeError):
            return ""

    def check_reminders(self, dt):
        """
        Reminder scheduler engine.
        Checks every second if any active reminder should trigger based on trigger_time or interval.
        """
        now = datetime.now()
        current_time = now.strftime("%H:%M")  # Always "HH:MM" (e.g. 09:00, 12:58)
        current_date = now.strftime("%Y-%m-%d")
        current_minute = f"{current_date} {current_time}"
        current_timestamp = now.timestamp()
        
        reminders = config_manager.get("reminders", [])
        last_fired = config_manager.get("last_fired", {})
        
        for reminder in reminders:
            if not reminder.get("is_active", True):
                continue
            
            # Get stable reminder ID (must exist, generated on creation)
            reminder_id = reminder.get("id")
            if not reminder_id:
                # Legacy reminder without ID - generate one and save it
                reminder_id = str(uuid.uuid4())
                reminder["id"] = reminder_id
                config_manager.set("reminders", reminders)
            
            trigger_type = reminder.get("trigger_type", "Specific Time")
            should_trigger = False
            
            if trigger_type == "Every X Minutes":
                # Interval-based reminder
                interval_minutes = reminder.get("interval_minutes", 5)
                last_fired_time = last_fired.get(reminder_id)
                
                if last_fired_time is None:
                    # First boot / first run: initialize timer so home face remains visible.
                    # This avoids firing interval reminders immediately at startup.
                    last_fired[reminder_id] = current_timestamp
                    config_manager.set("last_fired", last_fired)
                    continue
                else:
                    # Check if enough time has passed
                    try:
                        # Parse last fired timestamp
                        if isinstance(last_fired_time, str):
                            # Old format: "YYYY-MM-DD HH:MM"
                            last_dt = datetime.strptime(last_fired_time, "%Y-%m-%d %H:%M")
                        else:
                            # New format: timestamp
                            last_dt = datetime.fromtimestamp(last_fired_time)
                        
                        minutes_passed = (now - last_dt).total_seconds() / 60.0
                        if minutes_passed >= interval_minutes:
                            should_trigger = True
                    except (ValueError, TypeError):
                        # Invalid format - trigger anyway
                        should_trigger = True
            else:
                # Time-based reminder: compare normalized HH:MM
                raw_trigger = reminder.get("trigger_time", "")
                trigger_time = self._normalize_trigger_time(raw_trigger)
                if not trigger_time or trigger_time != current_time:
                    continue
                
                # Check if already fired this minute (prevent repeated triggers)
                if last_fired.get(reminder_id) == current_minute:
                    continue
                
                should_trigger = True
            
            if not should_trigger:
                continue
            
            # Check repeat settings (for time-based reminders)
            if trigger_type == "Specific Time":
                repeat_settings = reminder.get("repeat_settings", "once")
                if not self.repeat_allows_today(repeat_settings, now):
                    continue
            
            # Remember where to return after 1 minute
            self._return_screen = self.manager.current
            self.manager.current = "homescreen"
            self.trigger_reminder(reminder, is_real_trigger=True)
            
            # Mark as fired (use timestamp for interval, minute string for time-based)
            if trigger_type == "Every X Minutes":
                last_fired[reminder_id] = current_timestamp
            else:
                last_fired[reminder_id] = current_minute
            config_manager.set("last_fired", last_fired)
            
            # If "once" repeat (time-based only), disable the reminder after firing
            if trigger_type == "Specific Time" and reminder.get("repeat_settings") == "once":
                reminder["is_active"] = False
                config_manager.set("reminders", reminders)
                # Reload active reminders
                self.load_reminders()
    
    def repeat_allows_today(self, repeat_settings, now):
        """
        Check if repeat settings allow reminder to fire today.
        
        Args:
            repeat_settings: String like "daily", "weekly", "once", "weekdays", etc.
            now: datetime object for current time
        
        Returns:
            bool: True if reminder should fire today
        """
        if repeat_settings == "once":
            # "once" is handled by disabling after firing, so always allow if active
            return True
        elif repeat_settings == "daily":
            return True
        elif repeat_settings == "weekdays":
            return now.weekday() < 5  # Monday=0, Friday=4
        elif repeat_settings == "weekends":
            return now.weekday() >= 5  # Saturday=5, Sunday=6
        elif repeat_settings == "weekly":
            # Fire once per week (check last_fired for same weekday)
            return True  # Simplified - could check last week's date
        else:
            return True  # Default: allow
    
    REMINDER_DISPLAY_SECONDS = 60  # Show reminder for 1 minute then return

    def trigger_reminder(self, reminder, is_real_trigger=False):
        """
        Trigger a reminder - display it on the homescreen for 1 minute, then return to previous screen.
        
        Args:
            reminder: Dictionary containing reminder data
            is_real_trigger: If True, we have already set _return_screen in check_reminders.
        """
        if not is_real_trigger and not hasattr(self, '_return_screen'):
            # Test-in-10 or other call: remember current screen for return (if not already set by caller)
            self._return_screen = self.manager.current
        # For is_real_trigger, _return_screen was set in check_reminders before switching
        
        self.apply_card(reminder)
        self.triggered_reminder_showing = True
        self.cycling_paused_until = datetime.now().timestamp() + float(self.REMINDER_DISPLAY_SECONDS)

        def _after_reminder_duration(dt):
            self.triggered_reminder_showing = False
            self.cycling_paused_until = None
            return_to = getattr(self, '_return_screen', 'homescreen')
            if return_to != 'homescreen':
                self.manager.current = return_to
            else:
                # Stay on homescreen; show default view (reminder count only)
                self.load_reminders()

        Clock.schedule_once(_after_reminder_duration, self.REMINDER_DISPLAY_SECONDS)
    
    def cycle_if_allowed(self, dt):
        """Cycle to next reminder only if no triggered reminder is showing."""
        # Don't cycle if a triggered reminder is currently displayed
        if self.triggered_reminder_showing:
            return
        
        # Don't cycle if still in pause period
        if self.cycling_paused_until and datetime.now().timestamp() < self.cycling_paused_until:
            return
        
        self.next_card()
    
    def next_card(self):
        """Cycle to the next active reminder."""
        if self.active_reminders:
            self.idx = (self.idx + 1) % len(self.active_reminders)
            self.apply_card(self.active_reminders[self.idx])
    
    # Removed open_settings - homescreen only has Home button now


class SettingsScreen(Screen):
    """
    Settings screen - simplified to only provide access to Tools.
    Face customization is handled in the 3-page setup flow.
    """
    
    def __init__(self, **kwargs):
        """Initialize the settings screen."""
        super().__init__(**kwargs)
        self.setup_ui()
    
    def setup_ui(self):
        """Build the simplified settings UI."""
        layout = FloatLayout()
        
        # Background
        with layout.canvas.before:
            Color(0.05, 0.05, 0.10, 1.0)
            Rectangle(pos=layout.pos, size=Window.size)
        
        # Title
        title = Label(
            text="Settings",
            font_size="36sp",
            bold=True,
            color=(1, 1, 1, 1),
            halign="center",
            valign="top",
            size_hint=(1, 0.15),
            pos_hint={"x": 0, "y": 0.85}
        )
        layout.add_widget(title)
        
        # Info message
        info_label = Label(
            text="To customize your robot's face,\nuse the Customize option from Home.",
            font_size="20sp",
            color=(0.8, 0.8, 1, 1),
            halign="center",
            size_hint=(1, 0.15),
            pos_hint={"x": 0, "y": 0.65}
        )
        layout.add_widget(info_label)
        
        # Tools → Reminders button
        tools_btn = Button(
            text="Tools: Reminders",
            size_hint=(0.4, 0.12),
            pos_hint={"center_x": 0.5, "center_y": 0.45},
            font_size="24sp",
            bold=True,
            background_color=(0.6, 0.4, 0.8, 1.0),
            background_normal='',
            background_down='',
            color=(1, 1, 1, 1)
        )
        tools_btn.bind(on_release=lambda *_: setattr(self.manager, "current", "reminders"))
        layout.add_widget(tools_btn)
        
        # Return to Homescreen button
        home_btn = Button(
            text="← Return to Homescreen",
            size_hint=(0.4, 0.10),
            pos_hint={"center_x": 0.5, "y": 0.20},
            font_size="20sp",
            background_color=(0.3, 0.7, 0.4, 1.0),
            background_normal='',
            background_down='',
            color=(1, 1, 1, 1)
        )
        home_btn.bind(on_release=self.return_home)
        layout.add_widget(home_btn)
        
        self.add_widget(layout)
    
    def return_home(self, instance):
        """Navigate back to homescreen."""
        self.manager.current = app_main_nav_screen(self.manager)


# Built-in healthy habits for add/edit reminder UI (keys stable for JSON action + stick figure).
HEALTHY_HABIT_PRESETS = (
    {
        "key": "drink_water",
        "label": "Drink water",
        "text": "Drink water",
        "description": "Stay hydrated!",
        "action": "drink",
        "icon_path": "assets/icons/drink_water.png",
        "accent": [0.10, 0.90, 1.00, 1.0],
        "mood": "happy",
    },
    {
        "key": "stretch",
        "label": "Get up and stretch",
        "text": "Get up and stretch",
        "description": "Take a break and move around",
        "action": "stretch",
        "icon_path": "assets/icons/stretch.png",
        "accent": [0.15, 1.00, 0.55, 1.0],
        "mood": "calm",
    },
)

_TRIGGER_LABELS = {
    "Every X Minutes": "Every X minutes",
    "Specific Time": "At a specific time",
}


def _habit_preset_by_key(key: str):
    for p in HEALTHY_HABIT_PRESETS:
        if p["key"] == key:
            return p
    return HEALTHY_HABIT_PRESETS[0]


def _habit_preset_for_reminder(reminder: dict):
    """Pick the closest habit preset for an existing saved reminder."""
    text = (reminder.get("text") or "").strip().lower()
    ip = (reminder.get("icon_path") or "").lower()
    act = (reminder.get("action") or "").lower()
    for p in HEALTHY_HABIT_PRESETS:
        if (p["text"] or "").strip().lower() == text:
            return p
        if act and p.get("action") == act:
            return p
        pip = (p.get("icon_path") or "").lower()
        if ip and pip and ip.endswith(pip.split("/")[-1].lower()):
            return p
    return _habit_preset_by_key("drink_water")


class ReminderEditScreen(Screen):
    """
    Create or edit a reminder: pick a built-in healthy habit, then either
    an interval (every X minutes) or a specific clock time — same JSON schema
    as :func:`voice_reminder_tick` in the voice app.
    """

    def __init__(self, reminder_index=None, **kwargs):
        """Initialize the reminder edit screen."""
        super().__init__(**kwargs)
        self.reminder_index = reminder_index
        self._habit_key = HEALTHY_HABIT_PRESETS[0]["key"]
        self._trigger_type_stored = "Every X Minutes"
        self.setup_ui()

    def setup_ui(self):
        """Build the reminder edit UI with proper spacing and ScrollView."""
        # Main container
        main_layout = FloatLayout()
        
        # Background
        with main_layout.canvas.before:
            Color(0.05, 0.05, 0.10, 1.0)
            Rectangle(pos=main_layout.pos, size=Window.size)
        
        # Title (fixed at top)
        self.title_label = Label(
            text="Edit Reminder",
            font_size="36sp",
            bold=True,
            color=(1, 1, 1, 1),
            halign="center",
            valign="top",
            size_hint=(1, 0.10),
            pos_hint={"x": 0, "y": 0.90}
        )
        main_layout.add_widget(self.title_label)
        
        # Scrollable form area
        self.scroll = ScrollView(
            size_hint=(1, 0.75),
            pos_hint={"x": 0, "y": 0.15},
            do_scroll_x=False,
            do_scroll_y=True
        )
        
        # Form container with proper spacing
        form_layout = BoxLayout(
            orientation="vertical",
            spacing=dp(15),
            padding=dp(20),
            size_hint_y=None
        )
        form_layout.bind(minimum_height=form_layout.setter('height'))
        
        # Healthy habit (preset list — text, stick figure, colors come from preset)
        habit_container = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(50), spacing=dp(10))
        habit_label = Label(
            text="Healthy habit:",
            font_size="20sp",
            color=(0.9, 0.9, 1, 1),
            halign="left",
            size_hint_x=0.32,
            text_size=(None, None),
        )
        self.habit_dropdown = DropDown()
        self.habit_btn = Button(
            text=HEALTHY_HABIT_PRESETS[0]["label"],
            size_hint_x=0.63,
            font_size="16sp",
            background_color=(0.3, 0.5, 0.8, 1.0),
            background_normal="",
            background_down="",
            color=(1, 1, 1, 1),
        )
        for preset in HEALTHY_HABIT_PRESETS:
            btn = Button(text=preset["label"], size_hint_y=None, height=dp(44), font_size="16sp")
            btn.bind(on_release=lambda b, k=preset["key"]: self.select_habit(k))
            self.habit_dropdown.add_widget(btn)
        self.habit_btn.bind(on_release=self.habit_dropdown.open)
        habit_container.add_widget(habit_label)
        habit_container.add_widget(self.habit_btn)
        form_layout.add_widget(habit_container)

        # Schedule: interval vs clock time (stored values unchanged for voice_reminder_tick / JSON)
        trigger_type_container = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(50), spacing=dp(10))
        trigger_type_label = Label(
            text="When to remind:",
            font_size="20sp",
            color=(0.9, 0.9, 1, 1),
            halign="left",
            size_hint_x=0.32,
            text_size=(None, None),
        )
        self.trigger_type_dropdown = DropDown()
        self.trigger_type_btn = Button(
            text=_TRIGGER_LABELS["Every X Minutes"],
            size_hint_x=0.63,
            font_size="16sp",
            background_color=(0.3, 0.5, 0.8, 1.0),
            background_normal="",
            background_down="",
            color=(1, 1, 1, 1),
        )
        for stored, disp in (
            ("Every X Minutes", _TRIGGER_LABELS["Every X Minutes"]),
            ("Specific Time", _TRIGGER_LABELS["Specific Time"]),
        ):
            btn = Button(text=disp, size_hint_y=None, height=dp(45), font_size="16sp")
            btn.bind(on_release=lambda b, s=stored: self.select_trigger_type(s))
            self.trigger_type_dropdown.add_widget(btn)
        self.trigger_type_btn.bind(on_release=self.trigger_type_dropdown.open)
        trigger_type_container.add_widget(trigger_type_label)
        trigger_type_container.add_widget(self.trigger_type_btn)
        form_layout.add_widget(trigger_type_container)
        
        # Trigger Time section (shown when "Specific Time" is selected)
        time_container = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(50), spacing=dp(10))
        time_label = Label(
            text="Time (e.g. 2:30):",
            font_size="20sp",
            color=(0.9, 0.9, 1, 1),
            halign="left",
            size_hint_x=0.25,
            text_size=(None, None)
        )
        self.time_input = TextInput(
            text="12:00",
            multiline=False,
            size_hint_x=0.2,
            font_size="18sp",
            background_color=(0.15, 0.15, 0.20, 1.0),
            foreground_color=(1, 1, 1, 1),
            padding=dp(10),
            disabled=True,
        )
        # AM/PM selector
        self.am_pm_dropdown = DropDown()
        self.am_pm_btn = Button(
            text="PM",
            size_hint_x=0.15,
            font_size="18sp",
            background_color=(0.3, 0.5, 0.8, 1.0),
            background_normal='',
            background_down='',
            color=(1, 1, 1, 1),
            disabled=True,
        )
        for option in ["AM", "PM"]:
            btn = Button(text=option, size_hint_y=None, height=dp(45), font_size="16sp")
            btn.bind(on_release=lambda b, opt=option: self._select_am_pm(opt))
            self.am_pm_dropdown.add_widget(btn)
        self.am_pm_btn.bind(on_release=self.am_pm_dropdown.open)
        time_container.add_widget(time_label)
        time_container.add_widget(self.time_input)
        time_container.add_widget(self.am_pm_btn)
        time_container.add_widget(Widget())  # Spacer
        form_layout.add_widget(time_container)
        
        # Interval Minutes section (shown when "Every X Minutes" is selected)
        interval_container = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(50), spacing=dp(10))
        interval_label = Label(
            text="Every (minutes):",
            font_size="20sp",
            color=(0.9, 0.9, 1, 1),
            halign="left",
            size_hint_x=0.3,
            text_size=(None, None)
        )
        self.interval_input = TextInput(
            text="30",
            multiline=False,
            size_hint_x=0.3,
            font_size="18sp",
            background_color=(0.15, 0.15, 0.20, 1.0),
            foreground_color=(1, 1, 1, 1),
            padding=dp(10),
            disabled=False,
        )
        interval_container.add_widget(interval_label)
        interval_container.add_widget(self.interval_input)
        interval_container.add_widget(Widget())  # Spacer
        form_layout.add_widget(interval_container)
        
        # Repeat (only used for "At a specific time" in the voice assistant)
        self.repeat_container = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(50), spacing=dp(10))
        repeat_label = Label(
            text="Repeat (clock time):",
            font_size="18sp",
            color=(0.9, 0.9, 1, 1),
            halign="left",
            size_hint_x=0.32,
            text_size=(None, None),
        )
        self.repeat_dropdown = DropDown()
        self.repeat_btn = Button(
            text="daily",
            size_hint_x=0.35,
            font_size="18sp",
            background_color=(0.3, 0.5, 0.8, 1.0),
            background_normal='',
            background_down='',
            color=(1, 1, 1, 1)
        )
        for option in ["once", "daily", "weekdays", "weekends", "weekly"]:
            btn = Button(text=option, size_hint_y=None, height=dp(45), font_size="16sp")
            btn.bind(on_release=lambda b, opt=option: self.select_repeat(opt))
            self.repeat_dropdown.add_widget(btn)
        self.repeat_btn.bind(on_release=self.repeat_dropdown.open)
        self.repeat_container.add_widget(repeat_label)
        self.repeat_container.add_widget(self.repeat_btn)
        self.repeat_container.add_widget(Widget())
        form_layout.add_widget(self.repeat_container)

        # Active toggle section (must be ON for reminder to trigger at set time)
        active_container = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(50), spacing=dp(10))
        active_label = Label(
            text="Reminder active:",
            font_size="20sp",
            color=(0.9, 0.9, 1, 1),
            halign="left",
            size_hint_x=0.45,
            text_size=(None, None),
        )
        self.is_active_toggle = ToggleButton(
            text="Active",
            state="down",
            size_hint_x=0.25,
            font_size="18sp",
            background_color=(0.2, 0.7, 0.3, 1.0),
            background_normal='',
            background_down='',
            color=(1, 1, 1, 1)
        )
        active_container.add_widget(active_label)
        active_container.add_widget(self.is_active_toggle)
        active_container.add_widget(Widget())  # Spacer
        form_layout.add_widget(active_container)
        
        # Error message
        self.error_label = Label(
            text="",
            font_size="16sp",
            color=(1, 0.3, 0.3, 1),
            halign="center",
            size_hint_y=None,
            height=dp(30),
            text_size=(None, None)
        )
        form_layout.add_widget(self.error_label)
        
        # Add form to scroll view
        self.scroll.add_widget(form_layout)
        main_layout.add_widget(self.scroll)
        
        # Fixed bottom buttons with better styling
        button_container = BoxLayout(
            orientation="horizontal",
            spacing=dp(15),
            padding=dp(15),
            size_hint=(1, 0.12),
            pos_hint={"x": 0, "y": 0}
        )
        
        cancel_btn = Button(
            text="Cancel",
            size_hint_x=0.28,
            font_size="18sp",
            bold=True,
            background_color=(0.5, 0.5, 0.5, 1.0),
            background_normal='',
            background_down='',
            color=(1, 1, 1, 1)
        )
        cancel_btn.bind(on_release=self.cancel)
        button_container.add_widget(cancel_btn)
        
        test_btn = Button(
            text="Test in 10 sec",
            size_hint_x=0.28,
            font_size="18sp",
            bold=True,
            background_color=(0.6, 0.4, 0.9, 1.0),
            background_normal='',
            background_down='',
            color=(1, 1, 1, 1)
        )
        test_btn.bind(on_release=self.test_in_10_seconds)
        button_container.add_widget(test_btn)
        
        save_btn = Button(
            text="Save",
            size_hint_x=0.28,
            font_size="18sp",
            bold=True,
            background_color=(0.2, 0.8, 0.4, 1.0),
            background_normal='',
            background_down='',
            color=(1, 1, 1, 1)
        )
        save_btn.bind(on_release=self.save)
        button_container.add_widget(save_btn)
        
        main_layout.add_widget(button_container)
        
        self.add_widget(main_layout)
        self.select_trigger_type("Every X Minutes")

    def select_habit(self, key):
        """User picked a built-in healthy habit preset."""
        self.habit_dropdown.dismiss()
        self._habit_key = key
        self.habit_btn.text = _habit_preset_by_key(key)["label"]

    def setup_for_new(self):
        """Setup screen for creating a new reminder."""
        self.title_label.text = "New Reminder"
        self.reminder_index = None
        self._habit_key = HEALTHY_HABIT_PRESETS[0]["key"]
        self.habit_btn.text = _habit_preset_by_key(self._habit_key)["label"]
        self._reminder_icon_text = None
        self.interval_input.text = "30"
        self.time_input.text = "12:00"
        self.am_pm_btn.text = "PM"
        self.repeat_btn.text = "daily"
        self.is_active_toggle.state = "down"
        self.error_label.text = ""
        self.select_trigger_type("Every X Minutes")

    def setup_for_edit(self, index):
        """Setup screen for editing an existing reminder."""
        self.title_label.text = "Edit Reminder"
        self.reminder_index = index
        reminders = config_manager.get("reminders", [])
        if 0 <= index < len(reminders):
            reminder = reminders[index]
            preset = _habit_preset_for_reminder(reminder)
            self._habit_key = preset["key"]
            self.habit_btn.text = preset["label"]
            self._reminder_icon_text = reminder.get("icon")
            trigger_type = reminder.get("trigger_type", "Specific Time")
            self.select_trigger_type(trigger_type)
            if trigger_type == "Every X Minutes":
                self.interval_input.text = str(reminder.get("interval_minutes", 30))
            else:
                stored_time = reminder.get("trigger_time", "12:00")
                display_12h, display_am_pm = self._time_24h_to_12h_display(stored_time)
                self.time_input.text = display_12h
                self.am_pm_btn.text = display_am_pm
            self.repeat_btn.text = reminder.get("repeat_settings", "daily")
            self.is_active_toggle.state = "down" if reminder.get("is_active", True) else "normal"
        self.error_label.text = ""
        if hasattr(self, "scroll"):
            Clock.schedule_once(lambda dt: setattr(self.scroll, "scroll_y", 1.0), 0.1)
    
    def _select_am_pm(self, option):
        """Handle AM/PM selection."""
        self.am_pm_dropdown.dismiss()
        self.am_pm_btn.text = option

    def _time_12h_to_24h(self, time_str_12h, am_pm):
        """Convert 12-hour time string + AM/PM to 24-hour HH:MM string."""
        try:
            parts = time_str_12h.strip().split(":")
            if len(parts) != 2:
                return None
            hour, minute = int(parts[0]), int(parts[1])
            if not (1 <= hour <= 12 and 0 <= minute < 60):
                return None
            if am_pm == "PM":
                hour = 12 if hour == 12 else hour + 12
            else:  # AM
                hour = 0 if hour == 12 else hour
            return f"{hour:02d}:{minute:02d}"
        except (ValueError, IndexError):
            return None

    def _time_24h_to_12h_display(self, time_str_24h):
        """Convert 24-hour HH:MM string to (12h_display, AM_or_PM)."""
        try:
            parts = time_str_24h.strip().split(":")
            if len(parts) != 2:
                return "12:00", "PM"
            hour, minute = int(parts[0]), int(parts[1])
            hour = hour % 24
            if hour == 0:
                return f"12:{minute:02d}", "AM"
            if hour == 12:
                return f"12:{minute:02d}", "PM"
            if hour < 12:
                return f"{hour}:{minute:02d}", "AM"
            return f"{hour - 12}:{minute:02d}", "PM"
        except (ValueError, IndexError):
            return "12:00", "PM"

    def select_trigger_type(self, stored):
        """Every X minutes vs clock time — must match JSON values expected by voice_reminder_tick."""
        self.trigger_type_dropdown.dismiss()
        self._trigger_type_stored = stored
        self.trigger_type_btn.text = _TRIGGER_LABELS.get(stored, stored)
        if stored == "Every X Minutes":
            self.time_input.disabled = True
            self.am_pm_btn.disabled = True
            self.interval_input.disabled = False
            self.repeat_container.height = 0
            self.repeat_container.opacity = 0
            self.repeat_container.disabled = True
        else:
            self.time_input.disabled = False
            self.am_pm_btn.disabled = False
            self.interval_input.disabled = True
            self.repeat_container.height = dp(50)
            self.repeat_container.opacity = 1
            self.repeat_container.disabled = False

    def select_repeat(self, option):
        """Handle repeat selection."""
        self.repeat_dropdown.dismiss()
        self.repeat_btn.text = option

    def save(self, instance):
        """Save habit preset + schedule (same schema as voice assistant + homescreen)."""
        trigger_type = self._trigger_type_stored
        if trigger_type == "Every X Minutes":
            try:
                interval_minutes = int(self.interval_input.text.strip())
                if interval_minutes < 1 or interval_minutes > 1440:
                    raise ValueError
                trigger_time = None
            except ValueError:
                self.error_label.text = "Invalid interval (1-1440 minutes)"
                return
            repeat_settings = "daily"
        else:
            time_str = self.time_input.text.strip()
            am_pm = self.am_pm_btn.text
            if not time_str:
                self.error_label.text = "Trigger time is required"
                return
            trigger_time = self._time_12h_to_24h(time_str, am_pm)
            if trigger_time is None:
                self.error_label.text = "Invalid time (use e.g. 2:30 with AM/PM)"
                return
            interval_minutes = None
            repeat_settings = self.repeat_btn.text

        preset = _habit_preset_by_key(self._habit_key)
        legacy_icon = getattr(self, "_reminder_icon_text", None)
        if isinstance(legacy_icon, str):
            legacy_icon = legacy_icon.strip() or None

        reminders = config_manager.get("reminders", [])
        if self.reminder_index is not None and 0 <= self.reminder_index < len(reminders):
            existing_reminder = reminders[self.reminder_index]
            reminder_id = existing_reminder.get("id") or str(uuid.uuid4())
        else:
            reminder_id = str(uuid.uuid4())

        accent = [float(x) for x in preset["accent"][:4]]
        if len(accent) == 3:
            accent.append(1.0)

        reminder = {
            "id": reminder_id,
            "text": preset["text"],
            "icon": legacy_icon,
            "icon_path": preset.get("icon_path"),
            "action": preset.get("action"),
            "face_expression": None,
            "trigger_type": trigger_type,
            "trigger_time": trigger_time,
            "interval_minutes": interval_minutes,
            "repeat_settings": repeat_settings,
            "is_active": self.is_active_toggle.state == "down",
            "accent": accent,
            "mood": preset["mood"],
            "description": preset["description"],
        }

        if self.reminder_index is not None and 0 <= self.reminder_index < len(reminders):
            reminders[self.reminder_index] = reminder
        else:
            reminders.append(reminder)
        config_manager.set("reminders", reminders)
        self.error_label.text = ""
        self.manager.current = "reminders"

    def _build_reminder_dict_for_test(self):
        """Build a reminder dict from current form for 'Test in 10 sec' (no save)."""
        trigger_type = self._trigger_type_stored
        trigger_time = None
        interval_minutes = None
        repeat_settings = "daily"
        if trigger_type == "Every X Minutes":
            try:
                interval_minutes = int(self.interval_input.text.strip())
                interval_minutes = max(1, min(1440, interval_minutes))
            except ValueError:
                interval_minutes = 30
        else:
            time_str = self.time_input.text.strip()
            am_pm = self.am_pm_btn.text
            trigger_time = self._time_12h_to_24h(time_str, am_pm) if time_str else "12:00"
            repeat_settings = self.repeat_btn.text

        preset = _habit_preset_by_key(self._habit_key)
        accent = [float(x) for x in preset["accent"][:4]]
        if len(accent) == 3:
            accent.append(1.0)
        legacy_icon = getattr(self, "_reminder_icon_text", None)
        if isinstance(legacy_icon, str):
            legacy_icon = legacy_icon.strip() or None
        return {
            "id": str(uuid.uuid4()),
            "text": preset["text"],
            "icon": legacy_icon,
            "icon_path": preset.get("icon_path"),
            "action": preset.get("action"),
            "face_expression": None,
            "trigger_type": trigger_type,
            "trigger_time": trigger_time,
            "interval_minutes": interval_minutes,
            "repeat_settings": repeat_settings,
            "is_active": True,
            "accent": accent,
            "mood": preset["mood"],
            "description": preset["description"],
        }

    def test_in_10_seconds(self, instance):
        """Schedule this reminder to appear on the homescreen in 10 seconds (for testing)."""
        reminder = self._build_reminder_dict_for_test()
        from_screen = self.manager.current  # Return here after 1 minute
        self.error_label.text = "Switching to Home in 10 sec..."
        def _show_test_reminder(dt):
            self.error_label.text = ""
            # If a real reminder is set for current time, show that instead of the test reminder
            now = datetime.now()
            current_time = now.strftime("%H:%M")
            reminders = config_manager.get("reminders", [])
            real_reminder = None
            homescreen = self.manager.get_screen("homescreen") if self.manager.has_screen("homescreen") else None
            for r in reminders:
                if not r.get("is_active", True):
                    continue
                if r.get("trigger_type") != "Specific Time":
                    continue
                raw = r.get("trigger_time", "")
                normalized = (
                    homescreen._normalize_trigger_time(raw)
                    if homescreen and hasattr(homescreen, "_normalize_trigger_time")
                    else raw
                )
                if normalized == current_time:
                    real_reminder = r
                    break
            display_reminder = real_reminder if real_reminder else reminder
            app = App.get_running_app()
            if self.manager.has_screen("voice") and getattr(app, "engine", None):
                self.manager.current = "voice"
                app.engine.fire_reminder_display(display_reminder, return_screen=from_screen)
            else:
                if not homescreen:
                    return
                homescreen._return_screen = from_screen
                self.manager.current = "homescreen"
                if hasattr(homescreen, "trigger_reminder"):
                    homescreen.trigger_reminder(display_reminder, is_real_trigger=False)
        Clock.schedule_once(_show_test_reminder, 10.0)

    def cancel(self, instance):
        """Cancel editing and return to reminders screen."""
        self.manager.current = "reminders"


class RemindersScreen(Screen):
    """List healthy-habit reminders; add/edit uses preset habits plus interval or clock time."""
    
    def __init__(self, **kwargs):
        """Initialize the reminders screen."""
        super().__init__(**kwargs)
        self.setup_ui()
        self.load_reminders()
    
    def on_pre_enter(self, *args):
        """Refresh reminders when screen becomes visible."""
        self.load_reminders()
    
    def setup_ui(self):
        """Build the reminders management UI."""
        layout = FloatLayout()
        
        # Background
        with layout.canvas.before:
            Color(0.05, 0.05, 0.10, 1.0)
            Rectangle(pos=layout.pos, size=Window.size)
        
        # Title
        title = Label(
            text="Reminders",
            font_size="32sp",
            bold=True,
            color=(1, 1, 1, 1),
            halign="center",
            valign="top",
            size_hint=(1, 0.10),
            pos_hint={"x": 0, "y": 0.90}
        )
        layout.add_widget(title)
        
        # ScrollView wrapping the reminder list (fits 800x480; scroll when many reminders)
        scroll = ScrollView(
            size_hint=(1, 0.58),
            pos_hint={"x": 0, "y": 0.32},
            do_scroll_x=False,
            do_scroll_y=True,
            bar_width=dp(8),
            scroll_type=["bars", "content"]
        )
        self.reminder_list = BoxLayout(
            orientation="vertical",
            spacing=dp(10),
            padding=dp(12),
            size_hint_y=None,
            size_hint_x=1
        )
        self.reminder_list.bind(minimum_height=self.reminder_list.setter("height"))
        scroll.add_widget(self.reminder_list)
        layout.add_widget(scroll)
        
        # Bottom bar: Add + Home
        bottom = BoxLayout(
            orientation="horizontal",
            size_hint=(1, 0.14),
            pos_hint={"x": 0, "y": 0.06},
            padding=dp(20),
            spacing=dp(20)
        )
        add_btn = Button(
            text="+ Add New Reminder",
            size_hint_x=0.45,
            font_size="20sp",
            bold=True,
            background_color=(0.2, 0.75, 0.4, 1.0),
            background_normal='',
            background_down='',
            color=(1, 1, 1, 1)
        )
        add_btn.bind(on_release=self.show_add_dialog)
        bottom.add_widget(add_btn)
        home_btn = Button(
            text="Return Home",
            size_hint_x=0.45,
            font_size="20sp",
            bold=True,
            background_color=(0.35, 0.5, 0.8, 1.0),
            background_normal='',
            background_down='',
            color=(1, 1, 1, 1)
        )
        home_btn.bind(on_release=self.return_home)
        bottom.add_widget(home_btn)
        layout.add_widget(bottom)
        
        self.add_widget(layout)
    
    def load_reminders(self):
        """Load and display all reminders."""
        self.reminder_list.clear_widgets()
        reminders = config_manager.get("reminders", [])
        
        if not reminders:
            empty = Label(
                text="No reminders yet.\nTap '+ Add New Reminder' to create one.",
                font_size="20sp",
                color=(0.7, 0.75, 0.9, 1),
                halign="center",
                size_hint_y=None,
                height=dp(80),
                text_size=(None, None)
            )
            self.reminder_list.add_widget(empty)
            return
        for i, reminder in enumerate(reminders):
            reminder_widget = self.create_reminder_widget(reminder, i)
            self.reminder_list.add_widget(reminder_widget)
    
    def create_reminder_widget(self, reminder, index):
        """Create a card-style widget for displaying a reminder."""
        is_active = reminder.get("is_active", True)
        text = reminder.get("text", "Untitled") or "Untitled"
        icon = reminder.get("icon", "") or ""
        trigger_type = reminder.get("trigger_type", "Specific Time")
        trigger_time = reminder.get("trigger_time", "")
        interval_min = reminder.get("interval_minutes")
        repeat = reminder.get("repeat_settings", "daily")
        
        # Time/subtitle line
        if trigger_type == "Every X Minutes" and interval_min:
            time_str = f"Every {interval_min} min · {repeat}"
        else:
            time_str = f"{trigger_time} · {repeat}" if trigger_time else repeat
        status = "ON" if is_active else "OFF"
        status_color = (0.2, 0.8, 0.3, 1) if is_active else (0.5, 0.5, 0.5, 1)
        
        card = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            size_hint_x=1,
            height=dp(108),
            spacing=dp(4),
            padding=dp(10)
        )
        with card.canvas.before:
            Color(0.12, 0.12, 0.18, 1.0)
            rect = RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(10)])
        def _update_card_rect(w, *args):
            rect.pos = w.pos
            rect.size = w.size
        card.bind(pos=_update_card_rect, size=_update_card_rect)
        
        # Top row: title (wraps) + status
        row1 = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(8))
        title_label = Label(
            text=(f"{icon} {text}".strip() or "Untitled")[:60],
            font_size="18sp",
            bold=True,
            color=(1, 1, 1, 1),
            halign="left",
            valign="middle",
            size_hint_x=0.68,
            text_size=(None, None)
        )
        def _set_title_text_size(lbl, size):
            if size[0] > 1 and size[1] > 1:
                lbl.text_size = (size[0] - dp(4), None)
        title_label.bind(size=_set_title_text_size)
        status_label = Label(
            text=status,
            font_size="14sp",
            bold=True,
            color=status_color,
            halign="right",
            size_hint_x=0.22,
            text_size=(None, None)
        )
        row1.add_widget(title_label)
        row1.add_widget(status_label)
        card.add_widget(row1)
        
        # Second row: time + repeat (single line, truncate if needed)
        row2 = Label(
            text=time_str[:45] + ("…" if len(time_str) > 45 else ""),
            font_size="13sp",
            color=(0.75, 0.78, 0.9, 1),
            halign="left",
            size_hint_y=None,
            height=dp(20),
            text_size=(None, None)
        )
        card.add_widget(row2)
        
        # Button row
        btn_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(38), spacing=dp(6))
        edit_btn = Button(
            text="Edit",
            size_hint_x=0.28,
            font_size="14sp",
            background_color=(0.3, 0.5, 0.85, 1.0),
            background_normal='',
            background_down='',
            color=(1, 1, 1, 1)
        )
        edit_btn.bind(on_release=lambda b, idx=index: self.edit_reminder(idx))
        toggle_btn = Button(
            text="Toggle",
            size_hint_x=0.28,
            font_size="14sp",
            background_color=(0.4, 0.45, 0.55, 1.0),
            background_normal='',
            background_down='',
            color=(1, 1, 1, 1)
        )
        toggle_btn.bind(on_release=lambda b, idx=index: self.toggle_reminder(idx))
        delete_btn = Button(
            text="Delete",
            size_hint_x=0.28,
            font_size="14sp",
            background_color=(0.75, 0.25, 0.25, 1.0),
            background_normal='',
            background_down='',
            color=(1, 1, 1, 1)
        )
        delete_btn.bind(on_release=lambda b, idx=index: self.delete_reminder(idx))
        btn_row.add_widget(edit_btn)
        btn_row.add_widget(toggle_btn)
        btn_row.add_widget(delete_btn)
        card.add_widget(btn_row)
        
        return card
    
    def show_add_dialog(self, instance):
        """Navigate to edit screen to add a new reminder."""
        # Create a new reminder screen
        if "reminder_edit" not in [s.name for s in self.manager.screens]:
            self.manager.add_widget(ReminderEditScreen(name="reminder_edit", reminder_index=None))
        edit_screen = self.manager.get_screen("reminder_edit")
        edit_screen.setup_for_new()
        self.manager.current = "reminder_edit"
    
    def edit_reminder(self, index):
        """Navigate to edit screen to edit an existing reminder."""
        if "reminder_edit" not in [s.name for s in self.manager.screens]:
            self.manager.add_widget(ReminderEditScreen(name="reminder_edit", reminder_index=index))
        edit_screen = self.manager.get_screen("reminder_edit")
        edit_screen.setup_for_edit(index)
        self.manager.current = "reminder_edit"
    
    def toggle_reminder(self, index):
        """Toggle the active state of a reminder."""
        reminders = config_manager.get("reminders", [])
        if 0 <= index < len(reminders):
            reminders[index]["is_active"] = not reminders[index].get("is_active", True)
            config_manager.set("reminders", reminders)
            self.load_reminders()
    
    def delete_reminder(self, index):
        """Delete a reminder."""
        reminders = config_manager.get("reminders", [])
        if 0 <= index < len(reminders):
            reminders.pop(index)
            config_manager.set("reminders", reminders)
            self.load_reminders()
    
    def return_home(self, instance):
        """Navigate back to homescreen."""
        self.manager.current = app_main_nav_screen(self.manager)

# ============================================================================
# MAIN APPLICATION
# ============================================================================

