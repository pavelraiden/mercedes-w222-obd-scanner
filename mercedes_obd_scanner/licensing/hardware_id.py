"""
Система генерации Hardware ID для Mercedes OBD Scanner
"""
import hashlib
import platform
import psutil
import uuid
import subprocess
import logging
from typing import Optional


class HardwareIDGenerator:
    """Генератор уникального идентификатора оборудования"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def generate_hardware_id(self) -> str:
        """
        Генерация уникального Hardware ID на основе характеристик системы
        
        Returns:
            Уникальный идентификатор оборудования
        """
        try:
            # Сбор информации о системе
            components = []
            
            # MAC адрес сетевой карты
            mac_address = self._get_mac_address()
            if mac_address:
                components.append(f"mac:{mac_address}")
                
            # Серийный номер материнской платы
            motherboard_serial = self._get_motherboard_serial()
            if motherboard_serial:
                components.append(f"mb:{motherboard_serial}")
                
            # Серийный номер диска
            disk_serial = self._get_disk_serial()
            if disk_serial:
                components.append(f"disk:{disk_serial}")
                
            # CPU информация
            cpu_info = self._get_cpu_info()
            if cpu_info:
                components.append(f"cpu:{cpu_info}")
                
            # Объем RAM
            ram_size = self._get_ram_size()
            if ram_size:
                components.append(f"ram:{ram_size}")
                
            # Если не удалось получить достаточно информации, используем fallback
            if len(components) < 2:
                components.append(f"fallback:{platform.node()}")
                components.append(f"uuid:{uuid.getnode()}")
                
            # Создание хеша
            combined_info = "|".join(sorted(components))
            hardware_id = hashlib.sha256(combined_info.encode()).hexdigest()[:32]
            
            self.logger.info(f"Generated Hardware ID: {hardware_id}")
            return hardware_id
            
        except Exception as e:
            self.logger.error(f"Error generating hardware ID: {e}")
            # Fallback к простому методу
            return self._generate_fallback_id()
            
    def _get_mac_address(self) -> Optional[str]:
        """Получение MAC адреса основной сетевой карты"""
        try:
            # Получение MAC адреса первого активного интерфейса
            for interface, addrs in psutil.net_if_addrs().items():
                if interface.startswith(('eth', 'en', 'wlan', 'wi')):
                    for addr in addrs:
                        if addr.family == psutil.AF_LINK:
                            mac = addr.address.replace(':', '').replace('-', '').upper()
                            if mac and mac != '000000000000':
                                return mac
            return None
        except Exception:
            return None
            
    def _get_motherboard_serial(self) -> Optional[str]:
        """Получение серийного номера материнской платы"""
        try:
            if platform.system() == "Windows":
                result = subprocess.run(
                    ['wmic', 'baseboard', 'get', 'serialnumber'],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    if len(lines) > 1:
                        serial = lines[1].strip()
                        if serial and serial.lower() not in ['to be filled by o.e.m.', 'not specified']:
                            return serial
                            
            elif platform.system() == "Linux":
                try:
                    with open('/sys/class/dmi/id/board_serial', 'r') as f:
                        serial = f.read().strip()
                        if serial and serial.lower() not in ['to be filled by o.e.m.', 'not specified']:
                            return serial
                except:
                    pass
                    
            elif platform.system() == "Darwin":  # macOS
                result = subprocess.run(
                    ['system_profiler', 'SPHardwareDataType'],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if 'Serial Number' in line:
                            serial = line.split(':')[-1].strip()
                            if serial:
                                return serial
                                
            return None
        except Exception:
            return None
            
    def _get_disk_serial(self) -> Optional[str]:
        """Получение серийного номера основного диска"""
        try:
            if platform.system() == "Windows":
                result = subprocess.run(
                    ['wmic', 'diskdrive', 'get', 'serialnumber'],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    for line in lines[1:]:
                        serial = line.strip()
                        if serial and len(serial) > 5:
                            return serial
                            
            elif platform.system() == "Linux":
                # Попытка получить серийный номер через lsblk
                result = subprocess.run(
                    ['lsblk', '-o', 'NAME,SERIAL', '-n'],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        parts = line.strip().split()
                        if len(parts) >= 2 and not parts[0].startswith('loop'):
                            serial = parts[1]
                            if serial and len(serial) > 5:
                                return serial
                                
            elif platform.system() == "Darwin":  # macOS
                result = subprocess.run(
                    ['system_profiler', 'SPSerialATADataType'],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if 'Serial Number' in line:
                            serial = line.split(':')[-1].strip()
                            if serial and len(serial) > 5:
                                return serial
                                
            return None
        except Exception:
            return None
            
    def _get_cpu_info(self) -> Optional[str]:
        """Получение информации о процессоре"""
        try:
            if platform.system() == "Windows":
                result = subprocess.run(
                    ['wmic', 'cpu', 'get', 'processorid'],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    if len(lines) > 1:
                        cpu_id = lines[1].strip()
                        if cpu_id:
                            return cpu_id
                            
            elif platform.system() == "Linux":
                try:
                    with open('/proc/cpuinfo', 'r') as f:
                        for line in f:
                            if line.startswith('processor'):
                                # Используем модель процессора как идентификатор
                                continue
                            elif line.startswith('model name'):
                                model = line.split(':')[1].strip()
                                return hashlib.md5(model.encode()).hexdigest()[:16]
                except:
                    pass
                    
            # Fallback - используем количество ядер и архитектуру
            cpu_count = psutil.cpu_count()
            cpu_arch = platform.machine()
            return f"{cpu_arch}_{cpu_count}"
            
        except Exception:
            return None
            
    def _get_ram_size(self) -> Optional[str]:
        """Получение размера оперативной памяти"""
        try:
            # Получаем размер RAM в GB (округленно)
            ram_bytes = psutil.virtual_memory().total
            ram_gb = round(ram_bytes / (1024**3))
            return str(ram_gb)
        except Exception:
            return None
            
    def _generate_fallback_id(self) -> str:
        """Генерация fallback Hardware ID"""
        try:
            # Используем базовую информацию о системе
            fallback_info = [
                platform.system(),
                platform.machine(),
                platform.node(),
                str(uuid.getnode()),
                str(psutil.cpu_count()),
                str(round(psutil.virtual_memory().total / (1024**3)))
            ]
            
            combined = "|".join(fallback_info)
            return hashlib.sha256(combined.encode()).hexdigest()[:32]
            
        except Exception:
            # Последний fallback
            return hashlib.sha256(f"fallback_{uuid.uuid4()}".encode()).hexdigest()[:32]
            
    def validate_hardware_id(self, stored_id: str) -> bool:
        """
        Проверка соответствия сохраненного Hardware ID текущему
        
        Args:
            stored_id: Сохраненный Hardware ID
            
        Returns:
            True если ID совпадают
        """
        try:
            current_id = self.generate_hardware_id()
            return current_id == stored_id
        except Exception as e:
            self.logger.error(f"Error validating hardware ID: {e}")
            return False
            
    def get_system_info(self) -> dict:
        """
        Получение информации о системе для отладки
        
        Returns:
            Словарь с информацией о системе
        """
        try:
            return {
                'platform': platform.system(),
                'machine': platform.machine(),
                'processor': platform.processor(),
                'node': platform.node(),
                'mac_address': self._get_mac_address(),
                'motherboard_serial': self._get_motherboard_serial(),
                'disk_serial': self._get_disk_serial(),
                'cpu_info': self._get_cpu_info(),
                'ram_size': self._get_ram_size(),
                'cpu_count': psutil.cpu_count(),
                'total_ram_gb': round(psutil.virtual_memory().total / (1024**3))
            }
        except Exception as e:
            self.logger.error(f"Error getting system info: {e}")
            return {}


# Глобальный экземпляр для использования в приложении
hardware_id_generator = HardwareIDGenerator()
