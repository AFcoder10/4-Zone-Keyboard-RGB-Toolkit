# core/config.py

# Effect Types
EFFECT_TYPE_SOFTWARE = "software"
EFFECT_TYPE_HARDWARE = "hardware"
EFFECT_TYPE_EXTERNAL = "external"

SOFTWARE_MODES = [
    "Smooth Wave",
    "Lightning",
    "Party",
    "Realistic Fire",
    "Scanner (Cylon)",
    "Aurora Borealis",
    "Meteor Shower",
    "Ambient Screen Color",
    "Battery Visualizer",
    "Mouse-Reactive Aura",
    "Pomodoro Timer",
    "Live Audio Visualizer",
    "Temperature Mode",
    "Reactive Typing",
]

HARDWARE_MODES = ["Off", "Static", "Breath", "Smooth", "Wave"]

DEFAULT_CONTROL_SETTINGS = {
    "brightness": 100,
    "speed": 20,
    "storm_intensity": 50,
    "vibrance": 15,
    "ambient_fps": 30,
    "ambient_full_screen": False,
    "flicker": 0,
    "wave_fill": False,
    "scanner_rainbow": False,
    "reactive_rainbow": False,
    "smooth_wave_palette": "RGBW",
    "wave_direction": "left",
    "smooth_wave_direction": "left",
    "reactive_style": "Fade",
}

# UI Metadata - Hints for the main UI on which controls to show for which effect
EFFECT_METADATA = {
    "Smooth Wave": {"type": EFFECT_TYPE_SOFTWARE, "has_direction": True, "has_palette": True, "has_speed": True, "has_flicker": True},
    "Lightning": {"type": EFFECT_TYPE_SOFTWARE, "has_storm": True, "has_speed": True, "has_colors": True},
    "Reactive Typing": {"type": EFFECT_TYPE_SOFTWARE, "has_style": True, "has_rainbow": True, "has_speed": True, "has_colors": True},
    "Party": {"type": EFFECT_TYPE_SOFTWARE, "has_speed": True, "has_flicker": True},
    "Realistic Fire": {"type": EFFECT_TYPE_SOFTWARE, "has_speed": True},
    "Scanner (Cylon)": {"type": EFFECT_TYPE_SOFTWARE, "has_speed": True, "has_rainbow": True, "has_colors": True},
    "Aurora Borealis": {"type": EFFECT_TYPE_SOFTWARE, "has_speed": True, "has_flicker": True},
    "Meteor Shower": {"type": EFFECT_TYPE_SOFTWARE, "has_speed": True, "has_colors": True},
    "Ambient Screen Color": {"type": EFFECT_TYPE_SOFTWARE, "has_ambient_fps": True, "has_vibrance": True},
    "Battery Visualizer": {"type": EFFECT_TYPE_SOFTWARE},
    "Mouse-Reactive Aura": {"type": EFFECT_TYPE_SOFTWARE, "has_speed": True, "has_colors": True},
    "Pomodoro Timer": {"type": EFFECT_TYPE_SOFTWARE},
    "Live Audio Visualizer": {"type": EFFECT_TYPE_EXTERNAL, "has_speed": True, "has_flicker": True, "has_colors": True},
    "Temperature Mode": {"type": EFFECT_TYPE_EXTERNAL, "has_speed": True},
}

# General Constants
ZONE_COUNT = 4
COLOR_LENGTH = 12 # 4 zones * 3 (RGB)
DEFAULT_FPS = 30
