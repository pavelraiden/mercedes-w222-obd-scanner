#!/usr/bin/env python3
"""
Mercedes W222 OBD Scanner
Диагностический сканер для Mercedes-Benz W222 (S-класс 2013-2020)
"""

__version__ = "0.1.0"
__author__ = "Manus & Claude AI"
__description__ = "OBD-II diagnostic scanner for Mercedes W222"

from .core.config_manager import ConfigManager, config_manager
from .core.obd_controller import OBDController
from .gui.main_window import MercedesOBDScanner

__all__ = [
    "ConfigManager",
    "config_manager", 
    "OBDController",
    "MercedesOBDScanner"
]
