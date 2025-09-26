"""
Главный контроллер приложения Mercedes OBD Scanner v2.0
"""
import threading
import time
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import queue
import json
from datetime import datetime

from ..core.obd_controller import OBDController
from ..core.config_manager import ConfigManager


class ConnectionStatus(Enum):
    """Статусы подключения"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class DiagnosticStatus(Enum):
    """Статусы диагностики"""
    IDLE = "idle"
    SCANNING = "scanning"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class ParameterData:
    """Данные параметра"""
    name: str
    value: Any
    unit: str
    timestamp: datetime
    status: str = "ok"  # ok, warning, error
    min_value: Optional[float] = None
    max_value: Optional[float] = None


@dataclass
class DiagnosticCode:
    """Диагностический код ошибки"""
    code: str
    description: str
    status: str  # active, pending, permanent
    system: str
    severity: str  # info, warning, error


class AppController:
    """Главный контроллер приложения"""
    
    def __init__(self):
        # Инициализация компонентов
        self.obd_controller = OBDController()
        self.config_manager = ConfigManager()
        
        # Состояние приложения
        self.connection_status = ConnectionStatus.DISCONNECTED
        self.diagnostic_status = DiagnosticStatus.IDLE
        
        # Данные
        self.real_time_data: Dict[str, ParameterData] = {}
        self.diagnostic_codes: List[DiagnosticCode] = []
        self.data_history: Dict[str, List[tuple]] = {}  # parameter_name: [(timestamp, value), ...]
        
        # Наблюдатели (Observer pattern)
        self.observers: Dict[str, List[Callable]] = {
            'connection_status': [],
            'diagnostic_status': [],
            'parameter_update': [],
            'diagnostic_codes': [],
            'error': []
        }
        
        # Потоки и очереди
        self.data_thread: Optional[threading.Thread] = None
        self.data_queue = queue.Queue()
        self.stop_event = threading.Event()
        
        # Настройки
        self.update_interval = 0.5  # секунды
        self.max_history_points = 1000
        
        # Инициализация
        self._setup_obd_callbacks()
        
    def _setup_obd_callbacks(self):
        """Настройка callback'ов для OBD контроллера"""
        self.obd_controller.add_data_callback(self._on_obd_data)
        self.obd_controller.add_status_callback(self._on_obd_status)
        
    def _on_obd_data(self, parameter: str, value: Any, unit: str = ""):
        """Обработка данных от OBD контроллера"""
        timestamp = datetime.now()
        
        # Определение статуса параметра
        status = self._determine_parameter_status(parameter, value)
        
        # Создание объекта данных
        param_data = ParameterData(
            name=parameter,
            value=value,
            unit=unit,
            timestamp=timestamp,
            status=status
        )
        
        # Обновление текущих данных
        self.real_time_data[parameter] = param_data
        
        # Добавление в историю
        if parameter not in self.data_history:
            self.data_history[parameter] = []
            
        self.data_history[parameter].append((timestamp, value))
        
        # Ограничение размера истории
        if len(self.data_history[parameter]) > self.max_history_points:
            self.data_history[parameter] = self.data_history[parameter][-self.max_history_points:]
            
        # Уведомление наблюдателей
        self.notify_observers('parameter_update', parameter, param_data)
        
    def _on_obd_status(self, status: str):
        """Обработка изменения статуса OBD"""
        if status == "connected":
            self.connection_status = ConnectionStatus.CONNECTED
        elif status == "connecting":
            self.connection_status = ConnectionStatus.CONNECTING
        elif status == "disconnected":
            self.connection_status = ConnectionStatus.DISCONNECTED
        else:
            self.connection_status = ConnectionStatus.ERROR
            
        self.notify_observers('connection_status', self.connection_status)
        
    def _determine_parameter_status(self, parameter: str, value: Any) -> str:
        """Определение статуса параметра на основе его значения"""
        try:
            # Получение конфигурации параметра
            param_config = self.config_manager.get_parameter(parameter)
            if not param_config:
                return "ok"
                
            # Проверка диапазонов
            if isinstance(value, (int, float)):
                min_val = param_config.get('min_value')
                max_val = param_config.get('max_value')
                warning_min = param_config.get('warning_min')
                warning_max = param_config.get('warning_max')
                
                # Критические значения
                if min_val is not None and value < min_val:
                    return "error"
                if max_val is not None and value > max_val:
                    return "error"
                    
                # Предупреждения
                if warning_min is not None and value < warning_min:
                    return "warning"
                if warning_max is not None and value > warning_max:
                    return "warning"
                    
            return "ok"
            
        except Exception:
            return "ok"
            
    # Методы подключения
    def connect_obd(self, protocol: str, port: str) -> bool:
        """Подключение к OBD сканеру"""
        try:
            self.connection_status = ConnectionStatus.CONNECTING
            self.notify_observers('connection_status', self.connection_status)
            
            success = self.obd_controller.connect(protocol, port)
            
            if success:
                self.connection_status = ConnectionStatus.CONNECTED
                self._start_data_thread()
            else:
                self.connection_status = ConnectionStatus.ERROR
                
            self.notify_observers('connection_status', self.connection_status)
            return success
            
        except Exception as e:
            self.connection_status = ConnectionStatus.ERROR
            self.notify_observers('connection_status', self.connection_status)
            self.notify_observers('error', f"Ошибка подключения: {e}")
            return False
            
    def disconnect_obd(self):
        """Отключение от OBD сканера"""
        try:
            self._stop_data_thread()
            self.obd_controller.disconnect()
            self.connection_status = ConnectionStatus.DISCONNECTED
            self.notify_observers('connection_status', self.connection_status)
            
        except Exception as e:
            self.notify_observers('error', f"Ошибка отключения: {e}")
            
    def get_available_protocols(self) -> List[str]:
        """Получение списка доступных протоколов"""
        return self.obd_controller.get_available_protocols()

    def get_available_ports(self, protocol: str) -> List[str]:
        """Получение списка доступных портов для протокола"""
        return self.obd_controller.get_available_ports(protocol)
        
    # Методы работы с данными
    def _start_data_thread(self):
        """Запуск потока для получения данных"""
        if self.data_thread and self.data_thread.is_alive():
            return
            
        self.stop_event.clear()
        self.data_thread = threading.Thread(target=self._data_loop, daemon=True)
        self.data_thread.start()
        
    def _stop_data_thread(self):
        """Остановка потока данных"""
        self.stop_event.set()
        if self.data_thread and self.data_thread.is_alive():
            self.data_thread.join(timeout=2.0)
            
    def _data_loop(self):
        """Основной цикл получения данных"""
        while not self.stop_event.is_set():
            try:
                if self.connection_status == ConnectionStatus.CONNECTED:
                    # Получение данных от OBD контроллера
                    self.obd_controller.update_data()
                    
                time.sleep(self.update_interval)
                
            except Exception as e:
                self.notify_observers('error', f"Ошибка в цикле данных: {e}")
                time.sleep(1.0)
                
    def get_real_time_data(self) -> Dict[str, ParameterData]:
        """Получение текущих данных в реальном времени"""
        return self.real_time_data.copy()
        
    def get_parameter_history(self, parameter: str, max_points: int = None) -> List[tuple]:
        """Получение истории параметра"""
        history = self.data_history.get(parameter, [])
        if max_points:
            return history[-max_points:]
        return history
        
    def get_parameter_value(self, parameter: str) -> Optional[ParameterData]:
        """Получение текущего значения параметра"""
        return self.real_time_data.get(parameter)
        
    # Методы диагностики
    def start_diagnostic_scan(self) -> bool:
        """Запуск диагностического сканирования"""
        try:
            if self.connection_status != ConnectionStatus.CONNECTED:
                self.notify_observers('error', "Нет подключения к OBD сканеру")
                return False
                
            self.diagnostic_status = DiagnosticStatus.SCANNING
            self.notify_observers('diagnostic_status', self.diagnostic_status)
            
            # Запуск сканирования в отдельном потоке
            scan_thread = threading.Thread(target=self._diagnostic_scan_loop, daemon=True)
            scan_thread.start()
            
            return True
            
        except Exception as e:
            self.diagnostic_status = DiagnosticStatus.ERROR
            self.notify_observers('diagnostic_status', self.diagnostic_status)
            self.notify_observers('error', f"Ошибка запуска диагностики: {e}")
            return False
            
    def _diagnostic_scan_loop(self):
        """Цикл диагностического сканирования"""
        try:
            # Очистка предыдущих кодов
            self.diagnostic_codes.clear()
            
            # Получение кодов ошибок
            codes = self.obd_controller.get_diagnostic_codes()
            
            for code_data in codes:
                diagnostic_code = DiagnosticCode(
                    code=code_data.get('code', ''),
                    description=code_data.get('description', 'Неизвестная ошибка'),
                    status=code_data.get('status', 'active'),
                    system=code_data.get('system', 'unknown'),
                    severity=code_data.get('severity', 'warning')
                )
                self.diagnostic_codes.append(diagnostic_code)
                
            self.diagnostic_status = DiagnosticStatus.COMPLETED
            self.notify_observers('diagnostic_status', self.diagnostic_status)
            self.notify_observers('diagnostic_codes', self.diagnostic_codes)
            
        except Exception as e:
            self.diagnostic_status = DiagnosticStatus.ERROR
            self.notify_observers('diagnostic_status', self.diagnostic_status)
            self.notify_observers('error', f"Ошибка диагностики: {e}")
            
    def clear_diagnostic_codes(self) -> bool:
        """Очистка диагностических кодов"""
        try:
            if self.connection_status != ConnectionStatus.CONNECTED:
                self.notify_observers('error', "Нет подключения к OBD сканеру")
                return False
                
            success = self.obd_controller.clear_diagnostic_codes()
            
            if success:
                self.diagnostic_codes.clear()
                self.notify_observers('diagnostic_codes', self.diagnostic_codes)
                
            return success
            
        except Exception as e:
            self.notify_observers('error', f"Ошибка очистки кодов: {e}")
            return False
            
    def get_diagnostic_codes(self) -> List[DiagnosticCode]:
        """Получение диагностических кодов"""
        return self.diagnostic_codes.copy()
        
    # Методы экспорта данных
    def export_data(self, filename: str, format: str = "json") -> bool:
        """Экспорт данных в файл"""
        try:
            data = {
                'timestamp': datetime.now().isoformat(),
                'connection_status': self.connection_status.value,
                'real_time_data': {
                    param: {
                        'name': data.name,
                        'value': data.value,
                        'unit': data.unit,
                        'timestamp': data.timestamp.isoformat(),
                        'status': data.status
                    }
                    for param, data in self.real_time_data.items()
                },
                'diagnostic_codes': [
                    {
                        'code': code.code,
                        'description': code.description,
                        'status': code.status,
                        'system': code.system,
                        'severity': code.severity
                    }
                    for code in self.diagnostic_codes
                ],
                'data_history': {
                    param: [(ts.isoformat(), val) for ts, val in history]
                    for param, history in self.data_history.items()
                }
            }
            
            if format.lower() == "json":
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            else:
                raise ValueError(f"Неподдерживаемый формат: {format}")
                
            return True
            
        except Exception as e:
            self.notify_observers('error', f"Ошибка экспорта данных: {e}")
            return False
            
    # Методы наблюдателей (Observer pattern)
    def add_observer(self, event_type: str, callback: Callable):
        """Добавление наблюдателя для события"""
        if event_type in self.observers:
            self.observers[event_type].append(callback)
            
    def remove_observer(self, event_type: str, callback: Callable):
        """Удаление наблюдателя"""
        if event_type in self.observers and callback in self.observers[event_type]:
            self.observers[event_type].remove(callback)
            
    def notify_observers(self, event_type: str, *args, **kwargs):
        """Уведомление наблюдателей о событии"""
        if event_type in self.observers:
            for callback in self.observers[event_type]:
                try:
                    callback(*args, **kwargs)
                except Exception as e:
                    print(f"Ошибка в callback {callback}: {e}")
                    
    # Методы настроек
    def set_update_interval(self, interval: float):
        """Установка интервала обновления данных"""
        self.update_interval = max(0.1, interval)
        
    def get_connection_status(self) -> ConnectionStatus:
        """Получение статуса подключения"""
        return self.connection_status
        
    def get_diagnostic_status(self) -> DiagnosticStatus:
        """Получение статуса диагностики"""
        return self.diagnostic_status
        
    def is_connected(self) -> bool:
        """Проверка подключения"""
        return self.connection_status == ConnectionStatus.CONNECTED
        
    def cleanup(self):
        """Очистка ресурсов"""
        self._stop_data_thread()
        self.disconnect_obd()
