#!/usr/bin/env python3
"""
Comprehensive Monitoring and Logging System for Mercedes W222 OBD Scanner
Production-ready monitoring, alerting, and observability
"""

import os
import sys
import json
import time
import psutil
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import threading
from collections import defaultdict, deque
import sqlite3
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mercedes_obd_scanner.data.database_manager import DatabaseManager

class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class MetricType(Enum):
    """Types of metrics"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"

@dataclass
class Metric:
    """Metric data structure"""
    name: str
    value: float
    metric_type: MetricType
    timestamp: datetime
    labels: Dict[str, str] = None
    
    def __post_init__(self):
        if self.labels is None:
            self.labels = {}

@dataclass
class Alert:
    """Alert data structure"""
    id: str
    level: AlertLevel
    title: str
    message: str
    timestamp: datetime
    source: str
    metadata: Dict[str, Any] = None
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class MetricsCollector:
    """Collects and stores system metrics"""
    
    def __init__(self, retention_hours: int = 24):
        self.metrics = defaultdict(lambda: deque(maxlen=1000))
        self.retention_hours = retention_hours
        self.lock = threading.Lock()
        
    def record_metric(self, metric: Metric):
        """Record a metric"""
        with self.lock:
            key = f"{metric.name}:{json.dumps(metric.labels, sort_keys=True)}"
            self.metrics[key].append(metric)
            
    def get_metrics(self, name: str, labels: Dict[str, str] = None, 
                   since: datetime = None) -> List[Metric]:
        """Get metrics by name and labels"""
        if labels is None:
            labels = {}
            
        key = f"{name}:{json.dumps(labels, sort_keys=True)}"
        
        with self.lock:
            metrics = list(self.metrics.get(key, []))
            
        if since:
            metrics = [m for m in metrics if m.timestamp >= since]
            
        return metrics
    
    def get_latest_metric(self, name: str, labels: Dict[str, str] = None) -> Optional[Metric]:
        """Get the latest metric value"""
        metrics = self.get_metrics(name, labels)
        return metrics[-1] if metrics else None
    
    def cleanup_old_metrics(self):
        """Remove old metrics beyond retention period"""
        cutoff_time = datetime.now() - timedelta(hours=self.retention_hours)
        
        with self.lock:
            for key in list(self.metrics.keys()):
                # Filter out old metrics
                self.metrics[key] = deque(
                    [m for m in self.metrics[key] if m.timestamp >= cutoff_time],
                    maxlen=1000
                )
                
                # Remove empty queues
                if not self.metrics[key]:
                    del self.metrics[key]

class SystemMonitor:
    """Monitors system resources and performance"""
    
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self.running = False
        self.monitor_thread = None
        
    def start(self, interval: int = 30):
        """Start system monitoring"""
        self.running = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval,),
            daemon=True
        )
        self.monitor_thread.start()
        
    def stop(self):
        """Stop system monitoring"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join()
            
    def _monitor_loop(self, interval: int):
        """Main monitoring loop"""
        while self.running:
            try:
                self._collect_system_metrics()
                time.sleep(interval)
            except Exception as e:
                logging.error(f"Error in system monitoring: {e}")
                time.sleep(interval)
                
    def _collect_system_metrics(self):
        """Collect system metrics"""
        now = datetime.now()
        
        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        self.metrics_collector.record_metric(Metric(
            name="system_cpu_percent",
            value=cpu_percent,
            metric_type=MetricType.GAUGE,
            timestamp=now
        ))
        
        # Memory metrics
        memory = psutil.virtual_memory()
        self.metrics_collector.record_metric(Metric(
            name="system_memory_percent",
            value=memory.percent,
            metric_type=MetricType.GAUGE,
            timestamp=now
        ))
        
        self.metrics_collector.record_metric(Metric(
            name="system_memory_available_bytes",
            value=memory.available,
            metric_type=MetricType.GAUGE,
            timestamp=now
        ))
        
        # Disk metrics
        disk = psutil.disk_usage('/')
        self.metrics_collector.record_metric(Metric(
            name="system_disk_percent",
            value=(disk.used / disk.total) * 100,
            metric_type=MetricType.GAUGE,
            timestamp=now
        ))
        
        # Network metrics
        network = psutil.net_io_counters()
        self.metrics_collector.record_metric(Metric(
            name="system_network_bytes_sent",
            value=network.bytes_sent,
            metric_type=MetricType.COUNTER,
            timestamp=now
        ))
        
        self.metrics_collector.record_metric(Metric(
            name="system_network_bytes_recv",
            value=network.bytes_recv,
            metric_type=MetricType.COUNTER,
            timestamp=now
        ))
        
        # Process metrics
        process = psutil.Process()
        self.metrics_collector.record_metric(Metric(
            name="process_memory_rss_bytes",
            value=process.memory_info().rss,
            metric_type=MetricType.GAUGE,
            timestamp=now
        ))
        
        self.metrics_collector.record_metric(Metric(
            name="process_cpu_percent",
            value=process.cpu_percent(),
            metric_type=MetricType.GAUGE,
            timestamp=now
        ))

