
# 4-Zone Keyboard RGB Toolkit - Bug Tracker

**Generated:** 2026-07-02
**Total Issues:** 30 (5 Critical, 8 High, 10 Medium, 7 Low)

---

## 🔴 Critical (Fix Immediately - Data Loss / Hardware Lock / Crashes)

### CRIT-001: HID Device Never Closed on Crash/Exception
- **File:** `python_controller.py:112` (`close()` method)
- **Issue:** `L5PKeyboard.close()` only called in `tray_quit()` and `closeEvent()`. Any unhandled exception leaves the HID device open.
- **Impact:** Keyboard stays locked (LEDs frozen), requires physical unplug/replug or reboot to recover.
- **Fix:** Implement context manager (`__enter__`/`__exit__`), ensure `close()` called in `finally` blocks, add `atexit` handler.

### CRIT-002: Visualizer Subprocess Orphaned on Crash/Mode Switch
- **File:** `main.py:4735-4742` (`stop_visualizer()`)
- **Issue:** `stop_visualizer()` only called in `closeEvent()`/`tray_quit()`. Switching modes or crashes leaves `audio_visualizer.py` processes running.
- **Impact:** Multiple visualizer processes accumulate → audio capture conflicts, USB HID bus flooding, 100% CPU.
- **Fix:** Call `stop_visualizer()` in `apply_effect()` before starting new mode, use `try/finally` in visualizer subprocess.

### CRIT-003: Thread-Unsafe `self.custom_colors` Shared State
- **File:** `main.py:5896-5903` (UI timer) + `audio_visualizer.py` (subprocess)
- **Issue:** `self.custom_colors` list mutated by UI timer thread AND visualizer subprocess (via HID writes) without locks.
- **Impact:** Corrupted color data, visual glitches, race conditions causing random colors/freezes.
- **Fix:** Use `threading.Lock` for `custom_colors` access, or redesign to single-writer pattern.

### CRIT-004: Bare `except:` Swallows Critical Exceptions
- **Files:** `main.py:3488, 3497, 4718, 4730` (4 locations)
- **Issue:** Bare `except:` catches `KeyboardInterrupt`, `SystemExit`, `MemoryError`, making debugging impossible and preventing clean shutdown.
- **Impact:** App hangs on Ctrl+C, masks real bugs, prevents proper cleanup.
- **Fix:** Replace all bare `except:` with `except Exception:` at minimum.

### CRIT-005: Dynamic Attributes Cause AttributeError on First Use
- **Files:** `main.py:5061` (`spike_cooldown_until`), `main.py:5092` (`last_spike_scan`)
- **Issue:** Attributes created dynamically in `Valorant Spike Timer` logic but not initialized in `__init__`.
- **Impact:** `AttributeError` crash on first Spike detection attempt.
- **Fix:** Initialize all attributes in `__init__` with default values.

---

## 🟠 High (Major Functionality Broken / Resource Leaks)

### HIGH-001: Temperature Worker PID File Never Cleaned Up
- **File:** `temperature_worker.py:70` (writes PID), no cleanup on normal exit
- **Issue:** PID file persists after clean shutdown → false "worker alive" detection on next start.
- **Impact:** Temperature mode fails to start, requires manual file deletion.
- **Fix:** Remove PID file in `finally` block of worker `main()`.

### HIGH-002: MSS Screen Capture (`self.sct`) Handle Leak
- **File:** `main.py:4756` (`self.sct.close()`) only in `closeEvent()`
- **Issue:** `mss.mss()` instance created in `apply_effect()` for Ambient mode, only closed on app exit.
- **Impact:** Handle leak → eventual "too many open files" / capture failures after mode switches.
- **Fix:** Close previous `self.sct` before creating new one, use context manager.

### HIGH-003: PyAudio Stream Not Terminated on Visualizer Error
- **File:** `audio_visualizer.py:160-162` (loop error handler)
- **Issue:** Exception in audio loop caught but stream/PyAudio not terminated, loop continues.
- **Impact:** Audio device locked, requires app restart to recover.
- **Fix:** On loop error, properly terminate stream and PyAudio, then exit thread.

### HIGH-004: Visualizer Subprocess Stdout Pipe Not Drained
- **File:** `main.py:4825-4845` (`stdout=PIPE` with reader thread)
- **Issue:** Reader thread may lag → pipe buffer fills → subprocess blocks on write → visualizer freezes.
- **Impact:** Visualizer stops responding, audio continues but no LED updates.
- **Fix:** Use non-blocking I/O, larger buffers, or discard output if not needed.

### HIGH-005: Temperature Worker JSON Read Race Condition
- **Files:** `main.py:5011-5019` (read) + `temperature_worker.py:124-130` (write)
- **Issue:** Main thread reads JSON while worker writes it (tmp+rename not atomic on Windows).
- **Impact:** `JSONDecodeError`, temperature shows 0°C intermittently.
- **Fix:** Use file locking, or read with retry/validation, or use shared memory.

