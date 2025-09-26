#!/usr/bin/env python3
"""
Comprehensive Audit Logging System for Mercedes W222 OBD Scanner
Enterprise-grade audit trail for security, compliance, and forensics
"""

import os
import json
import time
import hashlib
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from contextlib import contextmanager
from enum import Enum
import threading
from queue import Queue, Empty
import gzip
import shutil
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AuditEventType(Enum):
    """Audit event types"""
    # Authentication events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    MFA_SUCCESS = "mfa_success"
    MFA_FAILURE = "mfa_failure"
    PASSWORD_CHANGE = "password_change"
    
    # Authorization events
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    PERMISSION_CHANGE = "permission_change"
    ROLE_CHANGE = "role_change"
    
    # Data events
    DATA_ACCESS = "data_access"
    DATA_EXPORT = "data_export"
    DATA_IMPORT = "data_import"
    DATA_DELETE = "data_delete"
    DATA_MODIFY = "data_modify"
    
    # System events
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    CONFIG_CHANGE = "config_change"
    BACKUP_CREATE = "backup_create"
    BACKUP_RESTORE = "backup_restore"
    
    # OBD specific events
    OBD_CONNECT = "obd_connect"
    OBD_DISCONNECT = "obd_disconnect"
    OBD_SCAN = "obd_scan"
    OBD_CLEAR_CODES = "obd_clear_codes"
    VEHICLE_PROFILE_CREATE = "vehicle_profile_create"
    VEHICLE_PROFILE_MODIFY = "vehicle_profile_modify"
    
    # Security events
    SECURITY_VIOLATION = "security_violation"
    INTRUSION_ATTEMPT = "intrusion_attempt"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    
    # Administrative events
    USER_CREATE = "user_create"
    USER_DELETE = "user_delete"
    USER_MODIFY = "user_modify"
    LICENSE_ACTIVATE = "license_activate"
    LICENSE_EXPIRE = "license_expire"

