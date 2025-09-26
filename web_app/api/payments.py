"""
Payment API endpoints for Mercedes W222 OBD Scanner.
Handles subscription management, billing, and payment processing.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime

from mercedes_obd_scanner.payments.stripe_integration import StripePaymentManager, PaymentResult
from mercedes_obd_scanner.auth.jwt_auth import verify_token
from mercedes_obd_scanner.data.database_manager import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payments", tags=["payments"])
security = HTTPBearer()

# Initialize payment manager
payment_manager = StripePaymentManager()
db_manager = DatabaseManager()


# Pydantic models for request/response
class CreateCustomerRequest(BaseModel):
    email: EmailStr
    name: Optional[str] = None


class CreateSubscriptionRequest(BaseModel):
    plan_id: str
    payment_method_id: Optional[str] = None


class UpdateSubscriptionRequest(BaseModel):
    new_plan_id: str


class CreatePaymentIntentRequest(BaseModel):
    amount: float
    currency: str = "usd"
    description: Optional[str] = None


class PaymentMethodResponse(BaseModel):
    id: str
    type: str
    card: Optional[Dict] = None
    created: int


class SubscriptionResponse(BaseModel):
    id: str
    status: str
    current_period_start: int
    current_period_end: int
    cancel_at_period_end: bool
    plan_id: str
    plan: Optional[Dict] = None


class PlanResponse(BaseModel):
    id: str
    name: str
    price: float
    currency: str
    interval: str
    features: List[str]
    max_devices: int
    max_vehicles: int


@router.get("/plans", response_model=List[PlanResponse])
async def get_available_plans():
    """Get all available subscription plans."""
    try:
        plans = payment_manager.get_available_plans()
        return [PlanResponse(**plan) for plan in plans]
    except Exception as e:
        logger.error(f"Failed to get plans: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve plans")


@router.post("/customers")
async def create_customer(
    request: CreateCustomerRequest,
    current_user: dict = Depends(verify_token)
):
    """Create a new Stripe customer for the user."""
    try:
        # Check if user already has a customer ID
        user_id = current_user["user_id"]
        
        # Get user details from database
        with db_manager.get_connection() as conn:
            cursor = conn.execute(
                "SELECT email, first_name, last_name FROM users WHERE id = ?",
                (user_id,)
            )
            user_data = cursor.fetchone()
            
            if not user_data:
                raise HTTPException(status_code=404, detail="User not found")
        
        # Create customer in Stripe
        result = payment_manager.create_customer(
            email=request.email,
            name=request.name or f"{user_data['first_name']} {user_data['last_name']}",
            metadata={"user_id": str(user_id)}
        )
        
        if not result.success:
            raise HTTPException(status_code=400, detail=result.message)
        
        # Store customer ID in database
        with db_manager.get_connection() as conn:
            conn.execute(
                "UPDATE users SET stripe_customer_id = ? WHERE id = ?",
                (result.data["customer_id"], user_id)
            )
            conn.commit()
        
        return {
            "success": True,
            "message": "Customer created successfully",
            "customer_id": result.data["customer_id"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create customer: {e}")
        raise HTTPException(status_code=500, detail="Failed to create customer")


@router.post("/subscriptions")
async def create_subscription(
    request: CreateSubscriptionRequest,
    current_user: dict = Depends(verify_token)
):
    """Create a new subscription for the user."""
    try:
        user_id = current_user["user_id"]
        
        # Get user's Stripe customer ID
        with db_manager.get_connection() as conn:
            cursor = conn.execute(
                "SELECT stripe_customer_id FROM users WHERE id = ?",
                (user_id,)
            )
            user_data = cursor.fetchone()
            
            if not user_data or not user_data["stripe_customer_id"]:
                raise HTTPException(
                    status_code=400, 
                    detail="No Stripe customer found. Please create a customer first."
                )
        
        customer_id = user_data["stripe_customer_id"]
        
        # Create subscription
        result = payment_manager.create_subscription(
            customer_id=customer_id,
            plan_id=request.plan_id,
            payment_method_id=request.payment_method_id
        )
        
        if not result.success:
            raise HTTPException(status_code=400, detail=result.message)
        
        # Update user subscription in database
        plan = payment_manager.get_plan(request.plan_id)
        if plan:
            with db_manager.get_connection() as conn:
                conn.execute(
                    """UPDATE users SET 
                       subscription_tier = ?, 
                       subscription_expires_at = datetime(?, 'unixepoch'),
                       stripe_subscription_id = ?
                       WHERE id = ?""",
                    (
                        request.plan_id,
                        result.data["current_period_end"],
                        result.data["subscription_id"],
                        user_id
                    )
                )
                conn.commit()
        
        return {
            "success": True,
            "message": "Subscription created successfully",
            "subscription": result.data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create subscription: {e}")
        raise HTTPException(status_code=500, detail="Failed to create subscription")


@router.get("/subscriptions", response_model=List[SubscriptionResponse])
async def get_user_subscriptions(current_user: dict = Depends(verify_token)):
    """Get all subscriptions for the current user."""
    try:
        user_id = current_user["user_id"]
        
        # Get user's Stripe customer ID
        with db_manager.get_connection() as conn:
            cursor = conn.execute(
                "SELECT stripe_customer_id FROM users WHERE id = ?",
                (user_id,)
            )
            user_data = cursor.fetchone()
            
            if not user_data or not user_data["stripe_customer_id"]:
                return []
        
        customer_id = user_data["stripe_customer_id"]
        
        # Get subscriptions from Stripe
        result = payment_manager.get_customer_subscriptions(customer_id)
        
        if not result.success:
            raise HTTPException(status_code=400, detail=result.message)
        
        subscriptions = result.data["subscriptions"]
        return [SubscriptionResponse(**sub) for sub in subscriptions]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get subscriptions: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve subscriptions")


@router.put("/subscriptions/{subscription_id}")
async def update_subscription(
    subscription_id: str,
    request: UpdateSubscriptionRequest,
    current_user: dict = Depends(verify_token)
):
    """Update an existing subscription."""
    try:
        # Verify subscription belongs to user
        user_id = current_user["user_id"]
        
        with db_manager.get_connection() as conn:
            cursor = conn.execute(
                "SELECT stripe_subscription_id FROM users WHERE id = ?",
                (user_id,)
            )
            user_data = cursor.fetchone()
            
            if not user_data or user_data["stripe_subscription_id"] != subscription_id:
                raise HTTPException(status_code=403, detail="Subscription not found or access denied")
        
        # Update subscription
        result = payment_manager.update_subscription(subscription_id, request.new_plan_id)
        
        if not result.success:
            raise HTTPException(status_code=400, detail=result.message)
        
        # Update user subscription in database
        with db_manager.get_connection() as conn:
            conn.execute(
                "UPDATE users SET subscription_tier = ? WHERE id = ?",
                (request.new_plan_id, user_id)
            )
            conn.commit()
        
        return {
            "success": True,
            "message": "Subscription updated successfully",
            "subscription": result.data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update subscription: {e}")
        raise HTTPException(status_code=500, detail="Failed to update subscription")


@router.delete("/subscriptions/{subscription_id}")
async def cancel_subscription(
    subscription_id: str,
    at_period_end: bool = True,
    current_user: dict = Depends(verify_token)
):
    """Cancel a subscription."""
    try:
        # Verify subscription belongs to user
        user_id = current_user["user_id"]
        
        with db_manager.get_connection() as conn:
            cursor = conn.execute(
                "SELECT stripe_subscription_id FROM users WHERE id = ?",
                (user_id,)
            )
            user_data = cursor.fetchone()
            
            if not user_data or user_data["stripe_subscription_id"] != subscription_id:
                raise HTTPException(status_code=403, detail="Subscription not found or access denied")
        
        # Cancel subscription
        result = payment_manager.cancel_subscription(subscription_id, at_period_end)
        
        if not result.success:
            raise HTTPException(status_code=400, detail=result.message)
        
        # Update user subscription in database if canceled immediately
        if not at_period_end:
            with db_manager.get_connection() as conn:
                conn.execute(
                    """UPDATE users SET 
                       subscription_tier = 'basic',
                       subscription_expires_at = NULL,
                       stripe_subscription_id = NULL
                       WHERE id = ?""",
                    (user_id,)
                )
                conn.commit()
        
        return {
            "success": True,
            "message": result.message,
            "subscription": result.data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel subscription: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel subscription")


@router.post("/payment-intents")
async def create_payment_intent(
    request: CreatePaymentIntentRequest,
    current_user: dict = Depends(verify_token)
):
    """Create a payment intent for one-time payments."""
    try:
        user_id = current_user["user_id"]
        
        # Get user's Stripe customer ID
        with db_manager.get_connection() as conn:
            cursor = conn.execute(
                "SELECT stripe_customer_id FROM users WHERE id = ?",
                (user_id,)
            )
            user_data = cursor.fetchone()
        
        customer_id = user_data["stripe_customer_id"] if user_data else None
        
        # Create payment intent
        result = payment_manager.create_payment_intent(
            amount=request.amount,
            currency=request.currency,
            customer_id=customer_id,
            metadata={
                "user_id": str(user_id),
                "description": request.description or "One-time payment"
            }
        )
        
        if not result.success:
            raise HTTPException(status_code=400, detail=result.message)
        
        return {
            "success": True,
            "message": "Payment intent created successfully",
            "client_secret": result.data["client_secret"],
            "payment_intent_id": result.data["payment_intent_id"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create payment intent: {e}")
        raise HTTPException(status_code=500, detail="Failed to create payment intent")


@router.post("/setup-intents")
async def create_setup_intent(current_user: dict = Depends(verify_token)):
    """Create a setup intent for saving payment methods."""
    try:
        user_id = current_user["user_id"]
        
        # Get user's Stripe customer ID
        with db_manager.get_connection() as conn:
            cursor = conn.execute(
                "SELECT stripe_customer_id FROM users WHERE id = ?",
                (user_id,)
            )
            user_data = cursor.fetchone()
            
            if not user_data or not user_data["stripe_customer_id"]:
                raise HTTPException(
                    status_code=400,
                    detail="No Stripe customer found. Please create a customer first."
                )
        
        customer_id = user_data["stripe_customer_id"]
        
        # Create setup intent
        result = payment_manager.create_setup_intent(customer_id)
        
        if not result.success:
            raise HTTPException(status_code=400, detail=result.message)
        
        return {
            "success": True,
            "message": "Setup intent created successfully",
            "client_secret": result.data["client_secret"],
            "setup_intent_id": result.data["setup_intent_id"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create setup intent: {e}")
        raise HTTPException(status_code=500, detail="Failed to create setup intent")


@router.get("/payment-methods", response_model=List[PaymentMethodResponse])
async def get_payment_methods(current_user: dict = Depends(verify_token)):
    """Get all payment methods for the current user."""
    try:
        user_id = current_user["user_id"]
        
        # Get user's Stripe customer ID
        with db_manager.get_connection() as conn:
            cursor = conn.execute(
                "SELECT stripe_customer_id FROM users WHERE id = ?",
                (user_id,)
            )
            user_data = cursor.fetchone()
            
            if not user_data or not user_data["stripe_customer_id"]:
                return []
        
        customer_id = user_data["stripe_customer_id"]
        
        # Get payment methods from Stripe
        result = payment_manager.get_customer_payment_methods(customer_id)
        
        if not result.success:
            raise HTTPException(status_code=400, detail=result.message)
        
        payment_methods = result.data["payment_methods"]
        return [PaymentMethodResponse(**pm) for pm in payment_methods]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get payment methods: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve payment methods")


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events."""
    try:
        payload = await request.body()
        signature = request.headers.get("stripe-signature")
        
        if not signature:
            raise HTTPException(status_code=400, detail="Missing Stripe signature")
        
        # Handle webhook
        result = payment_manager.handle_webhook(payload.decode(), signature)
        
        if not result.success:
            logger.error(f"Webhook handling failed: {result.message}")
            raise HTTPException(status_code=400, detail=result.message)
        
        return {"success": True, "message": result.message}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")


