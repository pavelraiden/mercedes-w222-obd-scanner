#!/usr/bin/env python3
"""
Scalability Infrastructure Manager for Mercedes W222 OBD Scanner
Enterprise-grade auto-scaling, load balancing, caching, and performance optimization
"""

import os
import json
import time
import redis
import sqlite3
import logging
import threading
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from contextlib import contextmanager
from enum import Enum
import asyncio
import aiohttp
import psutil
from collections import defaultdict, deque
import statistics
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ScalingAction(Enum):
    """Auto-scaling actions"""
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    MAINTAIN = "maintain"

class HealthStatus(Enum):
    """Health check status"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"

@dataclass
class ServiceInstance:
    """Service instance information"""
    instance_id: str
    service_name: str
    host: str
    port: int
    status: HealthStatus
    cpu_usage: float
    memory_usage: float
    request_count: int
    response_time_avg: float
    last_health_check: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'instance_id': self.instance_id,
            'service_name': self.service_name,
            'host': self.host,
            'port': self.port,
            'status': self.status.value,
            'cpu_usage': self.cpu_usage,
            'memory_usage': self.memory_usage,
            'request_count': self.request_count,
            'response_time_avg': self.response_time_avg,
            'last_health_check': self.last_health_check.isoformat()
        }

@dataclass
class ScalingRule:
    """Auto-scaling rule configuration"""
    rule_id: str
    service_name: str
    metric_name: str
    threshold_up: float
    threshold_down: float
    min_instances: int
    max_instances: int
    cooldown_seconds: int
    enabled: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class CacheManager:
    """Distributed caching system"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.redis_client = None
        self.local_cache = {}
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0
        }
        
        # Initialize Redis if configured
        if config.get('redis', {}).get('enabled', False):
            try:
                self.redis_client = redis.Redis(
                    host=config['redis'].get('host', 'localhost'),
                    port=config['redis'].get('port', 6379),
                    db=config['redis'].get('db', 0),
                    decode_responses=True
                )
                # Test connection
                self.redis_client.ping()
                logger.info("Redis cache connected successfully")
            except Exception as e:
                logger.warning(f"Redis connection failed, using local cache: {e}")
                self.redis_client = None
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache"""
        try:
            # Try Redis first
            if self.redis_client:
                value = self.redis_client.get(key)
                if value is not None:
                    self.cache_stats['hits'] += 1
                    return json.loads(value)
            
            # Try local cache
            if key in self.local_cache:
                entry = self.local_cache[key]
                if entry['expires'] > datetime.now():
                    self.cache_stats['hits'] += 1
                    return entry['value']
                else:
                    del self.local_cache[key]
            
            self.cache_stats['misses'] += 1
            return default
            
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            self.cache_stats['misses'] += 1
            return default
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache"""
        try:
            # Set in Redis
            if self.redis_client:
                self.redis_client.setex(key, ttl, json.dumps(value))
            
            # Set in local cache
            self.local_cache[key] = {
                'value': value,
                'expires': datetime.now() + timedelta(seconds=ttl)
            }
            
            self.cache_stats['sets'] += 1
            return True
            
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete value from cache"""
        try:
            # Delete from Redis
            if self.redis_client:
                self.redis_client.delete(key)
            
            # Delete from local cache
            if key in self.local_cache:
                del self.local_cache[key]
            
            self.cache_stats['deletes'] += 1
            return True
            
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False
    
    def clear(self) -> bool:
        """Clear all cache"""
        try:
            if self.redis_client:
                self.redis_client.flushdb()
            
            self.local_cache.clear()
            return True
            
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.cache_stats['hits'] + self.cache_stats['misses']
        hit_rate = (self.cache_stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            **self.cache_stats,
            'hit_rate_percent': hit_rate,
            'local_cache_size': len(self.local_cache),
            'redis_connected': self.redis_client is not None
        }

class DatabaseConnectionPool:
    """Database connection pooling"""
    
    def __init__(self, db_path: str, pool_size: int = 10):
        self.db_path = db_path
        self.pool_size = pool_size
        self.connections = deque()
        self.active_connections = set()
        self.lock = threading.Lock()
        
        # Initialize connection pool
        self._initialize_pool()
        
        # Statistics
        self.stats = {
            'total_connections': 0,
            'active_connections': 0,
            'pool_hits': 0,
            'pool_misses': 0
        }
    
    def _initialize_pool(self):
        """Initialize connection pool"""
        for _ in range(self.pool_size):
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self.connections.append(conn)
    
    @contextmanager
    def get_connection(self):
        """Get connection from pool"""
        conn = None
        try:
            with self.lock:
                if self.connections:
                    conn = self.connections.popleft()
                    self.active_connections.add(conn)
                    self.stats['pool_hits'] += 1
                else:
                    # Create new connection if pool is empty
                    conn = sqlite3.connect(self.db_path, check_same_thread=False)
                    conn.row_factory = sqlite3.Row
                    self.active_connections.add(conn)
                    self.stats['pool_misses'] += 1
                
                self.stats['active_connections'] = len(self.active_connections)
            
            yield conn
            
        finally:
            if conn:
                with self.lock:
                    self.active_connections.discard(conn)
                    if len(self.connections) < self.pool_size:
                        self.connections.append(conn)
                    else:
                        conn.close()
                    
                    self.stats['active_connections'] = len(self.active_connections)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics"""
        with self.lock:
            return {
                **self.stats,
                'pool_size': len(self.connections),
                'max_pool_size': self.pool_size
            }
    
    def close_all(self):
        """Close all connections"""
        with self.lock:
            # Close pooled connections
            while self.connections:
                conn = self.connections.popleft()
                conn.close()
            
            # Close active connections
            for conn in list(self.active_connections):
                conn.close()
            
            self.active_connections.clear()

