#!/usr/bin/env python3
"""
Setup script для Mercedes W222 OBD Scanner
"""

from setuptools import setup, find_packages
from pathlib import Path

# Читаем README файл
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding='utf-8') if (this_directory / "README.md").exists() else ""

# Читаем requirements
requirements = []
requirements_file = this_directory / "requirements.txt"
if requirements_file.exists():
    with open(requirements_file, 'r', encoding='utf-8') as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

setup(
    name="mercedes-obd-scanner",
    version="0.1.0",
    author="Manus & Claude AI",
    author_email="support@manus.im",
    description="OBD-II diagnostic scanner for Mercedes-Benz W222 (S-Class 2013-2020)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/username/mercedes-obd-scanner",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "Topic :: System :: Hardware :: Hardware Drivers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "flake8>=5.0.0",
            "mypy>=0.991",
        ],
        "serial": [
            "pyserial>=3.5",
        ],
    },
    entry_points={
        "console_scripts": [
            "mercedes-obd=mercedes_obd_scanner.gui.main_window:main",
            "mercedes-obd-demo=mercedes_obd_scanner.gui.main_window:main",
        ],
    },
    include_package_data=True,
    package_data={
        "mercedes_obd_scanner": [
            "configs/*.yaml",
            "configs/petrol/*/*.yaml",
            "configs/diesel/*/*.yaml",
        ],
    },
    zip_safe=False,
    keywords="mercedes obd obd2 diagnostic scanner w222 s-class automotive",
    project_urls={
        "Bug Reports": "https://github.com/username/mercedes-obd-scanner/issues",
        "Source": "https://github.com/username/mercedes-obd-scanner",
        "Documentation": "https://github.com/username/mercedes-obd-scanner/wiki",
    },
)
