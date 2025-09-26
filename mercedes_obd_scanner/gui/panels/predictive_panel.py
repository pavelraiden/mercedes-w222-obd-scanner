"""
Панель для отображения данных предиктивной диагностики.
"""
import customtkinter as ctk
from typing import List, Dict, Any

class PredictivePanel(ctk.CTkFrame):
    """Панель предиктивной диагностики."""

    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller

        self.label = ctk.CTkLabel(self, text="Предиктивная диагностика", font=ctk.CTkFont(size=20, weight="bold"))
        self.label.pack(pady=10, padx=10)

        self.text_area = ctk.CTkTextbox(self, width=400, height=300)
        self.text_area.pack(pady=10, padx=10, fill="both", expand=True)
        self.text_area.configure(state="disabled")

        # Подписываемся на обновления
        self.controller.add_observer("prediction_update", self.update_predictions)

    def update_predictions(self, predictions: List[Dict[str, Any]]):
        """Обновляет отображение данных предиктивной диагностики."""
        self.text_area.configure(state="normal")
        self.text_area.delete("1.0", "end")
        
        if not predictions:
            self.text_area.insert("end", "Нет данных для анализа.\n")
        else:
            for prediction in predictions:
                component = prediction.get("component", "N/A")
                wear_index = prediction.get("wear_index", 0)
                issues = prediction.get("issues", [])
                
                self.text_area.insert("end", f"Компонент: {component}\n")
                self.text_area.insert("end", f"Индекс износа: {wear_index}%\n")
                if issues:
                    self.text_area.insert("end", "Проблемы:\n")
                    for issue in issues:
                        self.text_area.insert("end", f"  - {issue}\n")
                self.text_area.insert("end", "---\n")

        self.text_area.configure(state="disabled")

