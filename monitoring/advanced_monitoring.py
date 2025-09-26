#!/usr/bin/env python3
"""
Advanced Monitoring System for Mercedes W222 OBD Scanner
Enterprise-grade monitoring with distributed tracing, real-time alerting, and SLA monitoring
"""

import os
import json
import time
import uuid
import sqlite3
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from contextlib import contextmanager
from enum import Enum
import asyncio
import aiohttp
from collections import defaultdict, deque
import statistics
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class MetricType(Enum):
    """Metric types"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"

@dataclass
class Span:
    """Distributed tracing span"""
    span_id: str
    trace_id: str
    parent_span_id: Optional[str]
    operation_name: str
    service_name: str
    start_time: datetime
    end_time: Optional[datetime]
    duration_ms: Optional[float]
    tags: Dict[str, Any]
    logs: List[Dict[str, Any]]
    status: str  # success, error, timeout
    
    def finish(self, status: str = "success"):
        """Finish the span"""
        self.end_time = datetime.now()
        self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000
        self.status = status
    
    def log(self, message: str, level: str = "info", **kwargs):
        """Add log entry to span"""
        self.logs.append({
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'message': message,
            **kwargs
        })
    
    def set_tag(self, key: str, value: Any):
        """Set span tag"""
        self.tags[key] = value
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'span_id': self.span_id,
            'trace_id': self.trace_id,
            'parent_span_id': self.parent_span_id,
            'operation_name': self.operation_name,
            'service_name': self.service_name,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_ms': self.duration_ms,
            'tags': self.tags,
            'logs': self.logs,
            'status': self.status
        }

@dataclass
class Metric:
    """System metric"""
    name: str
    metric_type: MetricType
    value: float
    timestamp: datetime
    tags: Dict[str, str]
    service: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'type': self.metric_type.value,
            'value': self.value,
            'timestamp': self.timestamp.isoformat(),
            'tags': self.tags,
            'service': self.service
        }

@dataclass
class Alert:
    """System alert"""
    alert_id: str
    severity: AlertSeverity
    title: str
    description: str
    service: str
    metric_name: str
    current_value: float
    threshold: float
    timestamp: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'alert_id': self.alert_id,
            'severity': self.severity.value,
            'title': self.title,
            'description': self.description,
            'service': self.service,
            'metric_name': self.metric_name,
            'current_value': self.current_value,
            'threshold': self.threshold,
            'timestamp': self.timestamp.isoformat(),
            'resolved': self.resolved,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None
        }

class DistributedTracer:
    """Distributed tracing system"""
    
    def __init__(self):
        self.spans = {}
        self.traces = defaultdict(list)
        self.active_spans = {}  # Thread-local active spans
        self.lock = threading.Lock()
        
    def start_span(self, operation_name: str, service_name: str, 
                   parent_span: Optional[Span] = None, trace_id: str = None) -> Span:
        """Start a new span"""
        span_id = str(uuid.uuid4())
        
        if trace_id is None:
            trace_id = parent_span.trace_id if parent_span else str(uuid.uuid4())
        
        parent_span_id = parent_span.span_id if parent_span else None
        
        span = Span(
            span_id=span_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            operation_name=operation_name,
            service_name=service_name,
            start_time=datetime.now(),
            end_time=None,
            duration_ms=None,
            tags={},
            logs=[],
            status="active"
        )
        
        with self.lock:
            self.spans[span_id] = span
            self.traces[trace_id].append(span)
            
            # Set as active span for current thread
            thread_id = threading.get_ident()
            self.active_spans[thread_id] = span
        
        return span
    
    def get_active_span(self) -> Optional[Span]:
        """Get active span for current thread"""
        thread_id = threading.get_ident()
        return self.active_spans.get(thread_id)
    
    def finish_span(self, span: Span, status: str = "success"):
        """Finish a span"""
        span.finish(status)
        
        with self.lock:
            # Remove from active spans if it's the current active span
            thread_id = threading.get_ident()
            if self.active_spans.get(thread_id) == span:
                # Set parent as active if exists
                if span.parent_span_id:
                    parent_span = self.spans.get(span.parent_span_id)
                    if parent_span and parent_span.status == "active":
                        self.active_spans[thread_id] = parent_span
                    else:
                        del self.active_spans[thread_id]
                else:
                    del self.active_spans[thread_id]
    
    def get_trace(self, trace_id: str) -> List[Span]:
        """Get all spans for a trace"""
        return self.traces.get(trace_id, [])
    
    def get_trace_summary(self, trace_id: str) -> Dict[str, Any]:
        """Get trace summary with timing analysis"""
        spans = self.get_trace(trace_id)
        
        if not spans:
            return {}
        
        # Calculate trace duration
        start_times = [s.start_time for s in spans]
        end_times = [s.end_time for s in spans if s.end_time]
        
        if not end_times:
            return {'status': 'incomplete', 'span_count': len(spans)}
        
        trace_start = min(start_times)
        trace_end = max(end_times)
        total_duration = (trace_end - trace_start).total_seconds() * 1000
        
        # Service breakdown
        service_times = defaultdict(float)
        for span in spans:
            if span.duration_ms:
                service_times[span.service_name] += span.duration_ms
        
        # Error analysis
        error_spans = [s for s in spans if s.status == "error"]
        
        return {
            'trace_id': trace_id,
            'span_count': len(spans),
            'total_duration_ms': total_duration,
            'service_breakdown': dict(service_times),
            'error_count': len(error_spans),
            'status': 'error' if error_spans else 'success',
            'start_time': trace_start.isoformat(),
            'end_time': trace_end.isoformat()
        }

class MetricsCollector:
    """Metrics collection and aggregation"""
    
    def __init__(self):
        self.metrics = deque(maxlen=10000)  # Keep last 10k metrics
        self.aggregated_metrics = defaultdict(list)
        self.lock = threading.Lock()
        
        # Start aggregation thread
        self.aggregation_thread = threading.Thread(target=self._aggregate_metrics)
        self.aggregation_thread.daemon = True
        self.aggregation_thread.start()
    
    def record_metric(self, name: str, value: float, metric_type: MetricType,
                     service: str = "unknown", tags: Dict[str, str] = None):
        """Record a metric"""
        metric = Metric(
            name=name,
            metric_type=metric_type,
            value=value,
            timestamp=datetime.now(),
            tags=tags or {},
            service=service
        )
        
        with self.lock:
            self.metrics.append(metric)
    
    def increment_counter(self, name: str, service: str = "unknown", 
                         tags: Dict[str, str] = None, value: float = 1.0):
        """Increment a counter metric"""
        self.record_metric(name, value, MetricType.COUNTER, service, tags)
    
    def set_gauge(self, name: str, value: float, service: str = "unknown",
                  tags: Dict[str, str] = None):
        """Set a gauge metric"""
        self.record_metric(name, value, MetricType.GAUGE, service, tags)
    
    def record_timer(self, name: str, duration_ms: float, service: str = "unknown",
                    tags: Dict[str, str] = None):
        """Record a timer metric"""
        self.record_metric(name, duration_ms, MetricType.TIMER, service, tags)
    
    def _aggregate_metrics(self):
        """Aggregate metrics periodically"""
        while True:
            try:
                time.sleep(60)  # Aggregate every minute
                
                with self.lock:
                    # Group metrics by name and service
                    current_metrics = list(self.metrics)
                
                # Aggregate by minute
                minute_buckets = defaultdict(lambda: defaultdict(list))
                
                for metric in current_metrics:
                    minute_key = metric.timestamp.replace(second=0, microsecond=0)
                    metric_key = f"{metric.service}.{metric.name}"
                    minute_buckets[minute_key][metric_key].append(metric)
                
                # Calculate aggregations
                for minute, metric_groups in minute_buckets.items():
                    for metric_key, metrics in metric_groups.items():
                        if not metrics:
                            continue
                        
                        values = [m.value for m in metrics]
                        metric_type = metrics[0].metric_type
                        
                        aggregation = {
                            'timestamp': minute,
                            'metric_key': metric_key,
                            'type': metric_type.value,
                            'count': len(values)
                        }
                        
                        if metric_type == MetricType.COUNTER:
                            aggregation['sum'] = sum(values)
                        elif metric_type == MetricType.GAUGE:
                            aggregation['last'] = values[-1]
                            aggregation['avg'] = statistics.mean(values)
                        elif metric_type in [MetricType.TIMER, MetricType.HISTOGRAM]:
                            aggregation.update({
                                'min': min(values),
                                'max': max(values),
                                'avg': statistics.mean(values),
                                'p50': statistics.median(values),
                                'p95': self._percentile(values, 0.95),
                                'p99': self._percentile(values, 0.99)
                            })
                        
                        self.aggregated_metrics[minute].append(aggregation)
                        
            except Exception as e:
                logger.error(f"Error aggregating metrics: {e}")
    
    def _percentile(self, values: List[float], percentile: float) -> float:
        """Calculate percentile"""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile)
        return sorted_values[min(index, len(sorted_values) - 1)]
    
    def get_recent_metrics(self, service: str = None, minutes: int = 60) -> List[Dict[str, Any]]:
        """Get recent aggregated metrics"""
        since = datetime.now() - timedelta(minutes=minutes)
        
        result = []
        for timestamp, metrics in self.aggregated_metrics.items():
            if timestamp >= since:
                for metric in metrics:
                    if service is None or service in metric['metric_key']:
                        result.append(metric)
        
        return sorted(result, key=lambda x: x['timestamp'])

class AlertManager:
    """Alert management and notification system"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or self._default_config()
        self.active_alerts = {}
        self.alert_rules = []
        self.notification_channels = []
        self.lock = threading.Lock()
        
        # Setup notification channels
        self._setup_notification_channels()
        
        # Load alert rules
        self._load_alert_rules()
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            'email': {
                'enabled': False,
                'smtp_server': 'localhost',
                'smtp_port': 587,
                'username': '',
                'password': '',
                'from_address': 'alerts@mercedes-obd.com',
                'to_addresses': []
            },
            'webhook': {
                'enabled': False,
                'url': '',
                'timeout': 30
            },
            'alert_rules': [
                {
                    'name': 'High Error Rate',
                    'metric': 'error_rate',
                    'threshold': 0.05,  # 5%
                    'operator': '>',
                    'severity': 'error',
                    'window_minutes': 5
                },
                {
                    'name': 'High Response Time',
                    'metric': 'response_time_p95',
                    'threshold': 5000,  # 5 seconds
                    'operator': '>',
                    'severity': 'warning',
                    'window_minutes': 10
                },
                {
                    'name': 'Low Disk Space',
                    'metric': 'disk_usage_percent',
                    'threshold': 90,
                    'operator': '>',
                    'severity': 'critical',
                    'window_minutes': 1
                }
            ]
        }
    
    def _setup_notification_channels(self):
        """Setup notification channels"""
        if self.config['email']['enabled']:
            self.notification_channels.append(self._send_email_alert)
        
        if self.config['webhook']['enabled']:
            self.notification_channels.append(self._send_webhook_alert)
    
    def _load_alert_rules(self):
        """Load alert rules from configuration"""
        self.alert_rules = self.config.get('alert_rules', [])
    
    def check_metrics_for_alerts(self, metrics: List[Dict[str, Any]]):
        """Check metrics against alert rules"""
        for rule in self.alert_rules:
            self._evaluate_rule(rule, metrics)
    
    def _evaluate_rule(self, rule: Dict[str, Any], metrics: List[Dict[str, Any]]):
        """Evaluate a single alert rule"""
        metric_name = rule['metric']
        threshold = rule['threshold']
        operator = rule['operator']
        window_minutes = rule.get('window_minutes', 5)
        
        # Filter metrics for this rule
        since = datetime.now() - timedelta(minutes=window_minutes)
        relevant_metrics = [
            m for m in metrics
            if metric_name in m['metric_key'] and m['timestamp'] >= since
        ]
        
        if not relevant_metrics:
            return
        
        # Calculate current value (depends on metric type)
        current_value = self._calculate_metric_value(relevant_metrics, rule)
        
        # Check threshold
        alert_triggered = False
        if operator == '>':
            alert_triggered = current_value > threshold
        elif operator == '<':
            alert_triggered = current_value < threshold
        elif operator == '>=':
            alert_triggered = current_value >= threshold
        elif operator == '<=':
            alert_triggered = current_value <= threshold
        elif operator == '==':
            alert_triggered = current_value == threshold
        
        rule_key = f"{rule['name']}_{metric_name}"
        
        if alert_triggered:
            # Create or update alert
            if rule_key not in self.active_alerts:
                alert = Alert(
                    alert_id=str(uuid.uuid4()),
                    severity=AlertSeverity(rule['severity']),
                    title=rule['name'],
                    description=f"{metric_name} is {current_value} (threshold: {threshold})",
                    service=self._extract_service_from_metrics(relevant_metrics),
                    metric_name=metric_name,
                    current_value=current_value,
                    threshold=threshold,
                    timestamp=datetime.now()
                )
                
                with self.lock:
                    self.active_alerts[rule_key] = alert
                
                # Send notifications
                self._send_alert_notifications(alert)
                
        else:
            # Resolve alert if it exists
            if rule_key in self.active_alerts:
                with self.lock:
                    alert = self.active_alerts[rule_key]
                    alert.resolved = True
                    alert.resolved_at = datetime.now()
                
                # Send resolution notification
                self._send_resolution_notifications(alert)
                
                # Remove from active alerts
                with self.lock:
                    del self.active_alerts[rule_key]
    
    def _calculate_metric_value(self, metrics: List[Dict[str, Any]], rule: Dict[str, Any]) -> float:
        """Calculate current metric value for rule evaluation"""
        if not metrics:
            return 0.0
        
        # Use the most recent aggregated value
        latest_metric = max(metrics, key=lambda x: x['timestamp'])
        
        # Return appropriate aggregated value
        if 'avg' in latest_metric:
            return latest_metric['avg']
        elif 'last' in latest_metric:
            return latest_metric['last']
        elif 'sum' in latest_metric:
            return latest_metric['sum']
        elif 'p95' in latest_metric:
            return latest_metric['p95']
        else:
            return 0.0
    
    def _extract_service_from_metrics(self, metrics: List[Dict[str, Any]]) -> str:
        """Extract service name from metrics"""
        if metrics:
            metric_key = metrics[0]['metric_key']
            return metric_key.split('.')[0] if '.' in metric_key else 'unknown'
        return 'unknown'
    
    def _send_alert_notifications(self, alert: Alert):
        """Send alert notifications through all channels"""
        for channel in self.notification_channels:
            try:
                channel(alert)
            except Exception as e:
                logger.error(f"Failed to send alert notification: {e}")
    
    def _send_resolution_notifications(self, alert: Alert):
        """Send alert resolution notifications"""
        for channel in self.notification_channels:
            try:
                channel(alert, resolved=True)
            except Exception as e:
                logger.error(f"Failed to send resolution notification: {e}")
    
    def _send_email_alert(self, alert: Alert, resolved: bool = False):
        """Send email alert notification"""
        if not self.config['email']['enabled']:
            return
        
        subject = f"{'RESOLVED: ' if resolved else ''}{alert.severity.value.upper()}: {alert.title}"
        
        body = f"""
Alert Details:
- Service: {alert.service}
- Metric: {alert.metric_name}
- Current Value: {alert.current_value}
- Threshold: {alert.threshold}
- Severity: {alert.severity.value}
- Time: {alert.timestamp}

Description: {alert.description}
        """
        
        msg = MIMEMultipart()
        msg['From'] = self.config['email']['from_address']
        msg['To'] = ', '.join(self.config['email']['to_addresses'])
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email (simplified - in production use proper SMTP)
        logger.info(f"[EMAIL ALERT] {subject}")
        logger.info(f"[EMAIL BODY] {body}")
    
    def _send_webhook_alert(self, alert: Alert, resolved: bool = False):
        """Send webhook alert notification"""
        if not self.config['webhook']['enabled']:
            return
        
        payload = {
            'alert_id': alert.alert_id,
            'severity': alert.severity.value,
            'title': alert.title,
            'description': alert.description,
            'service': alert.service,
            'metric_name': alert.metric_name,
            'current_value': alert.current_value,
            'threshold': alert.threshold,
            'timestamp': alert.timestamp.isoformat(),
            'resolved': resolved
        }
        
        # Send webhook (simplified - in production use proper HTTP client)
        logger.info(f"[WEBHOOK ALERT] {json.dumps(payload)}")
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts"""
        with self.lock:
            return list(self.active_alerts.values())
    
    def get_alert_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get alert history (would be stored in database in production)"""
        # In production, this would query a database
        return []