class AuditSeverity(Enum):
    """Audit event severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class AuditEvent:
    """Audit event data structure"""
    event_id: str
    timestamp: datetime
    event_type: AuditEventType
    severity: AuditSeverity
    user_id: Optional[str]
    session_id: Optional[str]
    ip_address: str
    user_agent: str
    resource: str
    action: str
    outcome: str  # success, failure, error
    details: Dict[str, Any]
    risk_score: int  # 0-100
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'event_id': self.event_id,
            'timestamp': self.timestamp.isoformat(),
            'event_type': self.event_type.value,
            'severity': self.severity.value,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'resource': self.resource,
            'action': self.action,
            'outcome': self.outcome,
            'details': self.details,
            'risk_score': self.risk_score
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

class RiskCalculator:
    """Calculate risk scores for audit events"""
    
    def __init__(self):
        # Risk scoring rules
        self.base_scores = {
            # High-risk events
            AuditEventType.LOGIN_FAILURE: 30,
            AuditEventType.MFA_FAILURE: 40,
            AuditEventType.ACCESS_DENIED: 25,
            AuditEventType.SECURITY_VIOLATION: 80,
            AuditEventType.INTRUSION_ATTEMPT: 90,
            AuditEventType.DATA_DELETE: 60,
            AuditEventType.OBD_CLEAR_CODES: 50,
            
            # Medium-risk events
            AuditEventType.LOGIN_SUCCESS: 10,
            AuditEventType.DATA_EXPORT: 30,
            AuditEventType.CONFIG_CHANGE: 40,
            AuditEventType.PERMISSION_CHANGE: 45,
            AuditEventType.USER_CREATE: 35,
            
            # Low-risk events
            AuditEventType.DATA_ACCESS: 5,
            AuditEventType.OBD_SCAN: 10,
            AuditEventType.LOGOUT: 0,
        }
        
        # Risk modifiers
        self.ip_risk_cache = {}
        self.user_risk_cache = {}
        
    def calculate_risk(self, event: AuditEvent, context: Dict[str, Any] = None) -> int:
        """Calculate risk score for audit event"""
        base_score = self.base_scores.get(event.event_type, 20)
        
        # Apply modifiers
        modifiers = 0
        
        # Outcome modifier
        if event.outcome == 'failure':
            modifiers += 20
        elif event.outcome == 'error':
            modifiers += 15
        
        # Time-based modifier (off-hours activity)
        hour = event.timestamp.hour
        if hour < 6 or hour > 22:  # Outside business hours
            modifiers += 10
        
        # IP-based modifier
        if event.ip_address:
            ip_risk = self._get_ip_risk(event.ip_address)
            modifiers += ip_risk
        
        # User-based modifier
        if event.user_id:
            user_risk = self._get_user_risk(event.user_id, context)
            modifiers += user_risk
        
        # Frequency modifier (if context provided)
        if context and 'recent_events' in context:
            frequency_risk = self._calculate_frequency_risk(event, context['recent_events'])
            modifiers += frequency_risk
        
        # Calculate final score
        final_score = min(100, max(0, base_score + modifiers))
        return final_score
    
    def _get_ip_risk(self, ip_address: str) -> int:
        """Get risk score for IP address"""
        if ip_address in self.ip_risk_cache:
            return self.ip_risk_cache[ip_address]
        
        risk = 0
        
        # Check for private/local IPs (lower risk)
        if ip_address.startswith(('127.', '192.168.', '10.', '172.')):
            risk = 0
        # Check for known suspicious patterns
        elif ip_address.startswith(('169.254.')):  # Link-local
            risk = 5
        else:
            # In production, check against threat intelligence feeds
            risk = 10  # Default for external IPs
        
        self.ip_risk_cache[ip_address] = risk
        return risk
    
    def _get_user_risk(self, user_id: str, context: Dict[str, Any] = None) -> int:
        """Get risk score for user"""
        if user_id in self.user_risk_cache:
            return self.user_risk_cache[user_id]
        
        risk = 0
        
        # Check user role/permissions (if available in context)
        if context and 'user_roles' in context:
            user_roles = context['user_roles'].get(user_id, [])
            if 'admin' in user_roles:
                risk += 15
            elif 'privileged' in user_roles:
                risk += 10
        
        # Check for new user (higher risk)
        if context and 'user_created' in context:
            user_created = context['user_created'].get(user_id)
            if user_created:
                days_since_creation = (datetime.now() - user_created).days
                if days_since_creation < 7:
                    risk += 20
                elif days_since_creation < 30:
                    risk += 10
        
        self.user_risk_cache[user_id] = risk
        return risk
    
    def _calculate_frequency_risk(self, event: AuditEvent, recent_events: List[AuditEvent]) -> int:
        """Calculate risk based on event frequency"""
        # Count similar events in the last hour
        one_hour_ago = event.timestamp - timedelta(hours=1)
        similar_events = [
            e for e in recent_events
            if e.event_type == event.event_type
            and e.user_id == event.user_id
            and e.timestamp >= one_hour_ago
        ]
        
        count = len(similar_events)
        
        # Risk increases with frequency
        if count > 10:
            return 30
        elif count > 5:
            return 20
        elif count > 2:
            return 10
        else:
            return 0

class AuditDatabase:
    """Audit database operations with integrity protection"""
    
    def __init__(self, db_path: str = "security/audit.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_database()
        
        # Integrity protection
        self.integrity_key = self._get_integrity_key()
        
    def _init_database(self):
        """Initialize audit database"""
        with self._get_connection() as conn:
            # Main audit events table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT UNIQUE NOT NULL,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    user_id TEXT,
                    session_id TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    resource TEXT NOT NULL,
                    action TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    details TEXT,
                    risk_score INTEGER,
                    integrity_hash TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Audit log integrity table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_integrity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_id TEXT NOT NULL,
                    start_event_id TEXT NOT NULL,
                    end_event_id TEXT NOT NULL,
                    event_count INTEGER NOT NULL,
                    batch_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Audit statistics table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    count INTEGER NOT NULL,
                    avg_risk_score REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_events(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_events(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_events(event_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_risk ON audit_events(risk_score)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_ip ON audit_events(ip_address)")
    
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
    
    def _get_integrity_key(self) -> str:
        """Get or create integrity protection key"""
        key_file = os.path.join(os.path.dirname(self.db_path), 'audit.key')
        
        if os.path.exists(key_file):
            with open(key_file, 'r') as f:
                return f.read().strip()
        else:
            # Generate new key
            import secrets
            key = secrets.token_hex(32)
            with open(key_file, 'w') as f:
                f.write(key)
            os.chmod(key_file, 0o600)  # Restrict permissions
            return key
    
    def _calculate_integrity_hash(self, event: AuditEvent) -> str:
        """Calculate integrity hash for event"""
        data = f"{event.event_id}{event.timestamp.isoformat()}{event.event_type.value}{event.user_id}{event.action}{event.outcome}"
        return hashlib.sha256(f"{data}{self.integrity_key}".encode()).hexdigest()
    
    def store_event(self, event: AuditEvent) -> bool:
        """Store audit event with integrity protection"""
        try:
            integrity_hash = self._calculate_integrity_hash(event)
            
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO audit_events 
                    (event_id, timestamp, event_type, severity, user_id, session_id,
                     ip_address, user_agent, resource, action, outcome, details,
                     risk_score, integrity_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event.event_id,
                    event.timestamp.isoformat(),
                    event.event_type.value,
                    event.severity.value,
                    event.user_id,
                    event.session_id,
                    event.ip_address,
                    event.user_agent,
                    event.resource,
                    event.action,
                    event.outcome,
                    json.dumps(event.details),
                    event.risk_score,
                    integrity_hash
                ))
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to store audit event: {e}")
            return False
    
    def get_events(self, filters: Dict[str, Any] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get audit events with optional filtering"""
        query = "SELECT * FROM audit_events WHERE 1=1"
        params = []
        
        if filters:
            if 'start_time' in filters:
                query += " AND timestamp >= ?"
                params.append(filters['start_time'].isoformat())
            
            if 'end_time' in filters:
                query += " AND timestamp <= ?"
                params.append(filters['end_time'].isoformat())
            
            if 'user_id' in filters:
                query += " AND user_id = ?"
                params.append(filters['user_id'])
            
            if 'event_type' in filters:
                query += " AND event_type = ?"
                params.append(filters['event_type'])
            
            if 'min_risk_score' in filters:
                query += " AND risk_score >= ?"
                params.append(filters['min_risk_score'])
            
            if 'ip_address' in filters:
                query += " AND ip_address = ?"
                params.append(filters['ip_address'])
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            events = []
            
            for row in cursor.fetchall():
                event_dict = dict(row)
                if event_dict['details']:
                    event_dict['details'] = json.loads(event_dict['details'])
                events.append(event_dict)
            
            return events
    
    def verify_integrity(self, event_id: str) -> bool:
        """Verify integrity of audit event"""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT event_id, timestamp, event_type, user_id, action, outcome, integrity_hash
                FROM audit_events WHERE event_id = ?
            """, (event_id,))
            
            row = cursor.fetchone()
            if not row:
                return False
            
            # Recreate event for hash calculation
            event = AuditEvent(
                event_id=row['event_id'],
                timestamp=datetime.fromisoformat(row['timestamp']),
                event_type=AuditEventType(row['event_type']),
                severity=AuditSeverity.LOW,  # Not used in hash
                user_id=row['user_id'],
                session_id=None,  # Not used in hash
                ip_address='',  # Not used in hash
                user_agent='',  # Not used in hash
                resource='',  # Not used in hash
                action=row['action'],
                outcome=row['outcome'],
                details={},  # Not used in hash
                risk_score=0  # Not used in hash
            )
            
            expected_hash = self._calculate_integrity_hash(event)
            return expected_hash == row['integrity_hash']
    
    def get_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get audit statistics"""
        since = datetime.now() - timedelta(days=days)
        
        with self._get_connection() as conn:
            # Total events
            cursor = conn.execute("""
                SELECT COUNT(*) FROM audit_events 
                WHERE timestamp >= ?
            """, (since.isoformat(),))
            total_events = cursor.fetchone()[0]
            
            # Events by type
            cursor = conn.execute("""
                SELECT event_type, COUNT(*) as count 
                FROM audit_events 
                WHERE timestamp >= ? 
                GROUP BY event_type 
                ORDER BY count DESC
            """, (since.isoformat(),))
            events_by_type = dict(cursor.fetchall())
            
            # High-risk events
            cursor = conn.execute("""
                SELECT COUNT(*) FROM audit_events 
                WHERE timestamp >= ? AND risk_score >= 70
            """, (since.isoformat(),))
            high_risk_events = cursor.fetchone()[0]
            
            # Top users by activity
            cursor = conn.execute("""
                SELECT user_id, COUNT(*) as count 
                FROM audit_events 
                WHERE timestamp >= ? AND user_id IS NOT NULL 
                GROUP BY user_id 
                ORDER BY count DESC 
                LIMIT 10
            """, (since.isoformat(),))
            top_users = dict(cursor.fetchall())
            
            # Failed events
            cursor = conn.execute("""
                SELECT COUNT(*) FROM audit_events 
                WHERE timestamp >= ? AND outcome = 'failure'
            """, (since.isoformat(),))
            failed_events = cursor.fetchone()[0]
            
            return {
                'total_events': total_events,
                'events_by_type': events_by_type,
                'high_risk_events': high_risk_events,
                'top_users': top_users,
                'failed_events': failed_events,
                'time_period_days': days
            }

