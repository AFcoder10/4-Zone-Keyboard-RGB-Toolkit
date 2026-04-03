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
    import subprocess
    script = Path(__file__).resolve()
    
    wrapper_exe = Path(tempfile.gettempdir()) / "Thermal_Sensor_Access_v2.exe"
    
    if not wrapper_exe.exists():
        csc_path = Path("C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe")
        if csc_path.exists():
            cs_code = """
using System;
using System.Diagnostics;
using System.Reflection;

[assembly: AssemblyTitle("Thermal Sensor Access")]
[assembly: AssemblyDescription("Temperature Monitor Background Service")]
[assembly: AssemblyProduct("4-Zone RGB Toolkit")]

class Program {
    static void Main(string[] args) {
        if (args.Length < 2) return;
        string py = args[0];
        string script = args[1];
        string allArgs = "\\"" + script + "\\"";
        for(int i=2; i<args.Length; i++) {
            allArgs += " " + args[i];
        }
        
        ProcessStartInfo info = new ProcessStartInfo();
        info.FileName = py;
        info.Arguments = allArgs;
        info.UseShellExecute = false;
        info.CreateNoWindow = true;
        
        Process.Start(info);
    }
}
"""
            cs_file = wrapper_exe.with_suffix(".cs")
            try:
                cs_file.write_text(cs_code)
                subprocess.run(
                    [str(csc_path), "/t:winexe", "/nologo", f"/out:{wrapper_exe}", str(cs_file)],
                    creationflags=0x08000000,
                    check=True
                )
                cs_file.unlink()
            except Exception:
                pass

    if wrapper_exe.exists():
        exe_to_run = str(wrapper_exe)
        all_child_args = [sys.executable, str(script)] + sys.argv[1:]
        params = " ".join(f'"{a}"' for a in all_child_args)
    else:
        exe_to_run = sys.executable
        params = f'"{script}" ' + ' '.join(sys.argv[1:])

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
    
    # We expect sys.path to include the project root so we can import wintemp
    # since we are inside python_app/, project root is one level up
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

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
        cpu_summary = wintemp.get_cpu_temperature_summary()
        cpu_temp = cpu_summary.get("core_average_c")
        gpu_temp = wintemp.get_gpu_core_temperature()
        
        data = {
            "cpu": cpu_temp if cpu_temp is not None else 0.0,
            "gpu": gpu_temp if gpu_temp is not None else 0.0
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

if __name__ == "__main__":
    main()