class LoadBalancer:
    """Load balancer for service instances"""
    
    def __init__(self):
        self.services = defaultdict(list)
        self.round_robin_counters = defaultdict(int)
        self.lock = threading.Lock()
        
        # Load balancing algorithms
        self.algorithms = {
            'round_robin': self._round_robin,
            'least_connections': self._least_connections,
            'weighted_response_time': self._weighted_response_time,
            'health_aware': self._health_aware
        }
    
    def register_instance(self, instance: ServiceInstance):
        """Register service instance"""
        with self.lock:
            # Remove existing instance with same ID
            self.services[instance.service_name] = [
                inst for inst in self.services[instance.service_name]
                if inst.instance_id != instance.instance_id
            ]
            
            # Add new instance
            self.services[instance.service_name].append(instance)
            
        logger.info(f"Registered instance: {instance.service_name}:{instance.instance_id}")
    
    def unregister_instance(self, service_name: str, instance_id: str):
        """Unregister service instance"""
        with self.lock:
            self.services[service_name] = [
                inst for inst in self.services[service_name]
                if inst.instance_id != instance_id
            ]
        
        logger.info(f"Unregistered instance: {service_name}:{instance_id}")
    
    def get_instance(self, service_name: str, algorithm: str = 'health_aware') -> Optional[ServiceInstance]:
        """Get service instance using load balancing algorithm"""
        with self.lock:
            instances = self.services.get(service_name, [])
            
            if not instances:
                return None
            
            # Use specified algorithm
            if algorithm in self.algorithms:
                return self.algorithms[algorithm](instances)
            else:
                return self._round_robin(instances)
    
    def _round_robin(self, instances: List[ServiceInstance]) -> ServiceInstance:
        """Round-robin load balancing"""
        if not instances:
            return None
        
        service_name = instances[0].service_name
        counter = self.round_robin_counters[service_name]
        instance = instances[counter % len(instances)]
        self.round_robin_counters[service_name] = (counter + 1) % len(instances)
        
        return instance
    
    def _least_connections(self, instances: List[ServiceInstance]) -> ServiceInstance:
        """Least connections load balancing"""
        if not instances:
            return None
        
        return min(instances, key=lambda x: x.request_count)
    
    def _weighted_response_time(self, instances: List[ServiceInstance]) -> ServiceInstance:
        """Weighted response time load balancing"""
        if not instances:
            return None
        
        # Choose instance with lowest response time
        return min(instances, key=lambda x: x.response_time_avg)
    
    def _health_aware(self, instances: List[ServiceInstance]) -> ServiceInstance:
        """Health-aware load balancing"""
        if not instances:
            return None
        
        # Filter healthy instances
        healthy_instances = [inst for inst in instances if inst.status == HealthStatus.HEALTHY]
        
        if healthy_instances:
            return self._weighted_response_time(healthy_instances)
        
        # If no healthy instances, try degraded ones
        degraded_instances = [inst for inst in instances if inst.status == HealthStatus.DEGRADED]
        
        if degraded_instances:
            return self._weighted_response_time(degraded_instances)
        
        # Last resort: any instance
        return instances[0]
    
    def get_service_stats(self, service_name: str) -> Dict[str, Any]:
        """Get service statistics"""
        with self.lock:
            instances = self.services.get(service_name, [])
            
            if not instances:
                return {'instance_count': 0}
            
            total_requests = sum(inst.request_count for inst in instances)
            avg_response_time = statistics.mean([inst.response_time_avg for inst in instances])
            healthy_count = sum(1 for inst in instances if inst.status == HealthStatus.HEALTHY)
            
            return {
                'instance_count': len(instances),
                'healthy_instances': healthy_count,
                'total_requests': total_requests,
                'avg_response_time': avg_response_time,
                'instances': [inst.to_dict() for inst in instances]
            }

