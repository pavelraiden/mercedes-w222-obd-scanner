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
        self.status_callback("connecting")
        time.sleep(1)
        self.is_connected = True
        self.status_callback("connected")
        return True

    def disconnect(self):
        self.is_connected = False
        self.status_callback("disconnected")

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

        self.data_callback("engine_rpm", rpm, "об/мин")
        self.data_callback("vehicle_speed", speed, "км/ч")
        self.data_callback("engine_temp", temp, "°C")
        self.data_callback("fuel_level", fuel, "%")
        self.data_callback("throttle_position", throttle, "%")
        self.data_callback("intake_pressure", pressure, "кПа")

    def get_diagnostic_codes(self) -> List[Dict[str, Any]]:
        # Имитация кодов ошибок
        return [
            {
                "code": "P0301",
                "description": "Cylinder 1 Misfire Detected",
                "status": "active",
                "system": "engine",
                "severity": "error"
            },
            {
                "code": "U0121",
                "description": "Lost Communication With Anti-Lock Brake System (ABS) Control Module",
                "status": "pending",
                "system": "abs",
                "severity": "warning"
            }
        ]

    def clear_diagnostic_codes(self) -> bool:
        return True

    @staticmethod
    def get_available_ports() -> List[str]:
        return ["DEMO"]