@router.get("/billing/usage")
async def get_billing_usage(current_user: dict = Depends(verify_token)):
    """Get current billing usage and limits."""
    try:
        user_id = current_user["user_id"]
        
        # Get user subscription info
        with db_manager.get_connection() as conn:
            cursor = conn.execute(
                """SELECT subscription_tier, subscription_expires_at 
                   FROM users WHERE id = ?""",
                (user_id,)
            )
            user_data = cursor.fetchone()
            
            if not user_data:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Get usage statistics
            cursor = conn.execute(
                "SELECT COUNT(*) as device_count FROM devices WHERE user_id = ? AND is_active = 1",
                (user_id,)
            )
            device_count = cursor.fetchone()["device_count"]
            
            cursor = conn.execute(
                "SELECT COUNT(*) as vehicle_count FROM vehicles WHERE user_id = ? AND is_active = 1",
                (user_id,)
            )
            vehicle_count = cursor.fetchone()["vehicle_count"]
        
        # Get plan limits
        plan_id = user_data["subscription_tier"] or "basic"
        plan = payment_manager.get_plan(plan_id)
        
        if not plan:
            plan = payment_manager.get_plan("basic")
        
        return {
            "current_plan": plan.__dict__,
            "usage": {
                "devices": {
                    "current": device_count,
                    "limit": plan.max_devices,
                    "unlimited": plan.max_devices == -1
                },
                "vehicles": {
                    "current": vehicle_count,
                    "limit": plan.max_vehicles,
                    "unlimited": plan.max_vehicles == -1
                }
            },
            "subscription_expires_at": user_data["subscription_expires_at"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get billing usage: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve billing usage")
