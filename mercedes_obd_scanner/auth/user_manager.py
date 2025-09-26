"""
User Management System for Mercedes W222 OBD Scanner
Handles user registration, device binding, and subscription management
"""

import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from pathlib import Path
import logging

from .jwt_auth import jwt_auth


@dataclass
class User:
    """User data class"""

    user_id: str
    email: str
    password_hash: str
    subscription_tier: str = "free"
    subscription_expires: Optional[datetime] = None
    device_id: Optional[str] = None
    device_activated: bool = False
    created_at: datetime = None
    last_login: Optional[datetime] = None
    is_active: bool = True


@dataclass
class Device:
    """Device data class"""

    device_id: str
    device_token: str
    user_id: Optional[str] = None
    device_type: str = "raspberry_pi"
    firmware_version: str = "1.0.0"
    last_seen: Optional[datetime] = None
    is_active: bool = True
    created_at: datetime = None


class UserManager:
    """User and device management system"""

    def __init__(self, db_path: str = "data/users.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        self._init_database()

    def _init_database(self):
        """Initialize user management database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Users table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    subscription_tier TEXT DEFAULT 'free',
                    subscription_expires DATETIME,
                    device_id TEXT,
                    device_activated BOOLEAN DEFAULT FALSE,
                    created_at DATETIME NOT NULL,
                    last_login DATETIME,
                    is_active BOOLEAN DEFAULT TRUE,
                    FOREIGN KEY (device_id) REFERENCES devices (device_id)
                )
            """
            )

            # Devices table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS devices (
                    device_id TEXT PRIMARY KEY,
                    device_token TEXT UNIQUE NOT NULL,
                    user_id TEXT,
                    device_type TEXT DEFAULT 'raspberry_pi',
                    firmware_version TEXT DEFAULT '1.0.0',
                    last_seen DATETIME,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at DATETIME NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """
            )

            # Subscription history
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS subscription_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    subscription_tier TEXT NOT NULL,
                    start_date DATETIME NOT NULL,
                    end_date DATETIME,
                    payment_id TEXT,
                    amount REAL,
                    currency TEXT DEFAULT 'USD',
                    status TEXT DEFAULT 'active',
                    created_at DATETIME NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """
            )

            # Refresh tokens table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS refresh_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    token_hash TEXT NOT NULL,
                    expires_at DATETIME NOT NULL,
                    created_at DATETIME NOT NULL,
                    is_revoked BOOLEAN DEFAULT FALSE,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """
            )

    def create_device(self, device_type: str = "raspberry_pi") -> Device:
        """Create a new device with unique token"""
        device_id = f"device_{uuid.uuid4().hex[:12]}"
        device_token = jwt_auth.generate_device_token(device_id, "")

        device = Device(
            device_id=device_id,
            device_token=device_token,
            device_type=device_type,
            created_at=datetime.utcnow(),
        )

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO devices (device_id, device_token, device_type, created_at)
                VALUES (?, ?, ?, ?)
            """,
                (device.device_id, device.device_token, device.device_type, device.created_at),
            )

        self.logger.info(f"Created device: {device_id}")
        return device

    def register_user(self, email: str, password: str, device_token: str) -> Optional[User]:
        """Register new user with device token"""
        # Verify device token exists and is not already used
        device = self.get_device_by_token(device_token)
        if not device:
            raise ValueError("Invalid device token")

        if device.user_id:
            raise ValueError("Device already registered to another user")

        # Check if email already exists
        if self.get_user_by_email(email):
            raise ValueError("Email already registered")

        # Create user
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        password_hash = jwt_auth.hash_password(password)

        user = User(
            user_id=user_id,
            email=email,
            password_hash=password_hash,
            device_id=device.device_id,
            device_activated=True,
            created_at=datetime.utcnow(),
        )

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Insert user
            cursor.execute(
                """
                INSERT INTO users (user_id, email, password_hash, device_id, device_activated, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    user.user_id,
                    user.email,
                    user.password_hash,
                    user.device_id,
                    user.device_activated,
                    user.created_at,
                ),
            )

            # Update device with user_id
            cursor.execute(
                """
                UPDATE devices SET user_id = ? WHERE device_id = ?
            """,
                (user.user_id, device.device_id),
            )

        self.logger.info(f"Registered user: {email} with device: {device.device_id}")
        return user

    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password"""
        user = self.get_user_by_email(email)
        if not user or not user.is_active:
            return None

        if not jwt_auth.verify_password(password, user.password_hash):
            return None

        # Update last login
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE users SET last_login = ? WHERE user_id = ?
            """,
                (datetime.utcnow(), user.user_id),
            )

        return user

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
            row = cursor.fetchone()

            if row:
                return User(
                    user_id=row[0],
                    email=row[1],
                    password_hash=row[2],
                    subscription_tier=row[3],
                    subscription_expires=datetime.fromisoformat(row[4]) if row[4] else None,
                    device_id=row[5],
                    device_activated=bool(row[6]),
                    created_at=datetime.fromisoformat(row[7]),
                    last_login=datetime.fromisoformat(row[8]) if row[8] else None,
                    is_active=bool(row[9]),
                )
        return None

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()

            if row:
                return User(
                    user_id=row[0],
                    email=row[1],
                    password_hash=row[2],
                    subscription_tier=row[3],
                    subscription_expires=datetime.fromisoformat(row[4]) if row[4] else None,
                    device_id=row[5],
                    device_activated=bool(row[6]),
                    created_at=datetime.fromisoformat(row[7]),
                    last_login=datetime.fromisoformat(row[8]) if row[8] else None,
                    is_active=bool(row[9]),
                )
        return None

    def get_device_by_token(self, device_token: str) -> Optional[Device]:
        """Get device by token"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM devices WHERE device_token = ?", (device_token,))
            row = cursor.fetchone()

            if row:
                return Device(
                    device_id=row[0],
                    device_token=row[1],
                    user_id=row[2],
                    device_type=row[3],
                    firmware_version=row[4],
                    last_seen=datetime.fromisoformat(row[5]) if row[5] else None,
                    is_active=bool(row[6]),
                    created_at=datetime.fromisoformat(row[7]),
                )
        return None

    def update_subscription(
        self,
        user_id: str,
        tier: str,
        duration_days: int,
        payment_id: str = None,
        amount: float = None,
    ) -> bool:
        """Update user subscription"""
        user = self.get_user_by_id(user_id)
        if not user:
            return False

        expires_at = datetime.utcnow() + timedelta(days=duration_days)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Update user subscription
            cursor.execute(
                """
                UPDATE users SET subscription_tier = ?, subscription_expires = ?
                WHERE user_id = ?
            """,
                (tier, expires_at, user_id),
            )

            # Add to subscription history
            cursor.execute(
                """
                INSERT INTO subscription_history 
                (user_id, subscription_tier, start_date, end_date, payment_id, amount, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    user_id,
                    tier,
                    datetime.utcnow(),
                    expires_at,
                    payment_id,
                    amount,
                    datetime.utcnow(),
                ),
            )

        self.logger.info(f"Updated subscription for user {user_id}: {tier} until {expires_at}")
        return True

    def is_subscription_active(self, user_id: str) -> bool:
        """Check if user subscription is active"""
        user = self.get_user_by_id(user_id)
        if not user or user.subscription_tier == "free":
            return True  # Free tier is always "active"

        if user.subscription_expires and user.subscription_expires > datetime.utcnow():
            return True

        return False

    def get_user_permissions(self, user_id: str) -> List[str]:
        """Get user permissions based on subscription tier"""
        user = self.get_user_by_id(user_id)
        if not user:
            return []

        permissions = ["basic_obd_scan", "trip_history"]

        if user.subscription_tier in ["premium", "pro"]:
            permissions.extend(["ai_analysis", "predictive_maintenance", "advanced_diagnostics"])

        if user.subscription_tier == "pro":
            permissions.extend(["custom_reports", "api_access", "priority_support"])

        return permissions

    def update_device_last_seen(self, device_id: str):
        """Update device last seen timestamp"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE devices SET last_seen = ? WHERE device_id = ?
            """,
                (datetime.utcnow(), device_id),
            )

    def get_user_stats(self) -> Dict[str, Any]:
        """Get user statistics"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Total users
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = TRUE")
            total_users = cursor.fetchone()[0]

            # Active subscriptions
            cursor.execute(
                """
                SELECT COUNT(*) FROM users 
                WHERE subscription_tier != 'free' 
                AND (subscription_expires IS NULL OR subscription_expires > ?)
            """,
                (datetime.utcnow(),),
            )
            active_subscriptions = cursor.fetchone()[0]

            # Devices
            cursor.execute("SELECT COUNT(*) FROM devices WHERE is_active = TRUE")
            total_devices = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM devices WHERE user_id IS NOT NULL")
            registered_devices = cursor.fetchone()[0]

            return {
                "total_users": total_users,
                "active_subscriptions": active_subscriptions,
                "total_devices": total_devices,
                "registered_devices": registered_devices,
                "unregistered_devices": total_devices - registered_devices,
            }


# Global user manager instance
user_manager = UserManager()