class SLAMonitor:
    """SLA/SLO monitoring system"""
    
    def __init__(self):
        self.sla_targets = {
            'availability': 99.9,  # 99.9% uptime
            'response_time_p95': 2000,  # 95th percentile < 2s
            'error_rate': 0.01,  # < 1% error rate
            'obd_scan_success_rate': 99.0  # 99% OBD scan success
        }
        
        self.sla_measurements = defaultdict(list)
        self.lock = threading.Lock()
    
    def record_measurement(self, sla_name: str, value: float, timestamp: datetime = None):
        """Record SLA measurement"""
        if timestamp is None:
            timestamp = datetime.now()
        
        with self.lock:
            self.sla_measurements[sla_name].append({
                'value': value,
                'timestamp': timestamp
            })
            
            # Keep only last 24 hours
            cutoff = datetime.now() - timedelta(hours=24)
            self.sla_measurements[sla_name] = [
                m for m in self.sla_measurements[sla_name]
                if m['timestamp'] >= cutoff
            ]
    
    def get_sla_status(self) -> Dict[str, Any]:
        """Get current SLA status"""
        status = {}
        
        for sla_name, target in self.sla_targets.items():
            measurements = self.sla_measurements.get(sla_name, [])
            
            if not measurements:
                status[sla_name] = {
                    'target': target,
                    'current': None,
                    'status': 'no_data',
                    'breach': False
                }
                continue
            
            # Calculate current value
            values = [m['value'] for m in measurements]
            
            if sla_name == 'availability':
                # Availability is percentage of successful measurements
                current = (sum(1 for v in values if v > 0) / len(values)) * 100
            elif 'rate' in sla_name:
                # Rates are averages
                current = statistics.mean(values)
            else:
                # Response times use 95th percentile
                current = self._percentile(values, 0.95)
            
            # Check if SLA is breached
            if sla_name == 'availability' or 'success_rate' in sla_name:
                breach = current < target
            else:
                breach = current > target
            
            status[sla_name] = {
                'target': target,
                'current': current,
                'status': 'breach' if breach else 'ok',
                'breach': breach,
                'measurement_count': len(measurements)
            }
        
        return status
    
    def _percentile(self, values: List[float], percentile: float) -> float:
        """Calculate percentile"""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile)
        return sorted_values[min(index, len(sorted_values) - 1)]

