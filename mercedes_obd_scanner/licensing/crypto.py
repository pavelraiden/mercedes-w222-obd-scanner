"""
Система шифрования для Mercedes OBD Scanner
"""

import base64
import json
import hashlib
import secrets
from datetime import datetime
from typing import Dict, Any, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging


class LicenseCrypto:
    """Класс для шифрования и расшифровки лицензионных данных"""

    def __init__(self, master_key: str = None):
        """
        Инициализация системы шифрования

        Args:
            master_key: Мастер-ключ для шифрования (если не указан, используется встроенный)
        """
        self.logger = logging.getLogger(__name__)

        # В реальном приложении этот ключ должен быть скрыт/обфусцирован
        self.master_key = master_key or "Mercedes_OBD_Scanner_2024_Secret_Key_v1.0"

        # Соль для генерации ключей
        self.salt = b"mercedes_obd_salt_2024"

        # Генерация ключа шифрования
        self.encryption_key = self._derive_key(self.master_key, self.salt)
        self.fernet = Fernet(self.encryption_key)

    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """
        Генерация ключа шифрования из пароля

        Args:
            password: Пароль для генерации ключа
            salt: Соль для усиления безопасности

        Returns:
            Ключ шифрования
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key

    def encrypt_license_data(self, license_data: Dict[str, Any]) -> str:
        """
        Шифрование данных лицензии

        Args:
            license_data: Данные лицензии для шифрования

        Returns:
            Зашифрованная строка в base64
        """
        try:
            # Добавление метаданных
            license_data["encrypted_at"] = datetime.now().isoformat()
            license_data["version"] = "1.0"

            # Сериализация в JSON
            json_data = json.dumps(license_data, sort_keys=True)

            # Шифрование
            encrypted_data = self.fernet.encrypt(json_data.encode())

            # Кодирование в base64 для удобства хранения
            encoded_data = base64.b64encode(encrypted_data).decode()

            self.logger.info("License data encrypted successfully")
            return encoded_data

        except Exception as e:
            self.logger.error(f"Error encrypting license data: {e}")
            raise

    def decrypt_license_data(self, encrypted_data: str) -> Dict[str, Any]:
        """
        Расшифровка данных лицензии

        Args:
            encrypted_data: Зашифрованная строка в base64

        Returns:
            Расшифрованные данные лицензии
        """
        try:
            # Декодирование из base64
            decoded_data = base64.b64decode(encrypted_data.encode())

            # Расшифровка
            decrypted_data = self.fernet.decrypt(decoded_data)

            # Десериализация из JSON
            license_data = json.loads(decrypted_data.decode())

            self.logger.info("License data decrypted successfully")
            return license_data

        except Exception as e:
            self.logger.error(f"Error decrypting license data: {e}")
            raise

    def generate_license_key(self, prefix: str = "MOBS") -> str:
        """
        Генерация лицензионного ключа

        Args:
            prefix: Префикс для ключа

        Returns:
            Лицензионный ключ в формате XXXX-XXXX-XXXX-XXXX
        """
        try:
            # Генерация случайных данных
            random_data = secrets.token_hex(8)

            # Создание контрольной суммы
            checksum = hashlib.sha256(random_data.encode()).hexdigest()[:8]

            # Формирование ключа
            key_parts = [
                prefix,
                random_data[:4].upper(),
                random_data[4:8].upper(),
                checksum.upper(),
            ]

            license_key = "-".join(key_parts)

            self.logger.info(f"Generated license key: {license_key}")
            return license_key

        except Exception as e:
            self.logger.error(f"Error generating license key: {e}")
            raise

    def validate_license_key_format(self, license_key: str) -> bool:
        """
        Проверка формата лицензионного ключа

        Args:
            license_key: Лицензионный ключ для проверки

        Returns:
            True если формат корректен
        """
        try:
            # Проверка базового формата
            if not license_key or len(license_key) != 19:  # XXXX-XXXX-XXXX-XXXX
                return False

            parts = license_key.split("-")
            if len(parts) != 4:
                return False

            # Проверка длины частей
            if not all(len(part) == 4 for part in parts):
                return False

            # Проверка что все символы - буквы или цифры
            clean_key = license_key.replace("-", "")
            if not clean_key.isalnum():
                return False

            # Проверка контрольной суммы
            prefix, part1, part2, checksum = parts
            random_data = (part1 + part2).lower()
            expected_checksum = hashlib.sha256(random_data.encode()).hexdigest()[:8].upper()

            return checksum == expected_checksum

        except Exception as e:
            self.logger.error(f"Error validating license key format: {e}")
            return False

    def create_license_signature(self, license_data: Dict[str, Any]) -> str:
        """
        Создание цифровой подписи для лицензии

        Args:
            license_data: Данные лицензии

        Returns:
            Цифровая подпись
        """
        try:
            # Создание строки для подписи
            signature_data = {
                "license_key": license_data.get("license_key"),
                "hardware_id": license_data.get("hardware_id"),
                "expiry_date": license_data.get("expiry_date"),
                "license_type": license_data.get("license_type"),
            }

            # Сортировка ключей для консистентности
            signature_string = json.dumps(signature_data, sort_keys=True)

            # Создание подписи
            signature = hashlib.sha256((signature_string + self.master_key).encode()).hexdigest()

            return signature

        except Exception as e:
            self.logger.error(f"Error creating license signature: {e}")
            raise

    def verify_license_signature(self, license_data: Dict[str, Any], signature: str) -> bool:
        """
        Проверка цифровой подписи лицензии

        Args:
            license_data: Данные лицензии
            signature: Подпись для проверки

        Returns:
            True если подпись корректна
        """
        try:
            expected_signature = self.create_license_signature(license_data)
            return signature == expected_signature

        except Exception as e:
            self.logger.error(f"Error verifying license signature: {e}")
            return False

    def obfuscate_string(self, text: str) -> str:
        """
        Простая обфускация строки

        Args:
            text: Текст для обфускации

        Returns:
            Обфусцированный текст
        """
        try:
            # Простое XOR шифрование с ключом
            key = 0x5A  # Простой ключ
            obfuscated = "".join(chr(ord(char) ^ key) for char in text)
            return base64.b64encode(obfuscated.encode()).decode()

        except Exception as e:
            self.logger.error(f"Error obfuscating string: {e}")
            return text

    def deobfuscate_string(self, obfuscated_text: str) -> str:
        """
        Деобфускация строки

        Args:
            obfuscated_text: Обфусцированный текст

        Returns:
            Оригинальный текст
        """
        try:
            # Декодирование из base64
            decoded = base64.b64decode(obfuscated_text.encode()).decode()

            # Обратное XOR
            key = 0x5A
            original = "".join(chr(ord(char) ^ key) for char in decoded)
            return original

        except Exception as e:
            self.logger.error(f"Error deobfuscating string: {e}")
            return obfuscated_text

    def generate_activation_token(self, license_key: str, hardware_id: str) -> str:
        """
        Генерация токена активации

        Args:
            license_key: Лицензионный ключ
            hardware_id: ID оборудования

        Returns:
            Токен активации
        """
        try:
            # Создание данных для токена
            token_data = {
                "license_key": license_key,
                "hardware_id": hardware_id,
                "timestamp": datetime.now().isoformat(),
            }

            # Шифрование токена
            token_json = json.dumps(token_data, sort_keys=True)
            encrypted_token = self.fernet.encrypt(token_json.encode())

            # Кодирование в base64
            activation_token = base64.b64encode(encrypted_token).decode()

            return activation_token

        except Exception as e:
            self.logger.error(f"Error generating activation token: {e}")
            raise

    def verify_activation_token(self, activation_token: str) -> Optional[Dict[str, Any]]:
        """
        Проверка токена активации

        Args:
            activation_token: Токен активации

        Returns:
            Данные токена если корректен, иначе None
        """
        try:
            # Декодирование из base64
            encrypted_token = base64.b64decode(activation_token.encode())

            # Расшифровка
            decrypted_token = self.fernet.decrypt(encrypted_token)

            # Десериализация
            token_data = json.loads(decrypted_token.decode())

            return token_data

        except Exception as e:
            self.logger.error(f"Error verifying activation token: {e}")
            return None


# Глобальный экземпляр для использования в приложении
license_crypto = LicenseCrypto()
