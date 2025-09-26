#!/usr/bin/env python3
"""
Главное окно Mercedes W222 OBD Scanner
"""

import customtkinter as ctk
import logging
from typing import Optional
from pathlib import Path

# Импорты панелей (будут созданы позже)
# from .panels.connection_panel import ConnectionPanel
# from .panels.monitoring_panel import MonitoringPanel
# from .panels.diagnostic_panel import DiagnosticPanel
# from .panels.settings_panel import SettingsPanel
# from .panels.quick_diagnostic_panel import QuickDiagnosticPanel

from ..core.config_manager import config_manager
from ..core.obd_controller import OBDController


class MercedesOBDScanner:
    """
    Главный класс приложения Mercedes W222 OBD Scanner
    """
    
    def __init__(self):
        """Инициализация главного окна"""
        self.logger = logging.getLogger(__name__)
        
        # Настройка CustomTkinter
        ctk.set_appearance_mode("dark")  # Темная тема по умолчанию
        ctk.set_default_color_theme("blue")  # Синяя цветовая схема
        
        # Создание главного окна
        self.root = ctk.CTk()
        self.root.title("Mercedes W222 OBD Scanner v1.0")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 600)
        
        # Переменные состояния
        self.is_connected = False
        self.current_engine = None
        
        # OBD контроллер (по умолчанию в демо-режиме)
        self.obd_controller = OBDController(demo_mode=True)
        
        # Инициализация компонентов
        self.setup_main_window()
        self.create_menu_bar()
        self.create_status_bar()
        self.create_tabs()
        
        # Загрузка конфигурации
        self.load_configuration()
        
        # Настройка обработчиков событий
        self.setup_event_handlers()
        
        self.logger.info("Mercedes OBD Scanner initialized")
    
    def setup_main_window(self):
        """Настройка главного окна"""
        # Настройка сетки
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)  # Основная область с вкладками
        
        # Иконка приложения (если есть)
        try:
            icon_path = Path(__file__).parent.parent.parent / "assets" / "icon.ico"
            if icon_path.exists():
                self.root.iconbitmap(str(icon_path))
        except Exception as e:
            self.logger.warning(f"Could not load application icon: {e}")
    
    def create_menu_bar(self):
        """Создание строки меню"""
        # В CustomTkinter нет встроенного меню, создаем кастомную панель
        self.menu_frame = ctk.CTkFrame(self.root, height=40)
        self.menu_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 0))
        self.menu_frame.grid_columnconfigure(4, weight=1)  # Растягиваем пустое пространство
        
        # Кнопки меню
        self.file_menu_btn = ctk.CTkButton(
            self.menu_frame, 
            text="Файл", 
            width=80,
            command=self.show_file_menu
        )
        self.file_menu_btn.grid(row=0, column=0, padx=5, pady=5)
        
        self.tools_menu_btn = ctk.CTkButton(
            self.menu_frame, 
            text="Инструменты", 
            width=100,
            command=self.show_tools_menu
        )
        self.tools_menu_btn.grid(row=0, column=1, padx=5, pady=5)
        
        self.help_menu_btn = ctk.CTkButton(
            self.menu_frame, 
            text="Справка", 
            width=80,
            command=self.show_help_menu
        )
        self.help_menu_btn.grid(row=0, column=2, padx=5, pady=5)
        
        # Индикатор подключения
        self.connection_indicator = ctk.CTkLabel(
            self.menu_frame,
            text="● Не подключен",
            text_color="red"
        )
        self.connection_indicator.grid(row=0, column=5, padx=10, pady=5)
    
    def create_status_bar(self):
        """Создание строки состояния"""
        self.status_frame = ctk.CTkFrame(self.root, height=30)
        self.status_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=(0, 5))
        self.status_frame.grid_columnconfigure(1, weight=1)
        
        # Статус подключения
        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="Готов к работе",
            anchor="w"
        )
        self.status_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        
        # Информация о двигателе
        self.engine_info_label = ctk.CTkLabel(
            self.status_frame,
            text="Двигатель: не определен",
            anchor="e"
        )
        self.engine_info_label.grid(row=0, column=2, padx=10, pady=5, sticky="e")
    
    def create_tabs(self):
        """Создание системы вкладок"""
        self.tab_view = ctk.CTkTabview(self.root)
        self.tab_view.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        
        # Создание вкладок
        self.connection_tab = self.tab_view.add("Подключение")
        self.monitoring_tab = self.tab_view.add("Мониторинг")
        self.quick_diag_tab = self.tab_view.add("Быстрая диагностика")
        self.diagnostic_tab = self.tab_view.add("Диагностика")
        self.settings_tab = self.tab_view.add("Настройки")
        
        # Инициализация содержимого вкладок
        self.setup_connection_tab()
        self.setup_monitoring_tab()
        self.setup_quick_diagnostic_tab()
        self.setup_diagnostic_tab()
        self.setup_settings_tab()
    
    def setup_connection_tab(self):
        """Настройка вкладки подключения"""
        # Временная заглушка - будет заменена на ConnectionPanel
        connection_label = ctk.CTkLabel(
            self.connection_tab,
            text="Панель подключения к OBD-сканеру\\n\\n" +
                 "Здесь будет:\\n" +
                 "• Выбор COM порта\\n" +
                 "• Настройки подключения\\n" +
                 "• Автоопределение двигателя\\n" +
                 "• Статус подключения",
            justify="left"
        )
        connection_label.pack(expand=True, fill="both", padx=20, pady=20)
    
    def setup_monitoring_tab(self):
        """Настройка вкладки мониторинга"""
        # Временная заглушка - будет заменена на MonitoringPanel
        monitoring_label = ctk.CTkLabel(
            self.monitoring_tab,
            text="Панель мониторинга в реальном времени\\n\\n" +
                 "Здесь будет:\\n" +
                 "• Графики параметров двигателя\\n" +
                 "• Таблица текущих значений\\n" +
                 "• Индикаторы состояния систем\\n" +
                 "• Настраиваемые дашборды",
            justify="left"
        )
        monitoring_label.pack(expand=True, fill="both", padx=20, pady=20)
    
    def setup_quick_diagnostic_tab(self):
        """Настройка вкладки быстрой диагностики"""
        # Новая панель для быстрой диагностики W222
        quick_diag_label = ctk.CTkLabel(
            self.quick_diag_tab,
            text="Быстрая диагностика Mercedes W222\\n\\n" +
                 "Здесь будет:\\n" +
                 "• Проверка критических систем одним кликом\\n" +
                 "• Health-check двигателя, Airmatic, трансмиссии\\n" +
                 "• Общий индикатор состояния автомобиля\\n" +
                 "• Рекомендации по обслуживанию",
            justify="left"
        )
        quick_diag_label.pack(expand=True, fill="both", padx=20, pady=20)
    
    def setup_diagnostic_tab(self):
        """Настройка вкладки диагностики"""
        # Временная заглушка - будет заменена на DiagnosticPanel
        diagnostic_label = ctk.CTkLabel(
            self.diagnostic_tab,
            text="Расширенная диагностика\\n\\n" +
                 "Здесь будет:\\n" +
                 "• Чтение и расшифровка DTC кодов\\n" +
                 "• Специфические тесты систем W222\\n" +
                 "• UDS команды для экспертов\\n" +
                 "• Сервисные процедуры",
            justify="left"
        )
        diagnostic_label.pack(expand=True, fill="both", padx=20, pady=20)
    
    def setup_settings_tab(self):
        """Настройка вкладки настроек"""
        # Временная заглушка - будет заменена на SettingsPanel
        settings_label = ctk.CTkLabel(
            self.settings_tab,
            text="Настройки приложения\\n\\n" +
                 "Здесь будет:\\n" +
                 "• Настройки подключения\\n" +
                 "• Параметры логирования\\n" +
                 "• Темы оформления\\n" +
                 "• Обновление конфигураций",
            justify="left"
        )
        settings_label.pack(expand=True, fill="both", padx=20, pady=20)
    
    def load_configuration(self):
        """Загрузка конфигурации приложения"""
        try:
            config_path = Path(__file__).parent.parent / "configs"
            config_manager.load_configs(str(config_path))
            
            engine_type = config_manager.get_engine_type()
            if engine_type:
                self.current_engine = engine_type
                self.engine_info_label.configure(text=f"Двигатель: {engine_type.value}")
            
            self.update_status("Конфигурация загружена")
            
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}")
            self.update_status(f"Ошибка загрузки конфигурации: {e}")
    
    def setup_event_handlers(self):
        """Настройка обработчиков событий"""
        # Обработчик закрытия окна
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Подписка на события ConfigManager
        config_manager.add_observer(self.on_config_event)
    
    def on_config_event(self, event: str, data=None):
        """Обработчик событий конфигурации"""
        if event == "config_loaded":
            self.update_status("Конфигурация обновлена")
        elif event == "engine_detected":
            self.current_engine = data
            self.engine_info_label.configure(text=f"Двигатель: {data.value}")
    
    def update_status(self, message: str):
        """Обновление строки состояния"""
        self.status_label.configure(text=message)
        self.logger.info(f"Status: {message}")
    
    def update_connection_status(self, connected: bool):
        """Обновление статуса подключения"""
        self.is_connected = connected
        
        if connected:
            self.connection_indicator.configure(
                text="● Подключен",
                text_color="green"
            )
            self.update_status("Подключен к OBD-сканеру")
        else:
            self.connection_indicator.configure(
                text="● Не подключен",
                text_color="red"
            )
            self.update_status("Отключен от OBD-сканера")
    
    # Обработчики меню (заглушки)
    def show_file_menu(self):
        """Показать меню Файл"""
        # TODO: Реализовать выпадающее меню
        self.logger.info("File menu clicked")
    
    def show_tools_menu(self):
        """Показать меню Инструменты"""
        # TODO: Реализовать выпадающее меню
        self.logger.info("Tools menu clicked")
    
    def show_help_menu(self):
        """Показать меню Справка"""
        # TODO: Реализовать выпадающее меню
        self.logger.info("Help menu clicked")
    
    def on_closing(self):
        """Обработчик закрытия приложения"""
        self.logger.info("Application closing")
        
        # Сохранение настроек
        # TODO: Сохранить состояние окна, настройки пользователя
        
        # Закрытие соединений
        if self.is_connected:
            # TODO: Закрыть OBD соединение
            pass
        
        self.root.destroy()
    
    def run(self):
        """Запуск главного цикла приложения"""
        self.logger.info("Starting Mercedes OBD Scanner")
        self.root.mainloop()


def main():
    """Точка входа в приложение"""
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Создание и запуск приложения
    app = MercedesOBDScanner()
    app.run()


if __name__ == "__main__":
    main()
