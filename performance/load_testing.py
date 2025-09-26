#!/usr/bin/env python3
"""
Performance Optimization and Load Testing for Mercedes W222 OBD Scanner
Production-ready performance testing and optimization tools
"""

import os
import sys
import time
import json
import asyncio
import threading
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import sqlite3
import requests
import psutil
from contextlib import contextmanager

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mercedes_obd_scanner.data.database_manager import DatabaseManager
from mercedes_obd_scanner.core.obd_controller import OBDController
from mercedes_obd_scanner.ml.inference.enhanced_anomaly_detector import EnhancedAnomalyDetector

@dataclass
class PerformanceMetric:
    """Performance metric data structure"""
    operation: str
    duration: float
    timestamp: datetime
    success: bool
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass
class LoadTestResult:
    """Load test result data structure"""
    test_name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    p95_response_time: float
    p99_response_time: float
    requests_per_second: float
    start_time: datetime
    end_time: datetime
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []

class PerformanceProfiler:
    """Performance profiling utilities"""
    
    def __init__(self):
        self.metrics = []
        self.lock = threading.Lock()
        
    @contextmanager
    def profile_operation(self, operation_name: str, metadata: Dict[str, Any] = None):
        """Context manager for profiling operations"""
        start_time = time.time()
        success = True
        error = None
        
        try:
            yield
        except Exception as e:
            success = False
            error = str(e)
            raise
        finally:
            duration = time.time() - start_time
            
            metric = PerformanceMetric(
                operation=operation_name,
                duration=duration,
                timestamp=datetime.now(),
                success=success,
                metadata=metadata or {}
            )
            
            if error:
                metric.metadata['error'] = error
                
            with self.lock:
                self.metrics.append(metric)
                
    def get_metrics(self, operation: str = None, since: datetime = None) -> List[PerformanceMetric]:
        """Get performance metrics"""
        with self.lock:
            metrics = self.metrics.copy()
            
        if operation:
            metrics = [m for m in metrics if m.operation == operation]
            
        if since:
            metrics = [m for m in metrics if m.timestamp >= since]
            
        return metrics
    
    def get_operation_stats(self, operation: str) -> Dict[str, Any]:
        """Get statistics for an operation"""
        metrics = self.get_metrics(operation)
        
        if not metrics:
            return {}
            
        durations = [m.duration for m in metrics if m.success]
        success_count = len([m for m in metrics if m.success])
        total_count = len(metrics)
        
        if not durations:
            return {
                'operation': operation,
                'total_calls': total_count,
                'successful_calls': success_count,
                'success_rate': 0.0
            }
        
        return {
            'operation': operation,
            'total_calls': total_count,
            'successful_calls': success_count,
            'success_rate': success_count / total_count,
            'avg_duration': statistics.mean(durations),
            'min_duration': min(durations),
            'max_duration': max(durations),
            'median_duration': statistics.median(durations),
            'p95_duration': self._percentile(durations, 95),
            'p99_duration': self._percentile(durations, 99)
        }
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def clear_metrics(self):
        """Clear all metrics"""
        with self.lock:
            self.metrics.clear()

