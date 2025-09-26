"""
Subscription Management API for Mercedes W222 OBD Scanner
Handles subscription plans, payments, and billing
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import stripe
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mercedes_obd_scanner.auth.jwt_auth import jwt_auth
from mercedes_obd_scanner.auth.user_manager import user_manager

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

# Configure Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "sk_test_your_stripe_key_here")

# Subscription plans
SUBSCRIPTION_PLANS = {
    "free": {
        "name": "Free Plan",
        "price": 0,
        "duration_days": 0,  # Unlimited
        "features": ["Basic OBD scanning", "Trip history (last 30 days)", "Basic diagnostics"],
        "limits": {"trips_per_month": 50, "ai_analyses_per_month": 0, "data_retention_days": 30},
    },
    "premium": {
        "name": "Premium Plan",
        "price": 9.99,
        "duration_days": 30,
        "stripe_price_id": "price_premium_monthly",
        "features": [
            "Advanced OBD scanning",
            "Unlimited trip history",
            "AI-powered trip analysis",
            "Predictive maintenance alerts",
            "Advanced diagnostics",
            "Email support",
        ],
        "limits": {
            "trips_per_month": -1,  # Unlimited
            "ai_analyses_per_month": 100,
            "data_retention_days": 365,
        },
    },
    "pro": {
        "name": "Professional Plan",
        "price": 19.99,
        "duration_days": 30,
        "stripe_price_id": "price_pro_monthly",
        "features": [
            "All Premium features",
            "Unlimited AI analyses",
            "Custom reports",
            "API access",
            "Priority support",
            "Fleet management (up to 5 vehicles)",
            "Advanced ML insights",
        ],
        "limits": {
            "trips_per_month": -1,  # Unlimited
            "ai_analyses_per_month": -1,  # Unlimited
            "data_retention_days": -1,  # Unlimited
            "vehicles": 5,
        },
    },
}


# Pydantic models
class SubscriptionPlan(BaseModel):
    plan_id: str
    name: str
    price: float
    duration_days: int
    features: List[str]
    limits: Dict[str, Any]
    stripe_price_id: Optional[str] = None


class CreateCheckoutSessionRequest(BaseModel):
    plan_id: str
    success_url: str
    cancel_url: str


class CheckoutSessionResponse(BaseModel):
    checkout_url: str
    session_id: str


class SubscriptionStatus(BaseModel):
    user_id: str
    current_plan: str
    expires_at: Optional[datetime]
    is_active: bool
    features: List[str]
    limits: Dict[str, Any]
    usage: Dict[str, Any]


class WebhookEvent(BaseModel):
    type: str
    data: Dict[str, Any]


@router.get("/plans", response_model=List[SubscriptionPlan])
async def get_subscription_plans():
    """Get all available subscription plans"""
    plans = []
    for plan_id, plan_data in SUBSCRIPTION_PLANS.items():
        plans.append(SubscriptionPlan(plan_id=plan_id, **plan_data))
    return plans


@router.get("/status", response_model=SubscriptionStatus)
async def get_subscription_status(
    current_user: Dict[str, Any] = Depends(jwt_auth.get_current_user),
):
    """Get current user's subscription status"""
    try:
        user = user_manager.get_user_by_id(current_user["user_id"])
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        plan_data = SUBSCRIPTION_PLANS.get(user.subscription_tier, SUBSCRIPTION_PLANS["free"])
        is_active = user_manager.is_subscription_active(user.user_id)

        # Get usage statistics (placeholder - implement based on your tracking)
        usage = {
            "trips_this_month": 0,  # TODO: Implement actual counting
            "ai_analyses_this_month": 0,  # TODO: Implement actual counting
            "data_storage_mb": 0,  # TODO: Implement actual calculation
        }

        return SubscriptionStatus(
            user_id=user.user_id,
            current_plan=user.subscription_tier,
            expires_at=user.subscription_expires,
            is_active=is_active,
            features=plan_data["features"],
            limits=plan_data["limits"],
            usage=usage,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get subscription status: {str(e)}",
        )


