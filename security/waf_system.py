#!/usr/bin/env python3
"""
Web Application Firewall (WAF) System for Mercedes W222 OBD Scanner
Enterprise-grade security protection against web attacks
"""

import os
import re
import json
import time
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import ipaddress
from urllib.parse import unquote, parse_qs
import sqlite3
import threading
from contextlib import contextmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SecurityEvent:
    """Security event data structure"""
    timestamp: datetime
    ip_address: str
    user_agent: str
    request_path: str
    attack_type: str
    severity: str
    blocked: bool
    details: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'request_path': self.request_path,
            'attack_type': self.attack_type,
            'severity': self.severity,
            'blocked': self.blocked,
            'details': self.details
        }

class RateLimiter:
    """Advanced rate limiting with multiple strategies"""
    
    def __init__(self):
        self.requests = defaultdict(deque)
        self.blocked_ips = {}
        self.lock = threading.Lock()
        
        # Rate limiting rules
        self.rules = {
            'global': {'requests': 1000, 'window': 3600},  # 1000 req/hour
            'per_ip': {'requests': 100, 'window': 3600},   # 100 req/hour per IP
            'auth': {'requests': 10, 'window': 900},       # 10 auth attempts per 15min
            'api': {'requests': 500, 'window': 3600}       # 500 API calls per hour
        }
        
    def is_allowed(self, ip_address: str, endpoint_type: str = 'global') -> Tuple[bool, Dict[str, Any]]:
        """Check if request is allowed based on rate limiting rules"""
        with self.lock:
            current_time = time.time()
            
            # Check if IP is temporarily blocked
            if ip_address in self.blocked_ips:
                if current_time < self.blocked_ips[ip_address]:
                    return False, {
                        'reason': 'ip_blocked',
                        'blocked_until': self.blocked_ips[ip_address]
                    }
                else:
                    del self.blocked_ips[ip_address]
            
            # Get rate limiting rule
            rule = self.rules.get(endpoint_type, self.rules['global'])
            window = rule['window']
            max_requests = rule['requests']
            
            # Clean old requests
            key = f"{ip_address}:{endpoint_type}"
            request_times = self.requests[key]
            
            while request_times and request_times[0] < current_time - window:
                request_times.popleft()
            
            # Check if limit exceeded
            if len(request_times) >= max_requests:
                # Block IP for 1 hour
                self.blocked_ips[ip_address] = current_time + 3600
                return False, {
                    'reason': 'rate_limit_exceeded',
                    'requests_in_window': len(request_times),
                    'max_requests': max_requests,
                    'window_seconds': window
                }
            
            # Add current request
            request_times.append(current_time)
            
            return True, {
                'requests_in_window': len(request_times),
                'max_requests': max_requests,
                'window_seconds': window
            }

