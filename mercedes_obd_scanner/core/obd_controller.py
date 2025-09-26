#!/usr/bin/env python3
"""
OBD Controller для Mercedes W222
Управляет подключением к OBD-сканеру и получением данных
"""

import time
import random
import logging
import threading
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    logging.warning("pyserial not available, only demo mode will work")


class ConnectionStatus(Enum):
    """Статусы подключения"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class OBDParameter:
    """Параметр OBD"""
    name: str
    value: Any
    unit: str
    timestamp: float
    status: str = "ok"  # ok, warning, critical


class OBDController:
    """
    Контроллер OBD с поддержкой демо-режима
    """
    
    def __init__(self, demo_mode: bool = False):
        """
        Инициализация OBD контроллера
        
        Args:
            demo_mode: Если True, работает в демо-режиме без реального OBD
        """
        self.logger = logging.getLogger(__name__)
        self.demo_mode = demo_mode
        self.connection_status = ConnectionStatus.DISCONNECTED
        
        # Настройки подключения
        self.port: Optional[str] = None
        self.baudrate: int = 38400
        self.timeout: float = 2.0
        
        # Соединение
        self.serial_connection: Optional[serial.Serial] = None
        
        # Данные
        self.current_data: Dict[str, OBDParameter] = {}
        self.data_callbacks: list[Callable] = []
        
        # Поток для чтения данных
        self.reading_thread: Optional[threading.Thread] = None
        self.stop_reading = threading.Event()
        
        # Демо-данные
        self.demo_data = self._init_demo_data()
        
        self.logger.info(f"OBD Controller initialized (demo_mode={demo_mode})")
    
    def _init_demo_data(self) -> Dict[str, Dict[str, Any]]:
        """Инициализация демо-данных"""
        return {
            "engine_rpm": {"base": 800, "variation": 200, "unit": "rpm"},
            "vehicle_speed": {"base": 0, "variation": 80, "unit": "km/h"},
            "coolant_temp": {"base": 90, "variation": 15, "unit": "°C"},
            "engine_load": {"base": 20, "variation": 60, "unit": "%"},
            "throttle_position": {"base": 0, "variation": 100, "unit": "%"},
            "fuel_level": {"base": 75, "variation": 25, "unit": "%"},
            "oil_pressure": {"base": 3.5, "variation": 1.5, "unit": "bar"},
            "oil_temperature": {"base": 95, "variation": 25, "unit": "°C"},
            "turbo_pressure_1": {"base": 0.8, "variation": 0.7, "unit": "bar"},
            "turbo_pressure_2": {"base": 0.8, "variation": 0.7, "unit": "bar"},
            "lambda_bank1": {"base": 1.0, "variation": 0.1, "unit": "λ"},
            "lambda_bank2": {"base": 1.0, "variation": 0.1, "unit": "λ"},
        }
    
    def get_available_ports(self) -> list[str]:
        """
        Получить список доступных COM портов
        
        Returns:
            Список доступных портов
        """
        if not SERIAL_AVAILABLE or self.demo_mode:
            return ["DEMO_PORT"]
        
        try:
            ports = serial.tools.list_ports.comports()
            return [port.device for port in ports]
        except Exception as e:
            self.logger.error(f"Error getting available ports: {e}")
            return []
    
    def connect(self, port: Optional[str] = None) -> bool:
        """
        Подключение к OBD-сканеру
        
        Args:
            port: COM порт для подключения
            
        Returns:
            True если подключение успешно
        """
        if self.demo_mode:
            return self._connect_demo()
        
        if not SERIAL_AVAILABLE:
            self.logger.error("pyserial not available, cannot connect to real OBD")
            return False
        
        if port:
            self.port = port
        
        if not self.port:
            available_ports = self.get_available_ports()
            if not available_ports:
                self.logger.error("No available ports found")
                return False
            self.port = available_ports[0]
        
        try:
            self.connection_status = ConnectionStatus.CONNECTING
            self.logger.info(f"Connecting to OBD on port {self.port}")
            
            # Создание соединения
            self.serial_connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            
            # Инициализация ELM327
            if self._initialize_elm327():
                self.connection_status = ConnectionStatus.CONNECTED
                self._start_data_reading()
                self.logger.info("Successfully connected to OBD")
                return True
            else:
                self.connection_status = ConnectionStatus.ERROR
                return False
                
        except Exception as e:
            self.logger.error(f"Error connecting to OBD: {e}")
            self.connection_status = ConnectionStatus.ERROR
            return False
    
    def _connect_demo(self) -> bool:
        """Подключение в демо-режиме"""
        self.connection_status = ConnectionStatus.CONNECTING
        time.sleep(1)  # Имитация подключения
        
        self.connection_status = ConnectionStatus.CONNECTED
        self._start_data_reading()
        self.logger.info("Connected in demo mode")
        return True
    
    def _initialize_elm327(self) -> bool:
        """
        Инициализация ELM327 адаптера
        
        Returns:
            True если инициализация успешна
        """
        try:
            # Базовые команды инициализации ELM327
            commands = [
                "ATZ",      # Reset
                "ATE0",     # Echo off
                "ATL0",     # Linefeeds off
                "ATS0",     # Spaces off
                "ATH1",     # Headers on
                "ATSP0",    # Auto protocol
            ]
            
            for cmd in commands:
                if not self._send_command(cmd):
                    return False
                time.sleep(0.1)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing ELM327: {e}")
            return False
    
    def _send_command(self, command: str) -> bool:
        """
        Отправка команды в OBD
        
        Args:
            command: Команда для отправки
            
        Returns:
            True если команда выполнена успешно
        """
        if not self.serial_connection:
            return False
        
        try:
            self.serial_connection.write(f"{command}\\r".encode())
            response = self.serial_connection.readline().decode().strip()
            return "OK" in response or ">" in response
            
        except Exception as e:
            self.logger.error(f"Error sending command {command}: {e}")
            return False
    
    def disconnect(self):
        """Отключение от OBD-сканера"""
        self.logger.info("Disconnecting from OBD")
        
        # Остановка чтения данных
        self.stop_reading.set()
        if self.reading_thread and self.reading_thread.is_alive():
            self.reading_thread.join(timeout=2)
        
        # Закрытие соединения
        if self.serial_connection:
            try:
                self.serial_connection.close()
            except Exception as e:
                self.logger.error(f"Error closing serial connection: {e}")
            finally:
                self.serial_connection = None
        
        self.connection_status = ConnectionStatus.DISCONNECTED
        self.current_data.clear()
    
    def _start_data_reading(self):
        """Запуск потока чтения данных"""
        self.stop_reading.clear()
        self.reading_thread = threading.Thread(target=self._data_reading_loop, daemon=True)
        self.reading_thread.start()
    
    def _data_reading_loop(self):
        """Основной цикл чтения данных"""
        while not self.stop_reading.is_set():
            try:
                if self.demo_mode:
                    self._read_demo_data()
                else:
                    self._read_real_data()
                
                # Уведомление подписчиков
                self._notify_data_callbacks()
                
                time.sleep(0.1)  # 10 Hz обновление
                
            except Exception as e:
                self.logger.error(f"Error in data reading loop: {e}")
                time.sleep(1)
    
    def _read_demo_data(self):
        """Чтение демо-данных"""
        current_time = time.time()
        
        for param_name, config in self.demo_data.items():
            # Генерация реалистичных значений
            base_value = config["base"]
            variation = config["variation"]
            
            # Добавляем немного случайности и трендов
            noise = random.uniform(-0.1, 0.1) * variation
            trend = 0.05 * variation * random.uniform(-1, 1)
            
            value = base_value + noise + trend
            
            # Ограничиваем значения разумными пределами
            if param_name == "engine_rpm":
                value = max(600, min(6500, value))
            elif param_name == "vehicle_speed":
                value = max(0, min(250, value))
            elif param_name == "coolant_temp":
                value = max(60, min(120, value))
            elif param_name in ["turbo_pressure_1", "turbo_pressure_2"]:
                value = max(0, min(2.0, value))
            elif param_name in ["lambda_bank1", "lambda_bank2"]:
                value = max(0.8, min(1.2, value))
            
            # Определение статуса
            status = self._determine_parameter_status(param_name, value)
            
            self.current_data[param_name] = OBDParameter(
                name=param_name,
                value=round(value, 2),
                unit=config["unit"],
                timestamp=current_time,
                status=status
            )
    
    def _read_real_data(self):
        """Чтение реальных данных с OBD"""
        # TODO: Реализовать чтение реальных PID кодов
        # Пока используем демо-данные
        self._read_demo_data()
    
    def _determine_parameter_status(self, param_name: str, value: float) -> str:
        """
        Определение статуса параметра
        
        Args:
            param_name: Название параметра
            value: Значение параметра
            
        Returns:
            Статус: "ok", "warning", "critical"
        """
        # Простая логика определения статуса
        if param_name == "coolant_temp":
            if value > 110:
                return "critical"
            elif value > 105:
                return "warning"
        elif param_name == "oil_pressure":
            if value < 1.5:
                return "critical"
            elif value < 2.0:
                return "warning"
        elif param_name == "engine_rpm":
            if value > 6000:
                return "warning"
        
        return "ok"
    
    def _notify_data_callbacks(self):
        """Уведомление подписчиков о новых данных"""
        for callback in self.data_callbacks:
            try:
                callback(self.current_data.copy())
            except Exception as e:
                self.logger.error(f"Error in data callback: {e}")
    
    def add_data_callback(self, callback: Callable):
        """
        Добавить callback для уведомления о новых данных
        
        Args:
            callback: Функция для вызова при получении новых данных
        """
        if callback not in self.data_callbacks:
            self.data_callbacks.append(callback)
    
    def remove_data_callback(self, callback: Callable):
        """
        Удалить callback
        
        Args:
            callback: Функция для удаления
        """
        if callback in self.data_callbacks:
            self.data_callbacks.remove(callback)
    
    def get_current_data(self) -> Dict[str, OBDParameter]:
        """
        Получить текущие данные
        
        Returns:
            Словарь текущих параметров
        """
        return self.current_data.copy()
    
    def get_parameter(self, param_name: str) -> Optional[OBDParameter]:
        """
        Получить конкретный параметр
        
        Args:
            param_name: Название параметра
            
        Returns:
            Параметр или None
        """
        return self.current_data.get(param_name)
    
    def is_connected(self) -> bool:
        """Проверка статуса подключения"""
        return self.connection_status == ConnectionStatus.CONNECTED
    
    def get_connection_status(self) -> ConnectionStatus:
        """Получить статус подключения"""
        return self.connection_status