class HealthChecker:
    """Health checking system for service instances"""
    
    def __init__(self, load_balancer: LoadBalancer):
        self.load_balancer = load_balancer
        self.health_check_interval = 30  # seconds
        self.timeout = 5  # seconds
        self.running = False
        self.health_check_thread = None
    
    def start(self):
        """Start health checking"""
        if not self.running:
            self.running = True
            self.health_check_thread = threading.Thread(target=self._health_check_loop)
            self.health_check_thread.daemon = True
            self.health_check_thread.start()
            logger.info("Health checker started")
    
    def stop(self):
        """Stop health checking"""
        self.running = False
        if self.health_check_thread:
            self.health_check_thread.join(timeout=5)
        logger.info("Health checker stopped")
    
    def _health_check_loop(self):
        """Main health check loop"""
        while self.running:
            try:
                self._check_all_instances()
                time.sleep(self.health_check_interval)
            except Exception as e:
                logger.error(f"Health check error: {e}")
    
    def _check_all_instances(self):
        """Check health of all registered instances"""
        for service_name, instances in self.load_balancer.services.items():
            for instance in instances:
                self._check_instance_health(instance)
    
    def _check_instance_health(self, instance: ServiceInstance):
        """Check health of a single instance"""
        try:
            # Simple HTTP health check
            import urllib.request
            import urllib.error
            
            health_url = f"http://{instance.host}:{instance.port}/health"
            
            start_time = time.time()
            
            try:
                with urllib.request.urlopen(health_url, timeout=self.timeout) as response:
                    if response.status == 200:
                        instance.status = HealthStatus.HEALTHY
                    else:
                        instance.status = HealthStatus.DEGRADED
                
                # Update response time
                response_time = (time.time() - start_time) * 1000
                instance.response_time_avg = (instance.response_time_avg + response_time) / 2
                
            except urllib.error.URLError:
                instance.status = HealthStatus.UNHEALTHY
            
            # Update system metrics
            instance.cpu_usage = psutil.cpu_percent()
            instance.memory_usage = psutil.virtual_memory().percent
            instance.last_health_check = datetime.now()
            
        except Exception as e:
            logger.error(f"Health check failed for {instance.instance_id}: {e}")
            instance.status = HealthStatus.UNKNOWN

