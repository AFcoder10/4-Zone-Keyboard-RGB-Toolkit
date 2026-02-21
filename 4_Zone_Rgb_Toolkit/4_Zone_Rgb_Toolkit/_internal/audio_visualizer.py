import time
import struct
import math
import numpy as np
import pyaudiowpatch as pyaudio
import colorsys
import sys
from python_controller import L5PKeyboard

CHUNK = 1024
FORMAT = pyaudio.paInt16

class AudioVisualizer:
    def __init__(self):
        print("\n--- INITIALIZING AUDIO VISUALIZER ---")
        self.p = pyaudio.PyAudio()

        print("Locating WASAPI Loopback Desktop Audio...")
        try:
            # Get default WASAPI info
            wasapi_info = self.p.get_host_api_info_by_type(pyaudio.paWASAPI)
            
            # Find loopback device associated with default output
            default_speakers = self.p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
            
            if not default_speakers["isLoopbackDevice"]:
                # PyAudioWPatch associates the loopback as the *next* device index in WASAPI
                for loopback in self.p.get_loopback_device_info_generator():
                    # We check if this loopback belongs to the default speakers
                    if default_speakers["name"] in loopback["name"]:
                        target_device = loopback
                        break
                else:
                    # Fallback if names don't match perfectly
                    target_device = self.p.get_default_wasapi_loopback()
            else:
                target_device = default_speakers

            input_device_index = target_device["index"]
            print(f"\n=> Capturing Desktop Audio directly from: {target_device['name']}")

        except OSError:
            print("CRITICAL ERROR: Looks like WASAPI isn't working on your system.")
            sys.exit(1)

        channels = target_device["maxInputChannels"]
        rate = int(target_device["defaultSampleRate"])
        
        try:
            self.stream = self.p.open(
                format=FORMAT,
                channels=channels,
                rate=rate,
                input=True,
                input_device_index=input_device_index,
                frames_per_buffer=CHUNK
            )
            print(f"Loopback Stream opened! {rate}Hz, {channels} channels")
        except Exception as e:
            print(f"CRITICAL ERROR: Could not open loopback stream: {e}")
            sys.exit(1)

        print("Initializing Keyboard...")
        self.kb = L5PKeyboard()
        self.kb.set_effect('static')
        
        # Maximize global keyboard brightness
        self.kb.set_brightness(2)

        self.channels = channels
        self.rate = rate
        
        # Keep track of previous intensities for smoothing (easing)
        self.previous_intensities = [0.0, 0.0, 0.0, 0.0]
        self.previous_color_intensities = [0.0, 0.0, 0.0, 0.0]

    def run(self):
        print("\n>>> VISUALIZER IS RUNNING! PLAY SOME MUSIC! (Ctrl+C to stop) <<<")
        
        # Smooth factor: higher means slower/smoother transitions (0.0 to 0.99)
        # Lowered to make it feel punchy and responsive to the beat!
        SMOOTHING_UP = 0.2    # Fast attack (instantly flashes on loud beats)
        SMOOTHING_DOWN = 0.75 # Moderate decay (fades out quickly enough to catch the next beat)
        
        try:
            while True:
                try:
                    # Read chunk of audio
                    data = self.stream.read(CHUNK, exception_on_overflow=False)
                    # Convert raw bytes to integer arrays
                    audio_data = np.frombuffer(data, dtype=np.int16)
                    
                    # Convert to mono if it's stereo by skipping every other sample
                    if self.channels > 1:
                        mono_data = audio_data[::self.channels]
                    else:
                        mono_data = audio_data
                    
                    # Compute strict RMS (Root Mean Square) volume for testing
                    avg_volume = np.sqrt(np.mean(mono_data.astype(np.float32)**2))
                    print(f"LIVE VOLUME LEVEL: {avg_volume:8.2f}", end='\r')
                    
                    # Horizontal volume level meter logic
                    # We map volume to a number from 0 to 4 (number of zones)
                    # Maximum volume threshold
                    MAX_VOL = 15000.0  
                    vol_ratio = min(1.0, avg_volume / MAX_VOL)
                    
                    # We want it to be punchy so we'll curve the volume ratio slightly
                    curved_vol = vol_ratio ** 0.8
                    active_zones = curved_vol * 4.0
                    
                    raw_bands = [0.0, 0.0, 0.0, 0.0]
                    for i in range(4):
                        # Calculate how much of this zone should be lit
                        # active_zones = 2.5 -> zone 0=1.0, zone 1=1.0, zone 2=0.5, zone 3=0.0
                        amt = max(0.0, min(1.0, active_zones - i))
                        raw_bands[i] = amt
                    
                    colors = []
                    for i, raw_intensity in enumerate(raw_bands):
                        prev = self.previous_intensities[i]
                        
                        # Apply exponential smoothing for BRIGHTNESS (Punchy)
                        if raw_intensity > prev:
                            smooth_factor = SMOOTHING_UP
                        else:
                            smooth_factor = SMOOTHING_DOWN
                            
                        intensity = (prev * smooth_factor) + (raw_intensity * (1.0 - smooth_factor))
                        self.previous_intensities[i] = intensity
                        
                        # Apply very heavy smoothing for COLOR (Subtle, gradual shifts)
                        # We slide the color around softly over time
                        prev_c = self.previous_color_intensities[i]
                        color_intensity = (prev_c * 0.98) + (raw_intensity * 0.02)
                        self.previous_color_intensities[i] = color_intensity
                        
                        if avg_volume < 10 and intensity < 0.05: 
                            r, g, b = 0, 0, 0
                        else:
                            # Map color entirely based on continuous average energy.
                            # We cap color intensity at 1.0. If color_intensity hits 0.5+, mapped_color caps at 1.0 (Solid Red)
                            mapped_color = min(1.0, color_intensity * 2.0)
                            
                            # Shift subtly from Blue (0.66) to Red (0.0) based on average energy
                            hue = max(0.0, 0.66 - (mapped_color * 0.66))
                            
                            # Boost brightness heavily (x6.0) so it glows and flashes instantly to the beat
                            r, g, b = colorsys.hsv_to_rgb(hue, 1.0, min(1.0, intensity * 6.0))
                            r, g, b = int(r * 255), int(g * 255), int(b * 255)
                        
                        colors.extend([r, g, b])
                    
                    self.kb.set_colors(colors)
                    
                    # IMPORTANT: Prevent USB HID Bus flooding lag. Limit to ~30 FPS update rate.
                    time.sleep(0.033)

                except Exception as loop_e:
                    print(f"Loop error: {loop_e}")
                    time.sleep(0.1)

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
