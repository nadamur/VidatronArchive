"""
Widgets
=======
Custom UI widgets for the Vidatron application.
"""

from kivy.clock import Clock
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle, Ellipse, Line, Rectangle
from kivy.metrics import dp
from math import sin, pi


class Face(Widget):
    """
    Animated robot face widget.
    Displays eyes and mouth with various moods and expressions.
    """
    
    def __init__(self, **kwargs):
        """Initialize the face widget with animation."""
        super().__init__(**kwargs)
        self.t = 0.0  # Animation time counter
        self.accent = (0.10, 0.90, 1.00, 1.0)  # Accent color (RGBA)
        self.mood = "happy"  # Current mood/expression
        self.selected_eyes = None  # Custom eyes selection (nullable)
        self.selected_mouth = None  # Custom mouth selection (nullable)
        Clock.schedule_interval(self._tick, 1/60)  # 60 FPS animation for smoother motion

    def set_style(self, accent, mood):
        """
        Update face style with accent color and mood.
        
        Args:
            accent: Tuple of (r, g, b, a) values for accent color
            mood: String mood identifier (happy, calm, wink, focused, thinking, speaking)
        """
        self.accent = accent
        self.mood = mood

    def set_customization(self, eyes=None, mouth=None):
        """
        Set custom eyes and mouth selections.
        
        Args:
            eyes: Optional string identifier for eyes style (nullable)
            mouth: Optional string identifier for mouth style (nullable)
        """
        self.selected_eyes = eyes
        self.selected_mouth = mouth

    def _tick(self, dt):
        """Animation tick - called every frame."""
        self.t += dt
        self._draw()

    def _draw(self):
        """Draw the face with current style and animation state."""
        self.canvas.clear()
        x, y = self.pos
        w, h = self.size

        r, g, b, a = self.accent
        # Pulsing effect for accent color
        pulse = 0.55 + 0.45*sin(2*pi*(self.t % 3.0)/3.0)

        pad = 16
        cx, cy = x + pad, y + pad
        cw, ch = w - 2*pad, h - 2*pad

        # Base color derived from accent
        base = (0.07 + r*0.70, 0.07 + g*0.70, 0.07 + b*0.70, 1.0)

        # Eye positioning
        eye_y = cy + ch*0.60
        eye_r = min(cw, ch)*0.095
        lx = cx + cw*0.35 - eye_r
        rx = cx + cw*0.65 - eye_r

        # Pupil wandering animation
        wander = 0.10*sin(2*pi*(self.t % 4.5)/4.5)
        pupil_dx = eye_r*(0.18*wander)
        pupil_dy = eye_r*(0.10*sin(2*pi*(self.t % 5.5)/5.5))

        # Mood-based pupil adjustments
        if self.mood == "focused":
            pupil_dx -= eye_r*0.25
        if self.mood == "happy":
            pupil_dx += eye_r*0.08
        if self.mood == "thinking":
            pupil_dx -= eye_r*0.08
            pupil_dy -= eye_r*0.12

        # Blink animation
        blink = 0.0
        phase = (self.t % 4.0)
        if 3.82 <= phase <= 4.0:
            p = (phase - 3.82)/0.18
            blink = sin(p*pi)

        # Wink animation (for wink mood)
        wink = 0.0
        if self.mood == "wink":
            p2 = (self.t % 2.4)
            if 2.05 <= p2 <= 2.4:
                q = (p2 - 2.05)/0.35
                wink = sin(q*pi)

        # Mouth positioning
        mouth_w = cw*0.40
        mouth_h = ch*0.12
        mx = cx + (cw-mouth_w)/2
        my = cy + ch*0.25

        with self.canvas:
            # Background
            Color(0.02, 0.02, 0.04, 1.0)
            RoundedRectangle(pos=(x, y), size=(w, h), radius=[22])

            # Accent glow
            Color(r, g, b, 0.30 + 0.35*pulse)
            RoundedRectangle(pos=(cx-10, cy-10), size=(cw+20, ch+20), radius=[26])

            # Face base
            Color(*base)
            RoundedRectangle(pos=(cx, cy), size=(cw, ch), radius=[26])

            # Face border
            Color(1, 1, 1, 0.18)
            Line(rounded_rectangle=(cx, cy, cw, ch, 26), width=2)

            # Eyes (white sclera) - apply customization
            # Only draw eyes if not None
            if self.selected_eyes is not None:
                eye_scale = 1.0
                eye_offset_y = 0.0
                
                # Apply eye style customization (at least 3 options)
                if self.selected_eyes == "Round":
                    eye_scale = 1.0  # Default round
                elif self.selected_eyes == "Oval":
                    eye_scale = 1.2  # Wider oval
                    eye_offset_y = -eye_r * 0.1
                elif self.selected_eyes == "Narrow":
                    eye_scale = 0.85  # Narrower
                elif self.selected_eyes == "Wide":
                    eye_scale = 1.3  # Very wide
                    eye_offset_y = -eye_r * 0.15
                elif self.selected_eyes == "Small":
                    eye_scale = 0.7  # Smaller eyes
                
                Color(1, 1, 1, 0.96)
                eye_w = eye_r * 2 * eye_scale
                eye_h = eye_r * 2
                Ellipse(pos=(lx + (eye_r*2 - eye_w)/2, eye_y-eye_r + eye_offset_y), size=(eye_w, eye_h))
                Ellipse(pos=(rx + (eye_r*2 - eye_w)/2, eye_y-eye_r + eye_offset_y), size=(eye_w, eye_h))

                # Pupils
                pr = eye_r*0.35
                Color(0.05, 0.06, 0.08, 1.0)
                Ellipse(pos=(lx+eye_r-pr+pupil_dx, eye_y-pr+pupil_dy), size=(pr*2, pr*2))
                Ellipse(pos=(rx+eye_r-pr+pupil_dx, eye_y-pr+pupil_dy), size=(pr*2, pr*2))

            # Eyelids for blink/wink (only if eyes are drawn)
            if self.selected_eyes is not None and (blink > 0.0 or wink > 0.0):
                Color(*base)
                eh_l = (eye_r*2)*(max(blink, wink)*0.95)
                RoundedRectangle(pos=(lx-2, eye_y-eh_l/2), size=(eye_r*2+4, eh_l), radius=[10])
                if blink > 0.0:
                    eh_r = (eye_r*2)*(blink*0.95)
                    RoundedRectangle(pos=(rx-2, eye_y-eh_r/2), size=(eye_r*2+4, eh_r), radius=[10])

            # Mouth (varies by mood and customization)
            # Only draw mouth if not None
            if self.selected_mouth is not None:
                Color(1, 1, 1, 0.90)
                
                # Apply mouth style customization if set (at least 3 options)
                mouth_style = self.selected_mouth
                
                if mouth_style == "Wide":
                    mouth_w = cw * 0.50  # Wider mouth
                elif mouth_style == "Small":
                    mouth_w = cw * 0.30  # Smaller mouth
                elif mouth_style == "Expressive":
                    mouth_w = cw * 0.45  # Slightly wider
                elif mouth_style == "Neutral":
                    mouth_w = cw * 0.35  # Neutral size
                elif mouth_style in ("Curved", "Smile"):
                    mouth_w = cw * 0.42  # Curved / smile style
                else:
                    mouth_w = cw * 0.40  # Default (Round or unknown)
                
                mx = cx + (cw-mouth_w)/2
                
                # Draw mouth based on mood (or use default if no customization)
                if self.mood == "speaking":
                    # Smoothed talking mouth with layered frequencies to reduce robotic motion.
                    talk_base = 0.5 + 0.5 * sin(2 * pi * (self.t * 2.2))
                    talk_detail = 0.5 + 0.5 * sin(2 * pi * (self.t * 4.6 + 0.17))
                    talk = (0.78 * talk_base) + (0.22 * talk_detail)
                    # Ease the envelope so open/close transitions are softer.
                    talk_eased = talk * talk * (3.0 - 2.0 * talk)
                    open_h = mouth_h * (0.28 + 0.90 * talk_eased)
                    # Lower jaw effect: shift mouth downward as it opens.
                    mouth_y = my + mouth_h * (0.08 - 0.22 * talk_eased)
                    RoundedRectangle(
                        pos=(mx + mouth_w * 0.16, mouth_y),
                        size=(mouth_w * 0.68, open_h),
                        radius=[dp(7 + 4 * talk_eased)],
                    )
                elif self.mood == "thinking":
                    # Flat mouth + animated thought bubbles.
                    Line(
                        points=[mx + mouth_w * 0.16, my + mouth_h * 0.24, mx + mouth_w * 0.84, my + mouth_h * 0.24],
                        width=6,
                        cap="round",
                    )
                    # Bubble chain in the top-right corner, with gentle float.
                    corner_x = cx + cw * 0.84
                    corner_y = cy + ch * 0.82
                    bubble_specs = (
                        (-cw * 0.08, -ch * 0.11, max(dp(2.5), mouth_h * 0.15), 0.00),
                        (-cw * 0.03, -ch * 0.05, max(dp(3.5), mouth_h * 0.20), 0.20),
                        (0.00, 0.00, max(dp(5.5), mouth_h * 0.30), 0.42),
                    )
                    for dx, dy, base_r, phase_offset in bubble_specs:
                        phase = (self.t * 0.95) - phase_offset
                        wave = 0.5 + 0.5 * sin(2 * pi * phase)
                        wave_eased = wave * wave * (3.0 - 2.0 * wave)
                        bubble_r = base_r * (0.92 + 0.15 * wave_eased)
                        bubble_y = corner_y + dy + (dp(2.5) * wave_eased)
                        bubble_x = corner_x + dx + (dp(0.8) * sin(2 * pi * (phase * 0.7)))
                        Ellipse(
                            pos=(bubble_x - bubble_r, bubble_y - bubble_r),
                            size=(bubble_r * 2, bubble_r * 2),
                        )
                elif self.mood in ("happy", "wink"):
                    # Smile
                    Line(bezier=[mx, my+mouth_h*0.42, mx+mouth_w*0.25, my, mx+mouth_w*0.75, my, mx+mouth_w, my+mouth_h*0.42],
                         width=7, cap="round")
                elif self.mood == "calm":
                    # Neutral line
                    Line(points=[mx, my+mouth_h*0.25, mx+mouth_w, my+mouth_h*0.25], width=7, cap="round")
                else:
                    # Focused (slight curve)
                    Line(points=[mx+mouth_w*0.10, my+mouth_h*0.28, mx+mouth_w*0.92, my+mouth_h*0.34], width=7, cap="round")


