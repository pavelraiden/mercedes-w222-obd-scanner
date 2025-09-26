"""
Панель подключения к OBD сканеру v2.0
"""
import customtkinter as ctk
from typing import List, Optional
import threading

from ..theme_manager import ThemedFrame, ThemedButton, StatusIndicator, theme_manager
from ..icon_manager import get_action_icon, get_status_icon
from ..app_controller import AppController, ConnectionStatus


class ConnectionPanel(ThemedFrame):
    """Панель для подключения к OBD сканеру"""
    
    def __init__(self, parent, app_controller: AppController):
        super().__init__(parent)
        
        self.app_controller = app_controller
        self.is_scanning_ports = False
        
        # Подписка на события контроллера
        self.app_controller.add_observer('connection_status', self._on_connection_status_changed)
        self.app_controller.add_observer('error', self._on_error)
        
        self._create_widgets()
        self._create_layout()
        self._update_protocols()
        
    def _create_widgets(self):
        """Создание виджетов панели"""
        # Заголовок панели
        self.title_label = ctk.CTkLabel(
            self,
            text="Подключение к OBD сканеру",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=theme_manager.get_color("text_primary")
        )
        
        # Статус подключения
        self.status_frame = ctk.CTkFrame(self)
        self.status_indicator = StatusIndicator(self.status_frame, status="disconnected")
        
        # Выбор протокола
        self.protocol_frame = ctk.CTkFrame(self)
        self.protocol_label = ctk.CTkLabel(self.protocol_frame, text="Протокол:", text_color=theme_manager.get_color("text_primary"))
        self.protocol_combo = ctk.CTkComboBox(self.protocol_frame, values=[], command=self._on_protocol_change)

        # Выбор порта
        self.port_frame = ctk.CTkFrame(self)
        self.port_label = ctk.CTkLabel(self.port_frame, text="Порт:", text_color=theme_manager.get_color("text_primary"))
        self.port_combo = ctk.CTkComboBox(self.port_frame, values=["Сканирование..."], state="readonly", width=200)
        self.refresh_button = ThemedButton(self.port_frame, text="", image=get_action_icon("refresh", (16, 16)), width=30, command=self._refresh_ports)
        
        # Кнопки управления
        self.control_frame = ctk.CTkFrame(self)
        self.connect_button = ThemedButton(self.control_frame, text="Подключить", image=get_action_icon("connect", (20, 20)), button_type="primary", command=self._toggle_connection)
        
        # Информационная панель
        self.info_frame = ctk.CTkFrame(self)
        self.info_text = ctk.CTkTextbox(self.info_frame, height=100, wrap="word", state="disabled")
        self._add_info_message("Готов к подключению. Выберите протокол, порт и нажмите 'Подключить'.")
        
    def _create_layout(self):
        """Создание макета панели"""
        self.grid_columnconfigure(0, weight=1)
        self.title_label.grid(row=0, column=0, pady=(10, 20), sticky="ew")
        self.status_frame.grid(row=1, column=0, pady=5, padx=20, sticky="ew")
        self.status_frame.grid_columnconfigure(0, weight=1)
        self.status_indicator.grid(row=0, column=0, pady=10)

        # Протокол
        self.protocol_frame.grid(row=2, column=0, pady=10, padx=20, sticky="ew")
        self.protocol_frame.grid_columnconfigure(1, weight=1)
        self.protocol_label.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="w")
        self.protocol_combo.grid(row=0, column=1, padx=5, pady=10, sticky="ew")

        # Порт
        self.port_frame.grid(row=3, column=0, pady=10, padx=20, sticky="ew")
        self.port_frame.grid_columnconfigure(1, weight=1)
        self.port_label.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="w")
        self.port_combo.grid(row=0, column=1, padx=5, pady=10, sticky="ew")
        self.refresh_button.grid(row=0, column=2, padx=(5, 10), pady=10)
        
        # Кнопки
        self.control_frame.grid(row=4, column=0, pady=10, padx=20, sticky="ew")
        self.control_frame.grid_columnconfigure(0, weight=1)
        self.connect_button.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        # Инфо
        self.info_frame.grid(row=5, column=0, pady=10, padx=20, sticky="ew")
        self.info_frame.grid_columnconfigure(0, weight=1)
        info_label = ctk.CTkLabel(self.info_frame, text="Информация:", text_color=theme_manager.get_color("text_primary"))
        info_label.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")
        self.info_text.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")

    def _update_protocols(self):
        protocols = self.app_controller.get_available_protocols()
        self.protocol_combo.configure(values=protocols)
        if protocols:
            self.protocol_combo.set(protocols[0])
            self._on_protocol_change(protocols[0])

    def _on_protocol_change(self, protocol: str):
        self._refresh_ports()

    def _refresh_ports(self):
        if self.is_scanning_ports:
            return
        self.is_scanning_ports = True
        self.port_combo.configure(values=["Сканирование..."])
        self.port_combo.set("Сканирование...")
        self.refresh_button.configure(state="disabled")
        protocol = self.protocol_combo.get()
        scan_thread = threading.Thread(target=self._scan_ports_thread, args=(protocol,), daemon=True)
        scan_thread.start()

    def _scan_ports_thread(self, protocol: str):
        try:
            ports = self.app_controller.get_available_ports(protocol)
            self.after(0, self._update_ports_list, ports)
        except Exception as e:
            self.after(0, self._on_scan_error, str(e))

    def _update_ports_list(self, ports: List[str]):
        self.is_scanning_ports = False
        self.refresh_button.configure(state="normal")
        if ports:
            self.port_combo.configure(values=ports)
            self.port_combo.set(ports[0])
            self._add_info_message(f"Найдено портов: {len(ports)}")
        else:
            self.port_combo.configure(values=["Порты не найдены"])
            self.port_combo.set("Порты не найдены")
            self._add_info_message("Адаптеры не найдены. Проверьте подключение.")

    def _on_scan_error(self, error: str):
        self.is_scanning_ports = False
        self.refresh_button.configure(state="normal")
        self.port_combo.configure(values=["Ошибка сканирования"])
        self.port_combo.set("Ошибка сканирования")
        self._add_info_message(f"Ошибка сканирования портов: {error}")

    def _toggle_connection(self):
        if self.app_controller.is_connected:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        protocol = self.protocol_combo.get()
        port = self.port_combo.get()
        if not port or port in ["Сканирование...", "Порты не найдены", "Ошибка сканирования"]:
            self._add_info_message("Выберите корректный порт для подключения.")
            return
        self._add_info_message(f"Подключение к {port} по протоколу {protocol}...")
        self.connect_button.configure(state="disabled")
        connect_thread = threading.Thread(target=lambda: self.app_controller.connect_obd(protocol, port), daemon=True)
        connect_thread.start()

    def _disconnect(self):
        self._add_info_message("Отключение...")
        self.app_controller.disconnect_obd()

    def _on_connection_status_changed(self, status: ConnectionStatus):
        status_map = {ConnectionStatus.DISCONNECTED: "disconnected", ConnectionStatus.CONNECTING: "connecting", ConnectionStatus.CONNECTED: "connected", ConnectionStatus.ERROR: "error"}
        ui_status = status_map.get(status, "error")
        self.status_indicator.update_status(ui_status)
        if status == ConnectionStatus.CONNECTED:
            self.connect_button.configure(text="Отключить", image=get_action_icon("disconnect", (20, 20)), state="normal")
            self.protocol_combo.configure(state="disabled")
            self.port_combo.configure(state="disabled")
            self.refresh_button.configure(state="disabled")
            self._add_info_message("Успешно подключено.")
        elif status == ConnectionStatus.CONNECTING:
            self.connect_button.configure(state="disabled")
        else:
            self.connect_button.configure(text="Подключить", image=get_action_icon("connect", (20, 20)), state="normal")
            self.protocol_combo.configure(state="normal")
            self.port_combo.configure(state="readonly")
            self.refresh_button.configure(state="normal")
            if status == ConnectionStatus.DISCONNECTED:
                self._add_info_message("Отключено.")

    def _on_error(self, error_message: str):
        self._add_info_message(f"Ошибка: {error_message}")

    def _add_info_message(self, message: str):
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\n"
        self.info_text.configure(state="normal")
        self.info_text.insert("end", formatted_message)
        self.info_text.see("end")
        self.info_text.configure(state="disabled")

    def on_theme_changed(self):
        super().on_theme_changed()
        self.title_label.configure(text_color=theme_manager.get_color("text_primary"))
        self.protocol_label.configure(text_color=theme_manager.get_color("text_primary"))
        self.port_label.configure(text_color=theme_manager.get_color("text_primary"))

