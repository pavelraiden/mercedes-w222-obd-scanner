#!/usr/bin/env python3
"""
Multi-Factor Authentication (MFA) System for Mercedes W222 OBD Scanner
Enterprise-grade authentication with TOTP, SMS, and backup codes
"""

import os
import secrets
import hashlib
import hmac
import time
import base64
import qrcode
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from contextlib import contextmanager
import json
import pyotp
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class MFADevice:
    """MFA device data structure"""
    device_id: str
    user_id: str
    device_type: str  # 'totp', 'sms', 'backup_codes'
    device_name: str
    secret_key: str
    is_active: bool
    created_at: datetime
    last_used: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'device_id': self.device_id,
            'user_id': self.user_id,
            'device_type': self.device_type,
            'device_name': self.device_name,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'last_used': self.last_used.isoformat() if self.last_used else None
        }

@dataclass
class MFAAttempt:
    """MFA authentication attempt"""
    attempt_id: str
    user_id: str
    device_id: str
    code_provided: str
    success: bool
    ip_address: str
    user_agent: str
    timestamp: datetime
    failure_reason: Optional[str] = None

class CryptoManager:
    """Cryptographic operations for MFA"""
    
    def __init__(self, master_key: Optional[bytes] = None):
        if master_key is None:
            # In production, this should come from secure key management
            master_key = os.environ.get('MFA_MASTER_KEY', 'default-key-change-in-production').encode()
        
        # Derive encryption key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'mfa_salt_mercedes_obd',  # In production, use random salt per installation
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(master_key))
        self.cipher = Fernet(key)
    
    def encrypt(self, data: str) -> str:
        """Encrypt sensitive data"""
        return self.cipher.encrypt(data.encode()).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt sensitive data"""
        return self.cipher.decrypt(encrypted_data.encode()).decode()
    
    def generate_secret(self, length: int = 32) -> str:
        """Generate cryptographically secure secret"""
        return base64.b32encode(secrets.token_bytes(length)).decode()
    
    def generate_backup_codes(self, count: int = 10) -> List[str]:
        """Generate backup recovery codes"""
        codes = []
        for _ in range(count):
            # Generate 8-character alphanumeric codes
            code = ''.join(secrets.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(8))
            codes.append(f"{code[:4]}-{code[4:]}")
        return codes

class TOTPManager:
    """Time-based One-Time Password manager"""
    
    def __init__(self, crypto_manager: CryptoManager):
        self.crypto = crypto_manager
        
    def generate_secret(self) -> str:
        """Generate TOTP secret key"""
        return pyotp.random_base32()
    
    def generate_qr_code(self, secret: str, user_email: str, issuer: str = "Mercedes OBD Scanner") -> bytes:
        """Generate QR code for TOTP setup"""
        totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=user_email,
            issuer_name=issuer
        )
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(totp_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to bytes
        from io import BytesIO
        img_buffer = BytesIO()
        img.save(img_buffer, format='PNG')
        return img_buffer.getvalue()
    
    def verify_code(self, secret: str, code: str, window: int = 1) -> bool:
        """Verify TOTP code with time window tolerance"""
        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=window)
    
    def get_current_code(self, secret: str) -> str:
        """Get current TOTP code (for testing)"""
        totp = pyotp.TOTP(secret)
        return totp.now()

class SMSManager:
    """SMS-based MFA manager"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get('enabled', False)
        
        # SMS provider configuration
        self.provider = config.get('provider', 'twilio')
        self.api_key = config.get('api_key')
        self.api_secret = config.get('api_secret')
        self.from_number = config.get('from_number')
        
    def send_code(self, phone_number: str, code: str) -> bool:
        """Send SMS verification code"""
        if not self.enabled:
            logger.warning("SMS MFA is disabled")
            return False
        
        try:
            message = f"Your Mercedes OBD Scanner verification code is: {code}. Valid for 5 minutes."
            
            if self.provider == 'twilio':
                return self._send_twilio_sms(phone_number, message)
            elif self.provider == 'aws_sns':
                return self._send_aws_sns(phone_number, message)
            else:
                logger.error(f"Unsupported SMS provider: {self.provider}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send SMS to {phone_number}: {e}")
            return False
    
    def _send_twilio_sms(self, phone_number: str, message: str) -> bool:
        """Send SMS via Twilio (requires twilio package)"""
        try:
            # In production, install and use: pip install twilio
            # from twilio.rest import Client
            # client = Client(self.api_key, self.api_secret)
            # message = client.messages.create(
            #     body=message,
            #     from_=self.from_number,
            #     to=phone_number
            # )
            
            # For demo, just log the message
            logger.info(f"[DEMO] SMS to {phone_number}: {message}")
            return True
            
        except Exception as e:
            logger.error(f"Twilio SMS error: {e}")
            return False
    
    def _send_aws_sns(self, phone_number: str, message: str) -> bool:
        """Send SMS via AWS SNS (requires boto3 package)"""
        try:
            # In production, install and use: pip install boto3
            # import boto3
            # sns = boto3.client('sns')
            # response = sns.publish(
            #     PhoneNumber=phone_number,
            #     Message=message
            # )
            
            # For demo, just log the message
            logger.info(f"[DEMO] AWS SNS to {phone_number}: {message}")
            return True
            
        except Exception as e:
            logger.error(f"AWS SNS error: {e}")
            return False
    
    def generate_sms_code(self) -> str:
        """Generate 6-digit SMS verification code"""
        return ''.join(secrets.choice('0123456789') for _ in range(6))

