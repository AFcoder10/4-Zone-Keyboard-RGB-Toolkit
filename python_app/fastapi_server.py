from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import threading
from PySide6.QtCore import QMetaObject, Qt, Q_ARG
from PySide6.QtGui import QColor

# Import modes directly from config
from core.config import HARDWARE_MODES, SOFTWARE_MODES

ALL_MODES = HARDWARE_MODES + SOFTWARE_MODES

app = FastAPI()

# Allow CORS for the React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_gui_app = None

@app.get("/api/status")
def get_status():
    if not _gui_app:
        return {"status": "starting"}
    try:
        zone_colors = ["#%02x%02x%02x" % (c[0], c[1], c[2]) for c in getattr(_gui_app, "zone_colors", [])]
    except Exception:
        zone_colors = ["#ff0000", "#00ff00", "#0000ff", "#ffff00"]

    return {
        "mode": getattr(_gui_app, "current_mode_name", "Static"),
        "speed": _gui_app.speed_slider.value() if hasattr(_gui_app, "speed_slider") else 50,
        "brightness": _gui_app.bright_slider.value() if hasattr(_gui_app, "bright_slider") else 100,
        "zone_colors": zone_colors,
        "available_modes": getattr(_gui_app, "HARDWARE_MODES", []) + getattr(_gui_app, "SOFTWARE_MODES", [])
    }

@app.post("/api/set_mode/{mode}")
def set_mode(mode: str):
    if _gui_app:
        QMetaObject.invokeMethod(_gui_app, "set_mode_from_mobile", Qt.QueuedConnection, Q_ARG(str, mode))
    return {"status": "ok"}

@app.post("/api/set_speed/{speed}")
def set_speed(speed: int):
    if _gui_app and hasattr(_gui_app, "speed_slider"):
        QMetaObject.invokeMethod(_gui_app.speed_slider, "setValue", Qt.QueuedConnection, Q_ARG(int, speed))
    return {"status": "ok"}

@app.post("/api/set_brightness/{brightness}")
def set_brightness(brightness: int):
    if _gui_app and hasattr(_gui_app, "bright_slider"):
        QMetaObject.invokeMethod(_gui_app.bright_slider, "setValue", Qt.QueuedConnection, Q_ARG(int, brightness))
    return {"status": "ok"}

@app.post("/api/set_color/{zone_idx}/{hex_color}")
def set_color(zone_idx: int, hex_color: str):
    if _gui_app:
        # hex_color might lack the hash due to URL routing
        if not hex_color.startswith("#"):
            hex_color = "#" + hex_color
        QMetaObject.invokeMethod(_gui_app, "set_custom_color_from_mobile", Qt.QueuedConnection, Q_ARG(int, zone_idx), Q_ARG(QColor, QColor(hex_color)))
    return {"status": "ok"}

class FastAPIThread(threading.Thread):
    def __init__(self, gui_app, port=8000):
        super().__init__(daemon=True)
        global _gui_app
        _gui_app = gui_app
        self.port = port
        
    def run(self):
        uvicorn.run(app, host="127.0.0.1", port=self.port, log_level="critical")
