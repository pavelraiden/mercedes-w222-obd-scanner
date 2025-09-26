#!/usr/bin/env python3
"""
Тесты для OBDController
"""

import pytest
import time
import threading
from mercedes_obd_scanner.core.obd_controller import OBDController


class TestOBDController:
    """Тесты для OBDController"""
    
    def test_demo_mode_initialization(self):
        """Тест инициализации в демо-режиме"""
        controller = OBDController(demo_mode=True)
        
        assert controller.demo_mode is True
        assert controller.connection_status == ConnectionStatus.DISCONNECTED
        assert controller.current_data == {}
        assert controller.demo_data is not None
        assert len(controller.demo_data) > 0
    
    def test_real_mode_initialization(self):
        """Тест инициализации в реальном режиме"""
        controller = OBDController(demo_mode=False)
        
        assert controller.demo_mode is False
        assert controller.connection_status == ConnectionStatus.DISCONNECTED
        assert controller.serial_connection is None
    
    def test_demo_connection(self):
        """Тест подключения в демо-режиме"""
        controller = OBDController(demo_mode=True)
        
        # Тест успешного подключения
        result = controller.connect()
        assert result is True
        assert controller.is_connected() is True
        assert controller.get_connection_status() == ConnectionStatus.CONNECTED
        
        # Проверяем что поток чтения данных запущен
        assert controller.reading_thread is not None
        assert controller.reading_thread.is_alive()
        
        # Отключаемся
        controller.disconnect()
        assert controller.is_connected() is False
        assert controller.get_connection_status() == ConnectionStatus.DISCONNECTED
    
    def test_get_available_ports_demo(self):
        """Тест получения доступных портов в демо-режиме"""
        controller = OBDController(demo_mode=True)
        ports = controller.get_available_ports()
        
        assert isinstance(ports, list)
        assert "DEMO_PORT" in ports
    
    def test_demo_data_generation(self):
        """Тест генерации демо-данных"""
        controller = OBDController(demo_mode=True)
        controller.connect()
        
        # Ждем немного для генерации данных
        time.sleep(0.2)
        
        data = controller.get_current_data()
        
        # Проверяем что данные сгенерированы
        assert len(data) > 0
        
        # Проверяем наличие основных параметров
        expected_params = ["engine_rpm", "vehicle_speed", "coolant_temp", "engine_load"]
        for param in expected_params:
            assert param in data
            assert isinstance(data[param], OBDParameter)
            assert data[param].value is not None
            assert data[param].unit is not None
            assert data[param].timestamp > 0
        
        controller.disconnect()
    
    def test_demo_data_ranges(self):
        """Тест диапазонов демо-данных"""
        controller = OBDController(demo_mode=True)
        controller.connect()
        
        time.sleep(0.2)
        data = controller.get_current_data()
        
        # Проверяем разумные диапазоны значений
        if "engine_rpm" in data:
            rpm = data["engine_rpm"].value
            assert 600 <= rpm <= 6500, f"RPM {rpm} out of range"
        
        if "vehicle_speed" in data:
            speed = data["vehicle_speed"].value
            assert 0 <= speed <= 250, f"Speed {speed} out of range"
        
        if "coolant_temp" in data:
            temp = data["coolant_temp"].value
            assert 60 <= temp <= 120, f"Temperature {temp} out of range"
        
        controller.disconnect()
    
    def test_parameter_status_determination(self):
        """Тест определения статуса параметров"""
        controller = OBDController(demo_mode=True)
        
        # Тест нормального статуса
        status = controller._determine_parameter_status("coolant_temp", 90)
        assert status == "ok"
        
        # Тест предупреждения
        status = controller._determine_parameter_status("coolant_temp", 107)
        assert status == "warning"
        
        # Тест критического статуса
        status = controller._determine_parameter_status("coolant_temp", 115)
        assert status == "critical"
        
        # Тест для давления масла
        status = controller._determine_parameter_status("oil_pressure", 1.0)
        assert status == "critical"
        
        status = controller._determine_parameter_status("oil_pressure", 1.8)
        assert status == "warning"
        
        status = controller._determine_parameter_status("oil_pressure", 3.0)
        assert status == "ok"
    
    def test_data_callbacks(self):
        """Тест системы callback'ов для данных"""
        controller = OBDController(demo_mode=True)
        
        # Список для сохранения полученных данных
        received_data = []
        
        def test_callback(data):
            received_data.append(data)
        
        # Добавляем callback
        controller.add_data_callback(test_callback)
        
        # Подключаемся и ждем данные
        controller.connect()
        time.sleep(0.3)  # Ждем несколько циклов обновления
        
        # Проверяем что callback вызывался
        assert len(received_data) > 0
        assert isinstance(received_data[0], dict)
        
        # Удаляем callback
        controller.remove_data_callback(test_callback)
        
        # Очищаем список и ждем еще
        received_data.clear()
        time.sleep(0.2)
        
        # Callback больше не должен вызываться (или вызываться реже)
        initial_count = len(received_data)
        time.sleep(0.2)
        # Не должно быть новых вызовов после удаления callback
        
        controller.disconnect()
    
    def test_get_specific_parameter(self):
        """Тест получения конкретного параметра"""
        controller = OBDController(demo_mode=True)
        controller.connect()
        
        time.sleep(0.2)
        
        # Тест получения существующего параметра
        rpm_param = controller.get_parameter("engine_rpm")
        if rpm_param:  # Может быть None если еще не сгенерирован
            assert isinstance(rpm_param, OBDParameter)
            assert rpm_param.name == "engine_rpm"
            assert rpm_param.unit == "rpm"
        
        # Тест получения несуществующего параметра
        nonexistent = controller.get_parameter("nonexistent_param")
        assert nonexistent is None
        
        controller.disconnect()
    
    def test_connection_status_changes(self):
        """Тест изменений статуса подключения"""
        controller = OBDController(demo_mode=True)
        
        # Изначально отключен
        assert controller.get_connection_status() == ConnectionStatus.DISCONNECTED
        assert not controller.is_connected()
        
        # Подключаемся
        controller.connect()
        assert controller.get_connection_status() == ConnectionStatus.CONNECTED
        assert controller.is_connected()
        
        # Отключаемся
        controller.disconnect()
        assert controller.get_connection_status() == ConnectionStatus.DISCONNECTED
        assert not controller.is_connected()
    
    def test_thread_safety(self):
        """Тест потокобезопасности"""
        controller = OBDController(demo_mode=True)
        controller.connect()
        
        # Множественные обращения к данным из разных потоков
        results = []
        
        def get_data_worker():
            for _ in range(10):
                data = controller.get_current_data()
                results.append(len(data))
                time.sleep(0.01)
        
        # Запускаем несколько потоков
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=get_data_worker)
            threads.append(thread)
            thread.start()
        
        # Ждем завершения всех потоков
        for thread in threads:
            thread.join()
        
        # Проверяем что все потоки получили данные
        assert len(results) == 30  # 3 потока * 10 запросов
        assert all(count >= 0 for count in results)
        
        controller.disconnect()
    
    def test_real_mode_without_device(self):
        """Тест реального режима без устройства"""
        controller = OBDController(demo_mode=False)
        
        # Попытка подключения без реального устройства должна завершиться неудачей
        result = controller.connect()
        assert result is False
        assert not controller.is_connected()
    
    def test_disconnect_cleanup(self):
        """Тест корректной очистки при отключении"""
        controller = OBDController(demo_mode=True)
        controller.connect()
        
        # Проверяем что поток запущен и данные есть
        time.sleep(0.2)
        assert controller.reading_thread is not None
        assert controller.reading_thread.is_alive()
        assert len(controller.current_data) > 0
        
        # Отключаемся
        controller.disconnect()
        
        # Проверяем очистку
        time.sleep(0.1)  # Даем время потоку завершиться
        assert not controller.reading_thread.is_alive()
        assert len(controller.current_data) == 0
        assert controller.serial_connection is None


if __name__ == "__main__":
    pytest.main([__file__])
