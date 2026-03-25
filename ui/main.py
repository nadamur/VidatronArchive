"""
Main Application
===============
Entry point for the Vidatron UI application.
"""

from kivy.app import App
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager

from config import config_manager
from screens import (
    WelcomeScreen,
    SetupFaceScreen,
    SetupFontScreen,
    SetupColorsScreen,
    Homescreen,
    SettingsScreen,
    RemindersScreen
)


class PreviewApp(App):
    """
    Main application class.
    Handles power-on cases:
    - First time setup: Shows setup screen
    - General startup: Boots directly to homescreen
    """
    
    def build(self):
        """Build the application with screen management."""
        Window.size = (800, 480)
        Window.minimum_width, Window.minimum_height = 800, 480
        
        # Screen manager for navigation
        sm = ScreenManager()
        
        # Add all screens
        sm.add_widget(WelcomeScreen(name="welcome"))
        sm.add_widget(SetupFaceScreen(name="setup_face"))
        sm.add_widget(SetupFontScreen(name="setup_font"))
        sm.add_widget(SetupColorsScreen(name="setup_colors"))
        sm.add_widget(Homescreen(name="homescreen"))
        sm.add_widget(SettingsScreen(name="settings"))
        sm.add_widget(RemindersScreen(name="reminders"))
        
        # Check if first-time setup is needed
        if not config_manager.get("first_time_setup_complete", False):
            # Power On Case: First time - show welcome screen
            sm.current = "welcome"
        else:
            # Power On Case: General startup - boot to homescreen
            sm.current = "homescreen"
        
        # Keyboard shortcuts for testing (GPIO simulation)
        # Only trigger shortcuts when NOT typing in a TextInput field
        def on_key(_window, _key, _sc, codepoint, _mods):
            # Check if any TextInput is currently focused
            # If so, ignore shortcuts to allow normal typing
            try:
                current_screen = sm.current_screen
                if current_screen:
                    # Check if any TextInput widget is focused
                    from kivy.uix.textinput import TextInput
                    for widget in current_screen.walk():
                        if isinstance(widget, TextInput) and widget.focus:
                            # A TextInput is focused - don't handle shortcuts
                            return
            except:
                pass  # If check fails, proceed with shortcuts
            
            # No TextInput is focused - handle shortcuts
            if codepoint == 's':
                # Open settings
                sm.current = "settings"
            elif codepoint == 'h':
                # Return to homescreen
                sm.current = "homescreen"
            elif codepoint == 'r':
                # Open reminders
                sm.current = "reminders"
            elif codepoint == 'd':
                # Dismiss reminder overlay (if on homescreen)
                if sm.current == "homescreen":
                    homescreen = sm.get_screen("homescreen")
                    if hasattr(homescreen, 'dismiss'):
                        homescreen.dismiss()
            elif codepoint == 'n':
                # Force next reminder (if on homescreen)
                if sm.current == "homescreen":
                    homescreen = sm.get_screen("homescreen")
                    if hasattr(homescreen, 'next_card'):
                        homescreen.next_card()
        
        Window.bind(on_key_down=on_key)
        
        return sm


if __name__ == "__main__":
    PreviewApp().run()
