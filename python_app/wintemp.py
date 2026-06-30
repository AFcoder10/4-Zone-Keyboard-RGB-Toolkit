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
        base = Path(os.path.abspath(os.path.dirname(__file__)))

    candidates = [
        base / "LibreHardwareMonitor" / "LibreHardwareMonitorLib.dll",
        Path("LibreHardwareMonitor/LibreHardwareMonitorLib.dll"),
        Path("lhm_extracted/ref/netstandard2.0/LibreHardwareMonitorLib.dll"),
        Path("lhm_extracted/ref/net472/LibreHardwareMonitorLib.dll"),
    ]
    return next((p for p in candidates if p.exists()), None)


class HardwareMonitor:
    def __init__(self):
        self.computer = None
        self.init_error = None
        self.hardware_nodes_count = 0
        self.HardwareType = None
        self.SensorType = None

        if clr is None:
            self.init_error = f"CLR module missing: {clr_error}"
            return

        dll_path = _resolve_lhm_dll_path()
        if dll_path is None:
            self.init_error = "LHM DLL not found"
            return

        try:
            clr.AddReference(str(dll_path.resolve()))
            from LibreHardwareMonitor.Hardware import Computer, HardwareType, SensorType  # type: ignore
            self.HardwareType = HardwareType
            self.SensorType = SensorType
        except Exception as e:
            self.init_error = f"LHM Init Error: {e}"
            return

        self.computer = Computer()
        self.computer.IsCpuEnabled = True
        self.computer.IsGpuEnabled = True
        self.computer.IsMotherboardEnabled = False
        self.computer.IsMemoryEnabled = False
        self.computer.IsStorageEnabled = False
        self.computer.IsNetworkEnabled = False
        self.computer.IsControllerEnabled = False
        if hasattr(self.computer, "IsBatteryEnabled"):
            self.computer.IsBatteryEnabled = False

        try:
            self.computer.Open()
            self.hardware_nodes_count = len(self.computer.Hardware)
        except Exception as e:
            self.init_error = f"Failed to open computer: {e}"
            self.computer = None

    def close(self):
        if self.computer:
            try:
                self.computer.Close()
            except Exception:
                pass
            self.computer = None

    def get_cpu_core_temperatures(self):
        if self.init_error:
            return [], self.init_error
        if self.computer is None:
            return [], "Computer not initialized"

        rows = []
        try:
            for hw in self.computer.Hardware:
                hw.Update()
                for node in _iter_hardware_tree(hw):
                    if node.HardwareType != self.HardwareType.Cpu:
                        continue

                    for sensor in node.Sensors:
                        if sensor.SensorType != self.SensorType.Temperature:
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
        except Exception as e:
            return [], f"Update Error: {e}"

        rows.sort(key=lambda x: x["name"])
        if len(rows) == 0:
            return (
                rows,
                f"Found 0 CPU sensors across {self.hardware_nodes_count} LHM hardware nodes.",
            )
        return rows, None

    def get_cpu_temperature_summary(self):
        sensors, sys_error = self.get_cpu_core_temperatures()

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

    def get_gpu_core_temperature(self):
        if self.init_error:
            return None, self.init_error
        if self.computer is None:
            return None, "Computer not initialized"

        try:
            best_temp = None
            for hw in self.computer.Hardware:
                hw.Update()
                for node in _iter_hardware_tree(hw):
                    if node.HardwareType not in (
                        self.HardwareType.GpuNvidia,
                        self.HardwareType.GpuAmd,
                        self.HardwareType.GpuIntel,
                    ):
                        continue

                    for sensor in node.Sensors:
                        if sensor.SensorType != self.SensorType.Temperature:
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
            return None, f"Found 0 GPU sensors across {self.hardware_nodes_count} LHM hardware nodes."
        except Exception as e:
            return None, f"GPU Update Error: {e}"
