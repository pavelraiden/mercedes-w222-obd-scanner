"""
Главное окно приложения Mercedes OBD Scanner v2.0
Профессиональная версия с полноценным GUI
"""
import customtkinter as ctk
import sys
import os
from typing import Optional

# Добавление пути к модулям
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from .theme_manager import theme_manager, ThemedFrame, ThemedButton
from .icon_manager import get_action_icon, icon_manager
from .app_controller import AppController
from .panels import ConnectionPanel, MonitoringPanel, PredictivePanel, TripHistoryPanel


class StatusBar(ThemedFrame):
    """Строка состояния приложения"""
    
    def __init__(self, parent, app_controller: AppController):
        super().__init__(parent)
        
        self.app_controller = app_controller
        
        # Подписка на события
        self.app_controller.add_observer('connection_status', self._on_status_update)
        self.app_controller.add_observer('error', self._on_error)
        
        self._create_widgets()
        self._create_layout()
        
    def _create_widgets(self):
        """Создание виджетов строки состояния"""
        # Статус подключения
        self.connection_label = ctk.CTkLabel(
            self,
            text="Отключено",
            text_color=theme_manager.get_color("text_secondary"),
            font=ctk.CTkFont(size=11)
        )
        
        # Разделитель
        self.separator1 = ctk.CTkLabel(
            self,
            text="|",
            text_color=theme_manager.get_color("border"),
            font=ctk.CTkFont(size=11)
        )
        
        # Информация о приложении
        self.app_info_label = ctk.CTkLabel(
            self,
            text="Mercedes W222 OBD Scanner v2.0",
            text_color=theme_manager.get_color("text_secondary"),
            font=ctk.CTkFont(size=11)
        )
        
        # Разделитель
        self.separator2 = ctk.CTkLabel(
            self,
            text="|",
            text_color=theme_manager.get_color("border"),
            font=ctk.CTkFont(size=11)
        )
        
        # Текущее время/статус
        self.time_label = ctk.CTkLabel(
            self,
            text="Готов",
            text_color=theme_manager.get_color("text_secondary"),
            font=ctk.CTkFont(size=11)
        )
        
    def _create_layout(self):
        """Создание макета строки состояния"""
        # Левая часть
        self.connection_label.pack(side="left", padx=(10, 5))
        self.separator1.pack(side="left", padx=5)
        self.app_info_label.pack(side="left", padx=5)
        
        # Правая часть
        self.time_label.pack(side="right", padx=(5, 10))
        self.separator2.pack(side="right", padx=5)
        
    def _on_status_update(self, status):
        """Обновление статуса подключения"""
        from .app_controller import ConnectionStatus
        
        status_text = {
            ConnectionStatus.DISCONNECTED: "Отключено",
            ConnectionStatus.CONNECTING: "Подключение...",
            ConnectionStatus.CONNECTED: "Подключено",
            ConnectionStatus.ERROR: "Ошибка подключения"
        }
        
        status_colors = {
            ConnectionStatus.DISCONNECTED: theme_manager.get_color("text_secondary"),
            ConnectionStatus.CONNECTING: theme_manager.get_color("warning"),
            ConnectionStatus.CONNECTED: theme_manager.get_color("success"),
            ConnectionStatus.ERROR: theme_manager.get_color("error")
        }
        
        text = status_text.get(status, "Неизвестно")
        color = status_colors.get(status, theme_manager.get_color("text_secondary"))
        
        self.connection_label.configure(text=text, text_color=color)
        
    def _on_error(self, error_message: str):
        """Отображение ошибки в строке состояния"""
        self.time_label.configure(
            text=f"Ошибка: {error_message[:50]}...",
            text_color=theme_manager.get_color("error")
        )
        
        # Сброс через 5 секунд
        self.after(5000, lambda: self.time_label.configure(
            text="Готов",
            text_color=theme_manager.get_color("text_secondary")
        ))


