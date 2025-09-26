"""
Панель мониторинга параметров в реальном времени
"""
import customtkinter as ctk
from collections import deque
from typing import Dict, List, Optional
import threading
import time

try:
    import matplotlib.pyplot as plt
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib import animation
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

from ..theme_manager import ThemedFrame, ThemedButton, theme_manager
from ..icon_manager import get_action_icon, get_system_icon
from ..app_controller import AppController, ParameterData


class ParameterCard(ThemedFrame):
    """Карточка для отображения параметра"""
    
    def __init__(self, parent, parameter_name: str, unit: str = ""):
        super().__init__(parent)
        
        self.parameter_name = parameter_name
        self.unit = unit
        self.current_value = None
        self.status = "unknown"
        
        self._create_widgets()
        self._create_layout()
        
    def _create_widgets(self):
        """Создание виджетов карточки"""
        # Иконка системы
        self.icon_label = ctk.CTkLabel(
            self,
            text="",
            image=get_system_icon(self.parameter_name.lower(), (24, 24))
        )
        
        # Название параметра
        self.name_label = ctk.CTkLabel(
            self,
            text=self.parameter_name.replace("_", " ").title(),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme_manager.get_color("text_primary")
        )
        
        # Значение
        self.value_label = ctk.CTkLabel(
            self,
            text="--",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=theme_manager.get_color("text_primary")
        )
        
        # Единица измерения
        self.unit_label = ctk.CTkLabel(
            self,
            text=self.unit,
            font=ctk.CTkFont(size=10),
            text_color=theme_manager.get_color("text_secondary")
        )
        
        # Индикатор статуса
        self.status_frame = ctk.CTkFrame(self, width=8, height=8, corner_radius=4)
        
    def _create_layout(self):
        """Создание макета карточки"""
        self.grid_columnconfigure(1, weight=1)
        
        # Иконка
        self.icon_label.grid(row=0, column=0, rowspan=2, padx=(10, 5), pady=10, sticky="w")
        
        # Название
        self.name_label.grid(row=0, column=1, padx=5, pady=(10, 2), sticky="w")
        
        # Значение и единица
        value_frame = ctk.CTkFrame(self, fg_color="transparent")
        value_frame.grid(row=1, column=1, padx=5, pady=(0, 10), sticky="w")
        
        self.value_label.pack(side="left")
        self.unit_label.pack(side="left", padx=(5, 0))
        
        # Статус
        self.status_frame.grid(row=0, column=2, padx=(5, 10), pady=10, sticky="ne")
        
    def update_value(self, value: any, status: str = "ok"):
        """Обновление значения параметра"""
        self.current_value = value
        self.status = status
        
        # Форматирование значения
        if isinstance(value, float):
            formatted_value = f"{value:.1f}"
        elif isinstance(value, int):
            formatted_value = str(value)
        else:
            formatted_value = str(value)
            
        self.value_label.configure(text=formatted_value)
        
        # Обновление цвета статуса
        status_colors = {
            "ok": theme_manager.get_color("success"),
            "warning": theme_manager.get_color("warning"),
            "error": theme_manager.get_color("error"),
            "unknown": theme_manager.get_color("text_secondary")
        }
        
        self.status_frame.configure(fg_color=status_colors.get(status, status_colors["unknown"]))