class BackupCodeManager:
    """Backup recovery codes manager"""
    
    def __init__(self, crypto_manager: CryptoManager):
        self.crypto = crypto_manager
    
    def generate_codes(self, count: int = 10) -> List[str]:
        """Generate backup recovery codes"""
        return self.crypto.generate_backup_codes(count)
    
    def hash_code(self, code: str) -> str:
        """Hash backup code for secure storage"""
        return hashlib.sha256(code.encode()).hexdigest()
    
    def verify_code(self, code: str, hashed_code: str) -> bool:
        """Verify backup code against hash"""
        return hmac.compare_digest(self.hash_code(code), hashed_code)

class MFADatabase:
    """MFA database operations"""
    
    def __init__(self, db_path: str = "security/mfa.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Initialize MFA database"""
        with self._get_connection() as conn:
            # MFA devices table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mfa_devices (
                    device_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    device_type TEXT NOT NULL,
                    device_name TEXT NOT NULL,
                    secret_key TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used TIMESTAMP
                )
            """)
            
            # Backup codes table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS backup_codes (
                    code_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    code_hash TEXT NOT NULL,
                    is_used BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    used_at TIMESTAMP
                )
            """)
            
            # MFA attempts table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mfa_attempts (
                    attempt_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    device_id TEXT,
                    code_provided TEXT,
                    success BOOLEAN NOT NULL,
                    ip_address TEXT,
                    user_agent TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    failure_reason TEXT
                )
            """)
            
            # SMS codes table (temporary storage)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sms_codes (
                    code_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    phone_number TEXT NOT NULL,
                    code_hash TEXT NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    is_used BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mfa_devices_user ON mfa_devices(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_backup_codes_user ON backup_codes(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mfa_attempts_user ON mfa_attempts(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sms_codes_user ON sms_codes(user_id)")
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with proper cleanup"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def add_device(self, device: MFADevice) -> bool:
        """Add MFA device"""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO mfa_devices 
                    (device_id, user_id, device_type, device_name, secret_key, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    device.device_id, device.user_id, device.device_type,
                    device.device_name, device.secret_key, device.is_active,
                    device.created_at.isoformat()
                ))
                return True
        except Exception as e:
            logger.error(f"Failed to add MFA device: {e}")
            return False
    
    def get_user_devices(self, user_id: str, active_only: bool = True) -> List[MFADevice]:
        """Get user's MFA devices"""
        with self._get_connection() as conn:
            query = "SELECT * FROM mfa_devices WHERE user_id = ?"
            params = [user_id]
            
            if active_only:
                query += " AND is_active = TRUE"
            
            cursor = conn.execute(query, params)
            devices = []
            
            for row in cursor.fetchall():
                device = MFADevice(
                    device_id=row['device_id'],
                    user_id=row['user_id'],
                    device_type=row['device_type'],
                    device_name=row['device_name'],
                    secret_key=row['secret_key'],
                    is_active=bool(row['is_active']),
                    created_at=datetime.fromisoformat(row['created_at']),
                    last_used=datetime.fromisoformat(row['last_used']) if row['last_used'] else None
                )
                devices.append(device)
            
            return devices
    
    def update_device_last_used(self, device_id: str):
        """Update device last used timestamp"""
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE mfa_devices 
                SET last_used = ? 
                WHERE device_id = ?
            """, (datetime.now().isoformat(), device_id))
    
    def deactivate_device(self, device_id: str) -> bool:
        """Deactivate MFA device"""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    UPDATE mfa_devices 
                    SET is_active = FALSE 
                    WHERE device_id = ?
                """, (device_id,))
                return True
        except Exception as e:
            logger.error(f"Failed to deactivate device: {e}")
            return False
    
    def log_attempt(self, attempt: MFAAttempt):
        """Log MFA attempt"""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO mfa_attempts 
                (attempt_id, user_id, device_id, code_provided, success, 
                 ip_address, user_agent, timestamp, failure_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                attempt.attempt_id, attempt.user_id, attempt.device_id,
                attempt.code_provided, attempt.success, attempt.ip_address,
                attempt.user_agent, attempt.timestamp.isoformat(), attempt.failure_reason
            ))

