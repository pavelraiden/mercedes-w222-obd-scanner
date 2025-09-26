"""
Главный файл для запуска Mercedes OBD Scanner
"""
import sys
import customtkinter as ctk

from mercedes_obd_scanner.gui.main_window_v2 import MainWindow
from mercedes_obd_scanner.gui.license_window import LicenseWindow
from mercedes_obd_scanner.licensing import license_manager, LicenseStatus
from mercedes_obd_scanner.updater import update_manager

class MercedesOBDApp(ctk.CTk):
    """Главный класс приложения"""
    
    def __init__(self):
        super().__init__()
        self.title("Mercedes OBD Scanner")
        self.geometry("800x600")
        
        self.main_window = None
        
        self.check_license_and_start()
        
    def check_license_and_start(self):
        license_status = license_manager.check_license()
        
        if license_status == LicenseStatus.VALID:
            self.start_main_app()
        else:
            self.show_license_window()
            
    def start_main_app(self):
        # Проверка обновлений
        self.check_for_updates()
        
        # Запуск главного окна
        self.main_window = MainWindow(self)
        self.main_window.pack(fill="both", expand=True)
        
    def show_license_window(self):
        license_window = LicenseWindow(self, on_success=self.on_license_success)
        
    def on_license_success(self):
        self.start_main_app()
        
    def check_for_updates(self):
        # В реальном приложении это должно быть в фоновом потоке
        update_available, info = update_manager.check_for_updates()
        if update_available:
            # Здесь можно показать уведомление пользователю
            print(f"Доступно обновление: {info.get("version")}")
            
            # Если включена автозагрузка
            if update_manager.auto_download:
                update_file = update_manager.download_update(info)
                if update_file and update_manager.auto_install:
                    update_manager.install_update(update_file, info)
                    # Перезапуск приложения
                    # ...

if __name__ == "__main__":
    app = MercedesOBDApp()
    app.mainloop()