class ApplicationMonitor:
    """Monitors application-specific metrics"""
    
    def __init__(self, metrics_collector: MetricsCollector, db_manager: DatabaseManager):
        self.metrics_collector = metrics_collector
        self.db_manager = db_manager
        self.running = False
        self.monitor_thread = None
        
    def start(self, interval: int = 60):
        """Start application monitoring"""
        self.running = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval,),
            daemon=True
        )
        self.monitor_thread.start()
        
    def stop(self):
        """Stop application monitoring"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join()
            
    def _monitor_loop(self, interval: int):
        """Main monitoring loop"""
        while self.running:
            try:
                self._collect_application_metrics()
                time.sleep(interval)
            except Exception as e:
                logging.error(f"Error in application monitoring: {e}")
                time.sleep(interval)
                
    def _collect_application_metrics(self):
        """Collect application-specific metrics"""
        now = datetime.now()
        
        try:
            # Database metrics
            stats = self.db_manager.get_database_stats()
            
            for key, value in stats.items():
                if isinstance(value, (int, float)):
                    self.metrics_collector.record_metric(Metric(
                        name=f"database_{key}",
                        value=value,
                        metric_type=MetricType.GAUGE,
                        timestamp=now
                    ))
            
            # Active sessions in last hour
            one_hour_ago = now - timedelta(hours=1)
            active_sessions = self._count_active_sessions(one_hour_ago)
            self.metrics_collector.record_metric(Metric(
                name="active_sessions_last_hour",
                value=active_sessions,
                metric_type=MetricType.GAUGE,
                timestamp=now
            ))
            
            # Recent anomalies
            recent_anomalies = self._count_recent_anomalies(one_hour_ago)
            self.metrics_collector.record_metric(Metric(
                name="anomalies_last_hour",
                value=recent_anomalies,
                metric_type=MetricType.GAUGE,
                timestamp=now
            ))
            
        except Exception as e:
            logging.error(f"Error collecting application metrics: {e}")
            
    def _count_active_sessions(self, since: datetime) -> int:
        """Count active sessions since timestamp"""
        try:
            with sqlite3.connect(self.db_manager.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COUNT(*) FROM sessions WHERE start_time >= ?",
                    (since.isoformat(),)
                )
                return cursor.fetchone()[0]
        except Exception:
            return 0
            
    def _count_recent_anomalies(self, since: datetime) -> int:
        """Count anomalies since timestamp"""
        try:
            with sqlite3.connect(self.db_manager.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COUNT(*) FROM anomaly_records WHERE timestamp >= ?",
                    (since.isoformat(),)
                )
                return cursor.fetchone()[0]
        except Exception:
            return 0

class AlertManager:
    """Manages alerts and notifications"""
    
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self.alerts = {}
        self.alert_rules = []
        self.notification_handlers = []
        self.lock = threading.Lock()
        
    def add_alert_rule(self, rule: Callable[[MetricsCollector], Optional[Alert]]):
        """Add an alert rule"""
        self.alert_rules.append(rule)
        
    def add_notification_handler(self, handler: Callable[[Alert], None]):
        """Add a notification handler"""
        self.notification_handlers.append(handler)
        
    def check_alerts(self):
        """Check all alert rules"""
        for rule in self.alert_rules:
            try:
                alert = rule(self.metrics_collector)
                if alert:
                    self._handle_alert(alert)
            except Exception as e:
                logging.error(f"Error checking alert rule: {e}")
                
    def _handle_alert(self, alert: Alert):
        """Handle a new alert"""
        with self.lock:
            existing_alert = self.alerts.get(alert.id)
            
            if existing_alert and not existing_alert.resolved:
                # Update existing alert
                existing_alert.message = alert.message
                existing_alert.timestamp = alert.timestamp
                existing_alert.metadata.update(alert.metadata)
            else:
                # New alert
                self.alerts[alert.id] = alert
                
                # Send notifications
                for handler in self.notification_handlers:
                    try:
                        handler(alert)
                    except Exception as e:
                        logging.error(f"Error sending notification: {e}")
                        
    def resolve_alert(self, alert_id: str):
        """Resolve an alert"""
        with self.lock:
            if alert_id in self.alerts:
                self.alerts[alert_id].resolved = True
                self.alerts[alert_id].resolved_at = datetime.now()
                
    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts"""
        with self.lock:
            return [alert for alert in self.alerts.values() if not alert.resolved]
            
    def get_all_alerts(self) -> List[Alert]:
        """Get all alerts"""
        with self.lock:
            return list(self.alerts.values())

