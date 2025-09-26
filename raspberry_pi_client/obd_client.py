"""
Raspberry Pi OBD Client for Mercedes W222 OBD Scanner
Connects to vehicle OBD port and transmits data to server
"""

import asyncio
import json
import logging
import sqlite3
import time
import websockets
import ssl
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path
import aiohttp
import obd
from dataclasses import dataclass, asdict


@dataclass
class OBDReading:
    """OBD parameter reading"""

    parameter: str
    value: float
    unit: str
    timestamp: datetime
    quality: float = 1.0


class LocalCache:
    """Local SQLite cache for offline data storage"""

    def __init__(self, db_path: str = "cache/obd_cache.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self):
        """Initialize local cache database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS obd_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parameter TEXT NOT NULL,
                    value REAL NOT NULL,
                    unit TEXT,
                    timestamp DATETIME NOT NULL,
                    quality REAL DEFAULT 1.0,
                    synced BOOLEAN DEFAULT FALSE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sync_status (
                    id INTEGER PRIMARY KEY,
                    last_sync DATETIME,
                    pending_count INTEGER DEFAULT 0,
                    total_readings INTEGER DEFAULT 0
                )
            """
            )

    def store_reading(self, reading: OBDReading):
        """Store OBD reading in local cache"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO obd_readings (parameter, value, unit, timestamp, quality)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    reading.parameter,
                    reading.value,
                    reading.unit,
                    reading.timestamp,
                    reading.quality,
                ),
            )

    def get_unsynced_readings(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get unsynced readings for transmission"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, parameter, value, unit, timestamp, quality
                FROM obd_readings
                WHERE synced = FALSE
                ORDER BY timestamp ASC
                LIMIT ?
            """,
                (limit,),
            )

            readings = []
            for row in cursor.fetchall():
                readings.append(
                    {
                        "id": row[0],
                        "parameter": row[1],
                        "value": row[2],
                        "unit": row[3],
                        "timestamp": row[4],
                        "quality": row[5],
                    }
                )

            return readings

    def mark_synced(self, reading_ids: List[int]):
        """Mark readings as synced"""
        if not reading_ids:
            return

        placeholders = ",".join("?" * len(reading_ids))
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE obd_readings SET synced = TRUE WHERE id IN ({placeholders})", reading_ids)
            )

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM obd_readings")
            total_readings = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM obd_readings WHERE synced = FALSE")
            pending_readings = cursor.fetchone()[0]

            cursor.execute("SELECT MAX(timestamp) FROM obd_readings")
            last_reading = cursor.fetchone()[0]

            return {
                "total_readings": total_readings,
                "pending_readings": pending_readings,
                "last_reading": last_reading,
                "sync_percentage": (
                    ((total_readings - pending_readings) / total_readings * 100)
                    if total_readings > 0
                    else 100
                ),
            }