class AttackDetector:
    """Advanced attack detection system"""
    
    def __init__(self):
        self.sql_injection_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)",
            r"(\b(OR|AND)\s+\d+\s*=\s*\d+)",
            r"(\b(OR|AND)\s+['\"]?\w+['\"]?\s*=\s*['\"]?\w+['\"]?)",
            r"(--|#|/\*|\*/)",
            r"(\bUNION\s+SELECT\b)",
            r"(\b(INFORMATION_SCHEMA|SYSOBJECTS|SYSCOLUMNS)\b)"
        ]
        
        self.xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
            r"<iframe[^>]*>",
            r"<object[^>]*>",
            r"<embed[^>]*>",
            r"<link[^>]*>",
            r"<meta[^>]*>",
            r"eval\s*\(",
            r"document\.(cookie|domain|location)"
        ]
        
        self.path_traversal_patterns = [
            r"\.\./",
            r"\.\.\\",
            r"%2e%2e%2f",
            r"%2e%2e%5c",
            r"\.\.%2f",
            r"\.\.%5c"
        ]
        
        self.command_injection_patterns = [
            r"[;&|`]",
            r"\$\(",
            r"``",
            r"\|\s*(cat|ls|pwd|whoami|id|uname)",
            r"(nc|netcat|wget|curl)\s+"
        ]
        
        # Compile patterns for performance
        self.compiled_patterns = {
            'sql_injection': [re.compile(p, re.IGNORECASE) for p in self.sql_injection_patterns],
            'xss': [re.compile(p, re.IGNORECASE) for p in self.xss_patterns],
            'path_traversal': [re.compile(p, re.IGNORECASE) for p in self.path_traversal_patterns],
            'command_injection': [re.compile(p, re.IGNORECASE) for p in self.command_injection_patterns]
        }
        
    def detect_attacks(self, request_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect various types of attacks in request data"""
        attacks = []
        
        # Combine all request data for analysis
        analysis_data = []
        
        # URL path
        if 'path' in request_data:
            analysis_data.append(('path', request_data['path']))
            
        # Query parameters
        if 'query_params' in request_data:
            for key, values in request_data['query_params'].items():
                for value in values:
                    analysis_data.append(('query_param', f"{key}={value}"))
                    
        # POST data
        if 'post_data' in request_data:
            if isinstance(request_data['post_data'], dict):
                for key, value in request_data['post_data'].items():
                    analysis_data.append(('post_data', f"{key}={value}"))
            else:
                analysis_data.append(('post_data', str(request_data['post_data'])))
                
        # Headers
        if 'headers' in request_data:
            for key, value in request_data['headers'].items():
                analysis_data.append(('header', f"{key}: {value}"))
        
        # Analyze each piece of data
        for data_type, data_value in analysis_data:
            decoded_data = unquote(str(data_value))
            
            # Check each attack type
            for attack_type, patterns in self.compiled_patterns.items():
                for pattern in patterns:
                    if pattern.search(decoded_data):
                        attacks.append({
                            'attack_type': attack_type,
                            'data_type': data_type,
                            'matched_pattern': pattern.pattern,
                            'matched_data': decoded_data[:200],  # Limit length
                            'severity': self._get_severity(attack_type)
                        })
                        break  # One match per attack type per data piece
                        
        return attacks
    
    def _get_severity(self, attack_type: str) -> str:
        """Get severity level for attack type"""
        severity_map = {
            'sql_injection': 'CRITICAL',
            'xss': 'HIGH',
            'path_traversal': 'HIGH',
            'command_injection': 'CRITICAL'
        }
        return severity_map.get(attack_type, 'MEDIUM')

class GeoIPFilter:
    """Geographic IP filtering and analysis"""
    
    def __init__(self):
        # Simplified country blocking (in production, use GeoIP database)
        self.blocked_countries = set()
        self.suspicious_countries = {'CN', 'RU', 'KP', 'IR'}  # Example
        
        # Known malicious IP ranges (simplified)
        self.blocked_ranges = [
            ipaddress.IPv4Network('10.0.0.0/8'),    # Private ranges for demo
            ipaddress.IPv4Network('192.168.0.0/16'),
        ]
        
    def is_ip_allowed(self, ip_address: str) -> Tuple[bool, Dict[str, Any]]:
        """Check if IP address is allowed"""
        try:
            ip = ipaddress.IPv4Address(ip_address)
            
            # Check blocked ranges
            for blocked_range in self.blocked_ranges:
                if ip in blocked_range:
                    return False, {
                        'reason': 'blocked_ip_range',
                        'range': str(blocked_range)
                    }
            
            # In production, you would use a GeoIP database here
            # For demo, we'll allow all IPs but mark suspicious ones
            country_code = self._get_country_code(ip_address)
            
            if country_code in self.blocked_countries:
                return False, {
                    'reason': 'blocked_country',
                    'country': country_code
                }
            
            return True, {
                'country': country_code,
                'suspicious': country_code in self.suspicious_countries
            }
            
        except Exception as e:
            logger.error(f"Error checking IP {ip_address}: {e}")
            return True, {'error': str(e)}
    
    def _get_country_code(self, ip_address: str) -> str:
        """Get country code for IP (simplified implementation)"""
        # In production, use a proper GeoIP database like MaxMind
        # This is a simplified demo implementation
        if ip_address.startswith('127.') or ip_address.startswith('192.168.'):
            return 'LOCAL'
        return 'UNKNOWN'

class SecurityEventLogger:
    """Security event logging and storage"""
    
    def __init__(self, db_path: str = "security/security_events.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_database()
        
    def _init_database(self):
        """Initialize security events database"""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS security_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    ip_address TEXT NOT NULL,
                    user_agent TEXT,
                    request_path TEXT,
                    attack_type TEXT,
                    severity TEXT,
                    blocked BOOLEAN,
                    details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_security_events_timestamp 
                ON security_events(timestamp)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_security_events_ip 
                ON security_events(ip_address)
            """)
            
    @contextmanager
    def _get_connection(self):
        """Get database connection with proper cleanup"""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
            
    def log_event(self, event: SecurityEvent):
        """Log security event to database"""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO security_events 
                (timestamp, ip_address, user_agent, request_path, attack_type, 
                 severity, blocked, details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.timestamp.isoformat(),
                event.ip_address,
                event.user_agent,
                event.request_path,
                event.attack_type,
                event.severity,
                event.blocked,
                json.dumps(event.details)
            ))
            
    def get_recent_events(self, hours: int = 24, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent security events"""
        since = datetime.now() - timedelta(hours=hours)
        
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM security_events 
                WHERE timestamp >= ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (since.isoformat(), limit))
            
            columns = [desc[0] for desc in cursor.description]
            events = []
            
            for row in cursor.fetchall():
                event_dict = dict(zip(columns, row))
                if event_dict['details']:
                    event_dict['details'] = json.loads(event_dict['details'])
                events.append(event_dict)
                
            return events
    
    def get_attack_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """Get attack statistics"""
        since = datetime.now() - timedelta(hours=hours)
        
        with self._get_connection() as conn:
            # Total events
            cursor = conn.execute("""
                SELECT COUNT(*) FROM security_events 
                WHERE timestamp >= ?
            """, (since.isoformat(),))
            total_events = cursor.fetchone()[0]
            
            # Events by attack type
            cursor = conn.execute("""
                SELECT attack_type, COUNT(*) as count 
                FROM security_events 
                WHERE timestamp >= ? 
                GROUP BY attack_type 
                ORDER BY count DESC
            """, (since.isoformat(),))
            attack_types = dict(cursor.fetchall())
            
            # Top attacking IPs
            cursor = conn.execute("""
                SELECT ip_address, COUNT(*) as count 
                FROM security_events 
                WHERE timestamp >= ? 
                GROUP BY ip_address 
                ORDER BY count DESC 
                LIMIT 10
            """, (since.isoformat(),))
            top_ips = dict(cursor.fetchall())
            
            # Blocked vs allowed
            cursor = conn.execute("""
                SELECT blocked, COUNT(*) as count 
                FROM security_events 
                WHERE timestamp >= ? 
                GROUP BY blocked
            """, (since.isoformat(),))
            blocked_stats = dict(cursor.fetchall())
            
            return {
                'total_events': total_events,
                'attack_types': attack_types,
                'top_attacking_ips': top_ips,
                'blocked_stats': blocked_stats,
                'time_period_hours': hours
            }

class WebApplicationFirewall:
    """Main WAF class coordinating all security components"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or self._default_config()
        
        # Initialize components
        self.rate_limiter = RateLimiter()
        self.attack_detector = AttackDetector()
        self.geo_filter = GeoIPFilter()
        self.event_logger = SecurityEventLogger()
        
        # WAF statistics
        self.stats = {
            'requests_processed': 0,
            'requests_blocked': 0,
            'attacks_detected': 0,
            'start_time': datetime.now()
        }
        
    def _default_config(self) -> Dict[str, Any]:
        """Default WAF configuration"""
        return {
            'enabled': True,
            'block_attacks': True,
            'log_all_requests': False,
            'rate_limiting_enabled': True,
            'geo_filtering_enabled': True,
            'attack_detection_enabled': True
        }
    
    def process_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming request through WAF"""
        self.stats['requests_processed'] += 1
        
        if not self.config['enabled']:
            return {'allowed': True, 'reason': 'waf_disabled'}
        
        ip_address = request_data.get('ip_address', 'unknown')
        user_agent = request_data.get('user_agent', 'unknown')
        request_path = request_data.get('path', '/')
        
        result = {
            'allowed': True,
            'blocked_reasons': [],
            'security_events': [],
            'rate_limit_info': {},
            'geo_info': {}
        }
        
        try:
            # 1. Rate limiting check
            if self.config['rate_limiting_enabled']:
                endpoint_type = self._get_endpoint_type(request_path)
                rate_allowed, rate_info = self.rate_limiter.is_allowed(ip_address, endpoint_type)
                result['rate_limit_info'] = rate_info
                
                if not rate_allowed:
                    result['allowed'] = False
                    result['blocked_reasons'].append('rate_limit')
                    self._log_security_event(
                        ip_address, user_agent, request_path,
                        'rate_limit', 'MEDIUM', True, rate_info
                    )
            
            # 2. Geographic filtering
            if self.config['geo_filtering_enabled']:
                geo_allowed, geo_info = self.geo_filter.is_ip_allowed(ip_address)
                result['geo_info'] = geo_info
                
                if not geo_allowed:
                    result['allowed'] = False
                    result['blocked_reasons'].append('geo_filter')
                    self._log_security_event(
                        ip_address, user_agent, request_path,
                        'geo_block', 'HIGH', True, geo_info
                    )
            
            # 3. Attack detection
            if self.config['attack_detection_enabled']:
                attacks = self.attack_detector.detect_attacks(request_data)
                
                if attacks:
                    self.stats['attacks_detected'] += len(attacks)
                    result['security_events'] = attacks
                    
                    # Check if any critical attacks should block the request
                    critical_attacks = [a for a in attacks if a['severity'] == 'CRITICAL']
                    
                    if critical_attacks and self.config['block_attacks']:
                        result['allowed'] = False
                        result['blocked_reasons'].append('attack_detected')
                    
                    # Log all detected attacks
                    for attack in attacks:
                        self._log_security_event(
                            ip_address, user_agent, request_path,
                            attack['attack_type'], attack['severity'],
                            not result['allowed'], attack
                        )
            
            # Update statistics
            if not result['allowed']:
                self.stats['requests_blocked'] += 1
                
            # Log request if configured
            if self.config['log_all_requests']:
                self._log_security_event(
                    ip_address, user_agent, request_path,
                    'request_log', 'INFO', False, result
                )
                
        except Exception as e:
            logger.error(f"WAF processing error: {e}")
            result['error'] = str(e)
            # In case of error, allow request but log the issue
            result['allowed'] = True
            
        return result
    
    def _get_endpoint_type(self, path: str) -> str:
        """Determine endpoint type for rate limiting"""
        if '/api/auth/' in path:
            return 'auth'
        elif '/api/' in path:
            return 'api'
        else:
            return 'global'
    
    def _log_security_event(self, ip_address: str, user_agent: str, 
                           request_path: str, attack_type: str, 
                           severity: str, blocked: bool, details: Dict[str, Any]):
        """Log security event"""
        event = SecurityEvent(
            timestamp=datetime.now(),
            ip_address=ip_address,
            user_agent=user_agent,
            request_path=request_path,
            attack_type=attack_type,
            severity=severity,
            blocked=blocked,
            details=details
        )
        
        self.event_logger.log_event(event)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get WAF statistics"""
        uptime = datetime.now() - self.stats['start_time']
        
        return {
            **self.stats,
            'uptime_seconds': uptime.total_seconds(),
            'requests_per_second': self.stats['requests_processed'] / max(uptime.total_seconds(), 1),
            'block_rate': self.stats['requests_blocked'] / max(self.stats['requests_processed'], 1),
            'recent_events': self.event_logger.get_recent_events(hours=1, limit=10),
            'attack_statistics': self.event_logger.get_attack_statistics(hours=24)
        }
    
    def update_config(self, new_config: Dict[str, Any]):
        """Update WAF configuration"""
        self.config.update(new_config)
        logger.info(f"WAF configuration updated: {new_config}")

# FastAPI middleware integration
class WAFMiddleware:
    """FastAPI middleware for WAF integration"""
    
    def __init__(self, app, waf: WebApplicationFirewall):
        self.app = app
        self.waf = waf
        
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # Extract request data
            request_data = await self._extract_request_data(scope, receive)
            
            # Process through WAF
            waf_result = self.waf.process_request(request_data)
            
            # Block request if not allowed
            if not waf_result['allowed']:
                response = {
                    "type": "http.response.start",
                    "status": 403,
                    "headers": [
                        [b"content-type", b"application/json"],
                        [b"x-waf-blocked", b"true"]
                    ]
                }
                await send(response)
                
                body = {
                    "error": "Request blocked by WAF",
                    "reasons": waf_result['blocked_reasons'],
                    "request_id": request_data.get('request_id', 'unknown')
                }
                
                await send({
                    "type": "http.response.body",
                    "body": json.dumps(body).encode()
                })
                return
            
            # Add WAF info to request scope
            scope["waf_result"] = waf_result
        
        await self.app(scope, receive, send)
    
    async def _extract_request_data(self, scope, receive) -> Dict[str, Any]:
        """Extract request data for WAF analysis"""
        # Get basic request info
        request_data = {
            'method': scope.get('method', 'GET'),
            'path': scope.get('path', '/'),
            'query_string': scope.get('query_string', b'').decode(),
            'headers': dict(scope.get('headers', [])),
            'ip_address': self._get_client_ip(scope),
            'user_agent': self._get_user_agent(scope)
        }
        
        # Parse query parameters
        if request_data['query_string']:
            request_data['query_params'] = parse_qs(request_data['query_string'])
        
        # For POST requests, get body (simplified)
        if request_data['method'] in ['POST', 'PUT', 'PATCH']:
            # In production, you'd need to handle this more carefully
            # to avoid consuming the request body
            pass
        
        return request_data
    
    def _get_client_ip(self, scope) -> str:
        """Get client IP address"""
        # Check for forwarded headers
        headers = dict(scope.get('headers', []))
        
        forwarded_for = headers.get(b'x-forwarded-for')
        if forwarded_for:
            return forwarded_for.decode().split(',')[0].strip()
        
        real_ip = headers.get(b'x-real-ip')
        if real_ip:
            return real_ip.decode()
        
        # Fallback to direct connection
        client = scope.get('client')
        if client:
            return client[0]
        
        return 'unknown'
    
    def _get_user_agent(self, scope) -> str:
        """Get user agent"""
        headers = dict(scope.get('headers', []))
        user_agent = headers.get(b'user-agent')
        return user_agent.decode() if user_agent else 'unknown'

if __name__ == "__main__":
    # Demo usage
    print("Mercedes W222 OBD Scanner - WAF System Demo")
    print("=" * 50)
    
    # Initialize WAF
    waf = WebApplicationFirewall()
    
    # Test requests
    test_requests = [
        {
            'ip_address': '192.168.1.100',
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'path': '/api/user/profile',
            'query_params': {'id': ['123']},
            'method': 'GET'
        },
        {
            'ip_address': '10.0.0.1',
            'user_agent': 'sqlmap/1.0',
            'path': '/api/data',
            'query_params': {'search': ["'; DROP TABLE users; --"]},
            'method': 'GET'
        },
        {
            'ip_address': '192.168.1.100',
            'user_agent': 'Mozilla/5.0',
            'path': '/login',
            'post_data': {'username': 'admin', 'password': '<script>alert("xss")</script>'},
            'method': 'POST'
        }
    ]
    
    print("Testing WAF with sample requests...")
    for i, request in enumerate(test_requests, 1):
        print(f"\nTest {i}: {request['method']} {request['path']}")
        result = waf.process_request(request)
        
        if result['allowed']:
            print("✅ Request ALLOWED")
        else:
            print("❌ Request BLOCKED")
            print(f"   Reasons: {', '.join(result['blocked_reasons'])}")
        
        if result['security_events']:
            print(f"   Attacks detected: {len(result['security_events'])}")
            for event in result['security_events']:
                print(f"   - {event['attack_type']} ({event['severity']})")
    
    # Show statistics
    print(f"\nWAF Statistics:")
    stats = waf.get_statistics()
    print(f"Requests processed: {stats['requests_processed']}")
    print(f"Requests blocked: {stats['requests_blocked']}")
    print(f"Attacks detected: {stats['attacks_detected']}")
    print(f"Block rate: {stats['block_rate']:.2%}")
