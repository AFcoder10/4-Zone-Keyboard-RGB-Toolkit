from pathlib import Path

try:
    import clr
except Exception:
    clr = None


def _iter_hardware_tree(hardware):
    yield hardware
    for sub_hw in hardware.SubHardware:
        sub_hw.Update()
        yield from _iter_hardware_tree(sub_hw)


def _resolve_lhm_dll_path():
    import sys
    import os
    if hasattr(sys, '_MEIPASS'):
        base = Path(sys._MEIPASS)
    else:
        # Fallback for source execution. Assume this file is one level up from python_app or at root
        base = Path(os.path.abspath(os.path.dirname(__file__)))
        
    candidates = [
        base / "LibreHardwareMonitor" / "LibreHardwareMonitorLib.dll",
        Path("LibreHardwareMonitor/LibreHardwareMonitorLib.dll"),
        Path("lhm_extracted/ref/netstandard2.0/LibreHardwareMonitorLib.dll"),
        Path("lhm_extracted/ref/net472/LibreHardwareMonitorLib.dll"),
    ]
    return next((p for p in candidates if p.exists()), None)


def get_cpu_core_temperatures():
    """
    Returns a list of CPU temperature sensors from LibreHardwareMonitor.
    Each item has: name, temp_c, identifier
    """
    if clr is None:
        return []

    dll_path = _resolve_lhm_dll_path()
    if dll_path is None:
        return []

    try:
        clr.AddReference(str(dll_path.resolve()))
        from LibreHardwareMonitor.Hardware import Computer, HardwareType, SensorType  # type: ignore
    except Exception:
        return []

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
                    if not (
                        "p-core #" in lower_name
                        or "e-core #" in lower_name
                        or "core #" in lower_name
                        or "cpu package" in lower_name
                    ):
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
    return rows


def get_cpu_temperature_summary():
    """
    Returns a dict with:
    - cores: list of per-core temperature sensors
    - core_average_c: average of all readable core sensors
    - cpu_package_c: CPU package temperature when available
    - delta_cpu_minus_average_c: package minus core average
    """
    sensors = get_cpu_core_temperatures()

    core_rows = []
    package_row = None

    for sensor in sensors:
        name = str(sensor.get("name", ""))
        temp_c = sensor.get("temp_c")
        lower_name = name.lower()

        if "distance to tjmax" in lower_name:
            continue

        if "cpu package" in lower_name:
            if isinstance(temp_c, (int, float)):
                package_row = sensor
            continue

        if any(marker in lower_name for marker in ("p-core #", "e-core #", "core #")):
            if isinstance(temp_c, (int, float)):
                core_rows.append(sensor)

    core_average = None
    if core_rows:
        core_average = sum(float(row["temp_c"]) for row in core_rows) / len(core_rows)

    cpu_package = None
    if package_row is not None:
        cpu_package = float(package_row["temp_c"])

    delta = None
    if cpu_package is not None and core_average is not None:
        delta = cpu_package - core_average

    return {
        "cores": core_rows,
        "core_average_c": core_average,
        "cpu_package_c": cpu_package,
        "delta_cpu_minus_average_c": delta,
    }


def get_gpu_core_temperature():
    """
    Returns the GPU Core temperature from LibreHardwareMonitor.
    It returns a float value or None if not found.
    """
    if clr is None:
        return None

    dll_path = _resolve_lhm_dll_path()
    if dll_path is None:
        return None

    try:
        clr.AddReference(str(dll_path.resolve()))
        from LibreHardwareMonitor.Hardware import Computer, HardwareType, SensorType  # type: ignore
    except Exception:
        return None

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
    try:
        for hw in computer.Hardware:
            hw.Update()
            for node in _iter_hardware_tree(hw):
                if node.HardwareType not in (HardwareType.GpuNvidia, HardwareType.GpuAmd, HardwareType.GpuIntel):
                    continue

                for sensor in node.Sensors:
                    if sensor.SensorType != SensorType.Temperature:
                        continue

                    sensor_name = str(sensor.Name).lower()
                    if "gpu core" in sensor_name or "gpu" in sensor_name:
                        value = sensor.Value
                        if value is not None:
                            return float(value)
    finally:
        computer.Close()

    return None

