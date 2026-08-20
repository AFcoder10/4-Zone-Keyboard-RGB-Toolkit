import asyncio
import json
import logging
import threading
import websockets
from PySide6.QtCore import QMetaObject, Qt, Q_ARG

logger = logging.getLogger("MobileServer")

# Suppress noisy handshake errors from random network scans or browsers
logging.getLogger("websockets").setLevel(logging.CRITICAL)
class MobileServer:
    def __init__(self, app_ref, port=6767):
        self.app = app_ref
        self.port = port
        self.loop = None
        self.thread = None
        self.connected_clients = set()
        self.connected_clients_lock = threading.Lock()
        
    async def ws_handler(self, websocket):
        with self.connected_clients_lock:
            self.connected_clients.add(websocket)
        try:
            # Send initial state
            state = {
                "type": "state",
                "available_modes": getattr(self.app, "HARDWARE_MODES", []) + getattr(self.app, "SOFTWARE_MODES", []),
                "mode": getattr(self.app, "current_mode_name", "Static"),
                "speed": self.app.speed_slider.value() if hasattr(self.app, "speed_slider") else 50,
                "brightness": self.app.bright_slider.value() if hasattr(self.app, "bright_slider") else 100,
                "direction": getattr(self.app, "wave_direction", "left"),
                "storm_intensity": self.app.storm_slider.value() if hasattr(self.app, "storm_slider") else 50,
                "vibrance": self.app.vibrance_slider.value() if hasattr(self.app, "vibrance_slider") else 15,
                "ambient_fps": self.app.ambient_fps_slider.value() if hasattr(self.app, "ambient_fps_slider") else 10,
                "flicker": self.app.flicker_slider.value() if hasattr(self.app, "flicker_slider") else 15,
                "wave_fill": self.app.wave_fill_cb.isChecked() if hasattr(self.app, "wave_fill_cb") else False,
                "smooth_wave_palette": self.app.smooth_wave_palette_combo.currentText() if hasattr(self.app, "smooth_wave_palette_combo") else "RGBW",
                "scanner_rainbow": self.app.scanner_rainbow_cb.isChecked() if hasattr(self.app, "scanner_rainbow_cb") else False,
                "reactive_rainbow": self.app.reactive_rainbow_cb.isChecked() if hasattr(self.app, "reactive_rainbow_cb") else False
            }
            try:
                state["zone_colors"] = ["#%02x%02x%02x" % (c[0], c[1], c[2]) for c in self.app.zone_colors]
            except Exception:
                state["zone_colors"] = ["#ff0000", "#00ff00", "#0000ff", "#ffff00"]
                
            await websocket.send(json.dumps(state))
            
            async for message in websocket:
                try:
                    data = json.loads(message)
                except Exception:
                    continue
                if data.get("command") == "set_mode":
                    mode = data.get("mode")
                    if mode is not None:
                        QMetaObject.invokeMethod(self.app, "set_mode_from_mobile", 
                            Qt.QueuedConnection, Q_ARG(str, mode))
                elif data.get("command") == "set_speed":
                    speed = data.get("speed")
                    if speed is not None:
                        QMetaObject.invokeMethod(self.app.speed_slider, "setValue", 
                            Qt.QueuedConnection, Q_ARG(int, speed))
                elif data.get("command") == "set_brightness":
                    brightness = data.get("brightness")
                    if brightness is not None:
                        QMetaObject.invokeMethod(self.app.bright_slider, "setValue", 
                            Qt.QueuedConnection, Q_ARG(int, brightness))
                elif data.get("command") == "set_direction":
                    d_raw = data.get("direction")
                    if d_raw is None: continue
                    d = d_raw.lower()
                    if "right" in d:
                        d = "right"
                    else:
                        d = "left"
                    if "Smooth" in getattr(self.app, "current_mode_name", ""):
                        QMetaObject.invokeMethod(self.app, "set_smooth_wave_direction", 
                            Qt.QueuedConnection, Q_ARG(str, d))
                    else:
                        QMetaObject.invokeMethod(self.app, "set_wave_direction", 
                            Qt.QueuedConnection, Q_ARG(str, d))
                elif data.get("command") == "set_storm_intensity":
                    QMetaObject.invokeMethod(self.app.storm_slider, "setValue", 
                        Qt.QueuedConnection, Q_ARG(int, data.get("intensity")))
                elif data.get("command") == "set_vibrance":
                    QMetaObject.invokeMethod(self.app.vibrance_slider, "setValue", 
                        Qt.QueuedConnection, Q_ARG(int, data.get("vibrance")))
                elif data.get("command") == "set_ambient_fps":
                    QMetaObject.invokeMethod(self.app.ambient_fps_slider, "setValue", 
                        Qt.QueuedConnection, Q_ARG(int, data.get("ambient_fps")))
                elif data.get("command") == "set_flicker":
                    QMetaObject.invokeMethod(self.app.flicker_slider, "setValue", 
                        Qt.QueuedConnection, Q_ARG(int, data.get("flicker")))
                elif data.get("command") == "set_zone_color":
                    zone_idx = data.get("zone_idx")
                    hex_val = data.get("hex")
                    if zone_idx is None or hex_val is None:
                        continue
                    from PySide6.QtGui import QColor
                    QMetaObject.invokeMethod(self.app, "set_custom_color_from_mobile", 
                        Qt.QueuedConnection, Q_ARG(int, zone_idx), Q_ARG(QColor, QColor(hex_val)))
                elif data.get("command") == "set_wave_fill":
                    QMetaObject.invokeMethod(self.app.wave_fill_cb, "setChecked", 
                        Qt.QueuedConnection, Q_ARG(bool, data.get("wave_fill")))
                    # Trigger the callback since setChecked via QMetaObject might not emit clicked/toggled natively sometimes
                    QMetaObject.invokeMethod(self.app, "on_wave_fill_toggled", 
                        Qt.QueuedConnection, Q_ARG(bool, data.get("wave_fill")))
                elif data.get("command") == "set_smooth_wave_palette":
                    QMetaObject.invokeMethod(self.app.smooth_wave_palette_combo, "setCurrentText", 
                        Qt.QueuedConnection, Q_ARG(str, data.get("palette")))
                elif data.get("command") == "set_scanner_rainbow":
                    QMetaObject.invokeMethod(self.app.scanner_rainbow_cb, "setChecked", 
                        Qt.QueuedConnection, Q_ARG(bool, data.get("scanner_rainbow")))
                    QMetaObject.invokeMethod(self.app, "on_scanner_rainbow_toggled", 
                        Qt.QueuedConnection, Q_ARG(bool, data.get("scanner_rainbow")))
                elif data.get("command") == "set_reactive_rainbow":
                    QMetaObject.invokeMethod(self.app.reactive_rainbow_cb, "setChecked", 
                        Qt.QueuedConnection, Q_ARG(bool, data.get("reactive_rainbow")))
                    QMetaObject.invokeMethod(self.app, "on_reactive_rainbow_toggled", 
                        Qt.QueuedConnection, Q_ARG(bool, data.get("reactive_rainbow")))
                elif data.get("command") == "start_pomo":
                    QMetaObject.invokeMethod(self.app, "start_pomodoro", Qt.QueuedConnection)
                elif data.get("command") == "stop_pomo":
                    QMetaObject.invokeMethod(self.app, "stop_pomodoro", Qt.QueuedConnection)
                elif data.get("command") == "set_pomo_time":
                    # Only set if not running
                    if not getattr(self.app, "pomo_running", False):
                        QMetaObject.invokeMethod(self.app.pomo_minutes, "setValue", 
                            Qt.QueuedConnection, Q_ARG(int, data.get("minutes")))
        except Exception as e:
            logger.error(f"Mobile Server Error: {e}")
        finally:
            with self.connected_clients_lock:
                self.connected_clients.remove(websocket)

    def broadcast_colors(self, colors):
        """ colors should be a list of 4 strings e.g. ['#ff0000', '#00ff00', ...] """
        if not self.loop or not self.loop.is_running() or not self.connected_clients:
            return
            
        message = json.dumps({"type": "colors", "data": colors})
        
        async def _broadcast():
            with self.connected_clients_lock:
                clients = self.connected_clients.copy()
            websockets.broadcast(clients, message)
            
        asyncio.run_coroutine_threadsafe(_broadcast(), self.loop)

    async def _main_serve(self):
        async with websockets.serve(self.ws_handler, "0.0.0.0", self.port):
            await asyncio.Future()  # run forever

    def _run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._main_serve())
        except Exception:
            pass

    def start(self):
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        
    def stop(self):
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)
