"""
Обработчик демо-протокола для Mercedes OBD Scanner
"""
import time
import random
from typing import List, Dict, Any, Callable

from .base_handler import ProtocolHandler

class DemoProtocolHandler(ProtocolHandler):
    """Обработчик для демонстрационного режима"""

    def __init__(self, data_callback: Callable, status_callback: Callable):
        super().__init__(data_callback, status_callback)
        self.start_time = time.time()

    def connect(self, port: str, **kwargs) -> bool:
        self.status_callback("connecting", "Connecting in demo mode...")
        time.sleep(1)
        self.is_connected = True
        self.status_callback("connected", "Successfully connected in demo mode.")
        return True

    def disconnect(self):
        self.is_connected = False
        self.status_callback("disconnected", "Disconnected from demo mode.")

    def update_data(self):
        if not self.is_connected:
            return

        # Имитация данных
        elapsed_time = time.time() - self.start_time
        rpm = 2000 + 1000 * (1 + random.uniform(-0.1, 0.1)) * (1 + 0.5 * random.random() * (elapsed_time % 10))
        speed = 80 + 20 * (1 + random.uniform(-0.1, 0.1)) * (1 + 0.5 * random.random() * (elapsed_time % 10))
        temp = 90 + 5 * random.uniform(-0.5, 0.5)
        fuel = 60 - 5 * (elapsed_time / 60)
        throttle = 30 + 10 * random.random()
        pressure = 101.3 + 2 * random.random()

        self.data_callback("ENGINE_RPM", rpm, "об/мин")
        self.data_callback("VEHICLE_SPEED", speed, "км/ч")
        self.data_callback("COOLANT_TEMP", temp, "°C")
        self.data_callback("FUEL_LEVEL", fuel, "%")
        self.data_callback("THROTTLE_POS", throttle, "%")
        self.data_callback("INTAKE_PRESSURE", pressure, "кПа")

    def get_diagnostic_codes(self) -> List[Dict[str, Any]]:
        # Имитация кодов ошибок
        return [
            {
                "code": "P0301",
                "description": "Cylinder 1 Misfire Detected",
                "status": "active",
                "system": "engine",
                "severity": "error"
            }
        ]

    def clear_diagnostic_codes(self) -> bool:
        return True

    @staticmethod
    def get_available_ports() -> List[str]:
        return ["DEMO"]