class AuditLogger:
    """Main audit logging system with async processing"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or self._default_config()
        
        # Initialize components
        self.db = AuditDatabase()
        self.risk_calculator = RiskCalculator()
        
        # Async processing
        self.event_queue = Queue()
        self.processing_thread = None
        self.running = False
        
        # File logging
        self.file_logger = None
        if self.config['file_logging']['enabled']:
            self._setup_file_logging()
        
        # Statistics
        self.stats = {
            'events_logged': 0,
            'events_processed': 0,
            'high_risk_events': 0,
            'start_time': datetime.now()
        }
        
        # Start processing
        self.start()
    
    def _default_config(self) -> Dict[str, Any]:
        """Default audit configuration"""
        return {
            'async_processing': True,
            'file_logging': {
                'enabled': True,
                'path': 'security/audit.log',
                'max_size_mb': 100,
                'backup_count': 10
            },
            'retention_days': 365,
            'high_risk_threshold': 70,
            'real_time_alerts': True
        }
    
    def _setup_file_logging(self):
        """Setup file logging for audit events"""
        from logging.handlers import RotatingFileHandler
        
        log_path = self.config['file_logging']['path']
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        
        max_bytes = self.config['file_logging']['max_size_mb'] * 1024 * 1024
        backup_count = self.config['file_logging']['backup_count']
        
        handler = RotatingFileHandler(
            log_path, maxBytes=max_bytes, backupCount=backup_count
        )
        
        formatter = logging.Formatter(
            '%(asctime)s - AUDIT - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        
        self.file_logger = logging.getLogger('audit_file')
        self.file_logger.addHandler(handler)
        self.file_logger.setLevel(logging.INFO)
    
    def start(self):
        """Start audit processing"""
        if self.config['async_processing'] and not self.running:
            self.running = True
            self.processing_thread = threading.Thread(target=self._process_events)
            self.processing_thread.daemon = True
            self.processing_thread.start()
    
    def stop(self):
        """Stop audit processing"""
        self.running = False
        if self.processing_thread:
            self.processing_thread.join(timeout=5)
    
    def _process_events(self):
        """Process audit events from queue"""
        while self.running:
            try:
                event = self.event_queue.get(timeout=1)
                
                # Store in database
                if self.db.store_event(event):
                    self.stats['events_processed'] += 1
                    
                    # File logging
                    if self.file_logger:
                        self.file_logger.info(event.to_json())
                    
                    # High-risk event handling
                    if event.risk_score >= self.config['high_risk_threshold']:
                        self.stats['high_risk_events'] += 1
                        self._handle_high_risk_event(event)
                
                self.event_queue.task_done()
                
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Error processing audit event: {e}")
    
    def _handle_high_risk_event(self, event: AuditEvent):
        """Handle high-risk audit events"""
        if self.config['real_time_alerts']:
            # In production, send alerts via email, Slack, etc.
            logger.warning(f"HIGH RISK AUDIT EVENT: {event.event_type.value} - Risk: {event.risk_score}")
    
    def log_event(self, event_type: AuditEventType, user_id: Optional[str] = None,
                  session_id: Optional[str] = None, ip_address: str = 'unknown',
                  user_agent: str = 'unknown', resource: str = 'unknown',
                  action: str = 'unknown', outcome: str = 'success',
                  details: Dict[str, Any] = None, severity: AuditSeverity = None) -> str:
        """Log audit event"""
        import uuid
        
        # Generate event ID
        event_id = str(uuid.uuid4())
        
        # Auto-determine severity if not provided
        if severity is None:
            severity = self._auto_determine_severity(event_type, outcome)
        
        # Create event
        event = AuditEvent(
            event_id=event_id,
            timestamp=datetime.now(),
            event_type=event_type,
            severity=severity,
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            resource=resource,
            action=action,
            outcome=outcome,
            details=details or {},
            risk_score=0  # Will be calculated
        )
        
        # Calculate risk score
        event.risk_score = self.risk_calculator.calculate_risk(event)
        
        # Queue for processing
        if self.config['async_processing']:
            self.event_queue.put(event)
        else:
            # Synchronous processing
            self.db.store_event(event)
            if self.file_logger:
                self.file_logger.info(event.to_json())
        
        self.stats['events_logged'] += 1
        return event_id
    
    def _auto_determine_severity(self, event_type: AuditEventType, outcome: str) -> AuditSeverity:
        """Auto-determine event severity"""
        # Critical events
        if event_type in [AuditEventType.SECURITY_VIOLATION, AuditEventType.INTRUSION_ATTEMPT]:
            return AuditSeverity.CRITICAL
        
        # High severity events
        if event_type in [AuditEventType.DATA_DELETE, AuditEventType.PERMISSION_CHANGE,
                         AuditEventType.USER_DELETE, AuditEventType.OBD_CLEAR_CODES]:
            return AuditSeverity.HIGH
        
        # Medium severity events
        if event_type in [AuditEventType.LOGIN_FAILURE, AuditEventType.ACCESS_DENIED,
                         AuditEventType.DATA_EXPORT, AuditEventType.CONFIG_CHANGE]:
            return AuditSeverity.MEDIUM
        
        # Failure outcomes increase severity
        if outcome == 'failure':
            return AuditSeverity.MEDIUM
        
        # Default to low
        return AuditSeverity.LOW
    
    def search_events(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search audit events"""
        return self.db.get_events(query.get('filters'), query.get('limit', 100))
    
    def get_user_activity(self, user_id: str, days: int = 7) -> Dict[str, Any]:
        """Get user activity summary"""
        since = datetime.now() - timedelta(days=days)
        
        filters = {
            'user_id': user_id,
            'start_time': since
        }
        
        events = self.db.get_events(filters, limit=1000)
        
        # Analyze activity
        activity_summary = {
            'total_events': len(events),
            'event_types': {},
            'risk_distribution': {'low': 0, 'medium': 0, 'high': 0, 'critical': 0},
            'daily_activity': {},
            'failed_attempts': 0
        }
        
        for event in events:
            # Count by type
            event_type = event['event_type']
            activity_summary['event_types'][event_type] = activity_summary['event_types'].get(event_type, 0) + 1
            
            # Risk distribution
            risk_score = event['risk_score']
            if risk_score >= 80:
                activity_summary['risk_distribution']['critical'] += 1
            elif risk_score >= 60:
                activity_summary['risk_distribution']['high'] += 1
            elif risk_score >= 30:
                activity_summary['risk_distribution']['medium'] += 1
            else:
                activity_summary['risk_distribution']['low'] += 1
            
            # Failed attempts
            if event['outcome'] == 'failure':
                activity_summary['failed_attempts'] += 1
            
            # Daily activity
            date = event['timestamp'][:10]  # YYYY-MM-DD
            activity_summary['daily_activity'][date] = activity_summary['daily_activity'].get(date, 0) + 1
        
        return activity_summary
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get audit system statistics"""
        db_stats = self.db.get_statistics()
        
        return {
            **self.stats,
            **db_stats,
            'queue_size': self.event_queue.qsize() if self.config['async_processing'] else 0,
            'uptime_seconds': (datetime.now() - self.stats['start_time']).total_seconds()
        }
    
    def cleanup_old_events(self, days: int = None):
        """Clean up old audit events"""
        if days is None:
            days = self.config['retention_days']
        
        cutoff = datetime.now() - timedelta(days=days)
        
        with self.db._get_connection() as conn:
            cursor = conn.execute("""
                DELETE FROM audit_events 
                WHERE timestamp < ?
            """, (cutoff.isoformat(),))
            
            deleted_count = cursor.rowcount
            logger.info(f"Cleaned up {deleted_count} old audit events")
            
            return deleted_count

# Decorator for automatic audit logging
def audit_log(event_type: AuditEventType, resource: str = None, action: str = None):
    """Decorator for automatic audit logging"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Get audit logger instance (you'd inject this properly in production)
            audit_logger = getattr(wrapper, '_audit_logger', None)
            if not audit_logger:
                return func(*args, **kwargs)
            
            # Extract context (simplified)
            user_id = kwargs.get('user_id') or getattr(args[0], 'user_id', None) if args else None
            
            try:
                result = func(*args, **kwargs)
                
                # Log successful execution
                audit_logger.log_event(
                    event_type=event_type,
                    user_id=user_id,
                    resource=resource or func.__name__,
                    action=action or func.__name__,
                    outcome='success',
                    details={'function': func.__name__, 'args_count': len(args)}
                )
                
                return result
                
            except Exception as e:
                # Log failed execution
                audit_logger.log_event(
                    event_type=event_type,
                    user_id=user_id,
                    resource=resource or func.__name__,
                    action=action or func.__name__,
                    outcome='failure',
                    details={'function': func.__name__, 'error': str(e)}
                )
                raise
        
        return wrapper
    return decorator