class LoggingSystem:
    """Enhanced logging system with structured logging"""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        
        # Configure loggers
        self._setup_loggers()
        
    def _setup_loggers(self):
        """Setup structured logging"""
        # Main application logger
        self.app_logger = logging.getLogger('mercedes_obd_scanner')
        self.app_logger.setLevel(logging.INFO)
        
        # Security logger
        self.security_logger = logging.getLogger('security')
        self.security_logger.setLevel(logging.INFO)
        
        # Performance logger
        self.performance_logger = logging.getLogger('performance')
        self.performance_logger.setLevel(logging.INFO)
        
        # Error logger
        self.error_logger = logging.getLogger('errors')
        self.error_logger.setLevel(logging.ERROR)
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        
        json_formatter = JsonFormatter()
        
        # Add handlers
        self._add_file_handler(self.app_logger, 'application.log', detailed_formatter)
        self._add_file_handler(self.security_logger, 'security.log', json_formatter)
        self._add_file_handler(self.performance_logger, 'performance.log', json_formatter)
        self._add_file_handler(self.error_logger, 'errors.log', detailed_formatter)
        
        # Add console handler for development
        if os.getenv('ENVIRONMENT') != 'production':
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(detailed_formatter)
            self.app_logger.addHandler(console_handler)
            
    def _add_file_handler(self, logger, filename, formatter):
        """Add file handler to logger"""
        handler = logging.FileHandler(os.path.join(self.log_dir, filename))
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    def log_performance(self, operation: str, duration: float, metadata: Dict[str, Any] = None):
        """Log performance metrics"""
        if metadata is None:
            metadata = {}
            
        self.performance_logger.info(json.dumps({
            'timestamp': datetime.now().isoformat(),
            'operation': operation,
            'duration_ms': duration * 1000,
            'metadata': metadata
        }))
        
    def log_security_event(self, event_type: str, details: Dict[str, Any], level: str = "INFO"):
        """Log security events"""
        log_data = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'level': level,
            'details': details
        }
        
        getattr(self.security_logger, level.lower())(json.dumps(log_data))
        
    def log_error(self, error: Exception, context: Dict[str, Any] = None):
        """Log errors with context"""
        if context is None:
            context = {}
            
        self.error_logger.error(
            f"Error: {str(error)} | Context: {json.dumps(context)}",
            exc_info=True
        )

class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def format(self, record):
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
            
        return json.dumps(log_data)

