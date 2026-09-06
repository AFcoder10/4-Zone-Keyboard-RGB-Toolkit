# 4-Zone Keyboard RGB Toolkit - v3.3 Update

Welcome to the **v3.3** release! This update brings enhanced system tray launch controls, fixes cursor flickering in ambient screen sampling, and delivers further reliability improvements.

## What's New & Improved

*   **Start Minimized (System Tray):** Added a new setting under Behavior to launch the application silently straight into the Windows system tray without showing the main window. Ideal for users launching manually via custom startup shortcuts or background task managers.
    *   *Special thanks to [@pranavakshit](https://github.com/pranavakshit) for proposing and pitching this feature!*

## Stability & Bug Fixes

*   **Auto-Updater Reliability Overhaul:** Completely rewrote the self-updating mechanism to be bulletproof. The updater now utilizes a rename-then-copy strategy to bypass Windows file locks, implements a 20-second exponential backoff retry loop, automatically requests UAC elevation for `Program Files` installations, and logs diagnostics to `%TEMP%\updater.log`. This ensures future updates from v3.3 onwards will apply smoothly without silent failures!
*   **Eliminated Mouse Cursor Flickering (Issue #12):** Fixed cursor flickering and flashing during rapid screen sampling in **Ambient Screen Color** mode and Valorant Spike Timer by disabling Windows GDI `CAPTUREBLT`. Desktop colors are now captured smoothly without interfering with the hardware mouse pointer.
    *   *Special thanks to [@pranavakshit](https://github.com/pranavakshit) for reporting the cursor blinking issue in #12 with helpful video footage and reproduction details!*
*   **Startup & Splash Screen Harmony:** Linked the *Start Minimized* and *Show Splash Screen on Boot* options with mutual exclusion so silent tray launches skip splash animations cleanly.

---

# 4-Zone Keyboard RGB Toolkit - v3.2 Update

Welcome to the **v3.2 Stability & Polish** release! This update is focused entirely on under-the-hood stability, crash protection, graceful hardware handling, and UI refinements.

## What's New & Improved

*   **Automatic Laptop Model Detection:** The application now identifies your Lenovo laptop model (e.g. `LOQ 15IRX9`, `Legion 5 Pro`, etc.) via fast, read-only SMBIOS lookups and displays it in Settings and the app footer.

## Stability & Bug Fixes

*   **Hardware Disconnect Protection:** Hardened all hardware mode switching (`apply_effect`) to prevent application crashes if a USB keyboard is unplugged, power-cycled, or re-enumerated.
*   **Clean Shutdown Lifecycle:** Resolved an asynchronous loop issue where closing the app could trigger unhandled `GeneratorExit` runtime warnings in the console.
*   **Thread & Port Safety:** Wrapped local background server threads in error handling to prevent startup crashes caused by port collisions.
*   **Resilient Dependency Fallbacks:** Implemented graceful fallbacks across all lighting modes so the app runs smoothly even in minimal Python environments.
*   **PyInstaller Build Hardening:** Bundled all new system information modules and hidden dependencies for rock-solid standalone `.exe` distributions.