### HIGH-006: WMI Temperature Fallback Returns Magic Number
- **File:** `main.py:4929-4930` (`t == 27.85 or t == 27.8`)
- **Issue:** Hardcoded check for `27.85°C` as "REQUIRES_ADMIN" indicator - unreliable, hardware-dependent.
- **Impact:** False admin detection on some systems, temperature mode fails silently.
- **Fix:** Use proper WMI error handling, check access rights explicitly.

### HIGH-007: `L5PKeyboard.__init__` Raises Unhandled `ValueError`
- **Files:** `python_controller.py:27-31`, `main.py:2402-2404`
- **Issue:** Keyboard not found raises `ValueError` but callers only catch in `__main__` block.
- **Impact:** App crashes on startup if keyboard disconnected/unsupported.
- **Fix:** Handle in `RGBControllerApp.__init__`, show user-friendly error dialog.

### HIGH-008: GlobalHotkeyListener Thread Safety Violations
- **File:** `main.py:874-951` (`self.modifiers` set, `self.hotkeys` dict)
- **Issue:** pynput callback thread modifies `self.modifiers` set and reads `self.hotkeys` dict without synchronization while UI thread writes to both.
- **Impact:** Race conditions → hotkeys fire incorrectly, crashes, corrupted state.
- **Fix:** Use `threading.Lock` for shared data, or queue events to UI thread.

---

## 🟡 Medium (Functionality Issues / UX Bugs)

### MED-001: Brightness Slider Label Stuck as "Smoothness"
- **File:** `main.py:4322-4331` (`on_mode_changed`)
- **Issue:** When switching FROM "Live Audio Visualizer" TO other modes, label remains "Smoothness".
- **Impact:** Confusing UI, user thinks brightness control is broken.
- **Fix:** Reset label text in `load_mode_controls()` or `on_mode_changed()` for all modes.

### MED-002: `custom_colors` Not Reset When Switching TO Hardware Modes
- **File:** `main.py:4848-4893` (`apply_effect` hardware path)
- **Issue:** Software effect colors persist in `self.custom_colors` → bleed into hardware Static/Breath modes.
- **Impact:** Hardware modes show wrong colors until manual color pick.
- **Fix:** Reset `self.custom_colors = [0]*12` when entering hardware modes.

### MED-003: Wave Direction Not Applied for Hardware Wave Mode
- **File:** `main.py:4871-4882` (`apply_effect` Wave handling)
- **Issue:** Sets `kb.wave_direction` but doesn't call `kb.refresh()` after.
- **Impact:** Direction change ignored until next effect change.
- **Fix:** Call `kb.refresh()` after setting `wave_direction`.

### MED-004: 50ms Timer Runs for Static Modes (Wastes CPU/Battery)
- **File:** `main.py:4856` (`custom_timer.start()` for all software modes)
- **Issue:** `Static`, `Breath` software modes don't need per-frame updates.
- **Impact:** ~2-5% CPU waste, reduced battery life.
- **Fix:** Only start timer for modes that actually animate.

### MED-005: Full Screen Capture Every Frame for Ambient Mode
- **File:** `main.py:5864-5889` (`sct.grab(monitor)` at slider FPS)
- **Issue:** Captures entire monitor at up to 60 FPS, resizes to 4x1.
- **Impact:** 15-20% CPU on modern laptops, high GPU usage.
- **Fix:** Capture only top/bottom strips, use hardware acceleration, lower default FPS.

### MED-006: Repeated `colorsys.hsv_to_rgb` Calls (No Caching)
- **Files:** Throughout `update_custom_effects()` - called 4x/frame/effect
- **Issue:** Same hue→RGB conversions repeated every frame.
- **Impact:** Unnecessary CPU overhead (~0.5-1%).
- **Fix:** Precompute LUT for common hues, cache results.

### MED-007: No Frame Skipping for Heavy Effects
- **File:** `main.py:4913-4915` (`update_timer_interval`)
- **Issue:** Timer interval adjusts but effect computation still runs every tick.
- **Impact:** UI lag on low-end systems during complex effects (Lightning, Fire).
- **Fix:** Skip frame computation if behind schedule, or use adaptive quality.

### MED-008: Spike Timer Cooldown Logic Flawed
- **File:** `main.py:5061, 5092` (`spike_cooldown_until`, `last_spike_scan`)
- **Issue:** Cooldown only set on detonation (48s), not on false positives. Scan interval hardcoded 0.1s.
- **Impact:** Rapid re-triggering on noisy detection, high CPU from constant screen capture.
- **Fix:** Add cooldown on detection failure, adaptive scan rate.

### MED-009: Settings Not Validated on Load
- **File:** `main.py:3234-3247` (`load_settings` mode_settings parsing)
- **Issue:** Corrupted/malformed JSON in settings → silent fallback to defaults, user loses config.
- **Impact:** Silent data loss, confusing behavior.
- **Fix:** Validate schema, show warning on corruption, backup before overwrite.

