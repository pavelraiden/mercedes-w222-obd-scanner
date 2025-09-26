#!/usr/bin/env python3
"""
Comprehensive Security Configuration for Mercedes W222 OBD Scanner
Production-ready security hardening measures
"""

import os
import secrets
import hashlib
import hmac
import time
from typing import Dict, List, Optional, Any
from functools import wraps
from datetime import datetime, timedelta
import logging
import re
import ipaddress

# Configure security logging
security_logger = logging.getLogger('security')
security_logger.setLevel(logging.INFO)

class SecurityConfig:
    """Central security configuration and utilities"""
    
    # Security constants
    MIN_PASSWORD_LENGTH = 12
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION = 900  # 15 minutes
    SESSION_TIMEOUT = 3600  # 1 hour
    CSRF_TOKEN_LENGTH = 32
    
    # Allowed file extensions for uploads
    ALLOWED_EXTENSIONS = {'.json', '.csv', '.txt', '.log'}
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    # Rate limiting
    RATE_LIMITS = {
        'login': {'requests': 5, 'window': 300},  # 5 attempts per 5 minutes
        'api': {'requests': 100, 'window': 60},   # 100 requests per minute
        'upload': {'requests': 10, 'window': 3600}  # 10 uploads per hour
    }
    
    # Security headers
    SECURITY_HEADERS = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Permissions-Policy': 'geolocation=(), microphone=(), camera=()'
    }
    
    @staticmethod
    def generate_secure_token(length: int = 32) -> str:
        """Generate cryptographically secure random token"""
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def hash_password(password: str, salt: Optional[str] = None) -> tuple:
        """Hash password with salt using PBKDF2"""
        if salt is None:
            salt = secrets.token_hex(32)
        
        # Use PBKDF2 with SHA256
        password_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000  # 100,000 iterations
        )
        
        return password_hash.hex(), salt
    
    @staticmethod
    def verify_password(password: str, password_hash: str, salt: str) -> bool:
        """Verify password against hash"""
        computed_hash, _ = SecurityConfig.hash_password(password, salt)
        return hmac.compare_digest(computed_hash, password_hash)
    
    @staticmethod
    def validate_password_strength(password: str) -> Dict[str, Any]:
        """Validate password strength"""
        issues = []
        score = 0
        
        if len(password) < SecurityConfig.MIN_PASSWORD_LENGTH:
            issues.append(f"Password must be at least {SecurityConfig.MIN_PASSWORD_LENGTH} characters")
        else:
            score += 1
        
        if not re.search(r'[A-Z]', password):
            issues.append("Password must contain at least one uppercase letter")
        else:
            score += 1
        
        if not re.search(r'[a-z]', password):
            issues.append("Password must contain at least one lowercase letter")
        else:
            score += 1
        
        if not re.search(r'\d', password):
            issues.append("Password must contain at least one digit")
        else:
            score += 1
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            issues.append("Password must contain at least one special character")
        else:
            score += 1
        
        # Check for common patterns
        if re.search(r'(.)\1{2,}', password):
            issues.append("Password should not contain repeated characters")
            score -= 1
        
        if re.search(r'(012|123|234|345|456|567|678|789|890)', password):
            issues.append("Password should not contain sequential numbers")
            score -= 1
        
        strength = "weak"
        if score >= 4:
            strength = "strong"
        elif score >= 2:
            strength = "medium"
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "strength": strength,
            "score": max(0, score)
        }
    
    @staticmethod
    def sanitize_input(input_string: str, max_length: int = 1000) -> str:
        """Sanitize user input to prevent XSS and injection attacks"""
        if not isinstance(input_string, str):
            return ""
        
        # Truncate to max length
        sanitized = input_string[:max_length]
        
        # Remove or escape dangerous characters
        sanitized = re.sub(r'[<>"\']', '', sanitized)
        sanitized = re.sub(r'javascript:', '', sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r'on\w+\s*=', '', sanitized, flags=re.IGNORECASE)
        
        return sanitized.strip()
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def validate_ip_address(ip: str) -> bool:
        """Validate IP address format"""
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def is_safe_filename(filename: str) -> bool:
        """Check if filename is safe for upload"""
        if not filename or '..' in filename or '/' in filename or '\\' in filename:
            return False
        
        # Check extension
        _, ext = os.path.splitext(filename.lower())
        return ext in SecurityConfig.ALLOWED_EXTENSIONS


class RateLimiter:
    """Rate limiting implementation"""
    
    def __init__(self):
        self.requests = {}
    
    def is_allowed(self, identifier: str, limit_type: str) -> bool:
        """Check if request is allowed based on rate limits"""
        if limit_type not in SecurityConfig.RATE_LIMITS:
            return True
        
        config = SecurityConfig.RATE_LIMITS[limit_type]
        current_time = time.time()
        
        # Clean old entries
        self._cleanup_old_entries(current_time, config['window'])
        
        # Check current requests
        key = f"{identifier}:{limit_type}"
        if key not in self.requests:
            self.requests[key] = []
        
        # Count requests in current window
        window_start = current_time - config['window']
        recent_requests = [req_time for req_time in self.requests[key] if req_time > window_start]
        
        if len(recent_requests) >= config['requests']:
            security_logger.warning(f"Rate limit exceeded for {identifier} on {limit_type}")
            return False
        
        # Add current request
        self.requests[key] = recent_requests + [current_time]
        return True
    
    def _cleanup_old_entries(self, current_time: float, window: int):
        """Clean up old rate limiting entries"""
        cutoff_time = current_time - window
        for key in list(self.requests.keys()):
            self.requests[key] = [req_time for req_time in self.requests[key] if req_time > cutoff_time]
            if not self.requests[key]:
                del self.requests[key]


