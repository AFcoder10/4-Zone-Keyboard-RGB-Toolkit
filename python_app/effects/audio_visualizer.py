import time
import collections
import math
import threading
import numpy as np
from typing import List, Dict

from core.base import BaseEffect
from effects import register_effect

try:
    import pyaudiowpatch as pyaudio
    HAS_PYAUDIO = True
except ImportError:
    HAS_PYAUDIO = False

# ── Audio ──────────────────────────────────────────────────────────────────────
CHUNK = 1024
FORMAT = pyaudio.paInt16 if HAS_PYAUDIO else 8

# ── Frequency bands (one per zone) ────────────────────────────────────────────
BAND_RANGES = [
    (20, 150),     # Sub-Bass / Kick
    (150, 500),    # Bass
    (500, 3000),   # Mids / Vocals
    (3000, 10000), # Highs / Cymbals
]

# ── Beat detection ─────────────────────────────────────────────────────────────
BEAT_HISTORY_LONG = 40  # frames (~1.3 s)
BEAT_HISTORY_SHORT = 5  # frames (~160 ms)
BEAT_THRESHOLD = 1.35   # short/long ratio to call a beat
BEAT_COOLDOWN = 0.10    # seconds min between beats per zone

BASE_REFS = [500.0, 300.0, 150.0, 100.0]

def slider_to_ref_mult(val: int) -> float:
    return 10.0 ** ((val - 50) / 25.0)

def slider_to_attack(val: int) -> float:
    return val / 100.0 * 0.70  # 0% → 0.00 (instant),  100% → 0.70 (smooth)

def slider_to_decay(val: int) -> float:
    return 0.10 + (val / 100.0) * 0.85  # 0% → 0.10 (flicker), 100% → 0.95 (glow)

def slider_to_brightness_mult(val: int) -> float:
    return 0.45 + (val / 100.0) * 2.55