class RealTimeChart(ThemedFrame):
    """График для отображения данных в реальном времени"""
    
    def __init__(self, parent, parameter_name: str, max_points: int = 100):
        super().__init__(parent)
        
        self.parameter_name = parameter_name
        self.max_points = max_points
        self.data_points = deque(maxlen=max_points)
        self.time_points = deque(maxlen=max_points)
        
        self.figure = None
        self.canvas = None
        self.animation_obj = None
        
        if MATPLOTLIB_AVAILABLE:
            self._create_matplotlib_chart()
        else:
            self._create_fallback_chart()
            
    def _create_matplotlib_chart(self):
        """Создание графика с matplotlib"""
        # Создание фигуры
        self.figure = Figure(figsize=(6, 3), dpi=100)
        self.figure.patch.set_facecolor(theme_manager.get_color("background"))
        
        # Создание осей
        self.ax = self.figure.add_subplot(111)
        self.ax.set_facecolor(theme_manager.get_color("surface"))
        
        # Настройка стиля
        self.ax.grid(True, linestyle='--', alpha=0.3, color=theme_manager.get_color("text_secondary"))
        self.ax.set_title(
            self.parameter_name.replace("_", " ").title(),
            color=theme_manager.get_color("text_primary"),
            fontsize=12
        )
        
        # Настройка осей
        for spine in self.ax.spines.values():
            spine.set_color(theme_manager.get_color("border"))
        self.ax.tick_params(colors=theme_manager.get_color("text_secondary"), labelsize=8)
        
        # Создание canvas
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=5)
        
        # Настройка анимации
        self.animation_obj = animation.FuncAnimation(
            self.figure,
            self._animate,
            interval=500,  # Обновление каждые 500мс
            blit=False,
            cache_frame_data=False
        )
        
    def _create_fallback_chart(self):
        """Создание fallback графика без matplotlib"""
        fallback_label = ctk.CTkLabel(
            self,
            text=f"График {self.parameter_name}\n(matplotlib не доступен)",
            text_color=theme_manager.get_color("text_secondary")
        )
        fallback_label.pack(expand=True, fill="both")
        
    def _animate(self, frame):
        """Анимация графика"""
        if not self.data_points:
            return
            
        self.ax.clear()
        
        # Настройка стиля (нужно повторить после clear)
        self.ax.set_facecolor(theme_manager.get_color("surface"))
        self.ax.grid(True, linestyle='--', alpha=0.3, color=theme_manager.get_color("text_secondary"))
        self.ax.set_title(
            self.parameter_name.replace("_", " ").title(),
            color=theme_manager.get_color("text_primary"),
            fontsize=12
        )
        
        for spine in self.ax.spines.values():
            spine.set_color(theme_manager.get_color("border"))
        self.ax.tick_params(colors=theme_manager.get_color("text_secondary"), labelsize=8)
        
        # Построение графика
        if len(self.data_points) > 1:
            self.ax.plot(
                list(range(len(self.data_points))),
                list(self.data_points),
                color=theme_manager.get_color("primary"),
                linewidth=2,
                alpha=0.8
            )
            
            # Заливка под графиком
            self.ax.fill_between(
                list(range(len(self.data_points))),
                list(self.data_points),
                alpha=0.2,
                color=theme_manager.get_color("primary")
            )
            
        # Настройка осей
        self.ax.set_xlim(0, self.max_points)
        if self.data_points:
            y_min = min(self.data_points) * 0.9
            y_max = max(self.data_points) * 1.1
            if y_min == y_max:
                y_min -= 1
                y_max += 1
            self.ax.set_ylim(y_min, y_max)
            
    def add_data_point(self, value: float):
        """Добавление новой точки данных"""
        self.data_points.append(value)
        self.time_points.append(time.time())
        
    def clear_data(self):
        """Очистка данных графика"""
        self.data_points.clear()
        self.time_points.clear()