class OBDScanner:
    """OBD-II scanner interface"""

    def __init__(self):
        self.connection = None
        self.logger = logging.getLogger(__name__)
        self.supported_commands = []

        # Mercedes W222 specific parameters
        self.mercedes_parameters = {
            "ENGINE_RPM": obd.commands.RPM,
            "COOLANT_TEMP": obd.commands.COOLANT_TEMP,
            "ENGINE_LOAD": obd.commands.ENGINE_LOAD,
            "SPEED": obd.commands.SPEED,
            "FUEL_LEVEL": obd.commands.FUEL_LEVEL,
            "INTAKE_PRESSURE": obd.commands.INTAKE_PRESSURE,
            "MAF": obd.commands.MAF,
            "THROTTLE_POS": obd.commands.THROTTLE_POS,
            "O2_B1S1": obd.commands.O2_B1S1,
            "SHORT_FUEL_TRIM_1": obd.commands.SHORT_FUEL_TRIM_1,
            "LONG_FUEL_TRIM_1": obd.commands.LONG_FUEL_TRIM_1,
        }

    def connect(self, port: str = None) -> bool:
        """Connect to OBD-II port"""
        try:
            if port:
                self.connection = obd.OBD(port)
            else:
                self.connection = obd.OBD()  # Auto-detect port

            if self.connection.is_connected():
                self.logger.info("Connected to OBD-II port")
                self._check_supported_commands()
                return True
            else:
                self.logger.error("Failed to connect to OBD-II port")
                return False

        except Exception as e:
            self.logger.error(f"OBD connection error: {str(e)}")
            return False

    def _check_supported_commands(self):
        """Check which commands are supported by the vehicle"""
        self.supported_commands = []
        for name, command in self.mercedes_parameters.items():
            if self.connection.supports(command):
                self.supported_commands.append(name)

        self.logger.info(f"Supported parameters: {self.supported_commands}")

    def read_parameters(self) -> List[OBDReading]:
        """Read all supported parameters"""
        readings = []

        if not self.connection or not self.connection.is_connected():
            return readings

        timestamp = datetime.utcnow()

        for param_name in self.supported_commands:
            try:
                command = self.mercedes_parameters[param_name]
                response = self.connection.query(command)

                if response.value is not None:
                    # Convert value to float
                    if hasattr(response.value, "magnitude"):
                        value = float(response.value.magnitude)
                        unit = str(response.value.units) if hasattr(response.value, "units") else ""
                    else:
                        value = float(response.value)
                        unit = ""

                    reading = OBDReading(
                        parameter=param_name,
                        value=value,
                        unit=unit,
                        timestamp=timestamp,
                        quality=1.0 if not response.is_null() else 0.5,
                    )
                    readings.append(reading)

            except Exception as e:
                self.logger.warning(f"Failed to read {param_name}: {str(e)}")

        return readings

    def disconnect(self):
        """Disconnect from OBD-II port"""
        if self.connection:
            self.connection.close()
            self.logger.info("Disconnected from OBD-II port")


