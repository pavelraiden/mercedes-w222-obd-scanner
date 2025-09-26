"""
Менеджер обновлений для Mercedes OBD Scanner
"""

import os
import json
import shutil
import zipfile
import hashlib
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, Callable
from enum import Enum
import logging

from ..licensing import license_manager, LicenseStatus


class UpdateStatus(Enum):
    """Статусы обновления"""

    CHECKING = "checking"
    AVAILABLE = "available"
    DOWNLOADING = "downloading"
    INSTALLING = "installing"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_UPDATES = "no_updates"


class UpdateManager:
    """Менеджер автоматических обновлений"""

    def __init__(
        self,
        current_version: str = "1.0.0",
        update_server: str = None,
        progress_callback: Callable = None,
        status_callback: Callable = None,
    ):
        """
        Инициализация менеджера обновлений

        Args:
            current_version: Текущая версия приложения
            update_server: URL сервера обновлений
            progress_callback: Callback для отображения прогресса
            status_callback: Callback для изменения статуса
        """
        self.logger = logging.getLogger(__name__)

        # Настройки
        self.current_version = current_version
        self.update_server = update_server or "https://api.mercedes-obd-scanner.com"
        self.progress_callback = progress_callback or (lambda x: None)
        self.status_callback = status_callback or (lambda x: None)

        # Директории
        self.app_dir = Path.cwd()
        self.temp_dir = Path.home() / ".mercedes_obd_scanner" / "temp"
        self.backup_dir = Path.home() / ".mercedes_obd_scanner" / "backup"
        self.update_cache_file = Path.home() / ".mercedes_obd_scanner" / "update_cache.json"

        # Создание директорий
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Настройки
        self.check_interval_hours = 24  # Проверка обновлений раз в сутки
        self.auto_download = True  # Автоматическая загрузка обновлений
        self.auto_install = False  # Ручная установка по умолчанию

        # Текущее состояние
        self.current_status = UpdateStatus.NO_UPDATES
        self.latest_version_info: Optional[Dict[str, Any]] = None

    def check_for_updates(self, force: bool = False) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Проверка наличия обновлений

        Args:
            force: Принудительная проверка (игнорировать кэш)

        Returns:
            Tuple (есть_обновления, информация_о_версии)
        """
        try:
            self.status_callback(UpdateStatus.CHECKING)

            # Проверка лицензии
            license_status = license_manager.check_license()
            if license_status != LicenseStatus.VALID:
                self.logger.warning("License invalid, skipping update check")
                return False, None

            # Проверка кэша (если не принудительная проверка)
            if not force:
                cached_info = self._get_cached_update_info()
                if cached_info and self._is_cache_valid(cached_info):
                    if self._compare_versions(cached_info["version"], self.current_version) > 0:
                        self.latest_version_info = cached_info
                        self.status_callback(UpdateStatus.AVAILABLE)
                        return True, cached_info
                    else:
                        self.status_callback(UpdateStatus.NO_UPDATES)
                        return False, None

            # Запрос к серверу
            license_info = license_manager.get_license_info()
            response = requests.get(
                f"{self.update_server}/api/v1/updates/check",
                params={
                    "current_version": self.current_version,
                    "license_key": license_info.get("license_key", ""),
                    "license_type": license_info.get("license_type", ""),
                    "platform": self._get_platform_info(),
                },
                timeout=30,
            )

            if response.status_code == 200:
                update_info = response.json()

                # Кэширование информации
                self._cache_update_info(update_info)

                if update_info.get("update_available", False):
                    self.latest_version_info = update_info
                    self.status_callback(UpdateStatus.AVAILABLE)
                    return True, update_info
                else:
                    self.status_callback(UpdateStatus.NO_UPDATES)
                    return False, None

            else:
                self.logger.error(f"Update check failed: {response.status_code}")
                self.status_callback(UpdateStatus.FAILED)
                return False, None

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error during update check: {e}")
            self.status_callback(UpdateStatus.FAILED)
            return False, None
        except Exception as e:
            self.logger.error(f"Error checking for updates: {e}")
            self.status_callback(UpdateStatus.FAILED)
            return False, None

    def download_update(self, version_info: Dict[str, Any]) -> Optional[Path]:
        """
        Загрузка обновления

        Args:
            version_info: Информация о версии для загрузки

        Returns:
            Путь к загруженному файлу или None
        """
        try:
            self.status_callback(UpdateStatus.DOWNLOADING)

            download_url = version_info.get("download_url")
            if not download_url:
                self.logger.error("No download URL provided")
                return None

            version = version_info.get("version")
            update_file = self.temp_dir / f"update_{version}.zip"

            # Загрузка с отображением прогресса
            license_info = license_manager.get_license_info()
            response = requests.get(
                download_url,
                params={"license_key": license_info.get("license_key", "")},
                stream=True,
                timeout=300,
            )

            if response.status_code == 200:
                total_size = int(response.headers.get("content-length", 0))
                downloaded_size = 0

                with open(update_file, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)

                            # Отображение прогресса
                            if total_size > 0:
                                progress = (downloaded_size / total_size) * 100
                                self.progress_callback(progress)

                # Проверка контрольной суммы
                expected_checksum = version_info.get("checksum")
                if expected_checksum:
                    if not self._verify_checksum(update_file, expected_checksum):
                        self.logger.error("Checksum verification failed")
                        update_file.unlink()
                        return None

                self.logger.info(f"Update downloaded successfully: {update_file}")
                return update_file

            else:
                self.logger.error(f"Download failed: {response.status_code}")
                return None

        except Exception as e:
            self.logger.error(f"Error downloading update: {e}")
            return None

    def install_update(self, update_file: Path, version_info: Dict[str, Any]) -> bool:
        """
        Установка обновления

        Args:
            update_file: Путь к файлу обновления
            version_info: Информация о версии

        Returns:
            True если установка успешна
        """
        try:
            self.status_callback(UpdateStatus.INSTALLING)

            # Создание резервной копии
            backup_path = self._create_backup()
            if not backup_path:
                self.logger.error("Failed to create backup")
                return False

            try:
                # Распаковка обновления
                with zipfile.ZipFile(update_file, "r") as zip_ref:
                    # Проверка содержимого архива
                    if not self._validate_update_archive(zip_ref, version_info):
                        self.logger.error("Invalid update archive")
                        return False

                    # Извлечение файлов
                    extract_dir = self.temp_dir / "extract"
                    zip_ref.extractall(extract_dir)

                    # Применение обновления
                    if self._apply_update(extract_dir, version_info):
                        self.logger.info("Update installed successfully")
                        self.status_callback(UpdateStatus.COMPLETED)

                        # Очистка временных файлов
                        self._cleanup_temp_files()

                        return True
                    else:
                        self.logger.error("Failed to apply update")
                        self._rollback(backup_path)
                        return False

            except Exception as e:
                self.logger.error(f"Error during installation: {e}")
                self._rollback(backup_path)
                return False

        except Exception as e:
            self.logger.error(f"Error installing update: {e}")
            self.status_callback(UpdateStatus.FAILED)
            return False

    def _create_backup(self) -> Optional[Path]:
        """Создание резервной копии критических файлов"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.backup_dir / f"backup_{self.current_version}_{timestamp}"
            backup_path.mkdir(parents=True, exist_ok=True)

            # Список критических файлов и директорий для резервного копирования
            critical_paths = ["mercedes_obd_scanner", "setup.py", "requirements.txt", "README.md"]

            for path_name in critical_paths:
                source_path = self.app_dir / path_name
                if source_path.exists():
                    if source_path.is_file():
                        shutil.copy2(source_path, backup_path / path_name)
                    else:
                        shutil.copytree(
                            source_path,
                            backup_path / path_name,
                            ignore=shutil.ignore_patterns("*.pyc", "__pycache__", "*.log"),
                        )

            self.logger.info(f"Backup created: {backup_path}")
            return backup_path

        except Exception as e:
            self.logger.error(f"Error creating backup: {e}")
            return None

    def _apply_update(self, extract_dir: Path, version_info: Dict[str, Any]) -> bool:
        """Применение обновления"""
        try:
            # Получение списка файлов для обновления
            update_manifest = extract_dir / "update_manifest.json"
            if update_manifest.exists():
                with open(update_manifest, "r") as f:
                    manifest = json.load(f)

                files_to_update = manifest.get("files", [])
            else:
                # Если нет манифеста, обновляем все файлы
                files_to_update = []
                for root, dirs, files in os.walk(extract_dir):
                    for file in files:
                        rel_path = Path(root).relative_to(extract_dir) / file
                        files_to_update.append(str(rel_path))

            # Применение обновлений
            for file_path in files_to_update:
                source_file = extract_dir / file_path
                target_file = self.app_dir / file_path

                if source_file.exists():
                    # Создание директории если не существует
                    target_file.parent.mkdir(parents=True, exist_ok=True)

                    # Копирование файла
                    shutil.copy2(source_file, target_file)

            # Обновление версии
            self._update_version_info(version_info)

            return True

        except Exception as e:
            self.logger.error(f"Error applying update: {e}")
            return False

    def _rollback(self, backup_path: Path) -> bool:
        """Откат к резервной копии"""
        try:
            self.logger.info(f"Rolling back to backup: {backup_path}")

            # Восстановление файлов из резервной копии
            for item in backup_path.iterdir():
                target_path = self.app_dir / item.name

                if target_path.exists():
                    if target_path.is_file():
                        target_path.unlink()
                    else:
                        shutil.rmtree(target_path)

                if item.is_file():
                    shutil.copy2(item, target_path)
                else:
                    shutil.copytree(item, target_path)

            self.logger.info("Rollback completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Error during rollback: {e}")
            return False

    def _verify_checksum(self, file_path: Path, expected_checksum: str) -> bool:
        """Проверка контрольной суммы файла"""
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)

            actual_checksum = sha256_hash.hexdigest()
            return actual_checksum == expected_checksum

        except Exception as e:
            self.logger.error(f"Error verifying checksum: {e}")
            return False

    def _validate_update_archive(
        self, zip_ref: zipfile.ZipFile, version_info: Dict[str, Any]
    ) -> bool:
        """Проверка архива обновления"""
        try:
            # Базовая проверка структуры архива
            file_list = zip_ref.namelist()

            # Проверка наличия критических файлов
            required_files = version_info.get("required_files", [])
            for required_file in required_files:
                if required_file not in file_list:
                    self.logger.error(f"Required file missing: {required_file}")
                    return False

            return True

        except Exception as e:
            self.logger.error(f"Error validating update archive: {e}")
            return False

    def _compare_versions(self, version1: str, version2: str) -> int:
        """
        Сравнение версий

        Returns:
            1 если version1 > version2
            0 если version1 == version2
            -1 если version1 < version2
        """
        try:
            v1_parts = [int(x) for x in version1.split(".")]
            v2_parts = [int(x) for x in version2.split(".")]

            # Выравнивание длины
            max_len = max(len(v1_parts), len(v2_parts))
            v1_parts.extend([0] * (max_len - len(v1_parts)))
            v2_parts.extend([0] * (max_len - len(v2_parts)))

            for v1, v2 in zip(v1_parts, v2_parts):
                if v1 > v2:
                    return 1
                elif v1 < v2:
                    return -1

            return 0

        except Exception:
            return 0

    def _get_platform_info(self) -> str:
        """Получение информации о платформе"""
        import platform

        return f"{platform.system()}_{platform.machine()}"

    def _cache_update_info(self, update_info: Dict[str, Any]):
        """Кэширование информации об обновлениях"""
        try:
            cache_data = {"timestamp": datetime.now().isoformat(), "update_info": update_info}

            with open(self.update_cache_file, "w") as f:
                json.dump(cache_data, f)

        except Exception as e:
            self.logger.error(f"Error caching update info: {e}")

    def _get_cached_update_info(self) -> Optional[Dict[str, Any]]:
        """Получение кэшированной информации об обновлениях"""
        try:
            if not self.update_cache_file.exists():
                return None

            with open(self.update_cache_file, "r") as f:
                cache_data = json.load(f)

            return cache_data.get("update_info")

        except Exception:
            return None

    def _is_cache_valid(self, cached_info: Dict[str, Any]) -> bool:
        """Проверка валидности кэша"""
        try:
            if not self.update_cache_file.exists():
                return False

            with open(self.update_cache_file, "r") as f:
                cache_data = json.load(f)

            timestamp_str = cache_data.get("timestamp")
            if not timestamp_str:
                return False

            cache_time = datetime.fromisoformat(timestamp_str)
            hours_passed = (datetime.now() - cache_time).total_seconds() / 3600

            return hours_passed < self.check_interval_hours

        except Exception:
            return False

    def _update_version_info(self, version_info: Dict[str, Any]):
        """Обновление информации о версии"""
        try:
            # Обновление текущей версии
            self.current_version = version_info.get("version", self.current_version)

            # Можно также обновить файл с версией приложения
            version_file = self.app_dir / "VERSION"
            with open(version_file, "w") as f:
                f.write(self.current_version)

        except Exception as e:
            self.logger.error(f"Error updating version info: {e}")

    def _cleanup_temp_files(self):
        """Очистка временных файлов"""
        try:
            for item in self.temp_dir.iterdir():
                if item.is_file():
                    item.unlink()
                else:
                    shutil.rmtree(item)

        except Exception as e:
            self.logger.error(f"Error cleaning up temp files: {e}")

    def get_update_status(self) -> Dict[str, Any]:
        """
        Получение статуса обновлений

        Returns:
            Информация о статусе обновлений
        """
        return {
            "current_version": self.current_version,
            "status": self.current_status.value,
            "latest_version_info": self.latest_version_info,
            "auto_download": self.auto_download,
            "auto_install": self.auto_install,
        }

    def set_auto_update_settings(self, auto_download: bool = None, auto_install: bool = None):
        """
        Настройка автоматических обновлений

        Args:
            auto_download: Автоматическая загрузка
            auto_install: Автоматическая установка
        """
        if auto_download is not None:
            self.auto_download = auto_download

        if auto_install is not None:
            self.auto_install = auto_install


# Глобальный экземпляр для использования в приложении
update_manager = UpdateManager()