class MonitoringPanel(ThemedFrame):
    """Панель мониторинга параметров в реальном времени"""
    
    def __init__(self, parent, app_controller: AppController):
        super().__init__(parent)
        
        self.app_controller = app_controller
        self.is_monitoring = False
        
        # Параметры для мониторинга
        self.monitored_parameters = [
            ("engine_rpm", "об/мин"),
            ("vehicle_speed", "км/ч"),
            ("engine_temp", "°C"),
            ("fuel_level", "%"),
            ("throttle_position", "%"),
            ("intake_pressure", "кПа")
        ]
        
        # Карточки параметров
        self.parameter_cards: Dict[str, ParameterCard] = {}
        
        # Графики
        self.charts: Dict[str, RealTimeChart] = {}
        
        # Подписка на события
        self.app_controller.add_observer('parameter_update', self._on_parameter_update)
        self.app_controller.add_observer('connection_status', self._on_connection_status)
        
        self._create_widgets()
        self._create_layout()
        
    def _create_widgets(self):
        """Создание виджетов панели"""
        # Заголовок
        self.title_label = ctk.CTkLabel(
            self,
            text="Мониторинг параметров",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=theme_manager.get_color("text_primary")
        )
        
        # Панель управления
        self.control_frame = ThemedFrame(self)
        
        self.start_button = ThemedButton(
            self.control_frame,
            text="Начать мониторинг",
            image=get_action_icon("play", (20, 20)),
            button_type="primary",
            command=self._toggle_monitoring
        )
        
        self.clear_button = ThemedButton(
            self.control_frame,
            text="Очистить",
            image=get_action_icon("clear", (20, 20)),
            button_type="secondary",
            command=self._clear_data
        )
        
        # Создание карточек параметров
        self.cards_frame = ThemedFrame(self)
        
        for param_name, unit in self.monitored_parameters:
            card = ParameterCard(self.cards_frame, param_name, unit)
            self.parameter_cards[param_name] = card
            
        # Создание графиков (только если matplotlib доступен)
        self.charts_frame = ThemedFrame(self)
        
        # Выбираем несколько ключевых параметров для графиков
        chart_parameters = ["engine_rpm", "vehicle_speed", "engine_temp"]
        
        for param_name in chart_parameters:
            if param_name in dict(self.monitored_parameters):
                chart = RealTimeChart(self.charts_frame, param_name)
                self.charts[param_name] = chart
                
    def _create_layout(self):
        """Создание макета панели"""
        self.grid_columnconfigure(0, weight=1)
        
        # Заголовок
        self.title_label.grid(row=0, column=0, pady=(10, 20), sticky="ew")
        
        # Панель управления
        self.control_frame.grid(row=1, column=0, pady=10, padx=20, sticky="ew")
        self.control_frame.grid_columnconfigure((0, 1), weight=1)
        
        self.start_button.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="ew")
        self.clear_button.grid(row=0, column=1, padx=(5, 10), pady=10, sticky="ew")
        
        # Карточки параметров
        cards_label = ctk.CTkLabel(
            self,
            text="Текущие значения:",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=theme_manager.get_color("text_primary")
        )
        cards_label.grid(row=2, column=0, pady=(20, 10), padx=20, sticky="w")
        
        self.cards_frame.grid(row=3, column=0, pady=10, padx=20, sticky="ew")
        self.cards_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        # Размещение карточек в сетке 2x3
        row, col = 0, 0
        for param_name, card in self.parameter_cards.items():
            card.grid(row=row, column=col, padx=5, pady=5, sticky="ew")
            col += 1
            if col >= 3:
                col = 0
                row += 1
                
        # Графики
        if self.charts and MATPLOTLIB_AVAILABLE:
            charts_label = ctk.CTkLabel(
                self,
                text="Графики в реальном времени:",
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=theme_manager.get_color("text_primary")
            )
            charts_label.grid(row=4, column=0, pady=(20, 10), padx=20, sticky="w")
            
            self.charts_frame.grid(row=5, column=0, pady=10, padx=20, sticky="ew")
            self.charts_frame.grid_columnconfigure(0, weight=1)
            
            # Размещение графиков вертикально
            for i, (param_name, chart) in enumerate(self.charts.items()):
                chart.grid(row=i, column=0, pady=5, sticky="ew")
                
    def _toggle_monitoring(self):
        """Переключение состояния мониторинга"""
        if self.is_monitoring:
            self._stop_monitoring()
        else:
            self._start_monitoring()
            
    def _start_monitoring(self):
        """Запуск мониторинга"""
        if not self.app_controller.is_connected():
            self.app_controller.notify_observers('error', "Нет подключения к OBD сканеру")
            return
            
        self.is_monitoring = True
        self.start_button.configure(
            text="Остановить мониторинг",
            image=get_action_icon("pause", (20, 20))
        )
        
    def _stop_monitoring(self):
        """Остановка мониторинга"""
        self.is_monitoring = False
        self.start_button.configure(
            text="Начать мониторинг",
            image=get_action_icon("play", (20, 20))
        )
        
    def _clear_data(self):
        """Очистка данных графиков"""
        for chart in self.charts.values():
            chart.clear_data()
            
        # Сброс значений карточек
        for card in self.parameter_cards.values():
            card.update_value("--", "unknown")
            
    def _on_parameter_update(self, parameter_name: str, param_data: ParameterData):
        """Обработка обновления параметра"""
        if not self.is_monitoring:
            return
            
        # Обновление карточки
        if parameter_name in self.parameter_cards:
            card = self.parameter_cards[parameter_name]
            card.update_value(param_data.value, param_data.status)
            
        # Обновление графика
        if parameter_name in self.charts and isinstance(param_data.value, (int, float)):
            chart = self.charts[parameter_name]
            chart.add_data_point(float(param_data.value))
            
    def _on_connection_status(self, status):
        """Обработка изменения статуса подключения"""
        from ..app_controller import ConnectionStatus
        
        if status != ConnectionStatus.CONNECTED and self.is_monitoring:
            self._stop_monitoring()
            
        # Активация/деактивация кнопок
        is_connected = (status == ConnectionStatus.CONNECTED)
        self.start_button.configure(state="normal" if is_connected else "disabled")
        
    def on_theme_changed(self):
        """Обработка изменения темы"""
        super().on_theme_changed()
        
        # Обновление цветов
        self.title_label.configure(text_color=theme_manager.get_color("text_primary"))
        
        # Обновление графиков
        if MATPLOTLIB_AVAILABLE:
            for chart in self.charts.values():
                if chart.figure:
                    chart.figure.patch.set_facecolor(theme_manager.get_color("background"))
                    if hasattr(chart, 'ax'):
                        chart.ax.set_facecolor(theme_manager.get_color("surface"))