class AutoScaler:
    """Auto-scaling system"""
    
    def __init__(self, load_balancer: LoadBalancer):
        self.load_balancer = load_balancer
        self.scaling_rules = {}
        self.scaling_history = []
        self.last_scaling_action = {}
        self.running = False
        self.scaling_thread = None
    
    def add_scaling_rule(self, rule: ScalingRule):
        """Add auto-scaling rule"""
        self.scaling_rules[rule.rule_id] = rule
        logger.info(f"Added scaling rule: {rule.service_name} - {rule.metric_name}")
    
    def remove_scaling_rule(self, rule_id: str):
        """Remove auto-scaling rule"""
        if rule_id in self.scaling_rules:
            del self.scaling_rules[rule_id]
            logger.info(f"Removed scaling rule: {rule_id}")
    
    def start(self):
        """Start auto-scaling"""
        if not self.running:
            self.running = True
            self.scaling_thread = threading.Thread(target=self._scaling_loop)
            self.scaling_thread.daemon = True
            self.scaling_thread.start()
            logger.info("Auto-scaler started")
    
    def stop(self):
        """Stop auto-scaling"""
        self.running = False
        if self.scaling_thread:
            self.scaling_thread.join(timeout=5)
        logger.info("Auto-scaler stopped")
    
    def _scaling_loop(self):
        """Main scaling loop"""
        while self.running:
            try:
                for rule in self.scaling_rules.values():
                    if rule.enabled:
                        self._evaluate_scaling_rule(rule)
                
                time.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Auto-scaling error: {e}")
    
    def _evaluate_scaling_rule(self, rule: ScalingRule):
        """Evaluate scaling rule and take action if needed"""
        # Get current instances
        instances = self.load_balancer.services.get(rule.service_name, [])
        current_count = len(instances)
        
        if current_count == 0:
            return
        
        # Calculate metric value
        metric_value = self._calculate_metric_value(instances, rule.metric_name)
        
        # Determine scaling action
        action = ScalingAction.MAINTAIN
        
        if metric_value > rule.threshold_up and current_count < rule.max_instances:
            action = ScalingAction.SCALE_UP
        elif metric_value < rule.threshold_down and current_count > rule.min_instances:
            action = ScalingAction.SCALE_DOWN
        
        # Check cooldown period
        last_action_time = self.last_scaling_action.get(rule.service_name)
        if last_action_time:
            time_since_last = (datetime.now() - last_action_time).total_seconds()
            if time_since_last < rule.cooldown_seconds:
                return  # Still in cooldown
        
        # Execute scaling action
        if action != ScalingAction.MAINTAIN:
            self._execute_scaling_action(rule, action, metric_value)
    
    def _calculate_metric_value(self, instances: List[ServiceInstance], metric_name: str) -> float:
        """Calculate metric value for scaling decision"""
        if not instances:
            return 0.0
        
        if metric_name == 'cpu_usage':
            return statistics.mean([inst.cpu_usage for inst in instances])
        elif metric_name == 'memory_usage':
            return statistics.mean([inst.memory_usage for inst in instances])
        elif metric_name == 'response_time':
            return statistics.mean([inst.response_time_avg for inst in instances])
        elif metric_name == 'request_rate':
            return sum(inst.request_count for inst in instances) / len(instances)
        else:
            return 0.0
    
    def _execute_scaling_action(self, rule: ScalingRule, action: ScalingAction, metric_value: float):
        """Execute scaling action"""
        logger.info(f"Scaling action: {action.value} for {rule.service_name} (metric: {metric_value})")
        
        # Record scaling action
        scaling_record = {
            'timestamp': datetime.now(),
            'service_name': rule.service_name,
            'action': action.value,
            'metric_name': rule.metric_name,
            'metric_value': metric_value,
            'threshold': rule.threshold_up if action == ScalingAction.SCALE_UP else rule.threshold_down
        }
        
        self.scaling_history.append(scaling_record)
        self.last_scaling_action[rule.service_name] = datetime.now()
        
        # In production, this would trigger actual instance creation/termination
        # For demo, we just log the action
        if action == ScalingAction.SCALE_UP:
            logger.info(f"Would scale up {rule.service_name} (add 1 instance)")
        elif action == ScalingAction.SCALE_DOWN:
            logger.info(f"Would scale down {rule.service_name} (remove 1 instance)")
    
    def get_scaling_history(self, service_name: str = None, hours: int = 24) -> List[Dict[str, Any]]:
        """Get scaling history"""
        since = datetime.now() - timedelta(hours=hours)
        
        history = [
            record for record in self.scaling_history
            if record['timestamp'] >= since and (service_name is None or record['service_name'] == service_name)
        ]
        
        # Convert datetime objects to strings
        for record in history:
            record['timestamp'] = record['timestamp'].isoformat()
        
        return history