class MenuBar(ThemedFrame):
    """Панель меню приложения"""
    
    def __init__(self, parent, app_controller: AppController):
        super().__init__(parent)
        
        self.app_controller = app_controller
        
        self._create_widgets()
        self._create_layout()
        
    def _create_widgets(self):
        """Создание виджетов меню"""
        # Логотип Mercedes
        from .icon_manager import icon_manager
        self.logo_label = ctk.CTkLabel(
            self,
            text="",
            image=icon_manager.create_mercedes_logo((32, 32))
        )
        
        # Название приложения
        self.title_label = ctk.CTkLabel(
            self,
            text="Mercedes W222 OBD Scanner",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=theme_manager.get_color("text_primary")
        )
        
        # Кнопки меню
        self.settings_button = ThemedButton(
            self,
            text="",
            image=get_action_icon("settings", (20, 20)),
            width=40,
            command=self._open_settings
        )
        
        self.help_button = ThemedButton(
            self,
            text="",
            image=get_action_icon("help", (20, 20)),
            width=40,
            command=self._open_help
        )
        
        # Переключатель темы
        self.theme_button = ThemedButton(
            self,
            text="Тема",
            width=60,
            command=self._toggle_theme
        )
        
    def _create_layout(self):
        """Создание макета меню"""
        # Левая часть - логотип и название
        self.logo_label.pack(side="left", padx=(10, 5))
        self.title_label.pack(side="left", padx=5)
        
        # Правая часть - кнопки
        self.theme_button.pack(side="right", padx=(5, 10))
        self.help_button.pack(side="right", padx=5)
        self.settings_button.pack(side="right", padx=5)
        
    def _open_settings(self):
        """Открытие настроек"""
        # TODO: Реализовать окно настроек
        print("Открытие настроек...")
        
    def _open_help(self):
        """Открытие справки"""
        # TODO: Реализовать окно справки
        print("Открытие справки...")
        
    def _toggle_theme(self):
        """Переключение темы"""
        current_themes = ["mercedes", "dark", "light"]
        current_index = current_themes.index(theme_manager.current_theme)
        next_index = (current_index + 1) % len(current_themes)
        next_theme = current_themes[next_index]
        
        theme_manager.set_theme(next_theme)


