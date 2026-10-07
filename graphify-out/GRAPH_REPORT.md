# Graph Report - 4-Zone-Keyboard-RGB-Toolkit  (2026-10-07)

## Corpus Check
- 67 files · ~359,780 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 57 file(s) not represented in the graph (top: .dll 38, .ico 5, (none) 3)

## Summary
- 662 nodes · 1266 edges · 57 communities (26 shown, 31 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 28 edges (avg confidence: 0.91)
- Token cost: 1,200 input · 800 output

## Community Hubs (Navigation)
- Cloud Hub & Community Effects
- Web Frontend & React Application
- Effect Studio Sequence Editor
- HID Protocol & RGB Hardware Interface
- Core App State & Controller
- Base Effect Framework
- Effect Registry & Math Utilities
- Packaging & Windows Installer Build
- FastAPI REST API & Server
- Ambient Screen Sampling Engine
- Preset Loading & Mode Switching
- OS Interop & System Architecture
- Custom Sequence Playback Engine
- HID & Audio Capture Drivers
- Async Core & Builder Subsystem
- Hardware Temperature Monitoring
- Dialog Windows & Log Viewer
- Audio Visualizer Realtime Effect
- Telemetry & Laptop Identification
- Global Keyboard Hotkey Hook
- Reactive Typing Keypress Effect
- UI Layout & Color Picker Controls
- Mobile Remote WebSocket Server
- Splash Screen & Live Preview Widget
- Hotkey Recording & Dialog UI
- Auto-Updater & Download Thread
- Feature Toggles & Mobile Sync
- Animated Slider Component
- Custom Frameless Titlebar
- Smooth Wave Color Palette Effect
- Hardware Temperature Color Mapping
- Valorant Spike Detection Effect
- Log Buffer & Output Redirection
- Animated Tooltip Info Icon
- Sequence Frame Card Widget
- Aurora Borealis Gradient Effect
- Battery Status RGB Effect
- Lightning Flash RGB Effect
- Meteor Shower RGB Effect
- Mouse Aura Cursor Tracking Effect
- Party Strobe Dynamic Effect
- Realistic Fire Simulation Effect
- Scanner Nightrider RGB Effect
- C# Hardware Monitor Wrapper
- Frontend Linting Configuration
- Glow Button Custom Widget
- Project Documentation & Architecture
- GitHub Pages & Web Deployment
- Version Metadata & Release Notes
- Splash Media Assets
- Python Dependency Manifest
- Web Verification Records
- Website Graphical Assets

## God Nodes (most connected - your core abstractions)
1. `RGBControllerApp` - 124 edges
2. `BaseEffect` - 45 edges
3. `EffectStudioDialog` - 38 edges
4. `MarketplaceDialog` - 20 edges
5. `RGBKeyboard` - 19 edges
6. `EffectManager` - 17 edges
7. `register_effect()` - 16 edges
8. `CustomSequenceEffect` - 14 edges
9. `EffectDetailDialog` - 12 edges
10. `GlowButton` - 11 edges

## Surprising Connections (you probably didn't know these)
- `4-Zone Keyboard RGB Toolkit Overview` --references--> `Root Application Preview Image`  [EXTRACTED]
  README.md → assets/preview.png
- `Deploy Static Content Workflow` --references--> `Website HTML Root Entry`  [INFERRED]
  .github/workflows/static.yml → website/index.html
- `4-Zone Keyboard RGB Toolkit Overview` --references--> `Updater System Architecture`  [INFERRED]
  README.md → UPDATER_ARCHITECTURE.md
- `Windows Executable Version Info` --conceptually_related_to--> `Release Notes v1.0.0`  [INFERRED]
  python_app/version_info.txt → RELEASE_NOTES.md
- `EffectDetailDialog` --uses--> `EffectStudioDialog`  [INFERRED]
  python_app/cloud_hub.py → python_app/custom_builder_gui.py

## Import Cycles
- None detected.

## Communities (57 total, 31 thin omitted)

### Community 0 - "Cloud Hub & Community Effects"
Cohesion: 0.05
Nodes (31): base64, glob, pyside6_qtwidgets, _decode_default_endpoint(), EffectDetailDialog, FetchCloudWorker, generate_obfuscated_url(), get_firebase_url() (+23 more)

### Community 1 - "Web Frontend & React Application"
Cohesion: 0.05
Nodes (41): animejs, gh-pages, oxlint, react, react-dom, react-markdown, react-router-dom, @types/react (+33 more)

### Community 2 - "Effect Studio Sequence Editor"
Cohesion: 0.15
Nodes (4): EffectStudioDialog, Schedules a debounced hardware update to prevent flooding., Pushes current sequence payload live to physical hardware. Emits black static…, Custom Effect Studio & Sequence Designer. Compact layout, interactive sliders…

### Community 3 - "HID Protocol & RGB Hardware Interface"
Cohesion: 0.08
Nodes (11): Speed from 1 (slow) to 4 (fast), Brightness from 0 (off) to 4 (max), Colors is a list of exactly 12 integers representing the RGB of 4 zones. [R1,…, Sets the entire keyboard to a single solid RGB color, Closes the connection to the HID device, RGBKeyboard, EffectManager, Any (+3 more)

### Community 4 - "Core App State & Controller"
Cohesion: 0.09
Nodes (3): Update battery cache every 500ms to avoid expensive repeated calls in tight…, RGBControllerApp, QMainWindow

### Community 5 - "Base Effect Framework"
Cohesion: 0.09
Nodes (12): ABC, BaseEffect, Any, Unique identifier for this effect., software, hardware, or external, Initialize and start the effect. Return True on success., Clean shutdown of the effect., Compute next frame colors. Returns: List of 12 ints [R,G,B * 4] or None to skip… (+4 more)

### Community 6 - "Effect Registry & Math Utilities"
Cohesion: 0.32
Nodes (5): json, math, register_effect(), random, typing

### Community 8 - "Packaging & Windows Installer Build"
Cohesion: 0.15
Nodes (8): os, PythonInnoSetupGenerator, is_admin(), main(), relaunch_as_admin(), subprocess, sys, tempfile

### Community 9 - "FastAPI REST API & Server"
Cohesion: 0.15
Nodes (12): fastapi, fastapi_middleware_cors, get, post, pyside6_qtgui, FastAPIThread, get_status(), set_brightness() (+4 more)

### Community 10 - "Ambient Screen Sampling Engine"
Cohesion: 0.14
Nodes (6): numpy, AmbientEffect, Lazily create the mss instance on the calling (render) thread., get_chroma_weighted_zone_colors(), Chroma-Weighted Color Averaging Helper --------------------------------------…, Given a PIL Image representing a screen capture, divides it into 4 vertical…

### Community 12 - "OS Interop & System Architecture"
Cohesion: 0.16
Nodes (11): collections, ctypes_wintypes, pil, platform, psutil, GUID, _guid_equals(), _ps_escape() (+3 more)

### Community 13 - "Custom Sequence Playback Engine"
Cohesion: 0.18
Nodes (5): CustomSequenceEffect, Any, Hot-reload frames without resetting playback position., Get frame by index, wrapping around circularly., Renders custom keyframe animations as a circular sequence. The frame list is…

### Community 14 - "HID & Audio Capture Drivers"
Cohesion: 0.26
Nodes (7): colorsys, hid, mss, mss_windows, pyaudiowpatch, threading, time

### Community 15 - "Async Core & Builder Subsystem"
Cohesion: 0.18
Nodes (8): asyncio, ctypes, logging, pynput, pyside6_qtcore, RECT, Structure, websockets

### Community 16 - "Hardware Temperature Monitoring"
Cohesion: 0.25
Nodes (5): clr, pathlib, HardwareMonitor, _iter_hardware_tree(), _resolve_lhm_dll_path()

### Community 17 - "Dialog Windows & Log Viewer"
Cohesion: 0.18
Nodes (3): FadeDialog, LogsDialog, QDialog

### Community 18 - "Audio Visualizer Realtime Effect"
Cohesion: 0.20
Nodes (5): AudioVisualizerEffect, _energy(), Background thread: reads audio, runs FFT, spectral flux, adaptive calibration,…, Called by the render thread at ~30fps. Reads brightness + hue from the audio…, RMS energy for a frequency band.

### Community 19 - "Telemetry & Laptop Identification"
Cohesion: 0.20
Nodes (5): TelemetryClient, get_laptop_model(), System & Hardware Information utilities for 4-Zone Keyboard RGB Toolkit.…, Safely retrieves the laptop model name (e.g. 'LOQ 15IRX9') using strict read-…, winreg

### Community 20 - "Global Keyboard Hotkey Hook"
Cohesion: 0.20
Nodes (3): _normalize_hotkey_key_name(), GlobalHotkeyListener, on_press()

### Community 25 - "Splash Screen & Live Preview Widget"
Cohesion: 0.25
Nodes (3): GifSplashScreen, KeyboardPreviewWidget, QWidget

### Community 26 - "Hotkey Recording & Dialog UI"
Cohesion: 0.25
Nodes (3): HotkeyDialog, HotkeyRecorderButton, QPushButton

### Community 38 - "Sequence Frame Card Widget"
Cohesion: 0.47
Nodes (3): FrameCardWidget, QFrame, Clean frame item widget for vertical sequence list with high visual polish and…

### Community 47 - "C# Hardware Monitor Wrapper"
Cohesion: 0.33
Nodes (4): Program, system, system_diagnostics, system_reflection

### Community 48 - "Frontend Linting Configuration"
Cohesion: 0.33
Nodes (5): plugins, rules, react/only-export-components, react/rules-of-hooks, $schema

### Community 50 - "Project Documentation & Architecture"
Cohesion: 0.67
Nodes (3): Root Application Preview Image, 4-Zone Keyboard RGB Toolkit Overview, Updater System Architecture

### Community 51 - "GitHub Pages & Web Deployment"
Cohesion: 0.67
Nodes (3): Deploy Static Content Workflow, Website HTML Root Entry, Toolkit Website Documentation

## Knowledge Gaps
- **39 isolated node(s):** `$schema`, `plugins`, `react/rules-of-hooks`, `react/only-export-components`, `name` (+34 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 231 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **31 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `RGBControllerApp` connect `Core App State & Controller` to `Cloud Hub & Community Effects`, `Effect Studio Sequence Editor`, `HID Protocol & RGB Hardware Interface`, `Hotkey & Preset Management`, `FastAPI REST API & Server`, `Preset Loading & Mode Switching`, `OS Interop & System Architecture`, `Dialog Windows & Log Viewer`, `UI Layout & Color Picker Controls`, `Power Policies & Dynamic Lighting`, `Mobile Remote WebSocket Server`, `Splash Screen & Live Preview Widget`, `Hotkey Recording & Dialog UI`, `Effect Tuning Controls & Sliders`, `Auto-Updater & Download Thread`, `Preview Collapse Animation System`, `Feature Toggles & Mobile Sync`, `Animated Slider Component`, `Custom Frameless Titlebar`, `Animated Tooltip Info Icon`, `Glow Button Custom Widget`?**
  _High betweenness centrality (0.289) - this node is a cross-community bridge._
- **Why does `BaseEffect` connect `Base Effect Framework` to `Smooth Wave Color Palette Effect`, `Hardware Temperature Color Mapping`, `HID Protocol & RGB Hardware Interface`, `Valorant Spike Detection Effect`, `Effect Registry & Math Utilities`, `Aurora Borealis Gradient Effect`, `Battery Status RGB Effect`, `Lightning Flash RGB Effect`, `Ambient Screen Sampling Engine`, `Meteor Shower RGB Effect`, `Mouse Aura Cursor Tracking Effect`, `Custom Sequence Playback Engine`, `HID & Audio Capture Drivers`, `Party Strobe Dynamic Effect`, `Realistic Fire Simulation Effect`, `Scanner Nightrider RGB Effect`, `Audio Visualizer Realtime Effect`, `Reactive Typing Keypress Effect`?**
  _High betweenness centrality (0.214) - this node is a cross-community bridge._
- **Why does `EffectManager` connect `HID Protocol & RGB Hardware Interface` to `Cloud Hub & Community Effects`, `Core App State & Controller`, `Base Effect Framework`, `Ambient Screen Sampling Engine`, `OS Interop & System Architecture`, `HID & Audio Capture Drivers`, `UI Layout & Color Picker Controls`?**
  _High betweenness centrality (0.150) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `RGBControllerApp` (e.g. with `MarketplaceDialog` and `RGBKeyboard`) actually correct?**
  _`RGBControllerApp` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `EffectStudioDialog` (e.g. with `EffectDetailDialog` and `RGBControllerApp`) actually correct?**
  _`EffectStudioDialog` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `RGBKeyboard` (e.g. with `EffectManager` and `RGBControllerApp`) actually correct?**
  _`RGBKeyboard` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `$schema`, `plugins`, `react/rules-of-hooks` to the rest of the system?**
  _39 weakly-connected nodes found - possible documentation gaps or missing edges._