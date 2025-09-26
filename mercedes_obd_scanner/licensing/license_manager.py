"""
Менеджер лицензий для Mercedes OBD Scanner
"""

import os
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from enum import Enum
import logging

from .hardware_id import hardware_id_generator
from .crypto import license_crypto


class LicenseType(Enum):
    """Типы лицензий"""

    TRIAL = "trial"
    FULL = "full"
    PROFESSIONAL = "professional"


class LicenseStatus(Enum):
    """Статусы лицензии"""

    VALID = "valid"
    EXPIRED = "expired"
    INVALID = "invalid"
    NOT_ACTIVATED = "not_activated"
    HARDWARE_MISMATCH = "hardware_mismatch"
    NETWORK_ERROR = "network_error"


class LicenseManager:
    """Менеджер лицензий"""

    def __init__(self, activation_server: str = None):
        """
        Инициализация менеджера лицензий

        Args:
            activation_server: URL сервера активации
        """
        self.logger = logging.getLogger(__name__)

        # Настройки
        self.activation_server = activation_server or "https://api.mercedes-obd-scanner.com"
        self.license_file = Path.home() / ".mercedes_obd_scanner" / "license.dat"
        self.cache_file = Path.home() / ".mercedes_obd_scanner" / "cache.dat"

        # Создание директории для лицензий
        self.license_file.parent.mkdir(parents=True, exist_ok=True)

        # Настройки grace period
        self.grace_period_days = 7  # Дни работы без интернета
        self.trial_period_days = 14  # Пробный период

        # Текущее состояние
        self.current_license: Optional[Dict[str, Any]] = None
        self.hardware_id = hardware_id_generator.generate_hardware_id()

        # Загрузка существующей лицензии
        self._load_license()

    def activate_license(self, license_key: str, offline_mode: bool = False) -> Tuple[bool, str]:
        """
        Активация лицензии

        Args:
            license_key: Лицензионный ключ
            offline_mode: Режим офлайн активации

        Returns:
            Tuple (успех, сообщение)
        """
        try:
            # Проверка формата ключа
            if not license_crypto.validate_license_key_format(license_key):
                return False, "Неверный формат лицензионного ключа"

            if offline_mode:
                return self._activate_offline(license_key)
            else:
                return self._activate_online(license_key)

        except Exception as e:
            self.logger.error(f"Error activating license: {e}")
            return False, f"Ошибка активации: {e}"

    def _activate_online(self, license_key: str) -> Tuple[bool, str]:
        """Онлайн активация лицензии"""
        try:
            # Генерация токена активации
            activation_token = license_crypto.generate_activation_token(
                license_key, self.hardware_id
            )

            # Отправка запроса на сервер
            response = requests.post(
                f"{self.activation_server}/api/v1/activate",
                json={
                    "license_key": license_key,
                    "hardware_id": self.hardware_id,
                    "activation_token": activation_token,
                    "product_version": "1.0.0",
                },
                timeout=30,
            )

            if response.status_code == 200:
                license_data = response.json()

                # Проверка подписи
                signature = license_data.pop("signature", "")
                if not license_crypto.verify_license_signature(license_data, signature):
                    return False, "Неверная подпись лицензии"

                # Сохранение лицензии
                self._save_license_data(license_data)
                self.current_license = license_data

                return True, "Лицензия успешно активирована"

            elif response.status_code == 400:
                error_data = response.json()
                return False, error_data.get("message", "Ошибка активации")

            elif response.status_code == 404:
                return False, "Лицензионный ключ не найден"

            else:
                return False, f"Ошибка сервера: {response.status_code}"

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error during activation: {e}")
            return False, "Ошибка сети. Проверьте подключение к интернету"

    def _activate_offline(self, license_key: str) -> Tuple[bool, str]:
        """Офлайн активация лицензии (для trial)"""
        try:
            # Проверка что это trial ключ
            if not license_key.startswith("MOBS-TRIAL"):
                return False, "Офлайн активация доступна только для trial версии"

            # Создание trial лицензии
            trial_data = {
                "license_key": license_key,
                "hardware_id": self.hardware_id,
                "license_type": LicenseType.TRIAL.value,
                "expiry_date": (
                    datetime.now() + timedelta(days=self.trial_period_days)
                ).isoformat(),
                "activated_at": datetime.now().isoformat(),
                "features": {
                    "max_sessions": 50,
                    "export_formats": ["json", "csv"],
                    "reports": True,
                    "advanced_diagnostics": False,
                },
                "offline_activation": True,
            }

            # Создание подписи
            signature = license_crypto.create_license_signature(trial_data)
            trial_data["signature"] = signature

            # Сохранение лицензии
            self._save_license_data(trial_data)
            self.current_license = trial_data

            return True, f"Trial лицензия активирована на {self.trial_period_days} дней"

        except Exception as e:
            self.logger.error(f"Error in offline activation: {e}")
            return False, f"Ошибка офлайн активации: {e}"

    def check_license(self, force_online_check: bool = False) -> LicenseStatus:
        """
        Проверка статуса лицензии

        Args:
            force_online_check: Принудительная онлайн проверка

        Returns:
            Статус лицензии
        """
        try:
            if not self.current_license:
                return LicenseStatus.NOT_ACTIVATED

            # Проверка привязки к оборудованию
            if self.current_license.get("hardware_id") != self.hardware_id:
                return LicenseStatus.HARDWARE_MISMATCH

            # Проверка срока действия
            expiry_date = datetime.fromisoformat(self.current_license["expiry_date"])
            if datetime.now() > expiry_date:
                return LicenseStatus.EXPIRED

            # Проверка подписи
            signature = self.current_license.get("signature", "")
            license_data_copy = self.current_license.copy()
            license_data_copy.pop("signature", None)

            if not license_crypto.verify_license_signature(license_data_copy, signature):
                return LicenseStatus.INVALID

            # Онлайн проверка (если требуется)
            if force_online_check and not self.current_license.get("offline_activation", False):
                return self._online_license_check()

            # Проверка grace period для онлайн лицензий
            if not self.current_license.get("offline_activation", False):
                last_online_check = self._get_last_online_check()
                if last_online_check:
                    days_offline = (datetime.now() - last_online_check).days
                    if days_offline > self.grace_period_days:
                        # Попытка онлайн проверки
                        online_status = self._online_license_check()
                        if online_status == LicenseStatus.NETWORK_ERROR:
                            # Если нет сети, но grace period истек
                            return LicenseStatus.EXPIRED
                        return online_status

            return LicenseStatus.VALID

        except Exception as e:
            self.logger.error(f"Error checking license: {e}")
            return LicenseStatus.INVALID

    def _online_license_check(self) -> LicenseStatus:
        """Онлайн проверка лицензии"""
        try:
            response = requests.post(
                f"{self.activation_server}/api/v1/verify",
                json={
                    "license_key": self.current_license["license_key"],
                    "hardware_id": self.hardware_id,
                },
                timeout=10,
            )

            if response.status_code == 200:
                # Обновление времени последней проверки
                self._update_last_online_check()
                return LicenseStatus.VALID
            elif response.status_code == 404:
                return LicenseStatus.INVALID
            else:
                return LicenseStatus.INVALID

        except requests.exceptions.RequestException:
            return LicenseStatus.NETWORK_ERROR

    def get_license_info(self) -> Dict[str, Any]:
        """
        Получение информации о лицензии

        Returns:
            Информация о лицензии
        """
        if not self.current_license:
            return {"status": "not_activated", "message": "Лицензия не активирована"}

        status = self.check_license()

        info = {
            "status": status.value,
            "license_key": self.current_license.get("license_key", ""),
            "license_type": self.current_license.get("license_type", ""),
            "expiry_date": self.current_license.get("expiry_date", ""),
            "hardware_id": self.hardware_id,
            "features": self.current_license.get("features", {}),
            "offline_activation": self.current_license.get("offline_activation", False),
        }

        # Добавление дополнительной информации в зависимости от статуса
        if status == LicenseStatus.VALID:
            expiry_date = datetime.fromisoformat(self.current_license["expiry_date"])
            days_remaining = (expiry_date - datetime.now()).days
            info["days_remaining"] = max(0, days_remaining)
            info["message"] = f"Лицензия действительна. Осталось дней: {days_remaining}"

        elif status == LicenseStatus.EXPIRED:
            info["message"] = "Лицензия истекла"

        elif status == LicenseStatus.HARDWARE_MISMATCH:
            info["message"] = "Лицензия привязана к другому оборудованию"

        elif status == LicenseStatus.INVALID:
            info["message"] = "Лицензия недействительна"

        elif status == LicenseStatus.NETWORK_ERROR:
            info["message"] = "Ошибка проверки лицензии (нет сети)"

        return info

    def is_feature_enabled(self, feature: str) -> bool:
        """
        Проверка доступности функции

        Args:
            feature: Название функции

        Returns:
            True если функция доступна
        """
        if self.check_license() != LicenseStatus.VALID:
            return False

        features = self.current_license.get("features", {})
        return features.get(feature, False)

    def get_feature_limit(self, feature: str) -> Optional[int]:
        """
        Получение лимита для функции

        Args:
            feature: Название функции

        Returns:
            Лимит функции или None если нет лимита
        """
        if self.check_license() != LicenseStatus.VALID:
            return 0

        features = self.current_license.get("features", {})
        return features.get(feature)

    def deactivate_license(self) -> bool:
        """
        Деактивация лицензии

        Returns:
            True если успешно деактивирована
        """
        try:
            # Удаление файлов лицензии
            if self.license_file.exists():
                self.license_file.unlink()

            if self.cache_file.exists():
                self.cache_file.unlink()

            self.current_license = None

            self.logger.info("License deactivated successfully")
            return True

        except Exception as e:
            self.logger.error(f"Error deactivating license: {e}")
            return False

    def _save_license_data(self, license_data: Dict[str, Any]):
        """Сохранение данных лицензии"""
        try:
            # Шифрование данных
            encrypted_data = license_crypto.encrypt_license_data(license_data)

            # Сохранение в файл
            with open(self.license_file, "w") as f:
                f.write(encrypted_data)

            self.logger.info("License data saved successfully")

        except Exception as e:
            self.logger.error(f"Error saving license data: {e}")
            raise

    def _load_license(self):
        """Загрузка лицензии из файла"""
        try:
            if not self.license_file.exists():
                return

            with open(self.license_file, "r") as f:
                encrypted_data = f.read()

            # Расшифровка данных
            license_data = license_crypto.decrypt_license_data(encrypted_data)
            self.current_license = license_data

            self.logger.info("License loaded successfully")

        except Exception as e:
            self.logger.error(f"Error loading license: {e}")
            # Удаление поврежденного файла лицензии
            if self.license_file.exists():
                self.license_file.unlink()

    def _get_last_online_check(self) -> Optional[datetime]:
        """Получение времени последней онлайн проверки"""
        try:
            if not self.cache_file.exists():
                return None

            with open(self.cache_file, "r") as f:
                cache_data = json.load(f)

            last_check_str = cache_data.get("last_online_check")
            if last_check_str:
                return datetime.fromisoformat(last_check_str)

            return None

        except Exception:
            return None

    def _update_last_online_check(self):
        """Обновление времени последней онлайн проверки"""
        try:
            cache_data = {"last_online_check": datetime.now().isoformat()}

            with open(self.cache_file, "w") as f:
                json.dump(cache_data, f)

        except Exception as e:
            self.logger.error(f"Error updating last online check: {e}")

    def generate_trial_key(self) -> str:
        """
        Генерация trial ключа

        Returns:
            Trial лицензионный ключ
        """
        return license_crypto.generate_license_key("MOBS-TRIAL")

    def get_hardware_info(self) -> Dict[str, Any]:
        """
        Получение информации об оборудовании

        Returns:
            Информация об оборудовании
        """
        return {
            "hardware_id": self.hardware_id,
            "system_info": hardware_id_generator.get_system_info(),
        }


# Глобальный экземпляр для использования в приложении
license_manager = LicenseManager()