class AdvancedMonitoringSystem:
    """Main advanced monitoring system"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Initialize components
        self.tracer = DistributedTracer()
        self.metrics = MetricsCollector()
        self.alerts = AlertManager(self.config.get('alerts', {}))
        self.sla_monitor = SLAMonitor()
        
        # Start monitoring loop
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
        
        # Statistics
        self.stats = {
            'spans_created': 0,
            'metrics_recorded': 0,
            'alerts_triggered': 0,
            'start_time': datetime.now()
        }
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        while True:
            try:
                time.sleep(60)  # Check every minute
                
                # Get recent metrics
                recent_metrics = self.metrics.get_recent_metrics(minutes=10)
                
                # Check for alerts
                self.alerts.check_metrics_for_alerts(recent_metrics)
                
                # Update SLA measurements
                self._update_sla_measurements(recent_metrics)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
    
    def _update_sla_measurements(self, metrics: List[Dict[str, Any]]):
        """Update SLA measurements from metrics"""
        for metric in metrics:
            metric_key = metric['metric_key']
            
            # Map metrics to SLA measurements
            if 'response_time' in metric_key and 'p95' in metric:
                self.sla_monitor.record_measurement('response_time_p95', metric['p95'])
            
            elif 'error_rate' in metric_key and 'avg' in metric:
                self.sla_monitor.record_measurement('error_rate', metric['avg'])
            
            elif 'availability' in metric_key and 'last' in metric:
                self.sla_monitor.record_measurement('availability', metric['last'])
            
            elif 'obd_scan_success' in metric_key and 'avg' in metric:
                self.sla_monitor.record_measurement('obd_scan_success_rate', metric['avg'])
    
    def start_trace(self, operation_name: str, service_name: str) -> Span:
        """Start a new trace"""
        span = self.tracer.start_span(operation_name, service_name)
        self.stats['spans_created'] += 1
        return span
    
    def start_span(self, operation_name: str, service_name: str, parent_span: Span = None) -> Span:
        """Start a new span"""
        if parent_span is None:
            parent_span = self.tracer.get_active_span()
        
        span = self.tracer.start_span(operation_name, service_name, parent_span)
        self.stats['spans_created'] += 1
        return span
    
    def finish_span(self, span: Span, status: str = "success"):
        """Finish a span"""
        self.tracer.finish_span(span, status)
        
        # Record metrics from span
        if span.duration_ms:
            self.metrics.record_timer(
                f"{span.service_name}.{span.operation_name}.duration",
                span.duration_ms,
                span.service_name,
                {'status': status}
            )
    
    def record_metric(self, name: str, value: float, metric_type: MetricType,
                     service: str = "unknown", tags: Dict[str, str] = None):
        """Record a metric"""
        self.metrics.record_metric(name, value, metric_type, service, tags)
        self.stats['metrics_recorded'] += 1
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get data for monitoring dashboard"""
        return {
            'system_stats': self.stats,
            'active_alerts': [alert.to_dict() for alert in self.alerts.get_active_alerts()],
            'sla_status': self.sla_monitor.get_sla_status(),
            'recent_metrics': self.metrics.get_recent_metrics(minutes=60),
            'trace_summary': self._get_recent_trace_summary()
        }
    
    def _get_recent_trace_summary(self) -> Dict[str, Any]:
        """Get summary of recent traces"""
        # Get traces from last hour
        recent_traces = {}
        cutoff = datetime.now() - timedelta(hours=1)
        
        for trace_id, spans in self.tracer.traces.items():
            if any(span.start_time >= cutoff for span in spans):
                recent_traces[trace_id] = self.tracer.get_trace_summary(trace_id)
        
        if not recent_traces:
            return {'trace_count': 0}
        
        # Calculate summary statistics
        durations = [t['total_duration_ms'] for t in recent_traces.values() if 'total_duration_ms' in t]
        error_count = sum(1 for t in recent_traces.values() if t.get('status') == 'error')
        
        return {
            'trace_count': len(recent_traces),
            'avg_duration_ms': statistics.mean(durations) if durations else 0,
            'error_rate': error_count / len(recent_traces) if recent_traces else 0,
            'slowest_traces': sorted(recent_traces.values(), 
                                   key=lambda x: x.get('total_duration_ms', 0), 
                                   reverse=True)[:5]
        }

