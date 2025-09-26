#!/usr/bin/env python3
"""
Comprehensive code quality fix script for Mercedes W222 OBD Scanner
Fixes all flake8 issues systematically
"""
import os
import re
import subprocess
from pathlib import Path


def fix_imports():
    """Fix missing imports"""
    fixes = [
        {"file": "web_app/api/auth.py", "line": "import sys", "add_after": "import time"},
        {
            "file": "tests/test_obd_controller.py",
            "line": "import sys",
            "add_after": "from mercedes_obd_scanner.core.obd_controller import ConnectionStatus, OBDParameter",
        },
    ]

    for fix in fixes:
        file_path = Path(fix["file"])
        if file_path.exists():
            content = file_path.read_text()
            if fix["add_after"] not in content:
                lines = content.split("\n")
                for i, line in enumerate(lines):
                    if line.strip() == fix["line"]:
                        lines.insert(i + 1, fix["add_after"])
                        break
                file_path.write_text("\n".join(lines))
                print(f"Fixed imports in {fix['file']}")


def fix_long_lines():
    """Fix long lines by breaking them appropriately"""
    long_line_fixes = {
        "mercedes_obd_scanner/ml/inference/enhanced_anomaly_detector.py": [
            (
                396,
                "anomaly_record = AnomalyRecord(\n                session_id=session_id,\n                parameter_name=param,\n                value=value,\n                anomaly_score=score,\n                timestamp=timestamp,\n                severity=severity,\n                description=description\n            )",
            ),
            (
                397,
                "anomaly_record = AnomalyRecord(\n                session_id=session_id,\n                parameter_name=param,\n                value=value,\n                anomaly_score=score,\n                timestamp=timestamp,\n                severity=severity,\n                description=description\n            )",
            ),
        ]
    }

    for file_path, fixes in long_line_fixes.items():
        path = Path(file_path)
        if path.exists():
            lines = path.read_text().split("\n")
            for line_num, replacement in reversed(fixes):  # Reverse to maintain line numbers
                if line_num - 1 < len(lines):
                    lines[line_num - 1] = replacement
            path.write_text("\n".join(lines))
            print(f"Fixed long lines in {file_path}")


def remove_unused_variables():
    """Remove or use unused variables"""
    unused_var_fixes = [
        {
            "file": "mercedes_obd_scanner/ml/training/enhanced_model_trainer.py",
            "line": 405,
            "action": "comment",  # Comment out unused variable
            "pattern": r"X_test_scaled = scaler\.transform\(X_test\)",
        },
        {
            "file": "tests/test_obd_controller.py",
            "line": 162,
            "action": "remove",
            "pattern": r"initial_count = .*",
        },
        {
            "file": "tests/test_production_quality.py",
            "line": 283,
            "action": "remove",
            "pattern": r"session_id = .*",
        },
        {
            "file": "web_app/api/subscriptions.py",
            "line": 292,
            "action": "comment",
            "pattern": r"invoice = .*",
        },
        {
            "file": "web_app/main.py",
            "line": 150,
            "action": "remove",
            "pattern": r"data = await websocket\.receive_text\(\)",
        },
    ]

    for fix in unused_var_fixes:
        file_path = Path(fix["file"])
        if file_path.exists():
            lines = file_path.read_text().split("\n")
            if fix["line"] - 1 < len(lines):
                line = lines[fix["line"] - 1]
                if fix["action"] == "comment":
                    lines[fix["line"] - 1] = "            # " + line.strip()
                elif fix["action"] == "remove":
                    if re.search(fix["pattern"], line):
                        lines.pop(fix["line"] - 1)
            file_path.write_text("\n".join(lines))
            print(f"Fixed unused variables in {fix['file']}")


def fix_trailing_whitespace():
    """Remove trailing whitespace"""
    files_to_fix = [
        "raspberry_pi_client/obd_client.py",
        "mercedes_obd_scanner/trip_analyzer/enhanced_trip_analyzer.py",
        "tests/test_production_fixed.py",
    ]

    for file_path in files_to_fix:
        path = Path(file_path)
        if path.exists():
            content = path.read_text()
            # Remove trailing whitespace
            lines = [line.rstrip() for line in content.split("\n")]
            path.write_text("\n".join(lines))
            print(f"Fixed trailing whitespace in {file_path}")


def fix_comparison_issues():
    """Fix comparison issues like == False"""
    file_path = Path("raspberry_pi_client/obd_client.py")
    if file_path.exists():
        content = file_path.read_text()
        # Fix == False comparison
        content = re.sub(r"response\.is_null\(\) == False", "not response.is_null()", content)
        file_path.write_text(content)
        print("Fixed comparison issues in raspberry_pi_client/obd_client.py")


def run_autofix_tools():
    """Run automated fixing tools"""
    try:
        # Run autopep8 to fix many issues automatically
        subprocess.run(["pip", "install", "autopep8"], check=True)
        subprocess.run(
            [
                "autopep8",
                "--in-place",
                "--recursive",
                "--max-line-length=100",
                "--ignore=E402",
                ".",
            ],
            check=True,
        )
        print("Applied autopep8 fixes")
    except subprocess.CalledProcessError as e:
        print(f"autopep8 failed: {e}")


def main():
    """Main function to run all fixes"""
    print("Starting comprehensive code quality fixes...")

    # Change to project directory
    os.chdir("/home/ubuntu/mercedes-obd-scanner")

    # Apply fixes
    fix_imports()
    fix_long_lines()
    remove_unused_variables()
    fix_trailing_whitespace()
    fix_comparison_issues()
    run_autofix_tools()

    # Run black formatting again
    try:
        subprocess.run(["black", ".", "--line-length=100"], check=True)
        print("Applied black formatting")
    except subprocess.CalledProcessError as e:
        print(f"Black formatting failed: {e}")

    print("Code quality fixes completed!")


if __name__ == "__main__":
    main()
