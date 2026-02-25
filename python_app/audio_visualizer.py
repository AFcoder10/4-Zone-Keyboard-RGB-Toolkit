"""
Beat-Reactive Audio Visualizer — 4 Frequency Bands
====================================================
Each keyboard zone shows a user-chosen static color.
Brightness is modulated by music energy in the corresponding frequency band.

CLI args:
  argv[1]      = sensitivity  (0–100, lower = more reactive)
  argv[2]      = smoothness   (0–100, higher = smoother decay / less flickery)
  argv[3..14]  = zone colors  R G B  R G B  R G B  R G B  (4 zones × 3 values)

Frequency-to-Zone mapping:
  Zone 0  |  Sub-Bass  20–150 Hz   ← Kick drum, sub-bass
  Zone 1  |  Bass     150–500 Hz   ← Bass guitar, low synths
  Zone 2  |  Mids     500–3000 Hz  ← Snares, vocals, melody
  Zone 3  |  Highs   3000–10000 Hz ← Hi-hats, cymbals, air
"""

import time
import sys
import collections

import numpy as np
import pyaudiowpatch as pyaudio
from python_controller import L5PKeyboard

# ── Audio ──────────────────────────────────────────────────────────────────────
CHUNK  = 1024
FORMAT = pyaudio.paInt16

# ── Frequency bands (one per zone) ────────────────────────────────────────────
BAND_RANGES = [
    (20,   150),    # Sub-Bass / Kick
    (150,  500),    # Bass
    (500,  3000),   # Mids / Vocals
    (3000, 10000),  # Highs / Cymbals
]

# ── Default static colors (fallback if not passed from UI) ────────────────────
DEFAULT_ZONE_COLORS = [
    (255, 255, 255),  # Zone 0 — White
    (255, 255, 255),  # Zone 1 — White
    (255, 255, 255),  # Zone 2 — White
    (255, 255, 255),  # Zone 3 — White
]

# ── Beat detection ─────────────────────────────────────────────────────────────
BEAT_HISTORY_LONG  = 40    # frames (~1.3 s)
BEAT_HISTORY_SHORT =  5    # frames (~160 ms)
BEAT_THRESHOLD     = 1.35  # short/long ratio to call a beat
BEAT_COOLDOWN      = 0.10  # seconds min between beats per zone

# ── Sensitivity → reference energy ────────────────────────────────────────────
# slider 0  → ref_mult ≈ 0.10  (very sensitive)
# slider 50 → ref_mult = 1.00  (default)
# slider 100→ ref_mult ≈ 100   (least sensitive)
BASE_REFS = [6000.0, 4000.0, 2500.0, 1500.0]

def slider_to_ref_mult(val: int) -> float:
    return 10.0 ** ((val - 50) / 25.0)

# ── Smoothness → attack + decay speeds ────────────────────────────────────────
# Low smoothness  = instant attack + fast decay  → sharp flicker on every beat
# High smoothness = gradual attack + slow decay  → a smooth glowing pulse
#
# attack_factor: fraction of old brightness retained per frame when RISING
#   0.0 = instant jump to full brightness
#   0.7 = slow gradual rise
#
# decay_factor: fraction of brightness retained per frame when FALLING
#   0.1 = very fast fall (flickery)
#   0.95 = very slow fall (smoothly fading glow)
def slider_to_attack(val: int) -> float:
    return val / 100.0 * 0.70   # 0% → 0.00 (instant),  100% → 0.70 (smooth)

def slider_to_decay(val: int) -> float:
    return 0.10 + (val / 100.0) * 0.85  # 0% → 0.10 (flicker), 100% → 0.95 (glow)

# ── Brightness Boost → master output multiplier ────────────────────────────────
# Applied to the FINAL brightness value before converting to RGB.
# This is a clean master dimmer — does not affect beat detection.
# slider 0   → 0.15 (very dim)
# slider 50  → 0.60 (balanced default)
# slider 100 → 1.00 (full brightness)
def slider_to_brightness_mult(val: int) -> float:
    # Range tripled: slider 0 → 0.45, slider 50 → 1.80, slider 100 → 3.00
    return 0.45 + (val / 100.0) * 2.55