class PerformanceOptimizer:
    """Performance optimization tools"""
    
    def __init__(self):
        self.optimization_rules = []
        self.performance_metrics = deque(maxlen=1000)
        self.optimization_history = []
    
    def add_optimization_rule(self, rule: Dict[str, Any]):
        """Add performance optimization rule"""
        self.optimization_rules.append(rule)
    
    def record_performance_metric(self, metric: Dict[str, Any]):
        """Record performance metric"""
        metric['timestamp'] = datetime.now()
        self.performance_metrics.append(metric)
    
    def analyze_performance(self) -> Dict[str, Any]:
        """Analyze performance and suggest optimizations"""
        if not self.performance_metrics:
            return {'recommendations': []}
        
        recommendations = []
        
        # Analyze response times
        response_times = [m.get('response_time', 0) for m in self.performance_metrics if 'response_time' in m]
        if response_times:
            avg_response_time = statistics.mean(response_times)
            p95_response_time = self._percentile(response_times, 0.95)
            
            if avg_response_time > 1000:  # > 1 second
                recommendations.append({
                    'type': 'performance',
                    'severity': 'high',
                    'message': f'High average response time: {avg_response_time:.2f}ms',
                    'suggestion': 'Consider adding caching or optimizing database queries'
                })
            
            if p95_response_time > 5000:  # > 5 seconds
                recommendations.append({
                    'type': 'performance',
                    'severity': 'critical',
                    'message': f'Very high P95 response time: {p95_response_time:.2f}ms',
                    'suggestion': 'Immediate optimization required - check for slow queries or blocking operations'
                })
        
        # Analyze error rates
        error_rates = [m.get('error_rate', 0) for m in self.performance_metrics if 'error_rate' in m]
        if error_rates:
            avg_error_rate = statistics.mean(error_rates)
            
            if avg_error_rate > 0.05:  # > 5%
                recommendations.append({
                    'type': 'reliability',
                    'severity': 'high',
                    'message': f'High error rate: {avg_error_rate:.2%}',
                    'suggestion': 'Investigate error causes and implement circuit breakers'
                })
        
        # Analyze resource usage
        cpu_usage = [m.get('cpu_usage', 0) for m in self.performance_metrics if 'cpu_usage' in m]
        if cpu_usage:
            avg_cpu = statistics.mean(cpu_usage)
            
            if avg_cpu > 80:  # > 80%
                recommendations.append({
                    'type': 'scaling',
                    'severity': 'medium',
                    'message': f'High CPU usage: {avg_cpu:.1f}%',
                    'suggestion': 'Consider scaling up or optimizing CPU-intensive operations'
                })
        
        memory_usage = [m.get('memory_usage', 0) for m in self.performance_metrics if 'memory_usage' in m]
        if memory_usage:
            avg_memory = statistics.mean(memory_usage)
            
            if avg_memory > 85:  # > 85%
                recommendations.append({
                    'type': 'scaling',
                    'severity': 'high',
                    'message': f'High memory usage: {avg_memory:.1f}%',
                    'suggestion': 'Check for memory leaks or consider adding more memory'
                })
        
        return {
            'recommendations': recommendations,
            'metrics_analyzed': len(self.performance_metrics),
            'analysis_timestamp': datetime.now().isoformat()
        }
    
    def _percentile(self, values: List[float], percentile: float) -> float:
        """Calculate percentile"""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile)
        return sorted_values[min(index, len(sorted_values) - 1)]

