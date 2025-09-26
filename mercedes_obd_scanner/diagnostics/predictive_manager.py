"""
Менеджер предиктивной диагностики.
"""

import yaml
from typing import List, Dict, Any, Optional, Type
from pathlib import Path

from .base_analyzer import BaseAnalyzer
from .engine_analyzer import EngineAnalyzer
from .transmission_analyzer import TransmissionAnalyzer


class PredictiveManager:
    """Управляет анализаторами для предиктивной диагностики."""

    def __init__(self, config_path: Path):
        self.config = self._load_config(config_path)
        self.analyzers = self._create_analyzers()

    def _load_config(self, config_path: Path) -> Dict[str, Any]:
        """Загружает конфигурацию из YAML файла."""
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _create_analyzers(self) -> List[BaseAnalyzer]:
        """Создает экземпляры анализаторов на основе конфига."""
        analyzers = []
        analyzer_map: Dict[str, Type[BaseAnalyzer]] = {
            "engine": EngineAnalyzer,
            "transmission": TransmissionAnalyzer,
        }
        for component_config in self.config.get("components", []):
            analyzer_type = component_config.get("type")
            analyzer_class = analyzer_map.get(analyzer_type)
            if analyzer_class:
                analyzers.append(analyzer_class(component_config))
        return analyzers

    def run_analysis(self, current_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Запускает анализ на основе текущих данных.

        Args:
            current_data: Словарь с объектами ParameterData от AppController.

        Returns:
            Список словарей с результатами анализа, только если найдены проблемы.
        """
        final_results = []
        simple_data = {
            name: data.value for name, data in current_data.items() if hasattr(data, "value")
        }

        for analyzer in self.analyzers:
            result = analyzer.analyze(simple_data)
            # Отправляем результат только если есть реальные проблемы
            if result and result.get("issues"):
                final_results.append(result)
        return final_results