class AudioVisualizerEffect(BaseEffect):
    preferred_smoothing = 0.0 # Handled internally
    ignore_global_brightness = True

    def __init__(self, keyboard_controller, parent_app=None, config: Dict = None):
        super().__init__(keyboard_controller, parent_app, config)
        self.update_config(self.config)
        
        self.p = None
        self.stream = None
        self.audio_thread = None
        
        # Audio thread outputs
        self._lock = threading.Lock()
        self.beat_targets = [0.0] * 4
        self.ambient_floors = [0.0] * 4
        self.beats = [False] * 4
        
        # Rendering state
        self.brightness = [0.0] * 4
        self.velocity = [0.0] * 4
        self.brightness_history = [
            collections.deque(maxlen=30) for _ in range(4)
        ]
        self.brightness_sums = [0.0] * 4
        
        # Precomputed FFT data
        self.rate = 44100  # Default, updated when stream opens
        self.channels = 2
        self.window = np.hanning(CHUNK)
        self.band_indices = []

    @property
    def effect_name(self) -> str:
        return "Live Audio Visualizer"

    def start(self) -> bool:
        if not HAS_PYAUDIO:
            print("[Visualizer] pyaudiowpatch is not installed. Cannot start.")
            return False

        print("[Visualizer] Locating WASAPI Loopback Desktop Audio...")
        self.p = pyaudio.PyAudio()
        try:
            wasapi_info = self.p.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_speakers = self.p.get_device_info_by_index(
                wasapi_info["defaultOutputDevice"]
            )

            if not default_speakers["isLoopbackDevice"]:
                for loopback in self.p.get_loopback_device_info_generator():
                    if default_speakers["name"] in loopback["name"]:
                        target_device = loopback
                        break
                else:
                    target_device = self.p.get_default_wasapi_loopback()
            else:
                target_device = default_speakers

            print(f"[Visualizer] Capturing from: {target_device['name']}")
        except Exception as e:
            print(f"[Visualizer] CRITICAL: WASAPI unavailable or error during initialization: {e}")
            if self.p:
                self.p.terminate()
            return False

        self.channels = target_device["maxInputChannels"]
        self.rate = int(target_device["defaultSampleRate"])

        try:
            self.stream = self.p.open(
                format=FORMAT,
                channels=self.channels,
                rate=self.rate,
                input=True,
                input_device_index=target_device["index"],
                frames_per_buffer=CHUNK,
            )
            print(f"[Visualizer] Stream: {self.rate} Hz  {self.channels} ch")
        except Exception as e:
            print(f"[Visualizer] CRITICAL: Could not open stream: {e}")
            self.p.terminate()
            return False

        freqs = np.fft.rfftfreq(CHUNK, 1.0 / self.rate)
        self.band_indices = []
        for low, high in BAND_RANGES:
            idx = np.where((freqs >= low) & (freqs <= high))[0]
            self.band_indices.append(idx)

        # Clear state
        with self._lock:
            self.beat_targets = [0.0] * 4
            self.ambient_floors = [0.0] * 4
            self.beats = [False] * 4
            
        self.brightness = [0.0] * 4
        self.velocity = [0.0] * 4
        self.brightness_history = [collections.deque(maxlen=30) for _ in range(4)]
        self.brightness_sums = [0.0] * 4
        
        self._running = True
        self.audio_thread = threading.Thread(target=self._audio_loop, daemon=True)
        self.audio_thread.start()
        
        return True

    def stop(self) -> None:
        self._running = False
        # Do NOT join the thread or destroy PyAudio from the UI thread!
        # The background _audio_loop will safely destroy its own stream when it exits.
        # This prevents the hard crash (Access Violation) in PortAudio.

    def _audio_loop(self):
        # Local state for audio thread
        energy_history = [collections.deque(maxlen=BEAT_HISTORY_LONG) for _ in range(4)]
        energy_sums = [0.0] * 4
        short_energy_history = [collections.deque(maxlen=BEAT_HISTORY_SHORT) for _ in range(4)]
        short_energy_sums = [0.0] * 4
        last_beat_time = [0.0] * 4

        while self._running:
            try:
                data = self.stream.read(CHUNK, exception_on_overflow=False)
                audio_data = np.frombuffer(data, dtype=np.int16).astype(np.float32)

                if self.channels > 1:
                    audio_data = audio_data.reshape(-1, self.channels).mean(axis=1)

                if len(audio_data) != CHUNK:
                    continue

                fft_mag = np.abs(np.fft.rfft(audio_data * self.window)) / (CHUNK / 2)
                now = time.monotonic()
                
                # Fetch sensitivity once per frame to avoid locking per zone
                with self._lock:
                    sensitivity = max(0, min(100, self.config.get("speed", 50)))
                ref_mult = slider_to_ref_mult(sensitivity)
                ref_levels = [r * ref_mult for r in BASE_REFS]

                new_beat_targets = [0.0] * 4
                new_ambient_floors = [0.0] * 4
                new_beats = [False] * 4

                for i in range(4):
                    idx = self.band_indices[i]
                    energy = float(np.sqrt(np.mean(fft_mag[idx] ** 2))) if len(idx) > 0 else 0.0

                    norm_linear = min(1.0, energy / (ref_levels[i] + 1e-9))
                    norm = math.log10(1.0 + 99.0 * norm_linear) / 2.0

                    hist = energy_history[i]
                    if len(hist) == hist.maxlen:
                        energy_sums[i] -= hist[0]
                    hist.append(energy)
                    energy_sums[i] += energy
                    long_avg = energy_sums[i] / len(hist)

                    short_hist = short_energy_history[i]
                    if len(short_hist) == short_hist.maxlen:
                        short_energy_sums[i] -= short_hist[0]
                    short_hist.append(energy)
                    short_energy_sums[i] += energy
                    short_avg = short_energy_sums[i] / len(short_hist)

                    smoothed_norm_linear = min(1.0, short_avg / (ref_levels[i] + 1e-9))
                    smoothed_norm = math.log10(1.0 + 99.0 * smoothed_norm_linear) / 2.0

                    beat = (
                        long_avg > 1e-6
                        and short_avg > long_avg * BEAT_THRESHOLD
                        and norm > 0.05
                        and (now - last_beat_time[i]) > BEAT_COOLDOWN
                    )

                    new_beat_targets[i] = min(1.0, norm)
                    new_ambient_floors[i] = min(0.40, smoothed_norm * 1.0)
                    if beat:
                        last_beat_time[i] = now
                        new_beats[i] = True

                with self._lock:
                    self.beat_targets = new_beat_targets
                    self.ambient_floors = new_ambient_floors
                    for i in range(4):
                        if new_beats[i]:
                            self.beats[i] = True

            except Exception as e:
                # If device is lost, thread stops gracefully
                if not self._running:
                    break
                time.sleep(0.05)

        # --- SAFE CLEANUP IN THE AUDIO THREAD ---
        if hasattr(self, 'stream') and self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
            
        if hasattr(self, 'p') and self.p:
            try:
                self.p.terminate()
            except Exception:
                pass
            self.p = None

    def update(self, dt: float) -> List[int]:
        # Config params
        # Note: In main.py, "brightness" slider is used for smoothness, "speed" for sensitivity
        with self._lock:
            smoothness = max(0, min(100, self.config.get("brightness", 0)))
            flicker_raw = max(0, min(100, self.config.get("flicker", 0)))
            zone_colors_raw = self.config.get("zone_colors", [[255, 255, 255]] * 4)
            zone_colors = [(c[0], c[1], c[2]) for c in zone_colors_raw]
            
            beat_targets = self.beat_targets[:]
            ambient_floors = self.ambient_floors[:]
            beats = self.beats[:]
            self.beats = [False] * 4 # Clear beats after reading

        attack_factor = slider_to_attack(smoothness)
        decay_factor = slider_to_decay(smoothness)
        brightness_mult = slider_to_brightness_mult(30) * 1.5 # Fixed max boost
        flicker_window_target = max(1, round(1 + (flicker_raw / 100.0) * 29))

        colors = [0] * 12

        for i in range(4):
            beat = beats[i]
            beat_target = beat_targets[i]
            ambient = ambient_floors[i]

            if beat:
                self.brightness[i] = self.brightness[i] * attack_factor + beat_target * (1.0 - attack_factor)
                self.velocity[i] = 0.0
            else:
                gravity = 0.002 + (1.0 - decay_factor) * 0.02
                self.velocity[i] += gravity
                decayed = self.brightness[i] - self.velocity[i]
                
                if decayed < ambient:
                    decayed = ambient
                    self.velocity[i] = 0.0

                self.brightness[i] = max(ambient, decayed)

            # Flicker reduction
            bright_hist = self.brightness_history[i]
            # Adjust window size dynamically if config changed
            if bright_hist.maxlen != flicker_window_target:
                new_hist = collections.deque(list(bright_hist)[-flicker_window_target:], maxlen=flicker_window_target)
                self.brightness_history[i] = new_hist
                self.brightness_sums[i] = sum(new_hist)
                bright_hist = new_hist
                
            if len(bright_hist) == bright_hist.maxlen:
                self.brightness_sums[i] -= bright_hist[0]
            bright_hist.append(self.brightness[i])
            self.brightness_sums[i] += self.brightness[i]
            smoothed_bv = self.brightness_sums[i] / len(bright_hist)

            bv = min(1.0, smoothed_bv * brightness_mult)
            base_r, base_g, base_b = zone_colors[i]
            
            colors[i * 3] = int(base_r * bv)
            colors[i * 3 + 1] = int(base_g * bv)
            colors[i * 3 + 2] = int(base_b * bv)

        return colors

register_effect("Live Audio Visualizer", AudioVisualizerEffect)