class MercedesOBDScannerV2:
    """Главное приложение Mercedes OBD Scanner v2.0"""
    
    def __init__(self):
        # Инициализация CustomTkinter
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        
        # Применение темы
        theme_manager.apply_theme()
        
        # Предзагрузка иконок
        icon_manager.preload_common_icons()
        
        # Создание главного окна
        self.root = ctk.CTk()
        self.root.title("Mercedes W222 OBD Scanner v2.0")
        self.root.geometry("1200x800")
        self.root.minsize(800, 600)
        
        # Установка иконки окна
        try:
            # Попытка установить иконку (если доступна)
            pass
        except:
            pass
            
        # Инициализация контроллера
        self.app_controller = AppController()
        
        # Создание интерфейса
        self._create_interface()
        
        # Подписка на события закрытия
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # Подписка на изменения темы
        theme_manager.add_observer(self)
        
    def _create_interface(self):
        """Создание интерфейса приложения"""
        # Настройка сетки главного окна
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)
        
        # Панель меню
        self.menu_bar = MenuBar(self.root, self.app_controller)
        self.menu_bar.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 0))
        
        # Основная область с вкладками
        self.tabview = ctk.CTkTabview(self.root)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        
        # Создание вкладок
        self._create_tabs()
        
        # Строка состояния
        self.status_bar = StatusBar(self.root, self.app_controller)
        self.status_bar.grid(row=2, column=0, sticky="ew", padx=5, pady=(0, 5))
        
    def _create_tabs(self):
        """Создание вкладок приложения"""
        # Вкладка подключения
        connection_tab = self.tabview.add("🔌 Подключение")
        self.connection_panel = ConnectionPanel(connection_tab, self.app_controller)
        self.connection_panel.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Вкладка мониторинга
        monitoring_tab = self.tabview.add("📊 Мониторинг")
        self.monitoring_panel = MonitoringPanel(monitoring_tab, self.app_controller)
        self.monitoring_panel.pack(fill="both", expand=True, padx=10, pady=10)

        # Вкладка предиктивной диагностики
        predictive_tab = self.tabview.add("🤖 Предиктивная диагностика")
        self.predictive_panel = PredictivePanel(predictive_tab, self.app_controller)
        self.predictive_panel.pack(fill="both", expand=True, padx=10, pady=10)

        # Вкладка истории поездок
        history_tab = self.tabview.add("📜 История поездок")
        self.trip_history_panel = TripHistoryPanel(history_tab, self.app_controller)
        self.trip_history_panel.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Вкладка настроек
        settings_tab = self.tabview.add("⚙️ Настройки")
        self._create_settings_tab(settings_tab)
        
    def _create_settings_tab(self, parent):
        """Создание вкладки настроек"""
        settings_frame = ThemedFrame(parent)
        settings_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Заголовок
        title_label = ctk.CTkLabel(
            settings_frame,
            text="Настройки приложения",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=theme_manager.get_color("text_primary")
        )
        title_label.pack(pady=(10, 20))
        
        # Настройки темы
        theme_frame = ThemedFrame(settings_frame)
        theme_frame.pack(fill="x", padx=20, pady=10)
        
        theme_label = ctk.CTkLabel(
            theme_frame,
            text="Тема оформления:",
            font=ctk.CTkFont(size=14),
            text_color=theme_manager.get_color("text_primary")
        )
        theme_label.pack(side="left", padx=10, pady=10)
        
        self.theme_combo = ctk.CTkComboBox(
            theme_frame,
            values=theme_manager.get_theme_names(),
            command=self._on_theme_selected
        )
        self.theme_combo.set(theme_manager.get_current_theme_name())
        self.theme_combo.pack(side="right", padx=10, pady=10)
        
        # Настройки обновления
        update_frame = ThemedFrame(settings_frame)
        update_frame.pack(fill="x", padx=20, pady=10)
        
        update_label = ctk.CTkLabel(
            update_frame,
            text="Интервал обновления (сек):",
            font=ctk.CTkFont(size=14),
            text_color=theme_manager.get_color("text_primary")
        )
        update_label.pack(side="left", padx=10, pady=10)
        
        self.update_slider = ctk.CTkSlider(
            update_frame,
            from_=0.1,
            to=2.0,
            number_of_steps=19,
            command=self._on_update_interval_changed
        )
        self.update_slider.set(0.5)  # По умолчанию 0.5 сек
        self.update_slider.pack(side="right", padx=10, pady=10)
        
    def _on_theme_selected(self, theme_name: str):
        """Обработка выбора темы"""
        # Найти ключ темы по имени
        for theme_key, theme_data in theme_manager.THEMES.items():
            if theme_data["name"] == theme_name:
                theme_manager.set_theme(theme_key)
                break
                
    def _on_update_interval_changed(self, value: float):
        """Обработка изменения интервала обновления"""
        self.app_controller.set_update_interval(value)
        
    def on_theme_changed(self):
        """Обработка изменения темы"""
        # Обновление комбобокса темы
        if hasattr(self, 'theme_combo'):
            self.theme_combo.set(theme_manager.get_current_theme_name())
            
    def _on_closing(self):
        """Обработка закрытия приложения"""
        try:
            # Очистка ресурсов контроллера
            self.app_controller.shutdown()
            
            # Сохранение настроек темы
            theme_manager.save_settings()
            
        except Exception as e:
            print(f"Ошибка при закрытии: {e}")
        finally:
            self.root.destroy()
            
    def run(self):
        """Запуск приложения"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self._on_closing()


def main():
    """Главная функция"""
    try:
        app = MercedesOBDScannerV2()
        app.run()
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

