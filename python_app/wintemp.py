from pathlib import Path

try:
    import clr

    clr_error = None
except Exception as e:
    clr = None
    clr_error = str(e)


def _iter_hardware_tree(hardware):
    yield hardware
    for sub_hw in hardware.SubHardware:
        sub_hw.Update()
        yield from _iter_hardware_tree(sub_hw)


def _resolve_lhm_dll_path():
    import sys
    import os

    if hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        # Fallback for source execution. Assume LibreHardwareMonitor is side-by-side with this script.
        base = Path(os.path.abspath(os.path.dirname(__file__)))

    candidates = [
        base / "LibreHardwareMonitor" / "LibreHardwareMonitorLib.dll",
        Path("LibreHardwareMonitor/LibreHardwareMonitorLib.dll"),
        Path("lhm_extracted/ref/netstandard2.0/LibreHardwareMonitorLib.dll"),
        Path("lhm_extracted/ref/net472/LibreHardwareMonitorLib.dll"),
    ]
    return next((p for p in candidates if p.exists()), None)


def get_cpu_core_temperatures():
    if clr is None:
        return [], "CLR module missing"

    dll_path = _resolve_lhm_dll_path()
    if dll_path is None:
        return [], "LHM DLL not found"

    try:
        clr.AddReference(str(dll_path.resolve()))
        from LibreHardwareMonitor.Hardware import Computer, HardwareType, SensorType  # type: ignore
    except Exception as e:
        return [], f"LHM Init Error: {e}"

    rows = []
    computer = Computer()
    computer.IsCpuEnabled = True
    computer.IsGpuEnabled = False
    computer.IsMotherboardEnabled = False
    computer.IsMemoryEnabled = False
    computer.IsStorageEnabled = False
    computer.IsNetworkEnabled = False
    computer.IsControllerEnabled = False
    if hasattr(computer, "IsBatteryEnabled"):
        computer.IsBatteryEnabled = False

    computer.Open()
    hardware_nodes_count = len(computer.Hardware)

    try:
        for hw in computer.Hardware:
            hw.Update()
            for node in _iter_hardware_tree(hw):
                if node.HardwareType != HardwareType.Cpu:
                    continue

                for sensor in node.Sensors:
                    if sensor.SensorType != SensorType.Temperature:
                        continue

                    sensor_name = str(sensor.Name)
                    lower_name = sensor_name.lower()
                    if "distance to tjmax" in lower_name:
                        continue

                    value = sensor.Value
                    rows.append(
                        {
                            "name": sensor_name,
                            "temp_c": float(value) if value is not None else None,
                            "identifier": str(sensor.Identifier),
                        }
                    )
    finally:
        computer.Close()

    rows.sort(key=lambda x: x["name"])
    if len(rows) == 0:
        return (
            rows,
            f"Found 0 CPU sensors across {hardware_nodes_count} LHM hardware nodes.",
        )
    return rows, None


def get_cpu_temperature_summary():
    """
    Returns a dict with:
    - cores: list of per-core temperature sensors
    - core_average_c: average of all readable core sensors
    - cpu_package_c: CPU package temperature when available
    - delta_cpu_minus_average_c: package minus core average
    """
    sensors, sys_error = get_cpu_core_temperatures()

    core_average = None
    cpu_package = None

    for sensor in sensors:
        name = str(sensor.get("name", ""))
        temp_c = sensor.get("temp_c")
        lower_name = name.lower()

        if "distance" in lower_name:
            continue

        if isinstance(temp_c, (int, float)):
            if "package" in lower_name or "tctl/tdie" in lower_name:
                cpu_package = temp_c
            if "average" in lower_name:
                core_average = temp_c

    # If LHM didn't outright give us an "average", calculate it from specific cores
    if core_average is None:
        core_rows = [
            s
            for s in sensors
            if any(
                m in str(s.get("name", "")).lower()
                for m in ("core #", "p-core", "e-core", "ccd")
            )
        ]
        valid_temps = [
            s["temp_c"] for s in core_rows if isinstance(s.get("temp_c"), (int, float))
        ]
        if valid_temps:
            core_average = sum(valid_temps) / len(valid_temps)

    # Ultimate fallback: Average ANY CPU temperature sensor
    if core_average is None and cpu_package is None:
        valid_temps = [
            s["temp_c"]
            for s in sensors
            if "distance" not in str(s.get("name", "")).lower()
            and isinstance(s.get("temp_c"), (int, float))
        ]
        if valid_temps:
            core_average = sum(valid_temps) / len(valid_temps)

    final_avg = core_average if core_average is not None else cpu_package

    return {
        "cores": sensors,
        "core_average_c": final_avg,
        "cpu_package_c": cpu_package,
        "delta_cpu_minus_average_c": None,
        "clr_error": clr_error,
        "sys_error": sys_error,
    }


def get_gpu_core_temperature():
    if clr is None:
        return None, "CLR missing"

    dll_path = _resolve_lhm_dll_path()
    if dll_path is None:
        return None, "DLL missing"

    try:
        clr.AddReference(str(dll_path.resolve()))
        from LibreHardwareMonitor.Hardware import Computer, HardwareType, SensorType  # type: ignore
    except Exception as e:
        return None, f"GPU Init Error: {e}"

    computer = Computer()
    computer.IsCpuEnabled = False
    computer.IsGpuEnabled = True
    computer.IsMotherboardEnabled = False
    computer.IsMemoryEnabled = False
    computer.IsStorageEnabled = False
    computer.IsNetworkEnabled = False
    computer.IsControllerEnabled = False
    if hasattr(computer, "IsBatteryEnabled"):
        computer.IsBatteryEnabled = False

    computer.Open()
    hw_count = len(computer.Hardware)
    try:
        best_temp = None
        for hw in computer.Hardware:
            hw.Update()
            for node in _iter_hardware_tree(hw):
                if node.HardwareType not in (
                    HardwareType.GpuNvidia,
                    HardwareType.GpuAmd,
                    HardwareType.GpuIntel,
                ):
                    continue

                for sensor in node.Sensors:
                    if sensor.SensorType != SensorType.Temperature:
                        continue

                    val = sensor.Value
                    if val is None:
                        continue

                    sensor_name = str(sensor.Name).lower()
                    if (
                        "core" in sensor_name
                        or "die" in sensor_name
                        or "edge" in sensor_name
                    ):
                        return float(val), None

                    if best_temp is None:
                        best_temp = float(val)

        if best_temp is not None:
            return best_temp, None
        return None, f"Found 0 GPU sensors across {hw_count} LHM hardware nodes."
    finally:
        computer.Close()

    return None, None
