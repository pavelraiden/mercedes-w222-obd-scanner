#!/usr/bin/env python3
"""
ConfigManager для Mercedes OBD Scanner
Управляет загрузкой, валидацией и доступом к конфигурационным файлам
"""

import yaml
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum


class EngineType(Enum):
    """Поддерживаемые типы двигателей"""

    M276_DE30LA = "m276_de30la"
    M276_DE35 = "m276_de35"
    M278_DE46LA = "m278_de46la"
    OM642_DE30LA = "om642_de30la"
    UNKNOWN = "unknown"


@dataclass
class ConfigValidationError(Exception):
    """Ошибка валидации конфигурации"""

    field: str
    message: str

    def __str__(self):
        return f"Config validation error in '{self.field}': {self.message}"


class ConfigManager:
    """
    Менеджер конфигураций с поддержкой иерархической загрузки,
    кэширования и валидации
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        """Реализация паттерна Singleton"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Инициализация ConfigManager"""
        if self._initialized:
            return

        self.logger = logging.getLogger(__name__)
        self._config_cache: Dict[str, Any] = {}
        self._current_engine: Optional[EngineType] = None
        self._base_path: Optional[Path] = None
        self._observers: List[callable] = []
        self._initialized = True

    def load_configs(self, base_path: str) -> None:
        """
        Загружает конфигурационные файлы по иерархии

        Args:
            base_path: Путь к директории с конфигами
        """
        self._base_path = Path(base_path)

        try:
            # Загружаем базовый конфиг
            base_config = self._load_yaml_file(self._base_path / "base_engine.yaml")

            # Определяем тип двигателя
            self._current_engine = self._detect_engine_type()

            # Загружаем специфичные конфиги
            engine_config = self._load_engine_specific_config()

            # Объединяем конфиги
            self._config_cache = self._merge_configs(base_config, engine_config)

            # Валидируем итоговый конфиг
            self._validate_config()

            # Уведомляем наблюдателей
            self._notify_observers("config_loaded")

            self.logger.info(
                f"Configs loaded successfully for engine: {self._current_engine.value}"
            )

        except Exception as e:
            self.logger.error(f"Error loading configs: {e}")
            raise

    def _detect_engine_type(self) -> EngineType:
        """
        Определяет тип двигателя комбинированным методом

        Returns:
            Тип двигателя
        """
        try:
            # Попытка автоопределения через OBD
            detected_engine = self._detect_from_obd()
            if detected_engine != EngineType.UNKNOWN:
                self.logger.info(f"Engine auto-detected: {detected_engine.value}")
                return detected_engine
        except Exception as e:
            self.logger.warning(f"Auto-detection failed: {e}")

        # Если автоопределение не удалось - запрашиваем у пользователя
        return self._request_engine_from_user()

    def _detect_from_obd(self) -> EngineType:
        """
        Пытается определить двигатель по OBD параметрам

        Returns:
            Тип двигателя или UNKNOWN
        """
        # TODO: Реализовать логику определения через OBD
        # Пока возвращаем UNKNOWN для дальнейшей реализации
        return EngineType.UNKNOWN

    def _request_engine_from_user(self) -> EngineType:
        """
        Запрашивает тип двигателя у пользователя

        Returns:
            Выбранный тип двигателя
        """
        # TODO: Интеграция с GUI для выбора двигателя
        # Пока возвращаем M276 как наиболее распространенный
        self.logger.info("Using default engine M276_DE30LA")
        return EngineType.M276_DE30LA

    def _load_engine_specific_config(self) -> Dict[str, Any]:
        """
        Загружает конфиги специфичные для текущего двигателя

        Returns:
            Объединенный конфиг для двигателя
        """
        config = {}

        if self._current_engine.value.startswith("m276"):
            # Загружаем конфиги для M276
            petrol_base = self._load_yaml_file(
                self._base_path / "petrol" / "base_petrol.yaml", optional=True
            )
            m276_common = self._load_yaml_file(self._base_path / "petrol" / "m276" / "common.yaml")
            m276_specific = self._load_yaml_file(
                self._base_path / "petrol" / "m276" / f"{self._current_engine.value}.yaml",
                optional=True,
            )

            # Объединяем в порядке приоритета
            for cfg in [petrol_base, m276_common, m276_specific]:
                if cfg:
                    config = self._merge_configs(config, cfg)

        elif self._current_engine.value.startswith("om642"):
            # Загружаем конфиги для OM642
            diesel_base = self._load_yaml_file(
                self._base_path / "diesel" / "base_diesel.yaml", optional=True
            )
            om642_common = self._load_yaml_file(
                self._base_path / "diesel" / "om642" / "common.yaml"
            )

            for cfg in [diesel_base, om642_common]:
                if cfg:
                    config = self._merge_configs(config, cfg)

        return config

    def _load_yaml_file(self, file_path: Path, optional: bool = False) -> Optional[Dict[str, Any]]:
        """
        Загружает YAML файл

        Args:
            file_path: Путь к файлу
            optional: Если True, не вызывает ошибку при отсутствии файла

        Returns:
            Содержимое файла или None
        """
        try:
            if not file_path.exists():
                if optional:
                    return None
                raise FileNotFoundError(f"Config file not found: {file_path}")

            with open(file_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)

        except Exception as e:
            self.logger.error(f"Error loading YAML file {file_path}: {e}")
            if not optional:
                raise
            return None

    def _merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        Рекурсивно объединяет конфиги с приоритетом override

        Args:
            base: Базовый конфиг
            override: Переопределяющий конфиг

        Returns:
            Объединенный конфиг
        """
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value

        return result

    def _validate_config(self) -> None:
        """Валидирует загруженную конфигурацию"""
        required_sections = ["metadata", "common_pids", "uds_commands"]

        for section in required_sections:
            if section not in self._config_cache:
                raise ConfigValidationError(section, "Required section missing")

        # Валидация PID параметров
        self._validate_pids()

        # Валидация диапазонов
        self._validate_ranges()

    def _validate_pids(self) -> None:
        """Валидирует PID параметры"""
        all_pids = {}
        all_pids.update(self._config_cache.get("common_pids", {}))
        all_pids.update(self._config_cache.get("specific_pids", {}))

        for pid_name, pid_config in all_pids.items():
            required_fields = ["code", "description", "formula", "units"]

            for field in required_fields:
                if field not in pid_config:
                    raise ConfigValidationError(
                        f"pids.{pid_name}.{field}", "Required field missing"
                    )

    def _validate_ranges(self) -> None:
        """Валидирует диапазоны значений"""
        all_pids = {}
        all_pids.update(self._config_cache.get("common_pids", {}))
        all_pids.update(self._config_cache.get("specific_pids", {}))

        for pid_name, pid_config in all_pids.items():
            ranges = pid_config.get("ranges", {})

            for range_type, range_values in ranges.items():
                if range_values and len(range_values) == 2:
                    min_val, max_val = range_values
                    if min_val is not None and max_val is not None and min_val >= max_val:
                        raise ConfigValidationError(
                            f"pids.{pid_name}.ranges.{range_type}",
                            f"Invalid range: min ({min_val}) >= max ({max_val})",
                        )

    def get_parameter(self, param_path: str, default: Any = None) -> Any:
        """
        Получает параметр по пути в конфиге

        Args:
            param_path: Путь к параметру (например, "common_pids.engine_rpm.ranges.normal")
            default: Значение по умолчанию

        Returns:
            Значение параметра или default
        """
        try:
            value = self._config_cache
            for key in param_path.split("."):
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def get_all_pids(self) -> Dict[str, Any]:
        """
        Возвращает все PID параметры (общие + специфичные)

        Returns:
            Словарь всех PID параметров
        """
        all_pids = {}
        all_pids.update(self.get_parameter("common_pids", {}))
        all_pids.update(self.get_parameter("specific_pids", {}))
        return all_pids

    def get_engine_type(self) -> Optional[EngineType]:
        """Возвращает текущий тип двигателя"""
        return self._current_engine

    def add_observer(self, callback: callable) -> None:
        """
        Добавляет наблюдателя для событий конфигурации

        Args:
            callback: Функция обратного вызова
        """
        if callback not in self._observers:
            self._observers.append(callback)

    def remove_observer(self, callback: callable) -> None:
        """
        Удаляет наблюдателя

        Args:
            callback: Функция обратного вызова
        """
        if callback in self._observers:
            self._observers.remove(callback)

    def _notify_observers(self, event: str, data: Any = None) -> None:
        """
        Уведомляет всех наблюдателей о событии

        Args:
            event: Тип события
            data: Дополнительные данные
        """
        for callback in self._observers:
            try:
                callback(event, data)
            except Exception as e:
                self.logger.error(f"Error in observer callback: {e}")

    def reload(self) -> None:
        """Принудительно перезагружает конфигурацию"""
        if self._base_path:
            self.load_configs(str(self._base_path))

    def export_config(self, output_path: str) -> None:
        """
        Экспортирует текущую конфигурацию в файл

        Args:
            output_path: Путь для сохранения
        """
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                yaml.dump(self._config_cache, f, default_flow_style=False, allow_unicode=True)
            self.logger.info(f"Config exported to: {output_path}")
        except Exception as e:
            self.logger.error(f"Error exporting config: {e}")
            raise


# Глобальный экземпляр ConfigManager
config_manager = ConfigManager()
