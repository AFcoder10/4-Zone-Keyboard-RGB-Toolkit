import sys
import os
import json
import time
import ctypes
import tempfile
from pathlib import Path


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin():
    script = Path(__file__).resolve()

    if hasattr(sys, "_MEIPASS"):
        wrapper_exe = Path(sys._MEIPASS) / "assets" / "thermal_sensor_access_v3.exe"
    else:
        wrapper_exe = Path(__file__).parent / "assets" / "thermal_sensor_access_v3.exe"

    if wrapper_exe.exists():
        exe_to_run = str(wrapper_exe)
        if hasattr(sys, "_MEIPASS"):
            all_child_args = [sys.executable, "--run-temperature-worker"] + sys.argv[1:]
        else:
            all_child_args = [sys.executable, str(script)] + sys.argv[1:]
        params = " ".join(f'"{a}"' for a in all_child_args)
    else:
        exe_to_run = sys.executable
        if hasattr(sys, "_MEIPASS"):
            params = '"--run-temperature-worker" ' + " ".join(sys.argv[1:])
        else:
            params = f'"{script}" ' + " ".join(sys.argv[1:])

    try:
        ctypes.windll.shell32.ShellExecuteW(None, "runas", exe_to_run, params, None, 0)
    except Exception:
        return False
    return True


def main():
    if not is_admin():
        # Will prompt UAC
        if not relaunch_as_admin():
            sys.exit(1)
        sys.exit(0)

    # Now we are admin.
    import psutil

    import wintemp

    parent_pid = None
    if len(sys.argv) > 1:
        try:
            parent_pid = int(sys.argv[1])
        except ValueError:
            pass

    out_file = Path(tempfile.gettempdir()) / "4zone_temperatures.json"
    stop_flag = Path(tempfile.gettempdir()) / "4zone_temp_worker_stop.flag"
    pid_file = Path(tempfile.gettempdir()) / "4zone_temp_worker.pid"

    try:
        pid_file.write_text(str(os.getpid()))
    except Exception:
        pass

    stop_timer_start = None

    try:
        Path(tempfile.gettempdir(), "4zone_worker_boot.txt").write_text(
            f"argv: {sys.argv}\\nparent_pid: {parent_pid}\\nis_admin: {is_admin()}\\n"
        )
    except Exception:
        pass

    monitor = wintemp.HardwareMonitor()
    try:
        while True:
            # Check parent first: Immediate death if parent application died.
            if parent_pid is not None:
                if not psutil.pid_exists(parent_pid):
                    break

            # Check if we should exit (15s grace period on stop_flag)
            if stop_flag.exists():
                if stop_timer_start is None:
                    stop_timer_start = time.time()
                elif time.time() - stop_timer_start >= 15.0:
                    try:
                        stop_flag.unlink()
                    except Exception:
                        pass
                    break
            else:
                stop_timer_start = None

            # Fetch temps
            cpu_summary = monitor.get_cpu_temperature_summary()
            cpu_temp = cpu_summary.get("core_average_c")
            gpu_temp, gpu_err = monitor.get_gpu_core_temperature()

            errs = []
            if cpu_summary.get("clr_error"):
                errs.append(cpu_summary.get("clr_error"))
            if cpu_summary.get("sys_error"):
                errs.append(cpu_summary.get("sys_error"))
            if gpu_err:
                errs.append(gpu_err)

            data = {
                "cpu": cpu_temp if cpu_temp is not None else 0.0,
                "gpu": gpu_temp if gpu_temp is not None else 0.0,
                "error": " | ".join(errs) if errs else None,
            }

            # Write to JSON safely using a temp file + rename to avoid read conflicts
            tmp_out = out_file.with_suffix(".tmp")
            try:
                with open(tmp_out, "w") as f:
                    json.dump(data, f)
                tmp_out.replace(out_file)
            except Exception:
                pass

            time.sleep(1.0)
    except BaseException as e:
        try:
            import traceback

            err_str = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            with open(Path(tempfile.gettempdir(), "4zone_worker_boot.txt"), "a") as f:
                f.write(f"\\nCRITICAL LOOP CRASH:\\n{err_str}\\n")
        except Exception:
            pass
    finally:
        monitor.close()


if __name__ == "__main__":
    main()
