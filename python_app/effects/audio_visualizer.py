import time
import colorsys
import collections
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
    (20, 100),     # Zone 1: Sub-Bass / Kick
    (100, 300),    # Zone 2: Bass / Toms
    (300, 800),    # Zone 3: Lower Mids / Synths / Guitars
    (3000, 10000), # Zone 4: Highs / Cymbals / Hi-Hats
]
BAND_NAMES = ["Sub", "Bass", "Mid", "High"]

# ── Adaptive Engine Constants ─────────────────────────────────────────────────
DEFAULT_MULT = [0.35, 0.45, 0.55, 0.65]
TARGET_LOW   = [1.2,  1.5,  1.0,  0.8]
TARGET_HIGH  = [4.5,  5.5,  3.5,  3.0]
MULT_MIN     = [0.10, 0.12, 0.15, 0.20]
MULT_MAX     = [0.85, 0.88, 0.92, 0.95]
MIN_FLOOR    = [20.0, 10.0, 8.0,  3.0]

def _energy(fft_mag, band_idx):
    """RMS energy for a frequency band."""
    if len(band_idx) == 0:
        return 0.0
    return float(np.sqrt(np.mean(fft_mag[band_idx] ** 2)))


class AudioVisualizerEffect(BaseEffect):
    preferred_smoothing = 0.0  # Handled internally
    ignore_global_brightness = True

    def __init__(self, keyboard_controller, parent_app=None, config: Dict = None):
        super().__init__(keyboard_controller, parent_app, config)
        self.update_config(self.config)
        
        self.p = None
        self.stream = None
        self.audio_thread = None
        
        # Audio thread → render thread communication
        self._lock = threading.Lock()
        self._led_brightness = [0.0] * 4
        self._zone_hues = [0.0] * 4
        
        # Precomputed FFT data
        self.rate = 44100
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
        self.stop()
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
            print(f"[Visualizer] CRITICAL: WASAPI unavailable: {e}")
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
            self._led_brightness = [0.0] * 4
            self._zone_hues = [0.0] * 4

        self._stop_event = threading.Event()
        self.audio_thread = threading.Thread(target=self._audio_loop, args=(self.p, self.stream, self._stop_event), daemon=True)
        self.audio_thread.start()
        
        return True

    def stop(self) -> None:
        if hasattr(self, '_stop_event'):
            self._stop_event.set()
        if hasattr(self, 'audio_thread') and getattr(self.audio_thread, 'is_alive', lambda: False)():
            self.audio_thread.join(timeout=2.0)

    def _audio_loop(self, p, stream, stop_event):
        """
        Background thread: reads audio, runs FFT, spectral flux, adaptive 
        calibration, silence detection, and outputs brightness + hue per zone.
        """
        # ── Adaptive Engine State ──
        prev_energy    = [0.0] * 4
        led_brightness = [0.0] * 4
        flux_peaks     = [0.0] * 4
        adaptive_mult  = list(DEFAULT_MULT)
        
        hit_timestamps = [collections.deque(maxlen=100) for _ in range(4)]
        
        # Song-transition detection
        energy_fast = [0.0] * 4
        energy_slow = [0.0] * 4
        
        # Silence detection
        global_rms = 0.0

        while not stop_event.is_set():
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
                audio_data = np.frombuffer(data, dtype=np.int16).astype(np.float32)

                if self.channels > 1:
                    audio_data = audio_data.reshape(-1, self.channels).mean(axis=1)
                elif self.channels < 1:
                    time.sleep(0.05)
                    continue

                if len(audio_data) != CHUNK:
                    time.sleep(0.01)
                    continue

                fft_mag = np.abs(np.fft.rfft(audio_data * self.window)) / (CHUNK / 2)
                now = time.monotonic()
                
                # ── Silence Detection ──
                frame_rms = float(np.sqrt(np.mean(audio_data ** 2)))
                global_rms = global_rms * 0.95 + frame_rms * 0.05
                is_silent = global_rms < 50.0

                zone_hues = [0.0] * 4

                for i in range(4):
                    curr_energy = _energy(fft_mag, self.band_indices[i])
                    
                    # ── 1. Song Transition Detection ──
                    energy_fast[i] = energy_fast[i] * 0.85 + curr_energy * 0.15
                    energy_slow[i] = energy_slow[i] * 0.995 + curr_energy * 0.005
                    
                    if energy_slow[i] > 1e-6:
                        ratio = energy_fast[i] / energy_slow[i]
                        if ratio > 3.0 or ratio < 0.33:
                            adaptive_mult[i] += (DEFAULT_MULT[i] - adaptive_mult[i]) * 0.1
                    
                    # ── 2. Spectral Flux ──
                    flux = max(0.0, curr_energy - prev_energy[i])
                    prev_energy[i] = curr_energy
                    
                    # ── 3. Peak Envelope ──
                    flux_peaks[i] = max(flux, flux_peaks[i] * 0.990)
                    
                    # ── 4. Hit-Rate Proportional Feedback ──
                    ts = hit_timestamps[i]
                    while ts and (now - ts[0]) > 1.5:
                        ts.popleft()
                    hps = len(ts) / 1.5
                    
                    if hps > TARGET_HIGH[i]:
                        overshoot = (hps - TARGET_HIGH[i]) / (TARGET_HIGH[i] + 1e-9)
                        adaptive_mult[i] += 0.003 + overshoot * 0.008
                    elif hps < TARGET_LOW[i]:
                        undershoot = (TARGET_LOW[i] - hps) / (TARGET_LOW[i] + 1e-9)
                        adaptive_mult[i] -= 0.002 + undershoot * 0.005
                    else:
                        adaptive_mult[i] += (DEFAULT_MULT[i] - adaptive_mult[i]) * 0.001
                    
                    adaptive_mult[i] = max(MULT_MIN[i], min(MULT_MAX[i], adaptive_mult[i]))
                    
                    # ── 5. Final Threshold ──
                    threshold = max(MIN_FLOOR[i], flux_peaks[i] * adaptive_mult[i])
                    
                    # ── 6. Beat Detection + Silence Handling ──
                    if is_silent:
                        led_brightness[i] *= 0.90
                    elif flux > threshold:
                        led_brightness[i] = 1.0
                        ts.append(now)
                    else:
                        led_brightness[i] *= 0.82
                        if led_brightness[i] < 0.01:
                            led_brightness[i] = 0.0

                    # ── 7. Individual Zone Rainbow Hue ──
                    zone_hues[i] = (time.time() * 0.15 + (i * 0.25)) % 1.0

                # Push results to render thread
                with self._lock:
                    self._led_brightness = led_brightness[:]
                    self._zone_hues = zone_hues[:]

            except Exception as e:
                if stop_event.is_set():
                    break
                time.sleep(0.05)

        # ── Safe Cleanup ──
        if stream:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass
            
        if p:
            try:
                p.terminate()
            except Exception:
                pass

    def update(self, dt: float) -> List[int]:
        """
        Called by the render thread at ~30fps. Reads brightness + hue from
        the audio thread and converts to RGB colors for the keyboard.
        All UI controls are disabled for this effect — the adaptive engine 
        handles everything automatically.
        """
        with self._lock:
            brightness = self._led_brightness[:]
            hues = self._zone_hues[:]

        colors = [0] * 12

        for i in range(4):
            br = brightness[i]
            r_f, g_f, b_f = colorsys.hsv_to_rgb(hues[i], 1.0, 1.0)
            
            colors[i * 3]     = int(r_f * 255 * br)
            colors[i * 3 + 1] = int(g_f * 255 * br)
            colors[i * 3 + 2] = int(b_f * 255 * br)

        return colors

register_effect("Live Audio Visualizer", AudioVisualizerEffect)
