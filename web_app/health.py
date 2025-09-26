"""
Health Check and Monitoring Endpoints for Mercedes W222 OBD Scanner
"""

import os
import psutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

# Import application components
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mercedes_obd_scanner.data.database_manager import DatabaseManager

router = APIRouter()


def get_system_info() -> Dict[str, Any]:
    """Get system information for health monitoring"""
    try:
        # CPU and Memory info
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        # Process info
        process = psutil.Process()
        process_memory = process.memory_info()

        return {
            "system": {
                "cpu_percent": cpu_percent,
                "memory_total": memory.total,
                "memory_available": memory.available,
                "memory_percent": memory.percent,
                "disk_total": disk.total,
                "disk_free": disk.free,
                "disk_percent": (disk.used / disk.total) * 100,
            },
            "process": {
                "pid": process.pid,
                "memory_rss": process_memory.rss,
                "memory_vms": process_memory.vms,
                "cpu_percent": process.cpu_percent(),
                "num_threads": process.num_threads(),
                "create_time": datetime.fromtimestamp(process.create_time()).isoformat(),
            },
        }
    except Exception as e:
        return {"error": f"Failed to get system info: {str(e)}"}


def check_database_health() -> Dict[str, Any]:
    """Check database connectivity and basic stats"""
    try:
        db_manager = DatabaseManager()
        stats = db_manager.get_database_stats()

        # Test database connection
        with sqlite3.connect(db_manager.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()

        return {
            "status": "healthy" if result else "unhealthy",
            "stats": stats,
            "database_path": str(db_manager.db_path),
            "database_exists": db_manager.db_path.exists(),
            "database_size_mb": (
                db_manager.db_path.stat().st_size / (1024 * 1024)
                if db_manager.db_path.exists()
                else 0
            ),
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


def check_ml_models() -> Dict[str, Any]:
    """Check ML models availability"""
    try:
        models_dir = Path("mercedes_obd_scanner/ml/models")

        if not models_dir.exists():
            return {"status": "no_models_directory", "models_count": 0, "models": []}

        model_files = list(models_dir.glob("*.pkl"))

        models_info = []
        for model_file in model_files:
            try:
                stat = model_file.stat()
                models_info.append(
                    {
                        "name": model_file.name,
                        "size_mb": stat.st_size / (1024 * 1024),
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    }
                )
            except Exception as e:
                models_info.append({"name": model_file.name, "error": str(e)})

        return {
            "status": "available" if model_files else "no_models",
            "models_count": len(model_files),
            "models": models_info,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def check_api_keys() -> Dict[str, Any]:
    """Check if required API keys are configured"""
    api_keys_status = {
        "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
        "openai": bool(os.getenv("OPENAI_API_KEY")),
    }

    return {
        "configured": api_keys_status,
        "all_configured": all(api_keys_status.values()),
        "missing": [key for key, configured in api_keys_status.items() if not configured],
    }


@router.get("/health")
async def health_check():
    """Basic health check endpoint"""
    try:
        # Basic checks
        db_health = check_database_health()
        api_keys = check_api_keys()

        # Determine overall health
        is_healthy = db_health.get("status") == "healthy" and api_keys.get("all_configured", False)

        status_code = 200 if is_healthy else 503

        return JSONResponse(
            status_code=status_code,
            content={
                "status": "healthy" if is_healthy else "unhealthy",
                "timestamp": datetime.now().isoformat(),
                "version": "2.0.0",
                "service": "Mercedes W222 OBD Scanner",
                "checks": {
                    "database": db_health.get("status"),
                    "api_keys": "configured" if api_keys.get("all_configured") else "missing",
                },
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
            },
        )


@router.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with system information"""
    try:
        system_info = get_system_info()
        db_health = check_database_health()
        ml_models = check_ml_models()
        api_keys = check_api_keys()

        # Determine overall health
        is_healthy = (
            db_health.get("status") == "healthy"
            and api_keys.get("all_configured", False)
            and system_info.get("system", {}).get("memory_percent", 100) < 90
            and system_info.get("system", {}).get("disk_percent", 100) < 90
        )

        status_code = 200 if is_healthy else 503

        return JSONResponse(
            status_code=status_code,
            content={
                "status": "healthy" if is_healthy else "unhealthy",
                "timestamp": datetime.now().isoformat(),
                "version": "2.0.0",
                "service": "Mercedes W222 OBD Scanner",
                "system": system_info,
                "database": db_health,
                "ml_models": ml_models,
                "api_keys": api_keys,
                "environment": {
                    "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                    "environment": os.getenv("ENVIRONMENT", "development"),
                    "debug": os.getenv("DEBUG", "false").lower() == "true",
                },
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "timestamp": datetime.now().isoformat(), "error": str(e)},
        )


@router.get("/metrics")
async def prometheus_metrics():
    """Prometheus-compatible metrics endpoint"""
    try:
        system_info = get_system_info()
        db_health = check_database_health()

        metrics = []

        # System metrics
        if "system" in system_info:
            sys_info = system_info["system"]
            metrics.extend(
                [
                    f"mercedes_obd_cpu_percent {sys_info.get('cpu_percent', 0)}",
                    f"mercedes_obd_memory_percent {sys_info.get('memory_percent', 0)}",
                    f"mercedes_obd_disk_percent {sys_info.get('disk_percent', 0)}",
                    f"mercedes_obd_memory_available_bytes {sys_info.get('memory_available', 0)}",
                    f"mercedes_obd_disk_free_bytes {sys_info.get('disk_free', 0)}",
                ]
            )

        # Process metrics
        if "process" in system_info:
            proc_info = system_info["process"]
            metrics.extend(
                [
                    f"mercedes_obd_process_memory_rss_bytes {proc_info.get('memory_rss', 0)}",
                    f"mercedes_obd_process_memory_vms_bytes {proc_info.get('memory_vms', 0)}",
                    f"mercedes_obd_process_cpu_percent {proc_info.get('cpu_percent', 0)}",
                    f"mercedes_obd_process_threads {proc_info.get('num_threads', 0)}",
                ]
            )

        # Database metrics
        if db_health.get("status") == "healthy" and "stats" in db_health:
            db_stats = db_health["stats"]
            for table, count in db_stats.items():
                if table.endswith("_count"):
                    table_name = table.replace("_count", "")
                    metrics.append(f"mercedes_obd_db_{table_name}_records {count}")

            metrics.append(f"mercedes_obd_db_size_mb {db_health.get('database_size_mb', 0)}")

        # Health status (1 = healthy, 0 = unhealthy)
        health_status = 1 if db_health.get("status") == "healthy" else 0
        metrics.append(f"mercedes_obd_health_status {health_status}")

        # API keys status
        api_keys = check_api_keys()
        api_status = 1 if api_keys.get("all_configured", False) else 0
        metrics.append(f"mercedes_obd_api_keys_configured {api_status}")

        return "\n".join(metrics) + "\n"

    except Exception as e:
        return f"# Error generating metrics: {str(e)}\n"


@router.get("/ready")
async def readiness_check():
    """Kubernetes-style readiness check"""
    try:
        # Check if application is ready to serve requests
        db_health = check_database_health()
        api_keys = check_api_keys()

        is_ready = db_health.get("status") == "healthy" and api_keys.get("all_configured", False)

        status_code = 200 if is_ready else 503

        return JSONResponse(
            status_code=status_code,
            content={"ready": is_ready, "timestamp": datetime.now().isoformat()},
        )
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"ready": False, "timestamp": datetime.now().isoformat(), "error": str(e)},
        )


@router.get("/live")
async def liveness_check():
    """Kubernetes-style liveness check"""
    try:
        # Basic liveness check - just return success if we can respond
        return JSONResponse(
            status_code=200, content={"alive": True, "timestamp": datetime.now().isoformat()}
        )
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"alive": False, "timestamp": datetime.now().isoformat(), "error": str(e)},
        )