class ScalabilityManager:
    """Main scalability infrastructure manager"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or self._default_config()
        
        # Initialize components
        self.cache_manager = CacheManager(self.config.get('cache', {}))
        self.db_pool = DatabaseConnectionPool(
            self.config.get('database', {}).get('path', 'data/mercedes_obd.db'),
            self.config.get('database', {}).get('pool_size', 10)
        )
        self.load_balancer = LoadBalancer()
        self.health_checker = HealthChecker(self.load_balancer)
        self.auto_scaler = AutoScaler(self.load_balancer)
        self.performance_optimizer = PerformanceOptimizer()
        
        # Setup default scaling rules
        self._setup_default_scaling_rules()
        
        # Start services
        self.health_checker.start()
        self.auto_scaler.start()
        
        # Statistics
        self.stats = {
            'requests_processed': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'scaling_actions': 0,
            'start_time': datetime.now()
        }
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            'cache': {
                'redis': {
                    'enabled': False,
                    'host': 'localhost',
                    'port': 6379,
                    'db': 0
                }
            },
            'database': {
                'path': 'data/mercedes_obd.db',
                'pool_size': 10
            },
            'auto_scaling': {
                'enabled': True,
                'check_interval': 60,
                'cooldown_period': 300
            }
        }
    
    def _setup_default_scaling_rules(self):
        """Setup default auto-scaling rules"""
        # Web service scaling rule
        web_rule = ScalingRule(
            rule_id="web_service_cpu",
            service_name="web_service",
            metric_name="cpu_usage",
            threshold_up=70.0,
            threshold_down=30.0,
            min_instances=2,
            max_instances=10,
            cooldown_seconds=300,
            enabled=True
        )
        self.auto_scaler.add_scaling_rule(web_rule)
        
        # API service scaling rule
        api_rule = ScalingRule(
            rule_id="api_service_response_time",
            service_name="api_service",
            metric_name="response_time",
            threshold_up=2000.0,  # 2 seconds
            threshold_down=500.0,  # 0.5 seconds
            min_instances=1,
            max_instances=5,
            cooldown_seconds=180,
            enabled=True
        )
        self.auto_scaler.add_scaling_rule(api_rule)
    
    def register_service_instance(self, service_name: str, host: str, port: int) -> str:
        """Register new service instance"""
        import uuid
        
        instance_id = str(uuid.uuid4())
        
        instance = ServiceInstance(
            instance_id=instance_id,
            service_name=service_name,
            host=host,
            port=port,
            status=HealthStatus.UNKNOWN,
            cpu_usage=0.0,
            memory_usage=0.0,
            request_count=0,
            response_time_avg=0.0,
            last_health_check=datetime.now()
        )
        
        self.load_balancer.register_instance(instance)
        return instance_id
    
    def get_service_instance(self, service_name: str, algorithm: str = 'health_aware') -> Optional[ServiceInstance]:
        """Get service instance for load balancing"""
        instance = self.load_balancer.get_instance(service_name, algorithm)
        
        if instance:
            # Update request count
            instance.request_count += 1
            self.stats['requests_processed'] += 1
        
        return instance
    
    def cache_get(self, key: str, default: Any = None) -> Any:
        """Get value from cache"""
        value = self.cache_manager.get(key, default)
        
        if value != default:
            self.stats['cache_hits'] += 1
        else:
            self.stats['cache_misses'] += 1
        
        return value
    
    def cache_set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache"""
        return self.cache_manager.set(key, value, ttl)
    
    def get_database_connection(self):
        """Get database connection from pool"""
        return self.db_pool.get_connection()
    
    def record_performance_metric(self, **kwargs):
        """Record performance metric"""
        self.performance_optimizer.record_performance_metric(kwargs)
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        return {
            'scalability_stats': self.stats,
            'cache_stats': self.cache_manager.get_stats(),
            'database_pool_stats': self.db_pool.get_stats(),
            'load_balancer_stats': {
                service: self.load_balancer.get_service_stats(service)
                for service in self.load_balancer.services.keys()
            },
            'scaling_history': self.auto_scaler.get_scaling_history(hours=24),
            'performance_analysis': self.performance_optimizer.analyze_performance(),
            'uptime_seconds': (datetime.now() - self.stats['start_time']).total_seconds()
        }
    
    def optimize_performance(self) -> Dict[str, Any]:
        """Run performance optimization analysis"""
        return self.performance_optimizer.analyze_performance()
    
    def shutdown(self):
        """Shutdown scalability manager"""
        self.health_checker.stop()
        self.auto_scaler.stop()
        self.db_pool.close_all()
        logger.info("Scalability manager shutdown complete")