class DatabasePerformanceTester:
    """Database performance testing"""
    
    def __init__(self, db_manager: DatabaseManager, profiler: PerformanceProfiler):
        self.db_manager = db_manager
        self.profiler = profiler
        
    def test_database_operations(self, num_operations: int = 1000) -> Dict[str, Any]:
        """Test database operation performance"""
        results = {}
        
        # Test session creation
        with self.profiler.profile_operation("db_create_session"):
            for i in range(num_operations // 10):  # Fewer sessions
                session_id = self.db_manager.create_session(
                    user_id=f"test_user_{i % 10}",
                    device_id=f"test_device_{i % 5}"
                )
                
        # Test parameter logging
        test_data = {
            'ENGINE_RPM': 2500 + (i % 1000),
            'VEHICLE_SPEED': 60 + (i % 40),
            'ENGINE_COOLANT_TEMP': 90 + (i % 20),
            'INTAKE_MANIFOLD_PRESSURE': 100 + (i % 50)
        }
        
        with self.profiler.profile_operation("db_log_parameters"):
            for i in range(num_operations):
                self.db_manager.log_obd_parameters(
                    session_id="test_session",
                    parameters=test_data
                )
                
        # Test anomaly logging
        with self.profiler.profile_operation("db_log_anomaly"):
            for i in range(num_operations // 20):  # Fewer anomalies
                self.db_manager.log_anomaly(
                    session_id="test_session",
                    anomaly_type="test_anomaly",
                    severity=0.5 + (i % 5) * 0.1,
                    description=f"Test anomaly {i}",
                    affected_parameters=["ENGINE_RPM", "VEHICLE_SPEED"]
                )
                
        # Test data retrieval
        with self.profiler.profile_operation("db_get_session_data"):
            for i in range(num_operations // 50):  # Fewer retrievals
                data = self.db_manager.get_session_data("test_session")
                
        # Collect results
        operations = ["db_create_session", "db_log_parameters", "db_log_anomaly", "db_get_session_data"]
        for operation in operations:
            results[operation] = self.profiler.get_operation_stats(operation)
            
        return results

class MLPerformanceTester:
    """Machine learning performance testing"""
    
    def __init__(self, profiler: PerformanceProfiler):
        self.profiler = profiler
        
    def test_anomaly_detection(self, num_samples: int = 1000) -> Dict[str, Any]:
        """Test anomaly detection performance"""
        detector = EnhancedAnomalyDetector()
        
        # Generate test data
        test_samples = []
        for i in range(num_samples):
            sample = {
                'ENGINE_RPM': 2000 + (i % 2000),
                'VEHICLE_SPEED': 50 + (i % 50),
                'ENGINE_COOLANT_TEMP': 85 + (i % 30),
                'INTAKE_MANIFOLD_PRESSURE': 95 + (i % 40),
                'FUEL_PRESSURE': 300 + (i % 100)
            }
            test_samples.append(sample)
            
        # Test individual predictions
        with self.profiler.profile_operation("ml_anomaly_detection_single"):
            for sample in test_samples[:100]:  # Test subset for single predictions
                try:
                    result = detector.detect_anomalies(sample)
                except Exception as e:
                    # Handle cases where detector isn't trained
                    pass
                    
        # Test batch predictions
        with self.profiler.profile_operation("ml_anomaly_detection_batch"):
            try:
                results = []
                for sample in test_samples:
                    result = detector.detect_anomalies(sample)
                    results.append(result)
            except Exception as e:
                # Handle cases where detector isn't trained
                pass
                
        return {
            'single_prediction': self.profiler.get_operation_stats("ml_anomaly_detection_single"),
            'batch_prediction': self.profiler.get_operation_stats("ml_anomaly_detection_batch")
        }

class WebAPILoadTester:
    """Web API load testing"""
    
    def __init__(self, base_url: str, profiler: PerformanceProfiler):
        self.base_url = base_url
        self.profiler = profiler
        
    def test_endpoint(self, endpoint: str, method: str = "GET", 
                     data: Dict[str, Any] = None, headers: Dict[str, str] = None,
                     concurrent_users: int = 10, requests_per_user: int = 100) -> LoadTestResult:
        """Load test a specific endpoint"""
        
        url = f"{self.base_url}{endpoint}"
        start_time = datetime.now()
        
        results = []
        errors = []
        
        def make_request(user_id: int) -> List[float]:
            """Make requests for a single user"""
            user_times = []
            
            for i in range(requests_per_user):
                request_start = time.time()
                success = True
                
                try:
                    if method.upper() == "GET":
                        response = requests.get(url, headers=headers, timeout=10)
                    elif method.upper() == "POST":
                        response = requests.post(url, json=data, headers=headers, timeout=10)
                    elif method.upper() == "PUT":
                        response = requests.put(url, json=data, headers=headers, timeout=10)
                    else:
                        raise ValueError(f"Unsupported method: {method}")
                        
                    response.raise_for_status()
                    
                except Exception as e:
                    success = False
                    errors.append(f"User {user_id}, Request {i}: {str(e)}")
                    
                duration = time.time() - request_start
                user_times.append((duration, success))
                
                # Small delay to avoid overwhelming the server
                time.sleep(0.01)
                
            return user_times
        
        # Run concurrent load test
        with ThreadPoolExecutor(max_workers=concurrent_users) as executor:
            futures = [executor.submit(make_request, user_id) for user_id in range(concurrent_users)]
            
            for future in as_completed(futures):
                try:
                    user_results = future.result()
                    results.extend(user_results)
                except Exception as e:
                    errors.append(f"Thread error: {str(e)}")
                    
        end_time = datetime.now()
        
        # Calculate statistics
        successful_times = [duration for duration, success in results if success]
        total_requests = len(results)
        successful_requests = len(successful_times)
        failed_requests = total_requests - successful_requests
        
        if successful_times:
            avg_response_time = statistics.mean(successful_times)
            min_response_time = min(successful_times)
            max_response_time = max(successful_times)
            p95_response_time = self._percentile(successful_times, 95)
            p99_response_time = self._percentile(successful_times, 99)
        else:
            avg_response_time = min_response_time = max_response_time = 0
            p95_response_time = p99_response_time = 0
            
        total_duration = (end_time - start_time).total_seconds()
        requests_per_second = successful_requests / total_duration if total_duration > 0 else 0
        
        return LoadTestResult(
            test_name=f"{method} {endpoint}",
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            avg_response_time=avg_response_time,
            min_response_time=min_response_time,
            max_response_time=max_response_time,
            p95_response_time=p95_response_time,
            p99_response_time=p99_response_time,
            requests_per_second=requests_per_second,
            start_time=start_time,
            end_time=end_time,
            errors=errors[:100]  # Limit error list
        )
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]

class SystemResourceMonitor:
    """Monitor system resources during testing"""
    
    def __init__(self):
        self.monitoring = False
        self.metrics = []
        self.monitor_thread = None
        
    def start_monitoring(self, interval: float = 1.0):
        """Start resource monitoring"""
        self.monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval,),
            daemon=True
        )
        self.monitor_thread.start()
        
    def stop_monitoring(self):
        """Stop resource monitoring"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join()
            
    def _monitor_loop(self, interval: float):
        """Resource monitoring loop"""
        while self.monitoring:
            try:
                timestamp = datetime.now()
                
                # CPU and memory
                cpu_percent = psutil.cpu_percent()
                memory = psutil.virtual_memory()
                
                # Disk I/O
                disk_io = psutil.disk_io_counters()
                
                # Network I/O
                network_io = psutil.net_io_counters()
                
                metric = {
                    'timestamp': timestamp.isoformat(),
                    'cpu_percent': cpu_percent,
                    'memory_percent': memory.percent,
                    'memory_available_mb': memory.available / (1024 * 1024),
                    'disk_read_mb': disk_io.read_bytes / (1024 * 1024) if disk_io else 0,
                    'disk_write_mb': disk_io.write_bytes / (1024 * 1024) if disk_io else 0,
                    'network_sent_mb': network_io.bytes_sent / (1024 * 1024) if network_io else 0,
                    'network_recv_mb': network_io.bytes_recv / (1024 * 1024) if network_io else 0
                }
                
                self.metrics.append(metric)
                
                time.sleep(interval)
                
            except Exception as e:
                print(f"Error in resource monitoring: {e}")
                time.sleep(interval)
                
    def get_resource_summary(self) -> Dict[str, Any]:
        """Get resource usage summary"""
        if not self.metrics:
            return {}
            
        cpu_values = [m['cpu_percent'] for m in self.metrics]
        memory_values = [m['memory_percent'] for m in self.metrics]
        
        return {
            'duration_seconds': len(self.metrics),
            'cpu': {
                'avg': statistics.mean(cpu_values),
                'max': max(cpu_values),
                'min': min(cpu_values)
            },
            'memory': {
                'avg': statistics.mean(memory_values),
                'max': max(memory_values),
                'min': min(memory_values)
            },
            'samples': len(self.metrics)
        }

class PerformanceOptimizer:
    """Performance optimization recommendations"""
    
    @staticmethod
    def analyze_database_performance(db_results: Dict[str, Any]) -> List[str]:
        """Analyze database performance and provide recommendations"""
        recommendations = []
        
        for operation, stats in db_results.items():
            if not stats:
                continue
                
            avg_duration = stats.get('avg_duration', 0)
            success_rate = stats.get('success_rate', 1.0)
            
            # Check for slow operations
            if operation == 'db_log_parameters' and avg_duration > 0.01:  # 10ms
                recommendations.append(
                    f"Parameter logging is slow ({avg_duration*1000:.1f}ms avg). "
                    "Consider batch inserts or database indexing."
                )
                
            if operation == 'db_get_session_data' and avg_duration > 0.1:  # 100ms
                recommendations.append(
                    f"Session data retrieval is slow ({avg_duration*1000:.1f}ms avg). "
                    "Consider adding database indexes or query optimization."
                )
                
            # Check success rates
            if success_rate < 0.95:
                recommendations.append(
                    f"Low success rate for {operation} ({success_rate*100:.1f}%). "
                    "Check for database connection issues or constraint violations."
                )
                
        return recommendations
    
    @staticmethod
    def analyze_api_performance(api_results: LoadTestResult) -> List[str]:
        """Analyze API performance and provide recommendations"""
        recommendations = []
        
        # Check response times
        if api_results.avg_response_time > 1.0:  # 1 second
            recommendations.append(
                f"High average response time ({api_results.avg_response_time:.2f}s). "
                "Consider caching, database optimization, or scaling."
            )
            
        if api_results.p95_response_time > 2.0:  # 2 seconds
            recommendations.append(
                f"High P95 response time ({api_results.p95_response_time:.2f}s). "
                "Some requests are very slow - investigate bottlenecks."
            )
            
        # Check success rate
        success_rate = api_results.successful_requests / api_results.total_requests
        if success_rate < 0.95:
            recommendations.append(
                f"Low success rate ({success_rate*100:.1f}%). "
                "Check for errors, timeouts, or resource constraints."
            )
            
        # Check throughput
        if api_results.requests_per_second < 10:
            recommendations.append(
                f"Low throughput ({api_results.requests_per_second:.1f} req/s). "
                "Consider horizontal scaling or performance optimization."
            )
            
        return recommendations
    
    @staticmethod
    def analyze_system_resources(resource_summary: Dict[str, Any]) -> List[str]:
        """Analyze system resource usage and provide recommendations"""
        recommendations = []
        
        if not resource_summary:
            return recommendations
            
        cpu_stats = resource_summary.get('cpu', {})
        memory_stats = resource_summary.get('memory', {})
        
        # CPU analysis
        if cpu_stats.get('avg', 0) > 80:
            recommendations.append(
                f"High average CPU usage ({cpu_stats['avg']:.1f}%). "
                "Consider CPU optimization or scaling."
            )
            
        if cpu_stats.get('max', 0) > 95:
            recommendations.append(
                f"CPU usage peaked at {cpu_stats['max']:.1f}%. "
                "System may be CPU-bound during peak load."
            )
            
        # Memory analysis
        if memory_stats.get('avg', 0) > 85:
            recommendations.append(
                f"High average memory usage ({memory_stats['avg']:.1f}%). "
                "Consider memory optimization or increasing available RAM."
            )
            
        if memory_stats.get('max', 0) > 95:
            recommendations.append(
                f"Memory usage peaked at {memory_stats['max']:.1f}%. "
                "Risk of out-of-memory errors during peak load."
            )
            
        return recommendations

class PerformanceTestSuite:
    """Complete performance test suite"""
    
    def __init__(self, db_manager: DatabaseManager, api_base_url: str = None):
        self.db_manager = db_manager
        self.api_base_url = api_base_url
        self.profiler = PerformanceProfiler()
        self.resource_monitor = SystemResourceMonitor()
        
    def run_comprehensive_tests(self) -> Dict[str, Any]:
        """Run comprehensive performance tests"""
        print("Starting comprehensive performance tests...")
        
        # Start resource monitoring
        self.resource_monitor.start_monitoring()
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'tests': {}
        }
        
        try:
            # Database performance tests
            print("Testing database performance...")
            db_tester = DatabasePerformanceTester(self.db_manager, self.profiler)
            results['tests']['database'] = db_tester.test_database_operations(1000)
            
            # ML performance tests
            print("Testing ML performance...")
            ml_tester = MLPerformanceTester(self.profiler)
            results['tests']['machine_learning'] = ml_tester.test_anomaly_detection(500)
            
            # API load tests (if API URL provided)
            if self.api_base_url:
                print("Testing API performance...")
                api_tester = WebAPILoadTester(self.api_base_url, self.profiler)
                
                # Test health endpoint
                health_result = api_tester.test_endpoint(
                    "/health", "GET", 
                    concurrent_users=5, requests_per_user=20
                )
                results['tests']['api_health'] = asdict(health_result)
                
        except Exception as e:
            print(f"Error during testing: {e}")
            results['error'] = str(e)
            
        finally:
            # Stop resource monitoring
            self.resource_monitor.stop_monitoring()
            
        # Get resource summary
        results['system_resources'] = self.resource_monitor.get_resource_summary()
        
        # Generate recommendations
        recommendations = []
        
        if 'database' in results['tests']:
            recommendations.extend(
                PerformanceOptimizer.analyze_database_performance(results['tests']['database'])
            )
            
        if 'api_health' in results['tests']:
            api_result = LoadTestResult(**results['tests']['api_health'])
            recommendations.extend(
                PerformanceOptimizer.analyze_api_performance(api_result)
            )
            
        recommendations.extend(
            PerformanceOptimizer.analyze_system_resources(results['system_resources'])
        )
        
        results['recommendations'] = recommendations
        
        return results
    
    def save_results(self, results: Dict[str, Any], filename: str = None):
        """Save test results to file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"performance_test_results_{timestamp}.json"
            
        os.makedirs("performance/results", exist_ok=True)
        filepath = os.path.join("performance/results", filename)
        
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2, default=str)
            
        print(f"Results saved to: {filepath}")
        return filepath

