"""
Widgets
=======
Custom UI widgets for the Vidatron application.
"""

from kivy.clock import Clock
from kivy.properties import ListProperty, StringProperty
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
                eye_h_mul = 1.0
                eye_offset_y = 0.0
                pr_mul = 1.0

                if self.selected_eyes == "Round":
                    pass
                elif self.selected_eyes == "Oval":
                    eye_scale = 1.35
                    eye_h_mul = 0.9
                    eye_offset_y = -eye_r * 0.12
                elif self.selected_eyes == "Narrow":
                    eye_scale = 0.56
                    eye_h_mul = 1.12
                    eye_offset_y = -eye_r * 0.04
                    pr_mul = 0.9
                elif self.selected_eyes == "Wide":
                    eye_scale = 1.42
                    eye_h_mul = 0.88
                    eye_offset_y = -eye_r * 0.1
                    pr_mul = 1.05
                elif self.selected_eyes == "Small":
                    eye_scale = 0.68
                    eye_h_mul = 0.68
                    pr_mul = 0.78

                Color(1, 1, 1, 0.96)
                eye_w = eye_r * 2 * eye_scale
                eye_h = eye_r * 2 * eye_h_mul
                Ellipse(pos=(lx + (eye_r * 2 - eye_w) / 2, eye_y - eye_r + eye_offset_y), size=(eye_w, eye_h))
                Ellipse(pos=(rx + (eye_r * 2 - eye_w) / 2, eye_y - eye_r + eye_offset_y), size=(eye_w, eye_h))

                # Pupils
                pr = eye_r * 0.35 * pr_mul
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
                    mouth_w = cw * 0.52
                elif mouth_style == "Small":
                    mouth_w = cw * 0.28
                elif mouth_style == "Neutral":
                    mouth_w = cw * 0.38
                elif mouth_style in ("Curved", "Smile", "Expressive"):
                    mouth_w = cw * 0.42
                else:
                    mouth_w = cw * 0.40
                
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
                    if mouth_style == "Neutral":
                        Line(
                            points=[mx, my + mouth_h * 0.26, mx + mouth_w, my + mouth_h * 0.26],
                            width=7,
                            cap="round",
                        )
                    else:
                        Line(
                            bezier=[
                                mx,
                                my + mouth_h * 0.42,
                                mx + mouth_w * 0.25,
                                my,
                                mx + mouth_w * 0.75,
                                my,
                                mx + mouth_w,
                                my + mouth_h * 0.42,
                            ],
                            width=7,
                            cap="round",
                        )
                elif self.mood == "calm":
                    # Neutral line
                    Line(points=[mx, my+mouth_h*0.25, mx+mouth_w, my+mouth_h*0.25], width=7, cap="round")
                else:
                    # Focused (slight curve)
                    Line(points=[mx+mouth_w*0.10, my+mouth_h*0.28, mx+mouth_w*0.92, my+mouth_h*0.34], width=7, cap="round")


