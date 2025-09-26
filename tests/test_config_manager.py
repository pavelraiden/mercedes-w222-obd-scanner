#!/usr/bin/env python3
"""
Тесты для ConfigManager
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from mercedes_obd_scanner.core.config_manager import (
    ConfigManager,
    EngineType,
    ConfigValidationError,
)


class TestConfigManager:
    """Тесты для ConfigManager"""

    def setup_method(self):
        """Настройка перед каждым тестом"""
        # Сбрасываем Singleton для чистого тестирования
        ConfigManager._instance = None
        ConfigManager._initialized = False

    def test_singleton_pattern(self):
        """Тест паттерна Singleton"""
        config1 = ConfigManager()
        config2 = ConfigManager()
        assert config1 is config2, "ConfigManager должен быть Singleton"

    def test_initialization(self):
        """Тест инициализации ConfigManager"""
        config = ConfigManager()
        assert config._config_cache == {}
        assert config._current_engine is None
        assert config._base_path is None
        assert config._observers == []

    def test_load_valid_config(self):
        """Тест загрузки валидной конфигурации"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Создаем тестовый конфиг
            config_data = {
                "metadata": {"version": "1.0", "description": "Test config"},
                "common_pids": {
                    "engine_rpm": {
                        "code": "0x0C",
                        "description": "Engine RPM",
                        "formula": "((A*256)+B)/4",
                        "units": "rpm",
                        "ranges": {"normal": [700, 6500]},
                    }
                },
                "uds_commands": {"read_dtc": {"service": "0x19", "description": "Read DTCs"}},
            }

            config_path = Path(temp_dir) / "base_engine.yaml"
            with open(config_path, "w") as f:
                yaml.dump(config_data, f)

            # Создаем директории для специфичных конфигов
            (Path(temp_dir) / "petrol" / "m276").mkdir(parents=True)
            m276_config = {
                "metadata": {"engine_family": "M276"},
                "specific_pids": {
                    "turbo_pressure": {
                        "code": "0x0B",
                        "description": "Turbo pressure",
                        "formula": "(A*256+B)/1000",
                        "units": "bar",
                        "ranges": {"normal": [0.2, 1.5]},
                    }
                },
            }

            m276_path = Path(temp_dir) / "petrol" / "m276" / "common.yaml"
            with open(m276_path, "w") as f:
                yaml.dump(m276_config, f)

            # Тестируем загрузку
            config = ConfigManager()
            config.load_configs(temp_dir)

            assert config._current_engine == EngineType.M276_DE30LA
            assert "metadata" in config._config_cache
            assert "common_pids" in config._config_cache
            assert "specific_pids" in config._config_cache

    def test_get_parameter(self):
        """Тест получения параметров"""
        config = ConfigManager()
        config._config_cache = {"common_pids": {"engine_rpm": {"ranges": {"normal": [700, 6500]}}}}

        # Тест успешного получения параметра
        result = config.get_parameter("common_pids.engine_rpm.ranges.normal")
        assert result == [700, 6500]

        # Тест получения несуществующего параметра
        result = config.get_parameter("nonexistent.parameter", default="default_value")
        assert result == "default_value"

    def test_get_all_pids(self):
        """Тест получения всех PID параметров"""
        config = ConfigManager()
        config._config_cache = {
            "common_pids": {"engine_rpm": {"code": "0x0C"}},
            "specific_pids": {"turbo_pressure": {"code": "0x0B"}},
        }

        all_pids = config.get_all_pids()
        assert "engine_rpm" in all_pids
        assert "turbo_pressure" in all_pids
        assert len(all_pids) == 2

    def test_config_validation_missing_section(self):
        """Тест валидации конфига с отсутствующей секцией"""
        config = ConfigManager()
        config._config_cache = {
            "metadata": {"version": "1.0"},
            # Отсутствует 'common_pids' и 'uds_commands'
        }

        with pytest.raises(ConfigValidationError) as exc_info:
            config._validate_config()

        assert "common_pids" in str(exc_info.value)

    def test_config_validation_invalid_pid(self):
        """Тест валидации PID с отсутствующими полями"""
        config = ConfigManager()
        config._config_cache = {
            "metadata": {"version": "1.0"},
            "common_pids": {
                "invalid_pid": {
                    "code": "0x0C",
                    # Отсутствуют обязательные поля
                }
            },
            "uds_commands": {},
        }

        with pytest.raises(ConfigValidationError) as exc_info:
            config._validate_config()

        assert "description" in str(exc_info.value) or "formula" in str(exc_info.value)

    def test_config_validation_invalid_range(self):
        """Тест валидации неправильного диапазона"""
        config = ConfigManager()
        config._config_cache = {
            "metadata": {"version": "1.0"},
            "common_pids": {
                "test_pid": {
                    "code": "0x0C",
                    "description": "Test PID",
                    "formula": "A",
                    "units": "test",
                    "ranges": {"normal": [100, 50]},  # min > max
                }
            },
            "uds_commands": {},
        }

        with pytest.raises(ConfigValidationError) as exc_info:
            config._validate_config()

        assert "Invalid range" in str(exc_info.value)

    def test_observer_pattern(self):
        """Тест системы наблюдателей"""
        config = ConfigManager()

        # Тестовый callback
        events_received = []

        def test_callback(event, data=None):
            events_received.append((event, data))

        # Добавляем наблюдателя
        config.add_observer(test_callback)
        assert test_callback in config._observers

        # Уведомляем наблюдателей
        config._notify_observers("test_event", "test_data")
        assert len(events_received) == 1
        assert events_received[0] == ("test_event", "test_data")

        # Удаляем наблюдателя
        config.remove_observer(test_callback)
        assert test_callback not in config._observers

    def test_merge_configs(self):
        """Тест объединения конфигураций"""
        config = ConfigManager()

        base_config = {
            "section1": {"param1": "base_value1", "param2": "base_value2"},
            "section2": {"param3": "base_value3"},
        }

        override_config = {
            "section1": {
                "param1": "override_value1",  # Переопределяем
                "param4": "new_value4",  # Добавляем новый
            },
            "section3": {"param5": "new_value5"},  # Новая секция
        }

        result = config._merge_configs(base_config, override_config)

        # Проверяем переопределение
        assert result["section1"]["param1"] == "override_value1"
        # Проверяем сохранение базовых значений
        assert result["section1"]["param2"] == "base_value2"
        # Проверяем добавление новых значений
        assert result["section1"]["param4"] == "new_value4"
        assert result["section3"]["param5"] == "new_value5"
        # Проверяем сохранение других секций
        assert result["section2"]["param3"] == "base_value3"


if __name__ == "__main__":
    pytest.main([__file__])
