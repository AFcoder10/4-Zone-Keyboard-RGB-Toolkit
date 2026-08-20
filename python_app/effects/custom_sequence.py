import time
from typing import List, Dict, Any
from core.base import BaseEffect
from effects import register_effect


class CustomSequenceEffect(BaseEffect):
    """
    Renders custom keyframe animations as a circular sequence.
    
    The frame list is treated as a ring: after the last frame comes the first 
    frame again, using the last frame's transition settings to blend into it.
    
    Each frame has:
      - zones: 4 RGB colors
      - hold_ms: how long to hold the solid colors
      - transition_style: "smooth" or "quick"
      - transition_ms: how long to blend into the NEXT frame (only if smooth)
    
    Timeline for frame i:
      [0 .. hold_sec]  ->  show frame[i] colors solid
      [hold_sec .. hold_sec + trans_sec]  ->  lerp from frame[i] to frame[(i+1) % N]
      then advance to frame (i+1) % N
    """
    preferred_smoothing = 0.0  # No EMA smoothing - we handle our own transitions

    def __init__(self, keyboard_controller, parent_app=None, config: Dict = None):
        super().__init__(keyboard_controller, parent_app, config)
        self._frames: List[Dict[str, Any]] = []
        self._phase = "hold"       # "hold" or "transition"
        self._frame_idx = 0
        self._phase_elapsed = 0.0
        if config:
            self._frames = list(config.get("frames", []))

    @property
    def effect_name(self) -> str:
        return "Custom Sequence"

    def update_config(self, new_config: Dict[str, Any]):
        """Hot-reload frames without resetting playback position."""
        with self._lock:
            if isinstance(new_config, dict):
                self.config.update(new_config)
                if "frames" in new_config:
                    self._frames = list(new_config["frames"])
                    # Clamp index if frames were removed
                    if self._frames and self._frame_idx >= len(self._frames):
                        self._frame_idx = 0
                        self._phase = "hold"
                        self._phase_elapsed = 0.0

    def start(self) -> bool:
        with self._lock:
            self._running = True
            self._frame_idx = 0
            self._phase = "hold"
            self._phase_elapsed = 0.0
        return True

    def stop(self) -> None:
        with self._lock:
            self._running = False

    def _lerp(self, c1: List[int], c2: List[int], t: float) -> List[int]:
        t = max(0.0, min(1.0, t))
        return [
            int(c1[0] + (c2[0] - c1[0]) * t),
            int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t),
        ]

    def _get_frame(self, idx: int) -> Dict[str, Any]:
        """Get frame by index, wrapping around circularly."""
        n = len(self._frames)
        if n == 0:
            return {"zones": [[0, 0, 0] for _ in range(4)], "hold_ms": 500, "transition_style": "smooth", "transition_ms": 300}
        return self._frames[idx % n]

    def _hold_sec(self, frame: Dict) -> float:
        return max(0.05, float(frame.get("hold_ms", 500)) / 1000.0)

    def _trans_sec(self, frame: Dict) -> float:
        style = str(frame.get("transition_style", "smooth")).lower()
        if style == "quick":
            return 0.0
        ms = float(frame.get("transition_ms", 300))
        if ms <= 0:
            ms = 300  # force minimum for smooth
        return max(0.0, ms / 1000.0)

    def update(self, dt: float) -> List[int]:
        with self._lock:
            n = len(self._frames)
            if n == 0:
                return [0] * 12

            # Speed multiplier from config
            speed_val = float(self.config.get("speed", 50))
            speed_mult = max(0.1, min(5.0, speed_val / 25.0))
            effective_dt = dt * speed_mult

            self._phase_elapsed += effective_dt

            # Current and next frame (circular)
            curr = self._get_frame(self._frame_idx)
            next_idx = (self._frame_idx + 1) % n
            nxt = self._get_frame(next_idx)

            hold = self._hold_sec(curr)
            trans = self._trans_sec(curr)

            # State machine: advance through phases
            if self._phase == "hold":
                if self._phase_elapsed >= hold:
                    # Move to transition phase (or skip if quick/zero)
                    self._phase_elapsed -= hold
                    if trans > 0:
                        self._phase = "transition"
                        self._phase_elapsed = 0.0
                    else:
                        # Quick: jump directly to next frame's hold
                        self._frame_idx = next_idx
                        self._phase = "hold"
                        # Re-fetch for the new frame
                        curr = self._get_frame(self._frame_idx)
                        nxt = self._get_frame((self._frame_idx + 1) % n)

            if self._phase == "transition":
                if self._phase_elapsed >= trans:
                    # Transition complete, advance to next frame's hold
                    self._phase_elapsed -= trans
                    self._frame_idx = next_idx
                    self._phase = "hold"
                    curr = self._get_frame(self._frame_idx)
                    nxt = self._get_frame((self._frame_idx + 1) % n)

            # Render colors based on current phase
            curr_zones = curr.get("zones", [[0, 0, 0] for _ in range(4)])
            next_zones = nxt.get("zones", [[0, 0, 0] for _ in range(4)])

            colors = []
            if self._phase == "hold":
                # Show current frame's solid colors
                for z in range(4):
                    zc = curr_zones[z] if z < len(curr_zones) else [0, 0, 0]
                    if len(zc) < 3: zc = zc + [0]*(3-len(zc))
                    colors.extend(zc[:3])
            else:
                # Smoothly blend from current to next
                trans = self._trans_sec(curr)
                t = self._phase_elapsed / trans if trans > 0 else 1.0
                t = max(0.0, min(1.0, t))
                for z in range(4):
                    c1 = curr_zones[z] if z < len(curr_zones) else [0, 0, 0]
                    c2 = next_zones[z] if z < len(next_zones) else [0, 0, 0]
                    if len(c1) < 3: c1 = c1 + [0]*(3-len(c1))
                    if len(c2) < 3: c2 = c2 + [0]*(3-len(c2))
                    colors.extend(self._lerp(c1[:3], c2[:3], t))

            # Apply brightness
            bright_mult = float(self.config.get("brightness", 100)) / 100.0
            if bright_mult < 1.0:
                colors = [max(0, min(255, int(c * bright_mult))) for c in colors]

            return colors


register_effect("Custom Sequence", CustomSequenceEffect)
