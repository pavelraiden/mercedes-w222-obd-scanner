"""
Базовый класс для обработчиков протоколов
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Callable


class ProtocolHandler(ABC):
    """Абстрактный базовый класс для обработчиков протоколов"""

    def __init__(self, data_callback: Callable, status_callback: Callable):
        self.data_callback = data_callback
        self.status_callback = status_callback
        self.is_connected = False

    @abstractmethod
    def connect(self, port: str, **kwargs) -> bool:
        """Подключение к устройству"""
        pass

    @abstractmethod
    def disconnect(self):
        """Отключение от устройства"""
        pass

    @abstractmethod
    def update_data(self):
        """Обновление данных"""
        pass

    @abstractmethod
    def get_diagnostic_codes(self) -> List[Dict[str, Any]]:
        """Получение диагностических кодов"""
        pass

    @abstractmethod
    def clear_diagnostic_codes(self) -> bool:
        """Очистка диагностических кодов"""
        pass

    @staticmethod
    def get_available_ports() -> List[str]:
        """Получение списка доступных портов"""
        return []