class StickFigureIcon(Widget):
    """
    Kivy-drawn stick figure icon representing an action (e.g. drink, stretch).
    Uses the same colored background as the Face (accent-derived) so the area is not black.
    """
    def __init__(self, action="stretch", accent=(0.10, 0.90, 1.00, 1.0), **kwargs):
        super().__init__(**kwargs)
        self._action = action
        self._accent = accent if isinstance(accent, (tuple, list)) and len(accent) >= 4 else (0.10, 0.90, 1.00, 1.0)
        self.bind(size=self._draw, pos=self._draw)

    @property
    def action(self):
        return self._action

    @action.setter
    def action(self, value):
        if value != self._action:
            self._action = value
            self._draw()

    @property
    def accent(self):
        return self._accent

    @accent.setter
    def accent(self, value):
        if value != self._accent:
            self._accent = value if isinstance(value, (tuple, list)) and len(value) >= 4 else (0.10, 0.90, 1.00, 1.0)
            self._draw()

    def _draw(self, *args):
        self.canvas.clear()
        x, y = self.pos
        w, h = self.size
        if w <= 0 or h <= 0:
            return
        r, g, b, a = self._accent
        pad = 16
        cx, cy = x + pad, y + pad
        cw, ch = w - 2 * pad, h - 2 * pad
        base = (0.07 + r * 0.70, 0.07 + g * 0.70, 0.07 + b * 0.70, 1.0)
        # Same background as Face so it's a color, not black
        with self.canvas:
            Color(0.02, 0.02, 0.04, 1.0)
            RoundedRectangle(pos=(x, y), size=(w, h), radius=[22])
            Color(r, g, b, 0.55)
            RoundedRectangle(pos=(cx - 10, cy - 10), size=(cw + 20, ch + 20), radius=[26])
            Color(*base)
            RoundedRectangle(pos=(cx, cy), size=(cw, ch), radius=[26])
            Color(1, 1, 1, 0.18)
            Line(rounded_rectangle=(cx, cy, cw, ch, 26), width=2)
        # Stick figure on top
        def px(nx, ny):
            return (x + nx * w, y + ny * h)
        line_w = max(2, dp(4))
        if self._action == "drink":
            self._draw_drink(px, w, h, line_w)
        else:
            self._draw_stretch(px, w, h, line_w)

    def _draw_drink(self, px, w, h, line_w):
        """Stick figure with cup to mouth (drink water)."""
        cx, cy = 0.5, 0.5
        head_r = 0.08
        # Head
        self.canvas.add(Color(1, 1, 1, 0.95))
        self.canvas.add(Ellipse(pos=px(cx - head_r, cy + 0.28 - head_r), size=(2*head_r*w, 2*head_r*h)))
        # Body (neck to pelvis)
        self.canvas.add(Line(points=px(cx, cy + 0.20) + px(cx, cy - 0.12), width=line_w, cap="round"))
        # Arm with cup: shoulder -> elbow (near mouth) -> hand/cup
        self.canvas.add(Line(points=px(cx, cy + 0.14) + px(cx + 0.12, cy + 0.18) + px(cx + 0.18, cy + 0.22), width=line_w, cap="round"))
        # Cup (small rectangle at mouth level)
        cup_w, cup_h = 0.06 * w, 0.08 * h
        cup_x, cup_y = px(cx + 0.14, cy + 0.18)
        self.canvas.add(Rectangle(pos=(cup_x, cup_y), size=(cup_w, cup_h)))
        # Other arm down
        self.canvas.add(Line(points=px(cx, cy + 0.14) + px(cx - 0.08, cy - 0.05), width=line_w, cap="round"))
        # Legs
        self.canvas.add(Line(points=px(cx, cy - 0.12) + px(cx - 0.10, cy - 0.38), width=line_w, cap="round"))
        self.canvas.add(Line(points=px(cx, cy - 0.12) + px(cx + 0.10, cy - 0.38), width=line_w, cap="round"))

    def _draw_stretch(self, px, w, h, line_w):
        """Stick figure in side stretch pose (arm up, body bent)."""
        cx, cy = 0.5, 0.5
        head_r = 0.08
        # Head
        self.canvas.add(Color(1, 1, 1, 0.95))
        self.canvas.add(Ellipse(pos=px(cx - head_r, cy + 0.22 - head_r), size=(2*head_r*w, 2*head_r*h)))
        # Torso bent to left (viewer's left): upper then lower
        self.canvas.add(Line(points=px(cx, cy + 0.14) + px(cx - 0.06, cy + 0.02), width=line_w, cap="round"))
        self.canvas.add(Line(points=px(cx - 0.06, cy + 0.02) + px(cx - 0.04, cy - 0.14), width=line_w, cap="round"))
        # Arm up over head (stretch)
        self.canvas.add(Line(points=px(cx, cy + 0.14) + px(cx + 0.02, cy + 0.20) + px(cx + 0.14, cy + 0.24), width=line_w, cap="round"))
        # Arm at hip
        self.canvas.add(Line(points=px(cx - 0.06, cy + 0.02) + px(cx - 0.18, cy - 0.02), width=line_w, cap="round"))
        # Legs
        self.canvas.add(Line(points=px(cx - 0.04, cy - 0.14) + px(cx - 0.14, cy - 0.38), width=line_w, cap="round"))
        self.canvas.add(Line(points=px(cx - 0.04, cy - 0.14) + px(cx + 0.08, cy - 0.36), width=line_w, cap="round"))
