"""
OBD контроллер v2.0 с поддержкой стратегии протоколов
"""

from typing import List, Dict, Any, Callable, Optional, Type

from .protocols import ProtocolHandler, DemoProtocolHandler, OBDProtocolHandler, UDSProtocolHandler


class OBDController:
    """Контроллер для работы с OBD, использующий стратегию протоколов"""

    def __init__(self):
        self.data_callbacks: List[Callable] = []
        self.status_callbacks: List[Callable] = []

        self.protocol_handlers: Dict[str, Type[ProtocolHandler]] = {
            "DEMO": DemoProtocolHandler,
            "OBD-II": OBDProtocolHandler,
            "UDS": UDSProtocolHandler,
        }

        self.active_handler: Optional[ProtocolHandler] = None

    def add_data_callback(self, callback: Callable):
        self.data_callbacks.append(callback)

    def add_status_callback(self, callback: Callable):
        self.status_callbacks.append(callback)

    def _on_data(self, parameter: str, value: Any, unit: str):
        for callback in self.data_callbacks:
            callback(parameter, value, unit)

    def _on_status(self, status: str, message: str = ""):
        for callback in self.status_callbacks:
            callback(status, message)

    def get_available_protocols(self) -> List[str]:
        return list(self.protocol_handlers.keys())

    def get_available_ports(self, protocol: str) -> List[str]:
        handler_class = self.protocol_handlers.get(protocol)
        if handler_class:
            return handler_class.get_available_ports()
        return []

    def connect(self, protocol: str, port: str, **kwargs) -> bool:
        if self.active_handler:
            self.disconnect()

        handler_class = self.protocol_handlers.get(protocol)
        if not handler_class:
            self._on_status("error", f"Unsupported protocol: {protocol}")
            raise ValueError(f"Unsupported protocol: {protocol}")

        self.active_handler = handler_class(self._on_data, self._on_status)
        return self.active_handler.connect(port, **kwargs)

    def disconnect(self):
        if self.active_handler:
            self.active_handler.disconnect()
            self.active_handler = None

    def update_data(self):
        if self.active_handler and self.active_handler.is_connected:
            self.active_handler.update_data()

    def get_diagnostic_codes(self) -> List[Dict[str, Any]]:
        if self.active_handler and self.active_handler.is_connected:
            return self.active_handler.get_diagnostic_codes()
        return []

    def clear_diagnostic_codes(self) -> bool:
        if self.active_handler and self.active_handler.is_connected:
            return self.active_handler.clear_diagnostic_codes()
        return False

    @property
    def is_connected(self) -> bool:
        return self.active_handler is not None and self.active_handler.is_connected