class RPiOBDClient:
    """Main Raspberry Pi OBD Client"""

    def __init__(self, config_file: str = "config.json"):
        self.config = self._load_config(config_file)
        self.logger = self._setup_logging()

        self.device_token = self.config.get("device_token")
        self.server_url = self.config.get("server_url", "wss://your-server.com/ws/obd")
        self.api_url = self.config.get("api_url", "https://your-server.com/api")

        self.cache = LocalCache()
        self.scanner = OBDScanner()
        self.websocket = None
        self.session_id = None

        self.running = False
        self.scan_interval = self.config.get("scan_interval", 5)  # seconds
        self.sync_interval = self.config.get("sync_interval", 30)  # seconds

    def _load_config(self, config_file: str) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        config_path = Path(config_file)
        if config_path.exists():
            with open(config_path, "r") as f:
                return json.load(f)
        else:
            # Create default config
            default_config = {
                "device_token": "your_device_token_here",
                "server_url": "wss://your-server.com/ws/obd",
                "api_url": "https://your-server.com/api",
                "scan_interval": 5,
                "sync_interval": 30,
                "obd_port": None,
                "log_level": "INFO",
            }

            with open(config_path, "w") as f:
                json.dump(default_config, f, indent=2)

            return default_config

    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        log_level = getattr(logging, self.config.get("log_level", "INFO"))

        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler("logs/obd_client.log"), logging.StreamHandler()],
        )

        return logging.getLogger(__name__)

    async def authenticate(self) -> bool:
        """Authenticate with server using device token"""
        try:
            async with aiohttp.ClientSession() as session:
                auth_data = {
                    "device_token": self.device_token,
                    "device_type": "raspberry_pi",
                    "firmware_version": "1.0.0",
                }

                async with session.post(f"{self.api_url}/auth/device", json=auth_data) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.session_id = data.get("session_id")
                        self.logger.info("Device authenticated successfully")
                        return True
                    else:
                        self.logger.error(f"Authentication failed: {response.status}")
                        return False

        except Exception as e:
            self.logger.error(f"Authentication error: {str(e)}")
            return False

    async def connect_websocket(self) -> bool:
        """Connect to server WebSocket"""
        try:
            # Create SSL context for secure connection
            ssl_context = ssl.create_default_context()

            headers = {
                "Authorization": f"Bearer {self.device_token}",
                "X-Device-Type": "raspberry_pi",
            }

            self.websocket = await websockets.connect(
                self.server_url, ssl=ssl_context, extra_headers=headers
            )

            self.logger.info("WebSocket connected")
            return True

        except Exception as e:
            self.logger.error(f"WebSocket connection error: {str(e)}")
            return False

    async def send_readings(self, readings: List[OBDReading]):
        """Send OBD readings to server via WebSocket"""
        if not self.websocket:
            return False

        try:
            message = {
                "type": "obd_data",
                "session_id": self.session_id,
                "timestamp": datetime.utcnow().isoformat(),
                "readings": [asdict(reading) for reading in readings],
            }

            # Convert datetime objects to ISO format
            for reading in message["readings"]:
                reading["timestamp"] = reading["timestamp"].isoformat()

            await self.websocket.send(json.dumps(message))
            return True

        except Exception as e:
            self.logger.error(f"Failed to send readings: {str(e)}")
            return False

    async def sync_cached_data(self):
        """Sync cached data with server"""
        unsynced_readings = self.cache.get_unsynced_readings(100)

        if not unsynced_readings:
            return

        try:
            async with aiohttp.ClientSession() as session:
                sync_data = {
                    "device_token": self.device_token,
                    "session_id": self.session_id,
                    "readings": unsynced_readings,
                }

                async with session.post(f"{self.api_url}/obd/sync", json=sync_data) as response:
                    if response.status == 200:
                        # Mark readings as synced
                        reading_ids = [r["id"] for r in unsynced_readings]
                        self.cache.mark_synced(reading_ids)
                        self.logger.info(f"Synced {len(reading_ids)} readings")
                    else:
                        self.logger.warning(f"Sync failed: {response.status}")

        except Exception as e:
            self.logger.error(f"Sync error: {str(e)}")

    async def scan_loop(self):
        """Main OBD scanning loop"""
        while self.running:
            try:
                # Read OBD parameters
                readings = self.scanner.read_parameters()

                if readings:
                    # Store in local cache
                    for reading in readings:
                        self.cache.store_reading(reading)

                    # Try to send via WebSocket if connected
                    if self.websocket:
                        await self.send_readings(readings)

                    self.logger.debug(f"Collected {len(readings)} readings")

                await asyncio.sleep(self.scan_interval)

            except Exception as e:
                self.logger.error(f"Scan loop error: {str(e)}")
                await asyncio.sleep(self.scan_interval)

    async def sync_loop(self):
        """Periodic sync loop for cached data"""
        while self.running:
            try:
                await self.sync_cached_data()
                await asyncio.sleep(self.sync_interval)

            except Exception as e:
                self.logger.error(f"Sync loop error: {str(e)}")
                await asyncio.sleep(self.sync_interval)

    async def start(self):
        """Start the OBD client"""
        self.logger.info("Starting Mercedes W222 OBD Client")

        # Connect to OBD port
        if not self.scanner.connect(self.config.get("obd_port")):
            self.logger.error("Failed to connect to OBD port")
            return False

        # Authenticate with server
        if not await self.authenticate():
            self.logger.error("Failed to authenticate with server")
            return False

        # Connect WebSocket
        await self.connect_websocket()

        # Start scanning
        self.running = True

        # Run scan and sync loops concurrently
        await asyncio.gather(self.scan_loop(), self.sync_loop())

    async def stop(self):
        """Stop the OBD client"""
        self.logger.info("Stopping OBD client")
        self.running = False

        if self.websocket:
            await self.websocket.close()

        self.scanner.disconnect()

    def get_status(self) -> Dict[str, Any]:
        """Get client status"""
        cache_stats = self.cache.get_cache_stats()

        return {
            "running": self.running,
            "obd_connected": self.scanner.connection and self.scanner.connection.is_connected(),
            "websocket_connected": self.websocket and not self.websocket.closed,
            "session_id": self.session_id,
            "supported_parameters": self.scanner.supported_commands,
            "cache_stats": cache_stats,
        }


async def main():
    """Main entry point"""
    client = RPiOBDClient()

    try:
        await client.start()
    except KeyboardInterrupt:
        print("Shutting down...")
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
