# Effect registry for dynamic loading
EFFECT_REGISTRY = {}

def register_effect(name: str, effect_class: type):
    EFFECT_REGISTRY[name] = effect_class

def get_effect(name: str) -> type:
    return EFFECT_REGISTRY.get(name)

def list_effects() -> list:
    return list(EFFECT_REGISTRY.keys())

# Auto-import all effects so they self-register on import
from effects.reactive_typing import ReactiveTypingEffect
from effects.smooth_wave import SmoothWaveEffect
from effects.lightning import LightningEffect
from effects.scanner import ScannerEffect
from effects.party import PartyEffect
from effects.realistic_fire import RealisticFireEffect
from effects.aurora import AuroraEffect
from effects.meteor import MeteorEffect
from effects.mouse_aura import MouseAuraEffect
from effects.valorant_spike import ValorantSpikeEffect
from effects.battery import BatteryEffect
from effects.temperature import TemperatureEffect
from effects.ambient import AmbientEffect
from effects.pomodoro import PomodoroEffect
from effects.audio_visualizer import AudioVisualizerEffect