class NotificationHandler:
    """Handles alert notifications"""
    
    def __init__(self, smtp_config: Dict[str, str] = None):
        self.smtp_config = smtp_config or {}
        
    def send_email_notification(self, alert: Alert):
        """Send email notification for alert"""
        if not self.smtp_config:
            logging.warning("SMTP not configured, skipping email notification")
            return
            
        try:
            msg = MIMEMultipart()
            msg['From'] = self.smtp_config['from_email']
            msg['To'] = self.smtp_config['to_email']
            msg['Subject'] = f"[{alert.level.value.upper()}] {alert.title}"
            
            body = f"""
            Alert: {alert.title}
            Level: {alert.level.value}
            Time: {alert.timestamp}
            Source: {alert.source}
            
            Message: {alert.message}
            
            Metadata: {json.dumps(alert.metadata, indent=2)}
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(self.smtp_config['smtp_server'], self.smtp_config['smtp_port'])
            if self.smtp_config.get('use_tls'):
                server.starttls()
            if self.smtp_config.get('username'):
                server.login(self.smtp_config['username'], self.smtp_config['password'])
                
            server.send_message(msg)
            server.quit()
            
            logging.info(f"Email notification sent for alert: {alert.id}")
            
        except Exception as e:
            logging.error(f"Failed to send email notification: {e}")
            
    def send_webhook_notification(self, alert: Alert, webhook_url: str):
        """Send webhook notification for alert"""
        try:
            import requests
            
            payload = {
                'alert_id': alert.id,
                'level': alert.level.value,
                'title': alert.title,
                'message': alert.message,
                'timestamp': alert.timestamp.isoformat(),
                'source': alert.source,
                'metadata': alert.metadata
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
            logging.info(f"Webhook notification sent for alert: {alert.id}")
            
        except Exception as e:
            logging.error(f"Failed to send webhook notification: {e}")

# Predefined alert rules
def high_cpu_alert_rule(metrics_collector: MetricsCollector) -> Optional[Alert]:
    """Alert rule for high CPU usage"""
    cpu_metric = metrics_collector.get_latest_metric("system_cpu_percent")
    
    if cpu_metric and cpu_metric.value > 80:
        return Alert(
            id="high_cpu_usage",
            level=AlertLevel.WARNING,
            title="High CPU Usage",
            message=f"CPU usage is {cpu_metric.value:.1f}%",
            timestamp=datetime.now(),
            source="system_monitor",
            metadata={"cpu_percent": cpu_metric.value}
        )
    
    return None

def high_memory_alert_rule(metrics_collector: MetricsCollector) -> Optional[Alert]:
    """Alert rule for high memory usage"""
    memory_metric = metrics_collector.get_latest_metric("system_memory_percent")
    
    if memory_metric and memory_metric.value > 85:
        return Alert(
            id="high_memory_usage",
            level=AlertLevel.WARNING,
            title="High Memory Usage",
            message=f"Memory usage is {memory_metric.value:.1f}%",
            timestamp=datetime.now(),
            source="system_monitor",
            metadata={"memory_percent": memory_metric.value}
        )
    
    return None

def disk_space_alert_rule(metrics_collector: MetricsCollector) -> Optional[Alert]:
    """Alert rule for low disk space"""
    disk_metric = metrics_collector.get_latest_metric("system_disk_percent")
    
    if disk_metric and disk_metric.value > 90:
        return Alert(
            id="low_disk_space",
            level=AlertLevel.CRITICAL,
            title="Low Disk Space",
            message=f"Disk usage is {disk_metric.value:.1f}%",
            timestamp=datetime.now(),
            source="system_monitor",
            metadata={"disk_percent": disk_metric.value}
        )
    
    return None

def anomaly_spike_alert_rule(metrics_collector: MetricsCollector) -> Optional[Alert]:
    """Alert rule for anomaly spikes"""
    anomaly_metric = metrics_collector.get_latest_metric("anomalies_last_hour")
    
    if anomaly_metric and anomaly_metric.value > 10:
        return Alert(
            id="anomaly_spike",
            level=AlertLevel.ERROR,
            title="High Number of Anomalies",
            message=f"Detected {anomaly_metric.value} anomalies in the last hour",
            timestamp=datetime.now(),
            source="application_monitor",
            metadata={"anomaly_count": anomaly_metric.value}
        )
    
    return None

class MonitoringSystem:
    """Main monitoring system orchestrator"""
    
    def __init__(self, db_manager: DatabaseManager, smtp_config: Dict[str, str] = None):
        self.db_manager = db_manager
        self.metrics_collector = MetricsCollector()
        self.system_monitor = SystemMonitor(self.metrics_collector)
        self.app_monitor = ApplicationMonitor(self.metrics_collector, db_manager)
        self.alert_manager = AlertManager(self.metrics_collector)
        self.logging_system = LoggingSystem()
        self.notification_handler = NotificationHandler(smtp_config)
        
        # Setup alert rules
        self._setup_alert_rules()
        
        # Setup notification handlers
        self._setup_notification_handlers()
        
        # Background tasks
        self.running = False
        self.cleanup_thread = None
        self.alert_thread = None
        
    def _setup_alert_rules(self):
        """Setup predefined alert rules"""
        self.alert_manager.add_alert_rule(high_cpu_alert_rule)
        self.alert_manager.add_alert_rule(high_memory_alert_rule)
        self.alert_manager.add_alert_rule(disk_space_alert_rule)
        self.alert_manager.add_alert_rule(anomaly_spike_alert_rule)
        
    def _setup_notification_handlers(self):
        """Setup notification handlers"""
        self.alert_manager.add_notification_handler(
            self.notification_handler.send_email_notification
        )
        
    def start(self):
        """Start the monitoring system"""
        logging.info("Starting monitoring system...")
        
        # Start monitors
        self.system_monitor.start(interval=30)
        self.app_monitor.start(interval=60)
        
        # Start background tasks
        self.running = True
        
        self.cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True
        )
        self.cleanup_thread.start()
        
        self.alert_thread = threading.Thread(
            target=self._alert_loop,
            daemon=True
        )
        self.alert_thread.start()
        
        logging.info("Monitoring system started")
        
    def stop(self):
        """Stop the monitoring system"""
        logging.info("Stopping monitoring system...")
        
        self.running = False
        self.system_monitor.stop()
        self.app_monitor.stop()
        
        if self.cleanup_thread:
            self.cleanup_thread.join()
        if self.alert_thread:
            self.alert_thread.join()
            
        logging.info("Monitoring system stopped")
        
    def _cleanup_loop(self):
        """Background cleanup loop"""
        while self.running:
            try:
                self.metrics_collector.cleanup_old_metrics()
                time.sleep(3600)  # Run every hour
            except Exception as e:
                logging.error(f"Error in cleanup loop: {e}")
                time.sleep(300)  # Wait 5 minutes on error
                
    def _alert_loop(self):
        """Background alert checking loop"""
        while self.running:
            try:
                self.alert_manager.check_alerts()
                time.sleep(60)  # Check every minute
            except Exception as e:
                logging.error(f"Error in alert loop: {e}")
                time.sleep(60)
                
    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status"""
        now = datetime.now()
        
        # Get latest metrics
        cpu_metric = self.metrics_collector.get_latest_metric("system_cpu_percent")
        memory_metric = self.metrics_collector.get_latest_metric("system_memory_percent")
        disk_metric = self.metrics_collector.get_latest_metric("system_disk_percent")
        
        # Get active alerts
        active_alerts = self.alert_manager.get_active_alerts()
        
        return {
            "timestamp": now.isoformat(),
            "system": {
                "cpu_percent": cpu_metric.value if cpu_metric else None,
                "memory_percent": memory_metric.value if memory_metric else None,
                "disk_percent": disk_metric.value if disk_metric else None
            },
            "alerts": {
                "active_count": len(active_alerts),
                "critical_count": len([a for a in active_alerts if a.level == AlertLevel.CRITICAL]),
                "warning_count": len([a for a in active_alerts if a.level == AlertLevel.WARNING])
            },
            "uptime": self._get_uptime()
        }
        
    def _get_uptime(self) -> str:
        """Get system uptime"""
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.readline().split()[0])
                uptime_delta = timedelta(seconds=uptime_seconds)
                return str(uptime_delta)
        except:
            return "unknown"

