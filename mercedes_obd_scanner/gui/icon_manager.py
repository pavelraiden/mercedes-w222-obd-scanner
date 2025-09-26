"""
Менеджер иконок для Mercedes OBD Scanner
"""

import os
from PIL import Image, ImageDraw, ImageFont
import customtkinter as ctk
from typing import Dict, Optional, Tuple


class IconManager:
    """Менеджер для создания и управления иконками"""

    def __init__(self):
        self.icons_cache = {}
        self.icons_dir = os.path.join(os.path.dirname(__file__), "icons")
        self.ensure_icons_dir()

    def ensure_icons_dir(self):
        """Создание директории для иконок если она не существует"""
        if not os.path.exists(self.icons_dir):
            os.makedirs(self.icons_dir)

    def create_system_icon(
        self, system_name: str, size: Tuple[int, int] = (24, 24), color: str = "#007AFF"
    ) -> ctk.CTkImage:
        """Создание иконки для системы автомобиля"""
        cache_key = f"{system_name}_{size}_{color}"

        if cache_key in self.icons_cache:
            return self.icons_cache[cache_key]

        # Создание изображения
        img = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Определение символов для разных систем
        system_symbols = {
            "engine": "⚙",
            "transmission": "⚡",
            "abs": "🛡",
            "esp": "🔄",
            "airmatic": "🔧",
            "srs": "🛡",
            "comand": "📱",
            "climate": "❄",
            "lighting": "💡",
            "doors": "🚪",
            "windows": "🪟",
            "seats": "💺",
            "steering": "🎯",
            "suspension": "🔧",
            "brakes": "🛑",
            "fuel": "⛽",
            "exhaust": "💨",
            "cooling": "❄",
            "electrical": "⚡",
            "body": "🚗",
            "default": "⚙",
        }

        symbol = system_symbols.get(system_name.lower(), system_symbols["default"])

        try:
            # Попытка использовать системный шрифт
            font_size = min(size) - 4
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            # Fallback на стандартный шрифт
            font = ImageFont.load_default()

        # Получение размеров текста
        bbox = draw.textbbox((0, 0), symbol, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Центрирование текста
        x = (size[0] - text_width) // 2
        y = (size[1] - text_height) // 2

        # Рисование символа
        draw.text((x, y), symbol, fill=color, font=font)

        # Создание CTkImage
        ctk_image = ctk.CTkImage(light_image=img, dark_image=img, size=size)

        # Кэширование
        self.icons_cache[cache_key] = ctk_image

        return ctk_image

    def create_status_icon(self, status: str, size: Tuple[int, int] = (16, 16)) -> ctk.CTkImage:
        """Создание иконки статуса"""
        cache_key = f"status_{status}_{size}"

        if cache_key in self.icons_cache:
            return self.icons_cache[cache_key]

        img = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Цвета для разных статусов
        status_colors = {
            "ok": "#34C759",
            "warning": "#FF9500",
            "error": "#FF3B30",
            "info": "#007AFF",
            "unknown": "#8E8E93",
        }

        color = status_colors.get(status, status_colors["unknown"])

        # Рисование круга
        margin = 2
        draw.ellipse(
            [margin, margin, size[0] - margin, size[1] - margin], fill=color, outline=color
        )

        # Добавление символа в центр
        symbols = {"ok": "✓", "warning": "!", "error": "✗", "info": "i", "unknown": "?"}

        symbol = symbols.get(status, symbols["unknown"])

        try:
            font_size = min(size) // 2
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), symbol, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = (size[0] - text_width) // 2
        y = (size[1] - text_height) // 2

        draw.text((x, y), symbol, fill="white", font=font)

        ctk_image = ctk.CTkImage(light_image=img, dark_image=img, size=size)
        self.icons_cache[cache_key] = ctk_image

        return ctk_image

    def create_action_icon(
        self, action: str, size: Tuple[int, int] = (20, 20), color: str = "#007AFF"
    ) -> ctk.CTkImage:
        """Создание иконки для действий"""
        cache_key = f"action_{action}_{size}_{color}"

        if cache_key in self.icons_cache:
            return self.icons_cache[cache_key]

        img = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Символы для действий
        action_symbols = {
            "connect": "🔌",
            "disconnect": "🔌",
            "scan": "🔍",
            "clear": "🗑",
            "save": "💾",
            "load": "📁",
            "export": "📤",
            "import": "📥",
            "settings": "⚙",
            "help": "❓",
            "refresh": "🔄",
            "play": "▶",
            "pause": "⏸",
            "stop": "⏹",
            "record": "⏺",
        }

        symbol = action_symbols.get(action, "⚙")

        try:
            font_size = min(size) - 4
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), symbol, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = (size[0] - text_width) // 2
        y = (size[1] - text_height) // 2

        draw.text((x, y), symbol, fill=color, font=font)

        ctk_image = ctk.CTkImage(light_image=img, dark_image=img, size=size)
        self.icons_cache[cache_key] = ctk_image

        return ctk_image

    def create_mercedes_logo(self, size: Tuple[int, int] = (32, 32)) -> ctk.CTkImage:
        """Создание логотипа Mercedes-Benz"""
        cache_key = f"mercedes_logo_{size}"

        if cache_key in self.icons_cache:
            return self.icons_cache[cache_key]

        img = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Рисование круга
        center = (size[0] // 2, size[1] // 2)
        radius = min(size) // 2 - 2

        draw.ellipse(
            [center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius],
            outline="#C4C4C4",
            width=2,
        )

        # Рисование трехлучевой звезды
        import math

        star_radius = radius * 0.7
        angles = [0, 120, 240]  # Углы для трех лучей

        for angle in angles:
            rad = math.radians(angle - 90)  # -90 для поворота вверх
            end_x = center[0] + star_radius * math.cos(rad)
            end_y = center[1] + star_radius * math.sin(rad)

            draw.line([center[0], center[1], end_x, end_y], fill="#C4C4C4", width=2)

        ctk_image = ctk.CTkImage(light_image=img, dark_image=img, size=size)
        self.icons_cache[cache_key] = ctk_image

        return ctk_image

    def get_system_icon(self, system_name: str, size: Tuple[int, int] = (24, 24)) -> ctk.CTkImage:
        """Получение иконки системы с автоматическим созданием"""
        from .theme_manager import theme_manager

        color = theme_manager.get_color("primary")
        return self.create_system_icon(system_name, size, color)

    def get_status_icon(self, status: str, size: Tuple[int, int] = (16, 16)) -> ctk.CTkImage:
        """Получение иконки статуса"""
        return self.create_status_icon(status, size)

    def get_action_icon(self, action: str, size: Tuple[int, int] = (20, 20)) -> ctk.CTkImage:
        """Получение иконки действия"""
        from .theme_manager import theme_manager

        color = theme_manager.get_color("primary")
        return self.create_action_icon(action, size, color)

    def clear_cache(self):
        """Очистка кэша иконок"""
        self.icons_cache.clear()

    def preload_common_icons(self):
        """Предзагрузка часто используемых иконок"""
        common_systems = ["engine", "transmission", "abs", "esp", "airmatic", "srs"]
        common_statuses = ["ok", "warning", "error", "info"]
        common_actions = ["connect", "scan", "clear", "save", "settings"]

        for system in common_systems:
            self.get_system_icon(system)

        for status in common_statuses:
            self.get_status_icon(status)

        for action in common_actions:
            self.get_action_icon(action)


# Глобальный экземпляр менеджера иконок
icon_manager = IconManager()


def get_icon_manager() -> IconManager:
    """Получение глобального экземпляра менеджера иконок"""
    return icon_manager


# Удобные функции для быстрого доступа
def get_system_icon(system_name: str, size: Tuple[int, int] = (24, 24)) -> ctk.CTkImage:
    """Быстрое получение иконки системы"""
    return icon_manager.get_system_icon(system_name, size)


def get_status_icon(status: str, size: Tuple[int, int] = (16, 16)) -> ctk.CTkImage:
    """Быстрое получение иконки статуса"""
    return icon_manager.get_status_icon(status, size)


def get_action_icon(action: str, size: Tuple[int, int] = (20, 20)) -> ctk.CTkImage:
    """Быстрое получение иконки действия"""
    return icon_manager.get_action_icon(action, size)
