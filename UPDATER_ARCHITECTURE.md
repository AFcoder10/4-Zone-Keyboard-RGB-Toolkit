# Auto-Updater Architecture

This document describes how the in-app auto-updater works in the 4-Zone Keyboard RGB Toolkit. **Any future AI agents modifying this project must read this document before touching `apply_update_and_restart` or `check_for_updates`.**

## The Problem (Why v3.2 Failed)
In v3.2, the updater relied on a direct `Copy-Item` command to overwrite the running `.exe` file. However, Windows enforces strict file locks on running executables and any DLLs they load (including background PyInstaller extraction folders and spawned subprocesses like the thermal sensor). Because these processes take a few seconds to exit fully, the `Copy-Item` command would fail with an "Access Denied" error, the retry loop would quickly expire, and the script would silently re-launch the old version without applying the update.

## The Solution (v3.3+)
To make the updater bulletproof and future-proof, we implemented the following strategies in the generated PowerShell script:

1. **Rename-Then-Copy Strategy (The Core Fix)**
   While Windows forbids *overwriting* or *deleting* a locked executable, it **does** allow *renaming* a locked executable. 
   - The script first renames `4_Zone_Rgb_Toolkit.exe` to `4_Zone_Rgb_Toolkit.exe.old`.
   - It then safely copies the newly downloaded executable into the original path.
   - If the copy fails (e.g. out of disk space), it rolls back the rename.
   - If it succeeds, it launches the new app and deletes the `.old` file.

2. **Longer Exponential Backoffs**
   The script attempts the rename and copy processes up to 20 times with 1-second delays, allowing up to 20 seconds for the application and all background processes (like the system tray icon or WMI thermal loops) to exit completely.

3. **UAC Elevation for Protected Directories**
   If the user placed the executable inside `C:\Program Files\` or `C:\Program Files (x86)\`, standard PowerShell scripts run without admin privileges and will fail to write. The Python script detects if the path contains `Program Files` and uses `Start-Process powershell -Verb RunAs` to automatically trigger a UAC prompt and run the updater with admin rights.

4. **Robust Asset Matching**
   The `check_for_updates` function parses the GitHub API `releases/latest`. To prevent it from accidentally downloading the InnoSetup Installer (e.g. `4_Zone_Rgb_Toolkit_Setup_v3.4.exe`) and replacing the raw executable with the installer executable, the matching logic explicitly enforces `asset_name.endswith(".exe") and "Setup" not in asset_name`.

5. **Diagnostic Logging**
   The PowerShell script writes a comprehensive execution log to `%TEMP%\updater.log`. If a user ever reports an update failure, ask them to provide this log file to see exactly where the script failed (Rename, Copy, or Cleanup).

## Guidelines for Modifying the Updater
- **DO NOT** revert to a direct `Copy-Item` overwrite. Always use the rename strategy.
- **DO NOT** shorten the 20-second timeout. PyInstaller extracts to `%TEMP%` and sometimes Windows Defender scans these temporary files, locking them for longer than you might expect.
- **ALWAYS** test updates with a running background thermal sensor loop and the UI minimized to the system tray, as these are the most likely to hold handles.