class StickFigureIcon(Widget):
    """
    Kivy-drawn stick figure for a healthy-reminder action (drink, stretch, wave, …).
    Uses the same panel framing as Face; updates ~30 FPS when visible for simple motion.
    """

    action = StringProperty("stretch")
    accent = ListProperty([0.10, 0.90, 1.00, 1.0])

    def __init__(self, action="stretch", accent=(0.10, 0.90, 1.00, 1.0), **kwargs):
        ac = accent if isinstance(accent, (tuple, list)) and len(accent) >= 3 else [0.10, 0.90, 1.00, 1.0]
        if len(ac) == 3:
            ac = [*map(float, ac[:3]), 1.0]
        kwargs.setdefault("action", action)
        kwargs.setdefault("accent", [float(ac[i]) for i in range(4)])
        super().__init__(**kwargs)
        self._phase = 0.0
        self.bind(size=self._draw, pos=self._draw)
        self.bind(action=self._draw, accent=self._draw)
        Clock.schedule_interval(self._anim_tick, 1 / 30.0)

    def _anim_tick(self, dt):
        if self.opacity < 0.01:
            return
        self._phase += dt * 5.0
        self._draw()

    def _draw(self, *args):
        self.canvas.clear()
        x, y = self.pos
        w, h = self.size
        if w <= 0 or h <= 0:
            return
        ac = self.accent
        if len(ac) < 3:
            r, g, b, a = (0.10, 0.90, 1.00, 1.0)
        else:
            r, g, b = float(ac[0]), float(ac[1]), float(ac[2])
            a = float(ac[3] if len(ac) > 3 else 1.0)
        ph = self._phase
        pad = 16
        cx, cy = x + pad, y + pad
        cw, ch = w - 2 * pad, h - 2 * pad
        base = (0.07 + r * 0.70, 0.07 + g * 0.70, 0.07 + b * 0.70, 1.0)
        with self.canvas:
            Color(0.02, 0.02, 0.04, 1.0)
            RoundedRectangle(pos=(x, y), size=(w, h), radius=[22])
            Color(r, g, b, 0.55)
            RoundedRectangle(pos=(cx - 10, cy - 10), size=(cw + 20, ch + 20), radius=[26])
            Color(*base)
            RoundedRectangle(pos=(cx, cy), size=(cw, ch), radius=[26])
            Color(1, 1, 1, 0.18)
            Line(rounded_rectangle=(cx, cy, cw, ch, 26), width=2)

        def px(nx, ny):
            return (x + nx * w, y + ny * h)

        line_w = max(2, dp(4))
        act = (self.action or "wave").strip().lower()
        if act == "drink":
            self._draw_drink(px, w, h, line_w, ph)
        elif act == "stretch":
            self._draw_stretch(px, w, h, line_w, ph)
        elif act == "walk":
            self._draw_walk(px, w, h, line_w, ph)
        elif act == "think":
            self._draw_think(px, w, h, line_w, ph)
        else:
            self._draw_wave(px, w, h, line_w, ph)

    def _draw_drink(self, px, w, h, line_w, ph):
        """Stick figure bringing cup to mouth — sipping motion."""
        cx, cy = 0.5, 0.5
        head_r = 0.08
        lift = 0.035 * max(0.0, sin(ph))
        sway = 0.03 * sin(ph * 0.9)
        self.canvas.add(Color(1, 1, 1, 0.95))
        self.canvas.add(
            Ellipse(
                pos=px(cx - head_r + sway * 0.3, cy + 0.28 - head_r),
                size=(2 * head_r * w, 2 * head_r * h),
            )
        )
        self.canvas.add(Line(points=px(cx, cy + 0.20) + px(cx, cy - 0.12), width=line_w, cap="round"))
        # Shorter reach to cup (upper arm + forearm both pulled in vs original pose)
        ex0, ey0 = cx + 0.095 + sway, cy + 0.168 + lift
        ex1, ey1 = cx + 0.142 + sway * 1.05, cy + 0.202 + lift
        self.canvas.add(
            Line(points=px(cx, cy + 0.14) + px(ex0, ey0) + px(ex1, ey1), width=line_w, cap="round")
        )
        cup_w, cup_h = 0.06 * w, 0.08 * h
        cpx, cpy = px(ex0 - 0.015, ey0 - 0.018)
        self.canvas.add(Color(0.92, 0.94, 1.0, 0.95))
        self.canvas.add(Rectangle(pos=(cpx, cpy), size=(cup_w, cup_h)))
        self.canvas.add(Color(1, 1, 1, 0.95))
        self.canvas.add(Line(points=px(cx, cy + 0.14) + px(cx - 0.08, cy - 0.05), width=line_w, cap="round"))
        self.canvas.add(Line(points=px(cx, cy - 0.12) + px(cx - 0.10, cy - 0.38), width=line_w, cap="round"))
        self.canvas.add(Line(points=px(cx, cy - 0.12) + px(cx + 0.10, cy - 0.38), width=line_w, cap="round"))

    def _draw_stretch(self, px, w, h, line_w, ph):
        """Overhead stretch — reach up, slight torso bend, gentle knee flex."""
        cx, cy = 0.5, 0.5
        head_r = 0.075

        # Animate: reach upward + tiny torso sway
        stretch_u = 0.5 + 0.5 * sin(ph * 0.75)  # 0..1
        reach = 0.06 + 0.06 * stretch_u
        sway = 0.02 * sin(ph * 0.45)

        # Head
        self.canvas.add(Color(1, 1, 1, 0.95))
        self.canvas.add(
            Ellipse(
                pos=px(cx - head_r + sway * 0.4, cy + 0.245 - head_r),
                size=(2 * head_r * w, 2 * head_r * h),
            )
        )

        # Torso (slight forward curve)
        shoulder_y = cy + 0.14
        hip_y = cy - 0.12
        torso_x_top = cx + sway
        torso_x_bot = cx + sway * 0.5 + 0.02 * stretch_u
        self.canvas.add(
            Line(
                points=px(torso_x_top, shoulder_y) + px(torso_x_bot, hip_y),
                width=line_w,
                cap="round",
            )
        )

        # Arms:
        # 1) Overhead reaching arm (dominant)
        # Start both arms exactly at the same shoulder joint as the spine top.
        sh_x = torso_x_top
        sh_y = shoulder_y
        elbow_x = cx + 0.09 + sway * 0.15
        elbow_y = cy + 0.16 + reach * 0.55
        hand_x = cx + 0.135 + sway * 0.2
        hand_y = cy + 0.27 + reach
        self.canvas.add(
            Line(
                points=px(sh_x, sh_y)
                + px(elbow_x, elbow_y)
                + px(hand_x, hand_y),
                width=line_w,
                cap="round",
            )
        )
        # 2) Other arm down (supporting arm)
        other_elbow_x = cx - 0.03 + sway * 0.1
        other_elbow_y = cy + 0.08 + 0.01 * reach
        other_hand_x = cx - 0.09 + sway * 0.1
        other_hand_y = cy - 0.02 - 0.01 * reach
        self.canvas.add(
            Line(
                points=px(torso_x_top, shoulder_y)
                + px(other_elbow_x, other_elbow_y)
                + px(other_hand_x, other_hand_y),
                width=line_w,
                cap="round",
            )
        )

        # Legs: one more straight, one slightly flexing at knee/ankle
        hip_y2 = hip_y
        # Left leg (flex)
        # Start both legs at the spine bottom joint.
        left_hip_x = torso_x_bot
        left_knee_x = cx - 0.07 + sway * 0.05
        left_knee_y = cy - 0.26 + 0.06 * stretch_u
        left_foot_x = cx - 0.02 + sway * 0.08
        left_foot_y = cy - 0.40 + 0.02 * stretch_u
        self.canvas.add(
            Line(
                points=px(left_hip_x, hip_y2)
                + px(left_knee_x, left_knee_y)
                + px(left_foot_x, left_foot_y),
                width=line_w,
                cap="round",
            )
        )
        # Right leg (support)
        right_hip_x = torso_x_bot
        right_knee_x = cx + 0.02 + sway * 0.05
        right_knee_y = cy - 0.28 + 0.03 * stretch_u
        right_foot_x = cx + 0.08 + sway * 0.08
        right_foot_y = cy - 0.40 + 0.01 * stretch_u
        self.canvas.add(
            Line(
                points=px(right_hip_x, hip_y2)
                + px(right_knee_x, right_knee_y)
                + px(right_foot_x, right_foot_y),
                width=line_w,
                cap="round",
            )
        )

    def _draw_wave(self, px, w, h, line_w, ph):
        """Friendly wave for generic / custom reminders."""
        cx, cy = 0.5, 0.5
        head_r = 0.08
        wave = 0.38 * sin(ph * 2.2)
        self.canvas.add(Color(1, 1, 1, 0.95))
        self.canvas.add(Ellipse(pos=px(cx - head_r, cy + 0.25 - head_r), size=(2 * head_r * w, 2 * head_r * h)))
        self.canvas.add(Line(points=px(cx, cy + 0.17) + px(cx, cy - 0.12), width=line_w, cap="round"))
        # Left arm down
        self.canvas.add(Line(points=px(cx, cy + 0.12) + px(cx - 0.12, cy - 0.02), width=line_w, cap="round"))
        # Right arm: shoulder -> elbow (waves in horizontal plane — arc in y)
        elbow_x = cx + 0.11
        elbow_y = cy + 0.14 + 0.06 * wave
        hand_x = cx + 0.20 + 0.04 * sin(ph * 2.2 + 0.8)
        hand_y = cy + 0.18 + 0.10 * sin(ph * 2.2)
        self.canvas.add(
            Line(
                points=px(cx, cy + 0.12) + px(elbow_x, elbow_y) + px(hand_x, hand_y),
                width=line_w,
                cap="round",
            )
        )
        self.canvas.add(Line(points=px(cx, cy - 0.12) + px(cx - 0.10, cy - 0.38), width=line_w, cap="round"))
        self.canvas.add(Line(points=px(cx, cy - 0.12) + px(cx + 0.10, cy - 0.38), width=line_w, cap="round"))

    def _draw_walk(self, px, w, h, line_w, ph):
        """Walking pose with alternating arm/leg swing."""
        cx, cy = 0.5, 0.5
        head_r = 0.08
        swing = 0.11 * sin(ph * 1.8)
        bob = 0.018 * sin(ph * 3.6)

        # Head + torso
        self.canvas.add(Color(1, 1, 1, 0.95))
        self.canvas.add(
            Ellipse(
                pos=px(cx - head_r, cy + 0.25 - head_r + bob),
                size=(2 * head_r * w, 2 * head_r * h),
            )
        )
        shoulder = (cx, cy + 0.14 + bob)
        hip = (cx, cy - 0.12 + bob)
        self.canvas.add(Line(points=px(*shoulder) + px(*hip), width=line_w, cap="round"))

        # Arms: opposite swing for natural walk cycle
        l_hand = (cx - 0.11 - swing, cy + 0.02 + bob)
        r_hand = (cx + 0.11 + swing, cy + 0.02 + bob)
        self.canvas.add(Line(points=px(*shoulder) + px(*l_hand), width=line_w, cap="round"))
        self.canvas.add(Line(points=px(*shoulder) + px(*r_hand), width=line_w, cap="round"))

        # Legs: opposite swing with subtle knee bend
        l_knee = (cx - 0.03 - 0.45 * swing, cy - 0.26 + bob)
        l_foot = (cx - 0.09 - swing, cy - 0.40 + bob)
        r_knee = (cx + 0.03 + 0.45 * swing, cy - 0.26 + bob)
        r_foot = (cx + 0.09 + swing, cy - 0.40 + bob)
        self.canvas.add(Line(points=px(*hip) + px(*l_knee) + px(*l_foot), width=line_w, cap="round"))
        self.canvas.add(Line(points=px(*hip) + px(*r_knee) + px(*r_foot), width=line_w, cap="round"))

    def _draw_think(self, px, w, h, line_w, ph):
        """Thinking pose: visible hand-to-chin and classic thought bubble."""
        cx, cy = 0.5, 0.5
        head_r = 0.075

        # Keep motion subtle to avoid awkward full-body sway.
        bob = 0.006 * sin(ph * 1.2)

        # Head
        head_cx = cx
        head_cy = cy + 0.21 + bob
        self.canvas.add(Color(1, 1, 1, 0.95))
        self.canvas.add(
            Ellipse(
                pos=px(head_cx - head_r, head_cy - head_r),
                size=(2 * head_r * w, 2 * head_r * h),
            )
        )

        # Torso stays mostly upright.
        shoulder_y = head_cy - head_r * 0.72
        hip_y = cy - 0.12 + bob
        shoulder = (cx, shoulder_y)
        hip = (cx, hip_y)
        self.canvas.add(Line(points=px(*shoulder) + px(*hip), width=line_w, cap="round"))

        # Right arm: shoulder -> elbow -> hand on chin (explicit hand marker).
        chin_x = cx + 0.02
        chin_y = head_cy - head_r * 0.20
        elbow = (cx + 0.10, cy + 0.10 + bob)
        hand = (cx + 0.045, chin_y)
        self.canvas.add(
            Line(
                points=px(*shoulder) + px(*elbow) + px(*hand),
                width=line_w,
                cap="round",
            )
        )
        # Hand dot so it is clearly visible.
        self.canvas.add(Ellipse(pos=px(hand[0] - 0.012, hand[1] - 0.012), size=(0.024 * w, 0.024 * h)))

        # Left arm relaxed down.
        self.canvas.add(
            Line(
                points=px(*shoulder) + px(cx - 0.11, cy + 0.01 + bob),
                width=line_w,
                cap="round",
            )
        )

        # Legs stable.
        self.canvas.add(
            Line(
                points=px(*hip) + px(hip[0] - 0.07, cy - 0.22 + bob) + px(hip[0] - 0.05, cy - 0.36 + bob),
                width=line_w,
                cap="round",
            )
        )
        self.canvas.add(
            Line(
                points=px(*hip) + px(hip[0] + 0.07, cy - 0.22 + bob) + px(hip[0] + 0.05, cy - 0.36 + bob),
                width=line_w,
                cap="round",
            )
        )

        # Classic thought bubble: cloud-like circles + trailing dots.
        bubble_cx = cx + 0.24
        bubble_cy = cy + 0.31 + 0.008 * sin(ph * 1.3)
        self.canvas.add(Color(1, 1, 1, 0.92))
        self.canvas.add(Ellipse(pos=px(bubble_cx - 0.11, bubble_cy - 0.05), size=(0.14 * w, 0.08 * h)))
        self.canvas.add(Ellipse(pos=px(bubble_cx - 0.03, bubble_cy - 0.07), size=(0.16 * w, 0.10 * h)))
        self.canvas.add(Ellipse(pos=px(bubble_cx + 0.06, bubble_cy - 0.05), size=(0.14 * w, 0.08 * h)))
        self.canvas.add(Ellipse(pos=px(bubble_cx - 0.01, bubble_cy - 0.00), size=(0.20 * w, 0.10 * h)))

        self.canvas.add(Color(0.86, 0.90, 0.97, 0.85))
        self.canvas.add(Ellipse(pos=px(cx + 0.14, cy + 0.17), size=(0.028 * w, 0.020 * h)))
        self.canvas.add(Ellipse(pos=px(cx + 0.10, cy + 0.14), size=(0.020 * w, 0.015 * h)))