# Decorators for caching and performance monitoring
def cached(ttl: int = 3600, key_prefix: str = ""):
    """Decorator for automatic caching"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Generate cache key
            import hashlib
            key_data = f"{key_prefix}{func.__name__}{str(args)}{str(sorted(kwargs.items()))}"
            cache_key = hashlib.md5(key_data.encode()).hexdigest()
            
            # Try to get from cache (would need access to scalability manager)
            # For demo, just execute function
            return func(*args, **kwargs)
        
        return wrapper
    return decorator

def performance_monitored(service_name: str = "unknown"):
    """Decorator for automatic performance monitoring"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                status = 'success'
                return result
            except Exception as e:
                status = 'error'
                raise
            finally:
                duration = (time.time() - start_time) * 1000
                
                # Record performance metric (would need access to scalability manager)
                # For demo, just log
                logger.info(f"Performance: {func.__name__} took {duration:.2f}ms - {status}")
        
        return wrapper
    return decorator

if __name__ == "__main__":
    # Demo usage
    print("Mercedes W222 OBD Scanner - Scalability Infrastructure Demo")
    print("=" * 70)
    
    # Initialize scalability manager
    scalability = ScalabilityManager()
    
    # Demo: Register service instances
    print("1. Registering service instances...")
    
    web_instance1 = scalability.register_service_instance("web_service", "192.168.1.10", 8000)
    web_instance2 = scalability.register_service_instance("web_service", "192.168.1.11", 8000)
    api_instance1 = scalability.register_service_instance("api_service", "192.168.1.20", 8080)
    
    print(f"  Registered web instances: {web_instance1[:8]}, {web_instance2[:8]}")
    print(f"  Registered API instance: {api_instance1[:8]}")
    
    # Demo: Load balancing
    print(f"\n2. Load balancing requests...")
    
    for i in range(5):
        instance = scalability.get_service_instance("web_service")
        if instance:
            print(f"  Request {i+1} -> {instance.host}:{instance.port}")
    
    # Demo: Caching
    print(f"\n3. Caching operations...")
    
    # Set cache values
    scalability.cache_set("user_profile_123", {"name": "John Doe", "vehicle": "W222"})
    scalability.cache_set("obd_scan_results", {"dtc_codes": ["P0001", "P0002"]})
    
    # Get cache values
    profile = scalability.cache_get("user_profile_123")
    scan_results = scalability.cache_get("obd_scan_results")
    missing_value = scalability.cache_get("non_existent_key", "default")
    
    print(f"  Cached profile: {profile}")
    print(f"  Cached scan results: {scan_results}")
    print(f"  Missing value: {missing_value}")
    
    # Demo: Performance monitoring
    print(f"\n4. Performance monitoring...")
    
    # Record some performance metrics
    scalability.record_performance_metric(
        response_time=150,
        cpu_usage=45.2,
        memory_usage=62.1,
        error_rate=0.02
    )
    
    scalability.record_performance_metric(
        response_time=2500,  # High response time
        cpu_usage=85.5,      # High CPU
        memory_usage=78.3,
        error_rate=0.08      # High error rate
    )
    
    # Get performance analysis
    analysis = scalability.optimize_performance()
    print(f"  Performance recommendations: {len(analysis['recommendations'])}")
    
    for rec in analysis['recommendations']:
        print(f"    - {rec['severity'].upper()}: {rec['message']}")
        print(f"      Suggestion: {rec['suggestion']}")
    
    # Demo: System status
    print(f"\n5. System status:")
    status = scalability.get_system_status()
    
    print(f"  Requests processed: {status['scalability_stats']['requests_processed']}")
    print(f"  Cache hit rate: {status['cache_stats']['hit_rate_percent']:.1f}%")
    print(f"  DB pool size: {status['database_pool_stats']['pool_size']}")
    print(f"  Active services: {len(status['load_balancer_stats'])}")
    
    # Show load balancer stats
    for service, stats in status['load_balancer_stats'].items():
        print(f"  {service}: {stats['instance_count']} instances, {stats['healthy_instances']} healthy")
    
    # Wait a bit for health checks
    print(f"\n6. Waiting for health checks...")
    time.sleep(3)
    
    # Show updated status
    status = scalability.get_system_status()
    print(f"  Health checks completed")
    
    # Cleanup
    scalability.shutdown()
    
    print(f"\nScalability infrastructure ready! 🚀")
