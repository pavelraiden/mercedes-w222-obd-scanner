"""
Система управления темами для Mercedes OBD Scanner
"""
import customtkinter as ctk
from typing import Dict, Any
import json
import os


class ThemeManager:
    """Менеджер тем для приложения"""
    
    # Определение тем
    THEMES = {
        "dark": {
            "name": "Темная",
            "ctk_mode": "dark",
            "ctk_theme": "dark-blue",
            "colors": {
                "background": "#1E1E1E",
                "surface": "#2B2B2B", 
                "primary": "#007AFF",
                "secondary": "#5856D6",
                "accent": "#FF9500",
                "text_primary": "#FFFFFF",
                "text_secondary": "#8E8E93",
                "success": "#34C759",
                "warning": "#FF9500", 
                "error": "#FF3B30",
                "info": "#007AFF",
                "border": "#3A3A3C",
                "hover": "#3A3A3C"
            },
            "matplotlib": {
                "figure.facecolor": "#1E1E1E",
                "axes.facecolor": "#2B2B2B",
                "axes.edgecolor": "#8E8E93",
                "axes.labelcolor": "#FFFFFF",
                "text.color": "#FFFFFF",
                "xtick.color": "#8E8E93",
                "ytick.color": "#8E8E93",
                "grid.color": "#3A3A3C",
                "lines.color": "#007AFF"
            }
        },
        "light": {
            "name": "Светлая",
            "ctk_mode": "light", 
            "ctk_theme": "blue",
            "colors": {
                "background": "#FFFFFF",
                "surface": "#F2F2F7",
                "primary": "#007AFF", 
                "secondary": "#5856D6",
                "accent": "#FF9500",
                "text_primary": "#000000",
                "text_secondary": "#6D6D70",
                "success": "#34C759",
                "warning": "#FF9500",
                "error": "#FF3B30", 
                "info": "#007AFF",
                "border": "#C6C6C8",
                "hover": "#E5E5EA"
            },
            "matplotlib": {
                "figure.facecolor": "#FFFFFF",
                "axes.facecolor": "#F2F2F7", 
                "axes.edgecolor": "#6D6D70",
                "axes.labelcolor": "#000000",
                "text.color": "#000000",
                "xtick.color": "#6D6D70",
                "ytick.color": "#6D6D70", 
                "grid.color": "#C6C6C8",
                "lines.color": "#007AFF"
            }
        },
        "mercedes": {
            "name": "Mercedes",
            "ctk_mode": "dark",
            "ctk_theme": "dark-blue", 
            "colors": {
                "background": "#0F1419",
                "surface": "#1A1F2E",
                "primary": "#00ADEF", # Mercedes blue
                "secondary": "#C4C4C4", # Mercedes silver
                "accent": "#FFD700", # Gold accent
                "text_primary": "#FFFFFF",
                "text_secondary": "#B0B0B0",
                "success": "#00D084",
                "warning": "#FFA500",
                "error": "#FF4444", 
                "info": "#00ADEF",
                "border": "#2A2F3E",
                "hover": "#2A2F3E"
            },
            "matplotlib": {
                "figure.facecolor": "#0F1419",
                "axes.facecolor": "#1A1F2E",
                "axes.edgecolor": "#B0B0B0", 
                "axes.labelcolor": "#FFFFFF",
                "text.color": "#FFFFFF",
                "xtick.color": "#B0B0B0",
                "ytick.color": "#B0B0B0",
                "grid.color": "#2A2F3E", 
                "lines.color": "#00ADEF"
            }
        }
    }
    
    def __init__(self):
        self.current_theme = "mercedes"  # По умолчанию Mercedes тема
        self.observers = []
        self.config_file = os.path.join(os.path.expanduser("~"), ".mercedes_obd_theme.json")
        self.load_settings()
        
    def load_settings(self):
        """Загрузка настроек темы из файла"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    self.current_theme = settings.get('theme', 'mercedes')
        except Exception as e:
            print(f"Ошибка загрузки настроек темы: {e}")
            
    def save_settings(self):
        """Сохранение настроек темы в файл"""
        try:
            settings = {'theme': self.current_theme}
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения настроек темы: {e}")
            
    def set_theme(self, theme_name: str):
        """Установка темы"""
        if theme_name in self.THEMES:
            self.current_theme = theme_name
            self.apply_theme()
            self.save_settings()
            self.notify_observers()
            
    def apply_theme(self):
        """Применение текущей темы"""
        theme = self.THEMES[self.current_theme]
        
        # Применение CustomTkinter темы
        ctk.set_appearance_mode(theme["ctk_mode"])
        ctk.set_default_color_theme(theme["ctk_theme"])
        
        # Применение matplotlib темы
        try:
            import matplotlib.pyplot as plt
            plt.rcParams.update(theme["matplotlib"])
        except ImportError:
            pass
            
    def get_color(self, color_name: str) -> str:
        """Получение цвета из текущей темы"""
        return self.THEMES[self.current_theme]["colors"].get(color_name, "#FFFFFF")
        
    def get_colors(self) -> Dict[str, str]:
        """Получение всех цветов текущей темы"""
        return self.THEMES[self.current_theme]["colors"]
        
    def get_theme_names(self) -> list:
        """Получение списка доступных тем"""
        return [self.THEMES[theme]["name"] for theme in self.THEMES.keys()]
        
    def get_current_theme_name(self) -> str:
        """Получение имени текущей темы"""
        return self.THEMES[self.current_theme]["name"]
        
    def add_observer(self, observer):
        """Добавление наблюдателя для уведомлений о смене темы"""
        self.observers.append(observer)
        
    def remove_observer(self, observer):
        """Удаление наблюдателя"""
        if observer in self.observers:
            self.observers.remove(observer)
            
    def notify_observers(self):
        """Уведомление всех наблюдателей о смене темы"""
        for observer in self.observers:
            if hasattr(observer, 'on_theme_changed'):
                observer.on_theme_changed()


# Глобальный экземпляр менеджера тем
theme_manager = ThemeManager()


def get_theme_manager() -> ThemeManager:
    """Получение глобального экземпляра менеджера тем"""
    return theme_manager


class ThemedFrame(ctk.CTkFrame):
    """Базовый класс для фреймов с поддержкой тем"""
    
    def __init__(self, parent, **kwargs):
        # Применение цветов темы
        theme_colors = theme_manager.get_colors()
        if 'fg_color' not in kwargs:
            kwargs['fg_color'] = theme_colors['surface']
            
        super().__init__(parent, **kwargs)
        
        # Подписка на изменения темы
        theme_manager.add_observer(self)
        
    def on_theme_changed(self):
        """Обработка изменения темы"""
        theme_colors = theme_manager.get_colors()
        self.configure(fg_color=theme_colors['surface'])


class ThemedButton(ctk.CTkButton):
    """Кнопка с поддержкой тем"""
    
    def __init__(self, parent, button_type="primary", **kwargs):
        theme_colors = theme_manager.get_colors()
        
        # Применение цветов в зависимости от типа кнопки
        if button_type == "primary":
            kwargs.setdefault('fg_color', theme_colors['primary'])
            kwargs.setdefault('hover_color', theme_colors['primary'])
        elif button_type == "secondary":
            kwargs.setdefault('fg_color', theme_colors['secondary'])
            kwargs.setdefault('hover_color', theme_colors['secondary'])
        elif button_type == "success":
            kwargs.setdefault('fg_color', theme_colors['success'])
            kwargs.setdefault('hover_color', theme_colors['success'])
        elif button_type == "error":
            kwargs.setdefault('fg_color', theme_colors['error'])
            kwargs.setdefault('hover_color', theme_colors['error'])
            
        kwargs.setdefault('text_color', theme_colors['text_primary'])
        
        super().__init__(parent, **kwargs)
        
        self.button_type = button_type
        theme_manager.add_observer(self)
        
    def on_theme_changed(self):
        """Обработка изменения темы"""
        theme_colors = theme_manager.get_colors()
        
        if self.button_type == "primary":
            self.configure(fg_color=theme_colors['primary'])
        elif self.button_type == "secondary":
            self.configure(fg_color=theme_colors['secondary'])
        elif self.button_type == "success":
            self.configure(fg_color=theme_colors['success'])
        elif self.button_type == "error":
            self.configure(fg_color=theme_colors['error'])
            
        self.configure(text_color=theme_colors['text_primary'])


class StatusIndicator(ctk.CTkFrame):
    """Индикатор состояния с цветовой индикацией"""
    
    def __init__(self, parent, status="disconnected", **kwargs):
        super().__init__(parent, **kwargs)
        
        self.status = status
        self.indicator = ctk.CTkFrame(self, width=12, height=12, corner_radius=6)
        self.indicator.pack(side="left", padx=(0, 8))
        
        self.label = ctk.CTkLabel(self, text="")
        self.label.pack(side="left")
        
        self.update_status(status)
        theme_manager.add_observer(self)
        
    def update_status(self, status: str):
        """Обновление статуса индикатора"""
        self.status = status
        theme_colors = theme_manager.get_colors()
        
        status_config = {
            "connected": {
                "color": theme_colors['success'],
                "text": "Подключено"
            },
            "connecting": {
                "color": theme_colors['warning'], 
                "text": "Подключение..."
            },
            "disconnected": {
                "color": theme_colors['error'],
                "text": "Отключено"
            },
            "error": {
                "color": theme_colors['error'],
                "text": "Ошибка"
            }
        }
        
        config = status_config.get(status, status_config["disconnected"])
        self.indicator.configure(fg_color=config["color"])
        self.label.configure(text=config["text"])
        
    def on_theme_changed(self):
        """Обработка изменения темы"""
        self.update_status(self.status)
