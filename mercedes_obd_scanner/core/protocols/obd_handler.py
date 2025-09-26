"""
Обработчик OBD-протокола для Mercedes OBD Scanner
"""
import obd
from typing import List, Dict, Any, Callable

from .base_handler import ProtocolHandler

class OBDProtocolHandler(ProtocolHandler):
    """Обработчик для стандартного OBD-II протокола"""

    def __init__(self, data_callback: Callable, status_callback: Callable):
        super().__init__(data_callback, status_callback)
        self.connection = None
        self.supported_commands = []

    def connect(self, port: str, **kwargs) -> bool:
        try:
            self.status_callback("connecting")
            self.connection = obd.OBD(port, **kwargs)
            if self.connection.is_connected():
                self.is_connected = True
                self.status_callback("connected")
                self.supported_commands = [cmd.name for cmd in self.connection.supported_commands]
                return True
            else:
                self.is_connected = False
                self.status_callback("error")
                return False
        except Exception as e:
            print(f"OBD connection error: {e}")
            self.is_connected = False
            self.status_callback("error")
            return False

    def disconnect(self):
        if self.connection:
            self.connection.close()
        self.is_connected = False
        self.status_callback("disconnected")

    def update_data(self):
        if not self.is_connected:
            return

        # Стандартные OBD-II параметры
        param_map = {
            "RPM": "engine_rpm",
            "SPEED": "vehicle_speed",
            "COOLANT_TEMP": "engine_temp",
            "FUEL_LEVEL": "fuel_level",
            "THROTTLE_POS": "throttle_position",
            "INTAKE_PRESSURE": "intake_pressure"
        }

        for obd_cmd, internal_name in param_map.items():
            if obd_cmd in self.supported_commands:
                try:
                    cmd = obd.commands[obd_cmd]
                    response = self.connection.query(cmd, force=True)
                    if response and not response.is_null():
                        self.data_callback(internal_name, response.value.magnitude, str(response.value.units))
                except Exception as e:
                    print(f"Error reading {obd_cmd}: {e}")

    def get_diagnostic_codes(self) -> List[Dict[str, Any]]:
        if not self.is_connected:
            return []

        try:
            response = self.connection.query(obd.commands.GET_DTC)
            if response and not response.is_null():
                return [
                    {
                        "code": code[0],
                        "description": code[1],
                        "status": "active",
                        "system": "obd",
                        "severity": "warning"
                    }
                    for code in response.value
                ]
            return []
        except Exception as e:
            print(f"Error getting DTCs: {e}")
            return []

    def clear_diagnostic_codes(self) -> bool:
        if not self.is_connected:
            return False

        try:
            response = self.connection.query(obd.commands.CLEAR_DTC)
            return response is not None
        except Exception as e:
            print(f"Error clearing DTCs: {e}")
            return False

    @staticmethod
    def get_available_ports() -> List[str]:
        try:
            ports = obd.scan_serial()
            return [p for p in ports if "COM" in p or "tty" in p]
        except Exception as e:
            print(f"Error scanning ports: {e}")
            return []