@router.post("/checkout", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    request: CreateCheckoutSessionRequest,
    current_user: Dict[str, Any] = Depends(jwt_auth.get_current_user),
):
    """Create Stripe checkout session for subscription"""
    try:
        if request.plan_id not in SUBSCRIPTION_PLANS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid subscription plan"
            )

        plan = SUBSCRIPTION_PLANS[request.plan_id]

        if request.plan_id == "free":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create checkout for free plan",
            )

        user = user_manager.get_user_by_id(current_user["user_id"])
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Create Stripe checkout session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price": plan.get("stripe_price_id", "price_default"),
                    "quantity": 1,
                }
            ],
            mode="subscription",
            success_url=request.success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=request.cancel_url,
            customer_email=user.email,
            metadata={"user_id": user.user_id, "plan_id": request.plan_id},
        )

        return CheckoutSessionResponse(
            checkout_url=checkout_session.url, session_id=checkout_session.id
        )

    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Stripe error: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create checkout session: {str(e)}",
        )


@router.post("/cancel")
async def cancel_subscription(current_user: Dict[str, Any] = Depends(jwt_auth.get_current_user)):
    """Cancel current subscription"""
    try:
        user = user_manager.get_user_by_id(current_user["user_id"])
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        if user.subscription_tier == "free":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="No active subscription to cancel"
            )

        # In a real implementation, you would:
        # 1. Cancel the Stripe subscription
        # 2. Update the user's subscription to expire at the end of the current period
        # For now, we'll just set it to free immediately

        success = user_manager.update_subscription(
            user_id=user.user_id, tier="free", duration_days=0
        )

        if success:
            return {"message": "Subscription cancelled successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to cancel subscription",
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel subscription: {str(e)}",
        )


@router.post("/webhook")
async def stripe_webhook(webhook_event: WebhookEvent):
    """Handle Stripe webhook events"""
    try:
        event_type = webhook_event.type

        if event_type == "checkout.session.completed":
            # Handle successful payment
            session = webhook_event.data["object"]
            user_id = session["metadata"]["user_id"]
            plan_id = session["metadata"]["plan_id"]

            plan = SUBSCRIPTION_PLANS.get(plan_id)
            if plan:
                success = user_manager.update_subscription(
                    user_id=user_id,
                    tier=plan_id,
                    duration_days=plan["duration_days"],
                    payment_id=session["id"],
                    amount=plan["price"],
                )

                if not success:
                    # Log error but don't fail the webhook
                    print(f"Failed to update subscription for user {user_id}")

        elif event_type == "invoice.payment_succeeded":
            # Handle recurring payment success
            invoice = webhook_event.data["object"]
            # Update subscription renewal
            pass

        elif event_type == "invoice.payment_failed":
            # Handle payment failure
            # invoice = webhook_event.data["object"]
            # Notify user, potentially downgrade subscription
            pass

        return {"status": "success"}

    except Exception as e:
        # Log the error but return success to avoid webhook retries
        print(f"Webhook error: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.get("/usage")
async def get_usage_statistics(current_user: Dict[str, Any] = Depends(jwt_auth.get_current_user)):
    """Get detailed usage statistics for current user"""
    try:
        user = user_manager.get_user_by_id(current_user["user_id"])
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # TODO: Implement actual usage tracking
        # This would query your database for:
        # - Number of trips this month
        # - Number of AI analyses used
        # - Data storage used
        # - API calls made (for Pro users)

        current_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        usage_stats = {
            "current_period": {
                "start": current_month.isoformat(),
                "end": (current_month + timedelta(days=32)).replace(day=1) - timedelta(days=1),
                "trips": 0,  # TODO: Count actual trips
                "ai_analyses": 0,  # TODO: Count actual AI analyses
                "data_storage_mb": 0,  # TODO: Calculate actual storage
                "api_calls": 0,  # TODO: Count API calls
            },
            "limits": SUBSCRIPTION_PLANS[user.subscription_tier]["limits"],
            "plan": user.subscription_tier,
        }

        return usage_stats

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get usage statistics: {str(e)}",
        )


@router.post("/upgrade")
async def upgrade_subscription(
    request: CreateCheckoutSessionRequest,
    current_user: Dict[str, Any] = Depends(jwt_auth.get_current_user),
):
    """Upgrade current subscription"""
    # This is essentially the same as creating a checkout session
    # but with additional logic to handle upgrades/downgrades
    return await create_checkout_session(request, current_user)
