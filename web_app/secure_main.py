#!/usr/bin/env python3
"""
Secure FastAPI Application for Mercedes W222 OBD Scanner
Production-ready with comprehensive security measures
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import asyncio
import uvicorn
from contextlib import asynccontextmanager

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, Depends, Request, Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, validator
import redis
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

# Import our security configuration
from security.security_config import SecurityConfig, SecurityMiddleware, log_security_event
from mercedes_obd_scanner.auth.jwt_auth import JWTAuth
from mercedes_obd_scanner.auth.user_manager import UserManager
from mercedes_obd_scanner.data.database_manager import DatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/security.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
security_logger = logging.getLogger('security')

# Initialize security components
security_middleware = SecurityMiddleware()
jwt_auth = JWTAuth(secret_key=os.getenv('JWT_SECRET_KEY', SecurityConfig.generate_secure_token()))

# Initialize rate limiter with Redis
try:
    redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    limiter = Limiter(key_func=get_remote_address, storage_uri="redis://localhost:6379")
except:
    # Fallback to memory storage
    limiter = Limiter(key_func=get_remote_address)

# Security models
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password too short')
        return v

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    
    @validator('password')
    def validate_password_strength(cls, v):
        validation = SecurityConfig.validate_password_strength(v)
        if not validation['valid']:
            raise ValueError(f"Password validation failed: {', '.join(validation['issues'])}")
        return v
    
    @validator('first_name', 'last_name')
    def sanitize_names(cls, v):
        return SecurityConfig.sanitize_input(v, 50)

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str
    
    @validator('new_password')
    def validate_new_password(cls, v):
        validation = SecurityConfig.validate_password_strength(v)
        if not validation['valid']:
            raise ValueError(f"Password validation failed: {', '.join(validation['issues'])}")
        return v

# Application lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Mercedes W222 OBD Scanner API with security hardening")
    
    # Initialize database connections
    try:
        db_manager = DatabaseManager()
        user_manager = UserManager()
        logger.info("Database connections initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    
    # Start background tasks
    cleanup_task = asyncio.create_task(cleanup_expired_tokens())
    
    yield
    
    # Shutdown
    cleanup_task.cancel()
    logger.info("Application shutdown complete")

async def cleanup_expired_tokens():
    """Background task to cleanup expired tokens and sessions"""
    while True:
        try:
            security_middleware.csrf_protection.cleanup_expired_tokens()
            await asyncio.sleep(300)  # Run every 5 minutes
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")
            await asyncio.sleep(60)

# Initialize FastAPI app with security
app = FastAPI(
    title="Mercedes W222 OBD Scanner API",
    description="Secure API for Mercedes W222 OBD diagnostics and analysis",
    version="2.1.0",
    lifespan=lifespan,
    docs_url="/docs" if os.getenv('ENVIRONMENT') != 'production' else None,
    redoc_url="/redoc" if os.getenv('ENVIRONMENT') != 'production' else None
)

# Add security middleware
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "*.yourdomain.com"]
)

# CORS configuration
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:8000",
    "https://yourdomain.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Rate limit exceeded handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    
    # Add security headers
    headers = security_middleware.add_security_headers({})
    for header, value in headers.items():
        response.headers[header] = value
    
    # Log request for security monitoring
    client_ip = get_remote_address(request)
    log_security_event(
        "http_request",
        {
            "ip": client_ip,
            "method": request.method,
            "url": str(request.url),
            "user_agent": request.headers.get("user-agent", ""),
            "status_code": response.status_code
        }
    )
    
    return response

# Authentication dependency
security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated user"""
    try:
        token = credentials.credentials
        payload = jwt_auth.validate_token(token)
        
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return payload
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Rate limiting dependency
def rate_limit_key(request: Request):
    """Generate rate limit key based on user or IP"""
    # Try to get user from token first
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            token = auth_header.split(" ")[1]
            payload = jwt_auth.validate_token(token)
            if payload:
                return f"user:{payload['user_id']}"
        except:
            pass
    
    # Fallback to IP address
    return f"ip:{get_remote_address(request)}"

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.1.0"
    }