if __name__ == "__main__":
    # Test the monitoring system
    print("Testing monitoring system...")
    
    # Initialize components
    db_manager = DatabaseManager()
    
    # SMTP configuration (optional)
    smtp_config = {
        'smtp_server': 'smtp.gmail.com',
        'smtp_port': 587,
        'use_tls': True,
        'from_email': 'alerts@yourdomain.com',
        'to_email': 'admin@yourdomain.com',
        'username': os.getenv('SMTP_USERNAME'),
        'password': os.getenv('SMTP_PASSWORD')
    }
    
    # Create monitoring system
    monitoring = MonitoringSystem(db_manager, smtp_config)
    
    try:
        # Start monitoring
        monitoring.start()
        
        # Run for a short time to collect metrics
        print("Collecting metrics for 30 seconds...")
        time.sleep(30)
        
        # Get system status
        status = monitoring.get_system_status()
        print(f"System Status: {json.dumps(status, indent=2)}")
        
        # Get active alerts
        alerts = monitoring.alert_manager.get_active_alerts()
        print(f"Active Alerts: {len(alerts)}")
        for alert in alerts:
            print(f"  - {alert.level.value}: {alert.title}")
            
    finally:
        # Stop monitoring
        monitoring.stop()
        
    print("Monitoring system test completed.")