class MFAManager:
    """Main MFA manager coordinating all MFA operations"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or self._default_config()
        
        # Initialize components
        self.crypto = CryptoManager()
        self.totp = TOTPManager(self.crypto)
        self.sms = SMSManager(self.config.get('sms', {}))
        self.backup_codes = BackupCodeManager(self.crypto)
        self.db = MFADatabase()
        
        # MFA statistics
        self.stats = {
            'total_devices': 0,
            'active_devices': 0,
            'successful_authentications': 0,
            'failed_authentications': 0,
            'start_time': datetime.now()
        }
    
    def _default_config(self) -> Dict[str, Any]:
        """Default MFA configuration"""
        return {
            'require_mfa': True,
            'allow_backup_codes': True,
            'max_devices_per_user': 5,
            'sms': {
                'enabled': False,
                'provider': 'twilio',
                'api_key': '',
                'api_secret': '',
                'from_number': ''
            },
            'totp': {
                'enabled': True,
                'issuer': 'Mercedes OBD Scanner',
                'window': 1
            }
        }
    
    def setup_totp_device(self, user_id: str, user_email: str, device_name: str) -> Dict[str, Any]:
        """Setup new TOTP device for user"""
        try:
            # Generate secret
            secret = self.totp.generate_secret()
            encrypted_secret = self.crypto.encrypt(secret)
            
            # Create device
            device = MFADevice(
                device_id=secrets.token_urlsafe(16),
                user_id=user_id,
                device_type='totp',
                device_name=device_name,
                secret_key=encrypted_secret,
                is_active=False,  # Will be activated after verification
                created_at=datetime.now()
            )
            
            # Generate QR code
            qr_code = self.totp.generate_qr_code(secret, user_email, self.config['totp']['issuer'])
            
            # Store device (inactive until verified)
            if self.db.add_device(device):
                return {
                    'success': True,
                    'device_id': device.device_id,
                    'secret': secret,  # Only return for initial setup
                    'qr_code': base64.b64encode(qr_code).decode(),
                    'backup_codes': self.generate_backup_codes(user_id)
                }
            else:
                return {'success': False, 'error': 'Failed to store device'}
                
        except Exception as e:
            logger.error(f"Failed to setup TOTP device: {e}")
            return {'success': False, 'error': str(e)}
    
    def verify_totp_setup(self, device_id: str, code: str) -> bool:
        """Verify TOTP setup and activate device"""
        try:
            with self.db._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT secret_key FROM mfa_devices 
                    WHERE device_id = ? AND device_type = 'totp' AND is_active = FALSE
                """, (device_id,))
                
                row = cursor.fetchone()
                if not row:
                    return False
                
                # Decrypt secret and verify code
                secret = self.crypto.decrypt(row['secret_key'])
                if self.totp.verify_code(secret, code, self.config['totp']['window']):
                    # Activate device
                    conn.execute("""
                        UPDATE mfa_devices 
                        SET is_active = TRUE 
                        WHERE device_id = ?
                    """, (device_id,))
                    return True
                
                return False
                
        except Exception as e:
            logger.error(f"Failed to verify TOTP setup: {e}")
            return False
    
    def generate_backup_codes(self, user_id: str) -> List[str]:
        """Generate backup recovery codes for user"""
        codes = self.backup_codes.generate_codes()
        
        # Store hashed codes in database
        with self.db._get_connection() as conn:
            for code in codes:
                code_hash = self.backup_codes.hash_code(code)
                conn.execute("""
                    INSERT INTO backup_codes (code_id, user_id, code_hash)
                    VALUES (?, ?, ?)
                """, (secrets.token_urlsafe(16), user_id, code_hash))
        
        return codes
    
    def authenticate(self, user_id: str, code: str, device_id: Optional[str] = None,
                    ip_address: str = 'unknown', user_agent: str = 'unknown') -> Dict[str, Any]:
        """Authenticate user with MFA code"""
        attempt_id = secrets.token_urlsafe(16)
        
        try:
            # Get user's active devices
            devices = self.db.get_user_devices(user_id, active_only=True)
            
            if not devices:
                return self._log_attempt_and_return(
                    attempt_id, user_id, None, code, False,
                    ip_address, user_agent, 'no_devices'
                )
            
            # Try specific device if provided
            if device_id:
                device = next((d for d in devices if d.device_id == device_id), None)
                if device:
                    result = self._verify_device_code(device, code)
                    if result['success']:
                        self.db.update_device_last_used(device_id)
                        return self._log_attempt_and_return(
                            attempt_id, user_id, device_id, code, True,
                            ip_address, user_agent, None
                        )
            
            # Try all devices
            for device in devices:
                result = self._verify_device_code(device, code)
                if result['success']:
                    self.db.update_device_last_used(device.device_id)
                    return self._log_attempt_and_return(
                        attempt_id, user_id, device.device_id, code, True,
                        ip_address, user_agent, None
                    )
            
            # Try backup codes
            if self.config['allow_backup_codes']:
                if self._verify_backup_code(user_id, code):
                    return self._log_attempt_and_return(
                        attempt_id, user_id, 'backup_code', code, True,
                        ip_address, user_agent, None
                    )
            
            return self._log_attempt_and_return(
                attempt_id, user_id, None, code, False,
                ip_address, user_agent, 'invalid_code'
            )
            
        except Exception as e:
            logger.error(f"MFA authentication error: {e}")
            return self._log_attempt_and_return(
                attempt_id, user_id, None, code, False,
                ip_address, user_agent, f'error: {str(e)}'
            )
    
    def _verify_device_code(self, device: MFADevice, code: str) -> Dict[str, Any]:
        """Verify code against specific device"""
        try:
            if device.device_type == 'totp':
                secret = self.crypto.decrypt(device.secret_key)
                success = self.totp.verify_code(secret, code, self.config['totp']['window'])
                return {'success': success, 'device_type': 'totp'}
            
            elif device.device_type == 'sms':
                # SMS verification would be handled separately
                return {'success': False, 'device_type': 'sms', 'error': 'sms_not_implemented'}
            
            else:
                return {'success': False, 'error': 'unknown_device_type'}
                
        except Exception as e:
            logger.error(f"Device verification error: {e}")
            return {'success': False, 'error': str(e)}
    
    def _verify_backup_code(self, user_id: str, code: str) -> bool:
        """Verify backup recovery code"""
        try:
            with self.db._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT code_id, code_hash FROM backup_codes 
                    WHERE user_id = ? AND is_used = FALSE
                """, (user_id,))
                
                for row in cursor.fetchall():
                    if self.backup_codes.verify_code(code, row['code_hash']):
                        # Mark code as used
                        conn.execute("""
                            UPDATE backup_codes 
                            SET is_used = TRUE, used_at = ? 
                            WHERE code_id = ?
                        """, (datetime.now().isoformat(), row['code_id']))
                        return True
                
                return False
                
        except Exception as e:
            logger.error(f"Backup code verification error: {e}")
            return False
    
    def _log_attempt_and_return(self, attempt_id: str, user_id: str, device_id: Optional[str],
                               code: str, success: bool, ip_address: str, user_agent: str,
                               failure_reason: Optional[str]) -> Dict[str, Any]:
        """Log attempt and return result"""
        attempt = MFAAttempt(
            attempt_id=attempt_id,
            user_id=user_id,
            device_id=device_id,
            code_provided=code[:2] + '*' * (len(code) - 2),  # Mask code
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
            timestamp=datetime.now(),
            failure_reason=failure_reason
        )
        
        self.db.log_attempt(attempt)
        
        # Update statistics
        if success:
            self.stats['successful_authentications'] += 1
        else:
            self.stats['failed_authentications'] += 1
        
        return {
            'success': success,
            'attempt_id': attempt_id,
            'device_id': device_id,
            'failure_reason': failure_reason
        }
    
    def get_user_mfa_status(self, user_id: str) -> Dict[str, Any]:
        """Get user's MFA status and devices"""
        devices = self.db.get_user_devices(user_id)
        
        return {
            'mfa_enabled': len(devices) > 0,
            'device_count': len(devices),
            'devices': [device.to_dict() for device in devices],
            'backup_codes_available': self._count_backup_codes(user_id)
        }
    
    def _count_backup_codes(self, user_id: str) -> int:
        """Count available backup codes for user"""
        with self.db._get_connection() as conn:
            cursor = conn.execute("""
                SELECT COUNT(*) FROM backup_codes 
                WHERE user_id = ? AND is_used = FALSE
            """, (user_id,))
            return cursor.fetchone()[0]
    
    def disable_mfa(self, user_id: str) -> bool:
        """Disable MFA for user (deactivate all devices)"""
        try:
            with self.db._get_connection() as conn:
                conn.execute("""
                    UPDATE mfa_devices 
                    SET is_active = FALSE 
                    WHERE user_id = ?
                """, (user_id,))
                
                conn.execute("""
                    UPDATE backup_codes 
                    SET is_used = TRUE 
                    WHERE user_id = ?
                """, (user_id,))
                
                return True
        except Exception as e:
            logger.error(f"Failed to disable MFA: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get MFA statistics"""
        with self.db._get_connection() as conn:
            # Count devices
            cursor = conn.execute("SELECT COUNT(*) FROM mfa_devices")
            total_devices = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT COUNT(*) FROM mfa_devices WHERE is_active = TRUE")
            active_devices = cursor.fetchone()[0]
            
            # Recent attempts
            since = datetime.now() - timedelta(hours=24)
            cursor = conn.execute("""
                SELECT success, COUNT(*) FROM mfa_attempts 
                WHERE timestamp >= ? 
                GROUP BY success
            """, (since.isoformat(),))
            
            recent_attempts = dict(cursor.fetchall())
            
        return {
            'total_devices': total_devices,
            'active_devices': active_devices,
            'successful_authentications_24h': recent_attempts.get(1, 0),
            'failed_authentications_24h': recent_attempts.get(0, 0),
            'uptime': (datetime.now() - self.stats['start_time']).total_seconds()
        }

if __name__ == "__main__":
    # Demo usage
    print("Mercedes W222 OBD Scanner - MFA System Demo")
    print("=" * 50)
    
    # Initialize MFA
    mfa = MFAManager()
    
    # Demo user
    user_id = "demo_user_123"
    user_email = "demo@mercedes-obd.com"
    
    print("1. Setting up TOTP device...")
    setup_result = mfa.setup_totp_device(user_id, user_email, "Demo Phone")
    
    if setup_result['success']:
        device_id = setup_result['device_id']
        secret = setup_result['secret']
        
        print(f"✅ TOTP device created: {device_id}")
        print(f"Secret: {secret}")
        print(f"Backup codes: {len(setup_result['backup_codes'])} generated")
        
        # Get current TOTP code for verification
        current_code = mfa.totp.get_current_code(secret)
        print(f"Current TOTP code: {current_code}")
        
        print("\n2. Verifying TOTP setup...")
        if mfa.verify_totp_setup(device_id, current_code):
            print("✅ TOTP device activated")
            
            print("\n3. Testing authentication...")
            # Test with correct code
            auth_result = mfa.authenticate(user_id, current_code)
            if auth_result['success']:
                print("✅ Authentication successful")
            else:
                print("❌ Authentication failed")
            
            # Test with wrong code
            auth_result = mfa.authenticate(user_id, "123456")
            if not auth_result['success']:
                print("✅ Correctly rejected invalid code")
            
            print("\n4. MFA Status:")
            status = mfa.get_user_mfa_status(user_id)
            print(f"MFA enabled: {status['mfa_enabled']}")
            print(f"Devices: {status['device_count']}")
            print(f"Backup codes: {status['backup_codes_available']}")
            
        else:
            print("❌ TOTP verification failed")
    else:
        print(f"❌ TOTP setup failed: {setup_result.get('error')}")
    
    # Show statistics
    print(f"\nMFA Statistics:")
    stats = mfa.get_statistics()
    for key, value in stats.items():
        print(f"{key}: {value}")