class AudioVisualizer:
    def __init__(self):
        print("\n--- INITIALIZING AUDIO VISUALIZER ---")

        # ── Parse CLI arguments ───────────────────────────────────────────────
        args = sys.argv[1:]

        # Parse CLI arguments (brightness boost fixed at max 30%)
        sensitivity = int(args[0]) if len(args) > 0 else 50
        smoothness = int(args[1]) if len(args) > 1 else 50
        # brightness boost slider removed – use max boost (30%) with 50% increase
        self.brightness_mult = slider_to_brightness_mult(30) * 1.5
        flicker_raw = int(args[2]) if len(args) > 2 else 0
        self.attack_factor = slider_to_attack(smoothness)
        self.decay_factor = slider_to_decay(smoothness)

        # Flicker reduction: number of frames to average together.
        # slider 0   → window = 1  (no averaging, raw signal)
        # slider 50  → window = 8  (moderate smoothing)
        # slider 100 → window = 30 (heavy averaging, very smooth)
        self.flicker_window = max(1, round(1 + (flicker_raw / 100.0) * 29))

        # Parse zone colors from CLI arguments (argv[3...14])
        self.zone_colors = []
        if len(args) >= 15:
            for i in range(4):
                try:
                    r = int(args[3 + i*3])
                    g = int(args[4 + i*3])
                    b = int(args[5 + i*3])
                    self.zone_colors.append((r, g, b))
                except (ValueError, IndexError):
                    self.zone_colors.append((255, 252, 247))
        else:
            self.zone_colors = [(255, 252, 247) for _ in range(4)]

        self.ref_levels = [r * slider_to_ref_mult(sensitivity) for r in BASE_REFS]
        # Note: attack_factor, decay_factor, brightness_mult already set above

        print(f"Sensitivity: {sensitivity}%  |  Smoothness: {smoothness}%  |  Brightness Boost: 30%  |  Reduce Flicker: {flicker_raw}% (window={self.flicker_window} frames)")
        print(f"Zone colors: {self.zone_colors}")

        # ── Locate WASAPI loopback ────────────────────────────────────────────
        print("Locating WASAPI Loopback Desktop Audio...")
        self.p = pyaudio.PyAudio()
        try:
            wasapi_info      = self.p.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_speakers = self.p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])

            if not default_speakers["isLoopbackDevice"]:
                for loopback in self.p.get_loopback_device_info_generator():
                    if default_speakers["name"] in loopback["name"]:
                        target_device = loopback
                        break
                else:
                    target_device = self.p.get_default_wasapi_loopback()
            else:
                target_device = default_speakers

            print(f"=> Capturing from: {target_device['name']}")
        except OSError:
            print("CRITICAL: WASAPI unavailable.")
            sys.exit(1)

        self.channels = target_device["maxInputChannels"]
        self.rate     = int(target_device["defaultSampleRate"])

        try:
            self.stream = self.p.open(
                format=FORMAT,
                channels=self.channels,
                rate=self.rate,
                input=True,
                input_device_index=target_device["index"],
                frames_per_buffer=CHUNK,
            )
            print(f"Stream: {self.rate} Hz  {self.channels} ch")
        except Exception as e:
            print(f"CRITICAL: Could not open stream: {e}")
            sys.exit(1)

        # ── Keyboard ──────────────────────────────────────────────────────────
        print("Initializing Keyboard...")
        self.kb = L5PKeyboard()
        self.kb.set_effect('static')
        self.kb.set_brightness(2)   # max HW brightness; SW controls levels

        # ── Per-zone state ────────────────────────────────────────────────────
        self.energy_history = [
            collections.deque(maxlen=BEAT_HISTORY_LONG) for _ in range(4)
        ]
        self.last_beat_time  = [0.0] * 4
        self.brightness      = [0.0] * 4   # internal brightness state (0–1, pre-boost)
        # Rolling window of recent brightness values for flicker reduction
        self.brightness_history = [
            collections.deque(maxlen=self.flicker_window) for _ in range(4)
        ]

    # ──────────────────────────────────────────────────────────────────────────
    def run(self):
        print("\n>>> VISUALIZER RUNNING — PLAY MUSIC! (Ctrl+C to stop) <<<")
        print("Zones: [Sub-Bass] [Bass] [Mids] [Highs]\n")

        try:
            while True:
                try:
                    # 1. Read audio chunk
                    data       = self.stream.read(CHUNK, exception_on_overflow=False)
                    audio_data = np.frombuffer(data, dtype=np.int16).astype(np.float32)

                    # Downmix to mono
                    if self.channels > 1:
                        audio_data = audio_data.reshape(-1, self.channels).mean(axis=1)

                    # 2. FFT
                    window  = np.hanning(len(audio_data))
                    fft_mag = np.abs(np.fft.rfft(audio_data * window))
                    freqs   = np.fft.rfftfreq(len(audio_data), 1.0 / self.rate)

                    # 3. Per-band energy + beat detection
                    now    = time.monotonic()
                    colors = []

                    for i in range(4):
                        low, high = BAND_RANGES[i]
                        idx = np.where((freqs >= low) & (freqs <= high))[0]

                        # RMS energy of this frequency band
                        energy = float(np.sqrt(np.mean(fft_mag[idx] ** 2))) if len(idx) > 0 else 0.0

                        # Normalised 0–1 vs reference
                        norm = min(1.0, energy / (self.ref_levels[i] + 1e-9))

                        # Update rolling energy history
                        self.energy_history[i].append(energy)
                        hist      = self.energy_history[i]
                        long_avg  = float(np.mean(hist))
                        short_win = list(hist)[-BEAT_HISTORY_SHORT:]
                        short_avg = float(np.mean(short_win)) if short_win else 0.0

                        # Beat: short-term spike well above long-term average
                        beat = (
                            long_avg > 1e-6
                            and short_avg > long_avg * BEAT_THRESHOLD
                            and norm > 0.05
                            and (now - self.last_beat_time[i]) > BEAT_COOLDOWN
                        )

                        # Beat target is derived from norm (0–1)
                        beat_target = min(1.0, norm * 2.5)

                        if beat:
                            self.last_beat_time[i] = now
                            # Attack: blend from current brightness toward beat_target
                            # attack_factor=0.0 → instant jump, higher → gradual rise
                            self.brightness[i] = (
                                self.brightness[i] * self.attack_factor
                                + beat_target * (1.0 - self.attack_factor)
                            )
                        else:
                            # Ambient floor: very dim continuous glow from ongoing audio
                            ambient = min(0.20, norm * 1.0)
                            # Decay: exponential fall back toward ambient
                            decayed = self.brightness[i] * self.decay_factor
                            self.brightness[i] = max(ambient, decayed)

                        # ── Flicker Reduction: average recent brightness frames ──
                        # Push current brightness into the rolling window and use the
                        # mean of all frames in that window as the output.
                        # Window=1  → raw (no smoothing)
                        # Window=30 → 30 frames blended together (very smooth)
                        self.brightness_history[i].append(self.brightness[i])
                        smoothed_bv = float(np.mean(self.brightness_history[i]))

                        # Apply master brightness boost as final output scaling
                        bv = min(1.0, smoothed_bv * self.brightness_mult)
                        base_r, base_g, base_b = self.zone_colors[i]
                        colors.extend([
                            int(base_r * bv),
                            int(base_g * bv),
                            int(base_b * bv),
                        ])

                    # 5. Send to keyboard
                    self.kb.set_colors(colors)

                except Exception as loop_e:
                    print(f"Loop error: {loop_e}")
                    time.sleep(0.05)

        except KeyboardInterrupt:
            print("\nShutting down visualizer...")
        finally:
            self.kb.set_solid_color(0, 0, 255)
            self.kb.close()
            self.stream.stop_stream()
            self.stream.close()
            self.p.terminate()


if __name__ == "__main__":
    visualizer = AudioVisualizer()
    visualizer.run()
