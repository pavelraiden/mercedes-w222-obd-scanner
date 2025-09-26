"""
Окно лицензирования для Mercedes OBD Scanner
"""
import customtkinter as ctk
from typing import Callable

from ..licensing import license_manager, LicenseStatus

class LicenseWindow(ctk.CTkToplevel):
    """Окно для активации и управления лицензией"""
    
    def __init__(self, master, on_success: Callable):
        super().__init__(master)
        self.title("Лицензирование")
        self.geometry("400x300")
        self.transient(master)
        self.grab_set()
        
        self.on_success = on_success
        
        self.create_widgets()
        self.update_status()
        
    def create_widgets(self):
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Статус лицензии
        self.status_label = ctk.CTkLabel(self.main_frame, text="Статус:")
        self.status_label.pack(pady=5)
        
        self.status_value = ctk.CTkLabel(self.main_frame, text="", font=("Arial", 12, "bold"))
        self.status_value.pack(pady=5)
        
        # Поле для ввода ключа
        self.key_entry = ctk.CTkEntry(self.main_frame, placeholder_text="Введите лицензионный ключ")
        self.key_entry.pack(fill="x", padx=10, pady=10)
        
        # Кнопка активации
        self.activate_button = ctk.CTkButton(self.main_frame, text="Активировать", command=self.activate)
        self.activate_button.pack(pady=10)
        
        # Активация trial
        self.trial_button = ctk.CTkButton(self.main_frame, text="Активировать Trial", command=self.activate_trial)
        self.trial_button.pack(pady=5)
        
        # Информация об оборудовании
        self.hwid_label = ctk.CTkLabel(self.main_frame, text=f"Hardware ID: {license_manager.hardware_id}")
        self.hwid_label.pack(pady=10)
        
    def activate(self):
        license_key = self.key_entry.get()
        if not license_key:
            self.show_message("Введите лицензионный ключ")
            return
            
        success, message = license_manager.activate_license(license_key)
        self.show_message(message)
        
        if success:
            self.on_success()
            self.destroy()
            
    def activate_trial(self):
        trial_key = license_manager.generate_trial_key()
        success, message = license_manager.activate_license(trial_key, offline_mode=True)
        self.show_message(message)
        
        if success:
            self.on_success()
            self.destroy()
            
    def update_status(self):
        license_info = license_manager.get_license_info()
        status = license_info.get("status")
        
        if status == LicenseStatus.VALID.value:
            self.status_value.configure(text="Лицензия действительна", text_color="green")
            self.activate_button.configure(state="disabled")
            self.trial_button.configure(state="disabled")
        elif status == LicenseStatus.EXPIRED.value:
            self.status_value.configure(text="Лицензия истекла", text_color="red")
        elif status == LicenseStatus.NOT_ACTIVATED.value:
            self.status_value.configure(text="Лицензия не активирована", text_color="orange")
        else:
            self.status_value.configure(text=f"Ошибка: {status}", text_color="red")
            
    def show_message(self, message: str):
        # В реальном приложении лучше использовать кастомные диалоговые окна
        print(f"[License Message]: {message}")