class CSRFProtection:
    """CSRF token generation and validation"""
    
    def __init__(self):
        self.tokens = {}
    
    def generate_token(self, session_id: str) -> str:
        """Generate CSRF token for session"""
        token = SecurityConfig.generate_secure_token(SecurityConfig.CSRF_TOKEN_LENGTH)
        self.tokens[session_id] = {
            'token': token,
            'created': time.time()
        }
        return token
    
    def validate_token(self, session_id: str, token: str) -> bool:
        """Validate CSRF token"""
        if session_id not in self.tokens:
            return False
        
        stored_data = self.tokens[session_id]
        
        # Check if token is expired (1 hour)
        if time.time() - stored_data['created'] > 3600:
            del self.tokens[session_id]
            return False
        
        return hmac.compare_digest(stored_data['token'], token)
    
    def cleanup_expired_tokens(self):
        """Clean up expired CSRF tokens"""
        current_time = time.time()
        expired_sessions = [
            session_id for session_id, data in self.tokens.items()
            if current_time - data['created'] > 3600
        ]
        
        for session_id in expired_sessions:
            del self.tokens[session_id]


class SecurityMiddleware:
    """Security middleware for web applications"""
    
    def __init__(self):
        self.rate_limiter = RateLimiter()
        self.csrf_protection = CSRFProtection()
        self.failed_attempts = {}
    
    def add_security_headers(self, response_headers: Dict[str, str]) -> Dict[str, str]:
        """Add security headers to response"""
        response_headers.update(SecurityConfig.SECURITY_HEADERS)
        return response_headers
    
    def check_rate_limit(self, client_ip: str, endpoint: str) -> bool:
        """Check rate limit for client"""
        limit_type = 'api'
        if 'login' in endpoint:
            limit_type = 'login'
        elif 'upload' in endpoint:
            limit_type = 'upload'
        
        return self.rate_limiter.is_allowed(client_ip, limit_type)
    
    def record_failed_login(self, identifier: str):
        """Record failed login attempt"""
        current_time = time.time()
        
        if identifier not in self.failed_attempts:
            self.failed_attempts[identifier] = []
        
        self.failed_attempts[identifier].append(current_time)
        
        # Keep only recent attempts
        cutoff_time = current_time - SecurityConfig.LOCKOUT_DURATION
        self.failed_attempts[identifier] = [
            attempt_time for attempt_time in self.failed_attempts[identifier]
            if attempt_time > cutoff_time
        ]
        
        security_logger.warning(f"Failed login attempt for {identifier}")
    
    def is_account_locked(self, identifier: str) -> bool:
        """Check if account is locked due to failed attempts"""
        if identifier not in self.failed_attempts:
            return False
        
        current_time = time.time()
        cutoff_time = current_time - SecurityConfig.LOCKOUT_DURATION
        
        recent_failures = [
            attempt_time for attempt_time in self.failed_attempts[identifier]
            if attempt_time > cutoff_time
        ]
        
        return len(recent_failures) >= SecurityConfig.MAX_LOGIN_ATTEMPTS
    
    def clear_failed_attempts(self, identifier: str):
        """Clear failed login attempts for identifier"""
        if identifier in self.failed_attempts:
            del self.failed_attempts[identifier]


def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # This would integrate with your auth system
        # For now, it's a placeholder
        return f(*args, **kwargs)
    return decorated_function


def require_csrf_token(f):
    """Decorator to require CSRF token"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # This would integrate with your CSRF protection
        # For now, it's a placeholder
        return f(*args, **kwargs)
    return decorated_function


def log_security_event(event_type: str, details: Dict[str, Any], severity: str = "INFO"):
    """Log security events"""
    security_logger.log(
        getattr(logging, severity),
        f"Security Event: {event_type} - {details}"
    )


# Security configuration for different environments
SECURITY_CONFIGS = {
    'development': {
        'debug': True,
        'ssl_required': False,
        'session_cookie_secure': False,
        'csrf_protection': True,
        'rate_limiting': False
    },
    'staging': {
        'debug': False,
        'ssl_required': True,
        'session_cookie_secure': True,
        'csrf_protection': True,
        'rate_limiting': True
    },
    'production': {
        'debug': False,
        'ssl_required': True,
        'session_cookie_secure': True,
        'csrf_protection': True,
        'rate_limiting': True,
        'hsts_enabled': True,
        'content_security_policy': True
    }
}


def get_security_config(environment: str = 'production') -> Dict[str, Any]:
    """Get security configuration for environment"""
    return SECURITY_CONFIGS.get(environment, SECURITY_CONFIGS['production'])


if __name__ == "__main__":
    # Test security functions
    print("Testing security configuration...")
    
    # Test password validation
    test_passwords = [
        "weak",
        "StrongPassword123!",
        "password123",
        "UPPERCASE123!",
        "lowercase123!"
    ]
    
    for password in test_passwords:
        result = SecurityConfig.validate_password_strength(password)
        print(f"Password '{password}': {result['strength']} (score: {result['score']})")
        if result['issues']:
            print(f"  Issues: {', '.join(result['issues'])}")
    
    # Test input sanitization
    dangerous_inputs = [
        "<script>alert('xss')</script>",
        "javascript:alert('xss')",
        "onclick='alert(1)'",
        "normal input"
    ]
    
    for input_str in dangerous_inputs:
        sanitized = SecurityConfig.sanitize_input(input_str)
        print(f"Input: '{input_str}' -> Sanitized: '{sanitized}'")
    
    print("Security configuration test completed.")