def print_test_summary(results: Dict[str, Any]):
    """Print a summary of test results"""
    print("\n" + "="*60)
    print("PERFORMANCE TEST SUMMARY")
    print("="*60)
    
    # Database results
    if 'database' in results.get('tests', {}):
        print("\nDatabase Performance:")
        for operation, stats in results['tests']['database'].items():
            if stats and 'avg_duration' in stats:
                print(f"  {operation}: {stats['avg_duration']*1000:.1f}ms avg, "
                      f"{stats['success_rate']*100:.1f}% success")
                      
    # ML results
    if 'machine_learning' in results.get('tests', {}):
        print("\nMachine Learning Performance:")
        ml_results = results['tests']['machine_learning']
        for test_type, stats in ml_results.items():
            if stats and 'avg_duration' in stats:
                print(f"  {test_type}: {stats['avg_duration']*1000:.1f}ms avg")
                
    # API results
    if 'api_health' in results.get('tests', {}):
        api_result = results['tests']['api_health']
        print(f"\nAPI Performance:")
        print(f"  Health endpoint: {api_result['avg_response_time']*1000:.1f}ms avg, "
              f"{api_result['requests_per_second']:.1f} req/s")
              
    # System resources
    if 'system_resources' in results:
        resources = results['system_resources']
        if resources:
            print(f"\nSystem Resources:")
            if 'cpu' in resources:
                print(f"  CPU: {resources['cpu']['avg']:.1f}% avg, "
                      f"{resources['cpu']['max']:.1f}% max")
            if 'memory' in resources:
                print(f"  Memory: {resources['memory']['avg']:.1f}% avg, "
                      f"{resources['memory']['max']:.1f}% max")
                      
    # Recommendations
    if 'recommendations' in results and results['recommendations']:
        print(f"\nRecommendations:")
        for i, rec in enumerate(results['recommendations'], 1):
            print(f"  {i}. {rec}")
    else:
        print(f"\nNo performance issues detected!")
        
    print("\n" + "="*60)

if __name__ == "__main__":
    # Run performance tests
    print("Mercedes W222 OBD Scanner - Performance Testing")
    print("=" * 50)
    
    try:
        # Initialize database manager
        db_manager = DatabaseManager()
        
        # Create test suite
        test_suite = PerformanceTestSuite(
            db_manager=db_manager,
            api_base_url="http://localhost:8000"  # Adjust as needed
        )
        
        # Run tests
        results = test_suite.run_comprehensive_tests()
        
        # Print summary
        print_test_summary(results)
        
        # Save results
        results_file = test_suite.save_results(results)
        
        print(f"\nDetailed results saved to: {results_file}")
        
    except Exception as e:
        print(f"Error running performance tests: {e}")
        import traceback
        traceback.print_exc()
