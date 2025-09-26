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
from ..data import DatabaseManager, DataExporter, ReportGenerator


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
        self.db_manager = DatabaseManager()
        self.data_exporter = DataExporter(self.db_manager)
        self.report_generator = ReportGenerator(self.db_manager)
        
        # Состояние приложения
        self.connection_status = ConnectionStatus.DISCONNECTED
        self.diagnostic_status = DiagnosticStatus.IDLE
        
        # Текущая сессия
        self.current_session_id: Optional[str] = None
        self.current_vehicle_id: Optional[str] = None
        self.current_protocol: Optional[str] = None
        
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
            'error': [],
            'session_started': [],
            'session_ended': []
        }
        
        # Потоки и очереди
        self.data_thread: Optional[threading.Thread] = None
        self.data_queue = queue.Queue()
        self.stop_event = threading.Event()
        
        # Настройки
        self.update_interval = 0.5  # секунды
        self.max_history_points = 1000
        self.auto_logging = True  # Автоматическое логирование
        
        # Пороги для алертов
        self.alert_thresholds = {
            'engine_temp': {'warning': 105, 'critical': 110},
            'engine_rpm': {'warning': 5500, 'critical': 6500},
            'oil_pressure': {'warning': 2.0, 'critical': 1.5}
        }
        
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
            
        # Логирование в базу данных
        if self.auto_logging and self.current_session_id:
            try:
                self.db_manager.log_parameter(
                    session_id=self.current_session_id,
                    parameter_name=parameter,
                    value=float(value) if isinstance(value, (int, float)) else 0,
                    unit=unit,
                    status=status,
                    vehicle_id=self.current_vehicle_id,
                    protocol=self.current_protocol
                )
            except Exception as e:
                self.notify_observers('error', f"Ошибка логирования: {e}")
                
        # Проверка алертов
        self._check_alerts(parameter, value, timestamp)
            
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
            # Проверка пороговых значений
            if parameter in self.alert_thresholds and isinstance(value, (int, float)):
                thresholds = self.alert_thresholds[parameter]
                
                if 'critical' in thresholds and value >= thresholds['critical']:
                    return "error"
                elif 'warning' in thresholds and value >= thresholds['warning']:
                    return "warning"
                    
            # Получение конфигурации параметра
            param_config = self.config_manager.get_parameter(parameter)
            if param_config and isinstance(value, (int, float)):
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
            
    def _check_alerts(self, parameter: str, value: Any, timestamp: datetime):
        """Проверка алертов для параметра"""
        if parameter not in self.alert_thresholds or not isinstance(value, (int, float)):
            return
            
        thresholds = self.alert_thresholds[parameter]
        
        # Проверка критического порога
        if 'critical' in thresholds and value >= thresholds['critical']:
            self._create_alert(parameter, value, thresholds['critical'], 'critical', 
                             f"Критическое значение {parameter}: {value}")
                             
        # Проверка порога предупреждения
        elif 'warning' in thresholds and value >= thresholds['warning']:
            self._create_alert(parameter, value, thresholds['warning'], 'warning',
                             f"Предупреждение {parameter}: {value}")
                             
    def _create_alert(self, parameter: str, value: float, threshold: float, alert_type: str, message: str):
        """Создание алерта"""
        if self.current_session_id:
            try:
                self.db_manager.log_alert(
                    session_id=self.current_session_id,
                    parameter_name=parameter,
                    value=value,
                    threshold=threshold,
                    alert_type=alert_type,
                    message=message
                )
                
                # Уведомление GUI
                self.notify_observers('error', message)
                
            except Exception as e:
                self.notify_observers('error', f"Ошибка создания алерта: {e}")
            
    # Методы подключения
    def connect_obd(self, protocol: str, port: str, vehicle_id: str = None) -> bool:
        """Подключение к OBD сканеру"""
        try:
            self.connection_status = ConnectionStatus.CONNECTING
            self.notify_observers('connection_status', self.connection_status)
            
            success = self.obd_controller.connect(protocol, port)
            
            if success:
                self.connection_status = ConnectionStatus.CONNECTED
                self.current_protocol = protocol
                self.current_vehicle_id = vehicle_id or f"vehicle_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                # Создание новой сессии
                self.current_session_id = self.db_manager.create_session(
                    vehicle_id=self.current_vehicle_id,
                    protocol=protocol,
                    port=port
                )
                
                self._start_data_thread()
                self.notify_observers('session_started', self.current_session_id)
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
            
            # Завершение сессии
            if self.current_session_id:
                self.db_manager.end_session(self.current_session_id)
                self.notify_observers('session_ended', self.current_session_id)
                self.current_session_id = None
                
            self.obd_controller.disconnect()
            self.connection_status = ConnectionStatus.DISCONNECTED
            self.current_protocol = None
            self.current_vehicle_id = None
            
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
                
            # Логирование кодов в базу данных
            if self.current_session_id and codes:
                self.db_manager.log_diagnostic_codes(self.current_session_id, codes)
                
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
    def export_current_session(self, format: str = "json", filename: str = None) -> Optional[str]:
        """Экспорт текущей сессии"""
        if not self.current_session_id:
            self.notify_observers('error', "Нет активной сессии для экспорта")
            return None
            
        try:
            if format.lower() == "json":
                return self.data_exporter.export_session_to_json(self.current_session_id, filename)
            elif format.lower() == "csv":
                return self.data_exporter.export_session_to_csv(self.current_session_id, filename)
            elif format.lower() == "excel":
                return self.data_exporter.export_session_to_excel(self.current_session_id, filename)
            else:
                self.notify_observers('error', f"Неподдерживаемый формат: {format}")
                return None
                
        except Exception as e:
            self.notify_observers('error', f"Ошибка экспорта: {e}")
            return None
            
    def export_parameter_history(self, parameter: str, format: str = "csv", filename: str = None) -> Optional[str]:
        """Экспорт истории параметра"""
        try:
            return self.data_exporter.export_parameter_history(parameter, format=format, filename=filename)
        except Exception as e:
            self.notify_observers('error', f"Ошибка экспорта параметра: {e}")
            return None
            
    def generate_session_report(self, session_id: str = None, filename: str = None) -> Optional[str]:
        """Генерация отчета по сессии"""
        target_session = session_id or self.current_session_id
        
        if not target_session:
            self.notify_observers('error', "Нет сессии для генерации отчета")
            return None
            
        try:
            return self.report_generator.generate_session_report(target_session, filename)
        except Exception as e:
            self.notify_observers('error', f"Ошибка генерации отчета: {e}")
            return None
            
    def get_sessions_list(self, limit: int = 50) -> List[tuple]:
        """Получение списка сессий"""
        try:
            return self.db_manager.get_sessions(limit)
        except Exception as e:
            self.notify_observers('error', f"Ошибка получения списка сессий: {e}")
            return []
            
    def get_session_data(self, session_id: str) -> Dict[str, Any]:
        """Получение данных сессии"""
        try:
            return self.db_manager.get_session_data(session_id)
        except Exception as e:
            self.notify_observers('error', f"Ошибка получения данных сессии: {e}")
            return {}
            
    # Методы настроек
    def set_update_interval(self, interval: float):
        """Установка интервала обновления данных"""
        self.update_interval = max(0.1, interval)
        
    def set_auto_logging(self, enabled: bool):
        """Включение/отключение автоматического логирования"""
        self.auto_logging = enabled
        
    def set_alert_threshold(self, parameter: str, threshold_type: str, value: float):
        """Установка порога алерта"""
        if parameter not in self.alert_thresholds:
            self.alert_thresholds[parameter] = {}
        self.alert_thresholds[parameter][threshold_type] = value
        
    def get_database_stats(self) -> Dict[str, int]:
        """Получение статистики базы данных"""
        try:
            return self.db_manager.get_database_stats()
        except Exception as e:
            self.notify_observers('error', f"Ошибка получения статистики БД: {e}")
            return {}
            
    def cleanup_old_data(self, days_to_keep: int = 30):
        """Очистка старых данных"""
        try:
            self.db_manager.cleanup_old_data(days_to_keep)
            self.data_exporter.cleanup_old_exports(days_to_keep // 4)  # Экспорты храним меньше
        except Exception as e:
            self.notify_observers('error', f"Ошибка очистки данных: {e}")
        
    def get_connection_status(self) -> ConnectionStatus:
        """Получение статуса подключения"""
        return self.connection_status
        
    def get_diagnostic_status(self) -> DiagnosticStatus:
        """Получение статуса диагностики"""
        return self.diagnostic_status
        
    def is_connected(self) -> bool:
        """Проверка подключения"""
        return self.connection_status == ConnectionStatus.CONNECTED
        
    def get_current_session_id(self) -> Optional[str]:
        """Получение ID текущей сессии"""
        return self.current_session_id
        
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
                    
    def cleanup(self):
        """Очистка ресурсов"""
        self._stop_data_thread()
        self.disconnect_obd()
