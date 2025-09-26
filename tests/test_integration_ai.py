"""
Интеграционные тесты для AI-функций.
"""
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import time
import os
from pathlib import Path

from mercedes_obd_scanner.gui.app_controller import AppController

class TestAIFeatures(unittest.TestCase):

    def setUp(self):
        """Настройка перед каждым тестом."""
        db_path = Path("data/obd_data.db")
        if db_path.exists():
            db_path.unlink()
        self.controller = AppController()

    def tearDown(self):
        """Очистка после каждого теста."""
        db_path = Path("data/obd_data.db")
        if db_path.exists():
            db_path.unlink()

    @patch('mercedes_obd_scanner.trip_analyzer.trip_analyzer.TripAnalyzer.analyze_and_save_trip', new_callable=AsyncMock)
    def test_trip_analysis_is_triggered_on_disconnect(self, mock_analyze_and_save):
        """Тестирует, что анализ поездки вызывается при отключении."""
        # 1. Вручную устанавливаем состояние "подключено"
        self.controller.is_connected = True
        self.controller.current_session_id = "test_session_for_trip_analysis"

        # 2. Вызываем disconnect
        self.controller.disconnect_obd()

        # 3. Проверяем, что метод анализа был вызван с правильным ID сессии
        mock_analyze_and_save.assert_called_once_with("test_session_for_trip_analysis")

    def test_predictive_diagnostics_triggers_on_correct_data(self):
        """Тестирует срабатывание правила предиктивной диагностики."""
        # 1. Создаем мок для коллбэка GUI
        mock_gui_callback = MagicMock()
        self.controller.add_observer("prediction_update", mock_gui_callback)

        # 2. Имитируем получение данных, которые НЕ должны вызвать срабатывание
        self.controller._on_obd_data("COOLANT_TEMP", 90, "°C")
        self.controller._on_obd_data("ENGINE_LOAD", 40, "%")
        mock_gui_callback.assert_not_called()

        # 3. Имитируем получение данных, которые ДОЛЖНЫ вызвать срабатывание
        # (согласно конфигу: COOLANT_TEMP > 105 AND ENGINE_LOAD > 50)
        # Сначала обновляем один параметр. Правило еще не должно сработать.
        self.controller._on_obd_data("COOLANT_TEMP", 106, "°C")
        mock_gui_callback.assert_not_called()

        # Теперь обновляем второй параметр, завершая условие.
        self.controller._on_obd_data("ENGINE_LOAD", 51, "%")

        # 4. Проверяем, что коллбэк был вызван
        mock_gui_callback.assert_called_once()
        
        # 5. Проверяем содержимое коллбэка
        args, _ = mock_gui_callback.call_args
        predictions = args[0]
        self.assertIsInstance(predictions, list)
        self.assertGreater(len(predictions), 0)
        self.assertEqual(predictions[0]['component'], 'Двигатель')
        self.assertEqual(predictions[0]['issues'][0]['description'], "Повышенная температура охлаждающей жидкости при высокой нагрузке.")

if __name__ == '__main__':
    unittest.main()