# Authentication endpoints
@app.post("/auth/register")
@limiter.limit("5/minute")
async def register(request: Request, user_data: RegisterRequest):
    """Register new user with security validation"""
    try:
        client_ip = get_remote_address(request)
        
        # Check rate limiting
        if not security_middleware.check_rate_limit(client_ip, "register"):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many registration attempts"
            )
        
        # Initialize user manager
        user_manager = UserManager()
        
        # Check if user already exists
        existing_user = user_manager.get_user_by_email(user_data.email)
        if existing_user:
            log_security_event(
                "registration_attempt_existing_email",
                {"email": user_data.email, "ip": client_ip},
                "WARNING"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already exists"
            )
        
        # Create user
        user_id = user_manager.register_user(
            email=user_data.email,
            password=user_data.password,
            first_name=user_data.first_name,
            last_name=user_data.last_name
        )
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user"
            )
        
        log_security_event(
            "user_registered",
            {"user_id": user_id, "email": user_data.email, "ip": client_ip}
        )
        
        return {"message": "User registered successfully", "user_id": user_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

@app.post("/auth/login")
@limiter.limit("10/minute")
async def login(request: Request, login_data: LoginRequest):
    """Authenticate user with security measures"""
    try:
        client_ip = get_remote_address(request)
        
        # Check if account is locked
        if security_middleware.is_account_locked(login_data.email):
            log_security_event(
                "login_attempt_locked_account",
                {"email": login_data.email, "ip": client_ip},
                "WARNING"
            )
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account temporarily locked due to multiple failed attempts"
            )
        
        # Check rate limiting
        if not security_middleware.check_rate_limit(client_ip, "login"):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts"
            )
        
        # Initialize user manager
        user_manager = UserManager()
        
        # Authenticate user
        user = user_manager.authenticate_user(login_data.email, login_data.password)
        
        if not user:
            # Record failed attempt
            security_middleware.record_failed_login(login_data.email)
            log_security_event(
                "failed_login_attempt",
                {"email": login_data.email, "ip": client_ip},
                "WARNING"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Clear failed attempts on successful login
        security_middleware.clear_failed_attempts(login_data.email)
        
        # Generate JWT token
        token_payload = {
            "user_id": user["user_id"],
            "email": user["email"],
            "role": user.get("role", "user")
        }
        
        token = jwt_auth.generate_token(token_payload)
        
        log_security_event(
            "successful_login",
            {"user_id": user["user_id"], "email": login_data.email, "ip": client_ip}
        )
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "user_id": user["user_id"],
                "email": user["email"],
                "first_name": user["first_name"],
                "last_name": user["last_name"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )

@app.post("/auth/change-password")
@limiter.limit("5/hour")
async def change_password(
    request: Request,
    password_data: PasswordChangeRequest,
    current_user: dict = Depends(get_current_user)
):
    """Change user password with security validation"""
    try:
        client_ip = get_remote_address(request)
        user_manager = UserManager()
        
        # Verify current password
        user = user_manager.authenticate_user(
            current_user["email"],
            password_data.current_password
        )
        
        if not user:
            log_security_event(
                "password_change_invalid_current",
                {"user_id": current_user["user_id"], "ip": client_ip},
                "WARNING"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Update password
        success = user_manager.update_password(
            current_user["user_id"],
            password_data.new_password
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update password"
            )
        
        log_security_event(
            "password_changed",
            {"user_id": current_user["user_id"], "ip": client_ip}
        )
        
        return {"message": "Password updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password change error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed"
        )

# Protected endpoints
@app.get("/api/user/profile")
@limiter.limit("30/minute")
async def get_user_profile(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Get user profile information"""
    try:
        user_manager = UserManager()
        user = user_manager.get_user_by_id(current_user["user_id"])
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Remove sensitive information
        safe_user = {
            "user_id": user["user_id"],
            "email": user["email"],
            "first_name": user["first_name"],
            "last_name": user["last_name"],
            "created_at": user.get("created_at"),
            "last_login": user.get("last_login")
        }
        
        return safe_user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profile fetch error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch profile"
        )

@app.get("/api/user/devices")
@limiter.limit("20/minute")
async def get_user_devices(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Get user's registered devices"""
    try:
        user_manager = UserManager()
        devices = user_manager.get_user_devices(current_user["user_id"])
        
        return {"devices": devices}
        
    except Exception as e:
        logger.error(f"Device fetch error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch devices"
        )

# Security monitoring endpoint
@app.get("/api/security/events")
@limiter.limit("10/minute")
async def get_security_events(
    request: Request,
    current_user: dict = Depends(get_current_user),
    limit: int = 50
):
    """Get security events for user (admin only)"""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    # This would fetch from security logs
    # For now, return placeholder
    return {"events": [], "message": "Security events endpoint"}

# Static files (with security headers)
app.mount("/static", StaticFiles(directory="web_app/static"), name="static")

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler with security logging"""
    client_ip = get_remote_address(request)
    
    if exc.status_code >= 400:
        log_security_event(
            "http_error",
            {
                "status_code": exc.status_code,
                "detail": exc.detail,
                "ip": client_ip,
                "url": str(request.url),
                "method": request.method
            },
            "WARNING" if exc.status_code >= 500 else "INFO"
        )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler with security logging"""
    client_ip = get_remote_address(request)
    
    log_security_event(
        "internal_error",
        {
            "error": str(exc),
            "ip": client_ip,
            "url": str(request.url),
            "method": request.method
        },
        "ERROR"
    )
    
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

if __name__ == "__main__":
    # Ensure logs directory exists
    os.makedirs("logs", exist_ok=True)
    
    # Get configuration
    environment = os.getenv('ENVIRONMENT', 'development')
    security_config = SecurityConfig.get_security_config(environment)
    
    # Configure SSL if required
    ssl_keyfile = None
    ssl_certfile = None
    if security_config.get('ssl_required'):
        ssl_keyfile = os.getenv('SSL_KEYFILE', 'certs/key.pem')
        ssl_certfile = os.getenv('SSL_CERTFILE', 'certs/cert.pem')
    
    # Run server
    uvicorn.run(
        "secure_main:app",
        host="0.0.0.0",
        port=int(os.getenv('PORT', 8000)),
        ssl_keyfile=ssl_keyfile,
        ssl_certfile=ssl_certfile,
        reload=security_config.get('debug', False),
        log_level="info"
    )
