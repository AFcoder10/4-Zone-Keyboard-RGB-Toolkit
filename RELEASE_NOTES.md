# 4-Zone Keyboard RGB Toolkit - v3.4 Update

Welcome to the **v3.4** release. This update introduces Cinema / Theater Mode for distraction-free video playback and Display Sync to turn off keyboard lighting when your display turns off.

## What's New

### Cinema / Theater Mode (Fullscreen Video Auto-Dim)
* Automatically fades keyboard lighting to black over 2.5 seconds when watching video in true fullscreen across web browsers (YouTube, Netflix, Prime Video) and media players (VLC, MPV).
* Accurately detects true fullscreen and ignores normal windowed or maximized browser tabs.
* Excludes Ambient Screen Color mode so ambient display backlighting stays active without dimming.
* Instantly restores full brightness on mouse movement or any keypress. Music players do not trigger dimming.
* Configurable under Settings (*Cinema Mode: Auto-dim lights in fullscreen video*).

### Display Sync (Turn Off LEDs with Display)
* Automatically shuts off keyboard LEDs whenever your display turns off, enters standby, or when the screen is locked (Win + L).
* Instantly restores your active lighting effect and colors when the display turns back on or is unlocked.
* Works across all lighting effects, including Ambient Screen Color and hardware modes.
* Configurable under Settings (*Display Sync: Turn off LEDs with display*).

## Bug Fixes and Improvements
* Installed a native Windows power event filter at the application pump level to guarantee display state detection even when minimized to the system tray.
* Fixed a settings loading signal issue to protect custom presets from being overwritten.