# Context manager for automatic span management
class traced_operation:
    """Context manager for automatic span tracing"""
    
    def __init__(self, monitoring_system: AdvancedMonitoringSystem, 
                 operation_name: str, service_name: str):
        self.monitoring = monitoring_system
        self.operation_name = operation_name
        self.service_name = service_name
        self.span = None
    
    def __enter__(self) -> Span:
        self.span = self.monitoring.start_span(self.operation_name, self.service_name)
        return self.span
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.span:
            status = "error" if exc_type else "success"
            self.monitoring.finish_span(self.span, status)

if __name__ == "__main__":
    # Demo usage
    print("Mercedes W222 OBD Scanner - Advanced Monitoring Demo")
    print("=" * 60)
    
    # Initialize monitoring
    monitoring = AdvancedMonitoringSystem()
    
    # Demo: Trace a complex operation
    print("1. Tracing complex operation...")
    
    # Start main trace
    main_span = monitoring.start_trace("obd_scan_operation", "obd_service")
    main_span.set_tag("vehicle_id", "W222_001")
    main_span.set_tag("scan_type", "full")
    
    # Simulate sub-operations
    time.sleep(0.1)
    
    # Database operation
    with traced_operation(monitoring, "load_vehicle_profile", "database_service") as db_span:
        db_span.set_tag("query_type", "select")
        time.sleep(0.05)
    
    # OBD communication
    with traced_operation(monitoring, "connect_obd", "obd_service") as obd_span:
        obd_span.set_tag("port", "COM3")
        time.sleep(0.2)
        
        # Nested operation
        with traced_operation(monitoring, "read_dtc_codes", "obd_service") as dtc_span:
            dtc_span.set_tag("code_count", 3)
            time.sleep(0.1)
    
    # AI analysis
    with traced_operation(monitoring, "analyze_codes", "ai_service") as ai_span:
        ai_span.set_tag("model", "claude-3")
        time.sleep(0.3)
    
    monitoring.finish_span(main_span)
    
    # Demo: Record metrics
    print("2. Recording metrics...")
    
    monitoring.record_metric("obd_scan_duration", 650, MetricType.TIMER, "obd_service")
    monitoring.record_metric("error_rate", 0.02, MetricType.GAUGE, "api_service")
    monitoring.record_metric("active_connections", 15, MetricType.GAUGE, "system")
    monitoring.record_metric("requests_total", 1, MetricType.COUNTER, "api_service")
    
    # Wait for processing
    time.sleep(2)
    
    # Demo: Get dashboard data
    print("3. Dashboard data:")
    dashboard = monitoring.get_dashboard_data()
    
    print(f"System stats: {dashboard['system_stats']}")
    print(f"Active alerts: {len(dashboard['active_alerts'])}")
    print(f"SLA status: {dashboard['sla_status']}")
    print(f"Recent traces: {dashboard['trace_summary']['trace_count']}")
    
    # Demo: Trace summary
    trace_id = main_span.trace_id
    trace_summary = monitoring.tracer.get_trace_summary(trace_id)
    print(f"\nTrace summary for {trace_id}:")
    print(f"- Duration: {trace_summary['total_duration_ms']:.2f}ms")
    print(f"- Spans: {trace_summary['span_count']}")
    print(f"- Services: {list(trace_summary['service_breakdown'].keys())}")
    print(f"- Status: {trace_summary['status']}")
    
    print("\nAdvanced monitoring system ready! 🚀")
