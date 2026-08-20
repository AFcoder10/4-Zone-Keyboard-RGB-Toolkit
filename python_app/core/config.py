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
    "flicker": 0,
    "wave_fill": False,
    "scanner_rainbow": False,
    "reactive_rainbow": False,
    "smooth_wave_palette": "RGBW",
    "wave_direction": "left",
    "smooth_wave_direction": "left",
    "reactive_style": "Fade",
}

# Mode-by-mode specific default configuration values
DEFAULT_MODE_SETTINGS = {
    # Hardware Modes
    "Off": {
        "brightness": 0,
    },
    "Static": {
        "brightness": 100,
    },
    "Breath": {
        "brightness": 100,
        "speed": 20,
    },
    "Smooth": {
        "brightness": 100,
        "speed": 20,
    },
    "Wave": {
        "brightness": 100,
        "speed": 20,
        "wave_direction": "left",
        "wave_fill": False,
    },
    # Software Modes
    "Smooth Wave": {
        "brightness": 100,
        "speed": 20,
        "smooth_wave_direction": "left",
        "smooth_wave_palette": "RGBW",
        "flicker": 0,
    },
    "Lightning": {
        "brightness": 100,
        "speed": 20,
        "storm_intensity": 50,
    },
    "Party": {
        "brightness": 100,
        "speed": 20,
        "flicker": 0,
    },
    "Realistic Fire": {
        "brightness": 100,
        "speed": 20,
    },
    "Scanner (Cylon)": {
        "brightness": 100,
        "speed": 20,
        "scanner_rainbow": False,
    },
    "Aurora Borealis": {
        "brightness": 100,
        "speed": 20,
        "flicker": 0,
    },
    "Meteor Shower": {
        "brightness": 100,
        "speed": 20,
    },
    "Ambient Screen Color": {
        "brightness": 100,
        "ambient_fps": 30,
        "vibrance": 15,
    },
    "Battery Visualizer": {
        "brightness": 100,
    },
    "Mouse-Reactive Aura": {
        "brightness": 100,
        "speed": 20,
    },
    "Live Audio Visualizer": {
        "brightness": 0,
        "speed": 20,
        "flicker": 0,
    },
    "Temperature Mode": {
        "brightness": 100,
        "speed": 20,
    },
    "Reactive Typing": {
        "brightness": 100,
        "speed": 60,
        "reactive_style": "Fade",
        "reactive_rainbow": False,
    },
    "Valorant Spike Timer": {
        "brightness": 100,
        "spike_target_red": (224, 60, 49),
    },
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
    "Live Audio Visualizer": {"type": EFFECT_TYPE_EXTERNAL, "has_speed": True, "has_flicker": True, "has_colors": True},
    "Temperature Mode": {"type": EFFECT_TYPE_EXTERNAL, "has_speed": True},
    "Valorant Spike Timer": {"type": EFFECT_TYPE_SOFTWARE},
}

# General Constants
ZONE_COUNT = 4
COLOR_LENGTH = 12 # 4 zones * 3 (RGB)
DEFAULT_FPS = 30
