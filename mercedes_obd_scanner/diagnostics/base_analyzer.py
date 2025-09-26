"""
Базовый класс для анализаторов компонентов.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
import re


class BaseAnalyzer(ABC):
    """Абстрактный базовый класс для всех анализаторов."""

    def __init__(self, config: Dict[str, Any]):
        self.component_name = config.get("name", "Unknown Component")
        self.rules = config.get("rules", [])

    def analyze(self, data: Dict[str, float]) -> Dict[str, Any]:
        """
        Анализирует данные на основе правил из конфигурации.

        Args:
            data (Dict[str, float]): Словарь с текущими значениями параметров.

        Returns:
            Dict[str, Any]: Результат анализа (компонент, индекс износа, проблемы).
        """
        total_wear_increase = 0
        issues_found = []

        for rule in self.rules:
            condition = rule["condition"]
            required_params = re.findall(r"[A-Z_]+", condition)

            if all(param in data for param in required_params):
                try:
                    # Safe condition evaluation - replace eval with specific condition checks
                    try:
                        # Parse simple conditions like "data['param'] > value"
                        if self._evaluate_condition_safely(condition, data):
                        total_wear_increase += rule["wear_increase"]
                        issues_found.append(
                            {
                                "description": rule["description"],
                                "wear_increase": rule["wear_increase"],
                            }
                        )
                except Exception:
                    pass

        if issues_found:
            return {
                "component": self.component_name,
                "wear_index": total_wear_increase,
                "issues": issues_found,
            }
        return None