### MED-010: Auto-Update No Signature Verification
- **File:** `main.py:2534-2574` (`apply_update_and_restart`)
- **Issue:** Downloaded EXE executed without checksum/signature verification.
- **Impact:** Supply chain attack risk (MITM on GitHub CDN).
- **Fix:** Verify SHA256 against released checksums, or code signing verification.

---

## 🔵 Low (Code Quality / Minor UX / Technical Debt)

### LOW-001: Temperature Worker Requires Admin + ShellExecuteW with User Args
- **File:** `temperature_worker.py:17-43` (`relaunch_as_admin`)
- **Issue:** Uses `ShellExecuteW` with constructed command line from `sys.argv`.
- **Impact:** Theoretical privilege escalation if args manipulated (low practical risk).
- **Fix:** Validate/sanitize args, use manifest for auto-elevation instead.

### LOW-002: Telemetry Enabled by Default (Privacy)
- **File:** `main.py:1058-1061` (`TelemetryClient._send_status`)
- **Issue:** Opt-out only, sends computer name to external endpoint.
- **Impact:** Privacy concern for enterprise/users.
- **Fix:** Opt-in default, clear consent UI on first run.

### LOW-003: No Unit Tests / Integration Tests
- **Evidence:** No `test_*.py` files, no CI config
- **Impact:** Regressions undetected, refactoring risky.
- **Fix:** Add pytest suite, mock HID/WMI/audio, GitHub Actions CI.

### LOW-004: Magic Numbers Throughout Effects
- **Files:** `main.py` (e.g., `0.15`, `0.6`, `1.5`, `20.0` in effect math)
- **Impact:** Hard to tune, inconsistent behavior.
- **Fix:** Extract to named constants with comments.

### LOW-005: Duplicate Code in Effect Implementations
- **Files:** `main.py` (Lightning, Party, Fire, Scanner, Aurora, Meteor all have similar structure)
- **Impact:** Bug fixes must be applied in 6+ places.
- **Fix:** Base `Effect` class with common timing/color utilities.

### LOW-006: Inconsistent Error Logging
- **Files:** `print()` vs `logging` vs silent `pass`
- **Impact:** Debugging difficult, errors lost in production.
- **Fix:** Standardize on `logging` module with levels.

### LOW-007: Single-Instance Mutex Name Hardcoded
- **File:** `main.py:5959` (`mutex_name = "4ZoneRGBToolkit_SingleInstanceLock"`)
- **Impact:** Conflicts if user runs multiple versions (dev + stable).
- **Fix:** Include version in mutex name, or allow override.

---

## 📋 Fix Priority Order

| Phase | Issues | Est. Effort |
|-------|--------|-------------|
| **Phase 1: Critical Stability** | CRIT-001, CRIT-002, CRIT-003, CRIT-004, CRIT-005 | 2-3 days |
| **Phase 2: Resource Leaks** | HIGH-001, HIGH-002, HIGH-003, HIGH-004, HIGH-005 | 1-2 days |
| **Phase 3: Thread Safety** | HIGH-006, HIGH-007, HIGH-008, MED-009 | 1-2 days |
| **Phase 4: Functionality Fixes** | MED-001 through MED-010 | 2-3 days |
| **Phase 5: Polish & Security** | LOW-001 through LOW-007 | 1-2 days |

**Total Estimated: 7-12 days**

---

## 🔧 Fix Tracking

| Issue | Status | Commit | Notes |
|-------|--------|--------|-------|
| CRIT-001 | 🔴 Open | | |
| CRIT-002 | 🔴 Open | | |
| CRIT-003 | 🔴 Open | | |
| CRIT-004 | 🔴 Open | | |
| CRIT-005 | 🔴 Open | | |
| HIGH-001 | 🟠 Open | | |
| HIGH-002 | 🟠 Open | | |
| HIGH-003 | 🟠 Open | | |
| HIGH-004 | 🟠 Open | | |
| HIGH-005 | 🟠 Open | | |
| HIGH-006 | 🟠 Open | | |
| HIGH-007 | 🟠 Open | | |
| HIGH-008 | 🟠 Open | | |
| MED-001 | 🟡 Open | | |
| MED-002 | 🟡 Open | | |
| MED-003 | 🟡 Open | | |
| MED-004 | 🟡 Open | | |
| MED-005 | 🟡 Open | | |
| MED-006 | 🟡 Open | | |
| MED-007 | 🟡 Open | | |
| MED-008 | 🟡 Open | | |
| MED-009 | 🟡 Open | | |
| MED-010 | 🟡 Open | | |
| LOW-001 | ⚪ Skipped | | Wont Fix |
| LOW-002 | 🟢 Closed | | Working as intended - User prefers Opt-Out |
| LOW-003 | ⚪ Skipped | | Wont Fix |
| LOW-004 | ⚪ Skipped | | Wont Fix |
| LOW-005 | ⚪ Skipped | | Wont Fix |
| LOW-006 | ⚪ Skipped | | Wont Fix |
| LOW-007 | ⚪ Skipped | | Wont Fix |