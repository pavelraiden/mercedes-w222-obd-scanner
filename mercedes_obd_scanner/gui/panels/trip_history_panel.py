"""
Панель для отображения истории поездок и их AI-анализа.
"""

import customtkinter as ctk
from typing import List, Dict, Any


class TripHistoryPanel(ctk.CTkFrame):
    """Панель истории поездок."""

    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller

        self.label = ctk.CTkLabel(
            self, text="История поездок", font=ctk.CTkFont(size=20, weight="bold")
        )
        self.label.pack(pady=10, padx=10)

        # Здесь будет список поездок и область для отображения анализа
        # Для простоты пока сделаем текстовое поле
        self.text_area = ctk.CTkTextbox(self, width=400, height=300)
        self.text_area.pack(pady=10, padx=10, fill="both", expand=True)
        self.text_area.configure(state="disabled")

        # Подписываемся на обновления
        self.controller.add_observer("trip_analysis_update", self.on_trip_analyzed)

    def on_trip_analyzed(self, session_id: str, analysis: Dict[str, str]):
        """Вызывается, когда анализ поездки завершен."""
        self.text_area.configure(state="normal")
        self.text_area.insert(
            "0.0",
            f"**Анализ поездки {session_id}**\n\n{analysis.get('final_report', 'Ошибка анализа.')}\n\n====================\n\n",
        )
        self.text_area.configure(state="disabled")
