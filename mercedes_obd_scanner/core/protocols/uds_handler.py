"""
Обработчик UDS-протокола для Mercedes OBD Scanner
"""
import can
import isotp
from udsoncan.client import Client
from udsoncan.connections import IsoTPConnection
from udsoncan.services import ReadDataByIdentifier, ClearDiagnosticInformation
from udsoncan.exceptions import *
from typing import List, Dict, Any, Callable

from .base_handler import ProtocolHandler

class UDSProtocolHandler(ProtocolHandler):
    """Обработчик для UDS (ISO 14229) протокола"""

    def __init__(self, data_callback: Callable, status_callback: Callable):
        super().__init__(data_callback, status_callback)
        self.can_bus = None
        self.uds_client = None

    def connect(self, port: str, **kwargs) -> bool:
        try:
            self.status_callback("connecting")
            self.can_bus = can.interface.Bus(channel=port, bustype='socketcan', bitrate=500000)
            tp_addr = isotp.Address(txid=0x7E0, rxid=0x7E8)
            stack = isotp.CanStack(self.can_bus, address=tp_addr)
            self.uds_client = Client(IsoTPConnection(stack), request_timeout=2)
            self.uds_client.open()
            self.is_connected = self.uds_client.is_open()
            if self.is_connected:
                self.status_callback("connected")
            else:
                self.status_callback("error")
            return self.is_connected
        except Exception as e:
            print(f"UDS connection error: {e}")
            self.is_connected = False
            self.status_callback("error")
            return False

    def disconnect(self):
        if self.uds_client:
            self.uds_client.close()
        if self.can_bus:
            self.can_bus.shutdown()
        self.is_connected = False
        self.status_callback("disconnected")

    def update_data(self):
        if not self.is_connected:
            return

        # Mercedes-специфичные параметры (примеры)
        # Давление в шинах (Tire Pressure Monitoring System)
        try:
            response = self.uds_client.read_data_by_identifier(0xFD47) # Пример DID
            # Здесь нужна логика парсинга ответа
            # self.data_callback("tire_pressure_fl", parsed_value, "bar")
        except Exception as e:
            print(f"Error reading TPMS: {e}")

        # Напряжение Airmatic
        try:
            response = self.uds_client.read_data_by_identifier(0xFD48) # Пример DID
            # Здесь нужна логика парсинга ответа
            # self.data_callback("airmatic_voltage", parsed_value, "V")
        except Exception as e:
            print(f"Error reading Airmatic voltage: {e}")

    def get_diagnostic_codes(self) -> List[Dict[str, Any]]:
        # TODO: Реализовать чтение DTC через UDS
        return []

    def clear_diagnostic_codes(self) -> bool:
        # TODO: Реализовать очистку DTC через UDS
        return False

    @staticmethod
    def get_available_ports() -> List[str]:
        # python-can не предоставляет простого способа сканирования
        # Обычно порты известны заранее (например, 'can0')
        return ['can0', 'can1', 'vcan0']