if __name__ == "__main__":
    # Demo usage
    print("Mercedes W222 OBD Scanner - Audit System Demo")
    print("=" * 50)
    
    # Initialize audit logger
    audit = AuditLogger()
    
    # Demo events
    print("Logging demo audit events...")
    
    # Login events
    audit.log_event(
        AuditEventType.LOGIN_SUCCESS,
        user_id="demo_user",
        ip_address="192.168.1.100",
        resource="auth_system",
        action="login",
        details={"method": "password"}
    )
    
    # OBD scan
    audit.log_event(
        AuditEventType.OBD_SCAN,
        user_id="demo_user",
        ip_address="192.168.1.100",
        resource="obd_scanner",
        action="scan_vehicle",
        details={"vehicle_id": "W222_001", "scan_type": "full"}
    )
    
    # Security violation
    audit.log_event(
        AuditEventType.SECURITY_VIOLATION,
        user_id="attacker",
        ip_address="10.0.0.1",
        resource="api_endpoint",
        action="sql_injection_attempt",
        outcome="failure",
        details={"payload": "'; DROP TABLE users; --"}
    )
    
    # Data export
    audit.log_event(
        AuditEventType.DATA_EXPORT,
        user_id="demo_user",
        ip_address="192.168.1.100",
        resource="trip_data",
        action="export_csv",
        details={"records_count": 150, "date_range": "2024-01-01 to 2024-01-31"}
    )
    
    # Wait for async processing
    import time
    time.sleep(2)
    
    # Show statistics
    print(f"\nAudit Statistics:")
    stats = audit.get_statistics()
    for key, value in stats.items():
        if isinstance(value, dict):
            print(f"{key}:")
            for k, v in value.items():
                print(f"  {k}: {v}")
        else:
            print(f"{key}: {value}")
    
    # Search high-risk events
    print(f"\nHigh-risk events:")
    high_risk_events = audit.search_events({
        'filters': {'min_risk_score': 70},
        'limit': 10
    })
    
    for event in high_risk_events:
        print(f"- {event['event_type']} (Risk: {event['risk_score']}) - {event['action']}")
    
    # User activity
    print(f"\nUser activity for demo_user:")
    activity = audit.get_user_activity("demo_user")
    print(f"Total events: {activity['total_events']}")
    print(f"Event types: {activity['event_types']}")
    print(f"Failed attempts: {activity['failed_attempts']}")
    
    # Cleanup
    audit.stop()
