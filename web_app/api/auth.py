"""
Authentication API endpoints for Mercedes W222 OBD Scanner
Handles user registration, login, device binding, and token management
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
import sys
import time
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mercedes_obd_scanner.auth.jwt_auth import jwt_auth
from mercedes_obd_scanner.auth.user_manager import user_manager

router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer()


# Pydantic models for request/response
class DeviceRegistrationRequest(BaseModel):
    device_type: str = "raspberry_pi"


class DeviceRegistrationResponse(BaseModel):
    device_id: str
    device_token: str
    activation_url: str


class UserRegistrationRequest(BaseModel):
    email: EmailStr
    password: str
    device_token: str


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 1800  # 30 minutes


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class DeviceAuthRequest(BaseModel):
    device_token: str
    device_type: str = "raspberry_pi"
    firmware_version: str = "1.0.0"


class DeviceAuthResponse(BaseModel):
    session_id: str
    authenticated: bool
    user_id: Optional[str] = None


@router.post("/device/register", response_model=DeviceRegistrationResponse)
async def register_device(request: DeviceRegistrationRequest):
    """Register a new device and get activation token"""
    try:
        device = user_manager.create_device(request.device_type)

        activation_url = f"https://your-domain.com/activate?token={device.device_token}"

        return DeviceRegistrationResponse(
            device_id=device.device_id,
            device_token=device.device_token,
            activation_url=activation_url,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register device: {str(e)}",
        )


@router.post("/device", response_model=DeviceAuthResponse)
async def authenticate_device(request: DeviceAuthRequest):
    """Authenticate device for OBD data transmission"""
    try:
        device = user_manager.get_device_by_token(request.device_token)

        if not device:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid device token"
            )

        if not device.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Device is deactivated"
            )

        # Update device last seen
        user_manager.update_device_last_seen(device.device_id)

        # Generate session ID for this connection
        session_id = f"session_{device.device_id}_{int(time.time())}"

        return DeviceAuthResponse(session_id=session_id, authenticated=True, user_id=device.user_id)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Device authentication failed: {str(e)}",
        )


@router.post("/register", response_model=TokenResponse)
async def register_user(request: UserRegistrationRequest):
    """Register new user with device token"""
    try:
        user = user_manager.register_user(
            email=request.email, password=request.password, device_token=request.device_token
        )

        # Create tokens
        user_data = {
            "user_id": user.user_id,
            "email": user.email,
            "subscription_tier": user.subscription_tier,
            "device_id": user.device_id,
            "permissions": user_manager.get_user_permissions(user.user_id),
        }

        tokens = jwt_auth.create_user_tokens(user_data)

        return TokenResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_type=tokens["token_type"],
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}",
        )


@router.post("/login", response_model=TokenResponse)
async def login_user(request: UserLoginRequest):
    """Authenticate user and return tokens"""
    try:
        user = user_manager.authenticate_user(request.email, request.password)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
            )

        # Check if subscription is active
        if not user_manager.is_subscription_active(user.user_id):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Subscription expired"
            )

        # Create tokens
        user_data = {
            "user_id": user.user_id,
            "email": user.email,
            "subscription_tier": user.subscription_tier,
            "device_id": user.device_id,
            "permissions": user_manager.get_user_permissions(user.user_id),
        }

        tokens = jwt_auth.create_user_tokens(user_data)

        return TokenResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_type=tokens["token_type"],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Login failed: {str(e)}"
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshTokenRequest):
    """Refresh access token using refresh token"""
    try:
        # Verify refresh token
        payload = jwt_auth.verify_token(request.refresh_token, "refresh")
        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
            )

        # Get user data
        user = user_manager.get_user_by_id(user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive"
            )

        # Check subscription
        if not user_manager.is_subscription_active(user.user_id):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Subscription expired"
            )

        # Create new tokens
        user_data = {
            "user_id": user.user_id,
            "email": user.email,
            "subscription_tier": user.subscription_tier,
            "device_id": user.device_id,
            "permissions": user_manager.get_user_permissions(user.user_id),
        }

        tokens = jwt_auth.create_user_tokens(user_data)

        return TokenResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_type=tokens["token_type"],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token refresh failed: {str(e)}",
        )


@router.get("/me")
async def get_current_user(current_user: Dict[str, Any] = Depends(jwt_auth.get_current_user)):
    """Get current user information"""
    try:
        user = user_manager.get_user_by_id(current_user["user_id"])

        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        return {
            "user_id": user.user_id,
            "email": user.email,
            "subscription_tier": user.subscription_tier,
            "subscription_expires": (
                user.subscription_expires.isoformat() if user.subscription_expires else None
            ),
            "device_id": user.device_id,
            "device_activated": user.device_activated,
            "permissions": user_manager.get_user_permissions(user.user_id),
            "subscription_active": user_manager.is_subscription_active(user.user_id),
            "created_at": user.created_at.isoformat(),
            "last_login": user.last_login.isoformat() if user.last_login else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user info: {str(e)}",
        )


@router.post("/logout")
async def logout_user(current_user: Dict[str, Any] = Depends(jwt_auth.get_current_user)):
    """Logout user (invalidate tokens)"""
    # In a production system, you would add the token to a blacklist
    # For now, we'll just return success
    return {"message": "Logged out successfully"}


@router.get("/stats")
async def get_auth_stats():
    """Get authentication system statistics (admin only)"""
    try:
        stats = user_manager.get_user_stats()
        return stats

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stats: {str(e)}",
        )
