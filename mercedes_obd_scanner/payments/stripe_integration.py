"""
Comprehensive Stripe payment integration for Mercedes W222 OBD Scanner.
Handles subscriptions, one-time payments, and billing management.
"""

import stripe
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
import os
import json

logger = logging.getLogger(__name__)


@dataclass
class SubscriptionPlan:
    """Subscription plan configuration."""
    id: str
    name: str
    price: float
    currency: str
    interval: str  # 'month' or 'year'
    features: List[str]
    stripe_price_id: str
    max_devices: int
    max_vehicles: int


@dataclass
class PaymentResult:
    """Payment operation result."""
    success: bool
    message: str
    data: Optional[Dict] = None
    error_code: Optional[str] = None


class StripePaymentManager:
    """Manages Stripe payment operations."""
    
    # Subscription plans configuration
    PLANS = {
        'basic': SubscriptionPlan(
            id='basic',
            name='Basic Plan',
            price=9.99,
            currency='usd',
            interval='month',
            features=[
                'Real-time OBD monitoring',
                'Basic diagnostics',
                'Trip logging',
                '1 device',
                '1 vehicle',
                'Email support'
            ],
            stripe_price_id='price_basic_monthly',  # Set in Stripe dashboard
            max_devices=1,
            max_vehicles=1
        ),
        'professional': SubscriptionPlan(
            id='professional',
            name='Professional Plan',
            price=29.99,
            currency='usd',
            interval='month',
            features=[
                'Everything in Basic',
                'AI-powered analysis',
                'Predictive maintenance',
                'Advanced reporting',
                'Up to 3 devices',
                'Up to 3 vehicles',
                'Priority support'
            ],
            stripe_price_id='price_professional_monthly',
            max_devices=3,
            max_vehicles=3
        ),
        'enterprise': SubscriptionPlan(
            id='enterprise',
            name='Enterprise Plan',
            price=99.99,
            currency='usd',
            interval='month',
            features=[
                'Everything in Professional',
                'Unlimited devices',
                'Unlimited vehicles',
                'Team management',
                'API access',
                'Custom integrations',
                'Dedicated support'
            ],
            stripe_price_id='price_enterprise_monthly',
            max_devices=-1,  # Unlimited
            max_vehicles=-1  # Unlimited
        )
    }
    
    def __init__(self, api_key: str = None, webhook_secret: str = None):
        """Initialize Stripe payment manager."""
        self.api_key = api_key or os.getenv('STRIPE_SECRET_KEY')
        self.webhook_secret = webhook_secret or os.getenv('STRIPE_WEBHOOK_SECRET')
        
        if not self.api_key:
            raise ValueError("Stripe API key is required")
        
        stripe.api_key = self.api_key
        logger.info("Stripe payment manager initialized")
    
    def create_customer(self, email: str, name: str = None, metadata: Dict = None) -> PaymentResult:
        """Create a new Stripe customer."""
        try:
            customer_data = {
                'email': email,
                'metadata': metadata or {}
            }
            
            if name:
                customer_data['name'] = name
            
            customer = stripe.Customer.create(**customer_data)
            
            return PaymentResult(
                success=True,
                message="Customer created successfully",
                data={
                    'customer_id': customer.id,
                    'email': customer.email,
                    'created': customer.created
                }
            )
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create customer: {e}")
            return PaymentResult(
                success=False,
                message=f"Failed to create customer: {str(e)}",
                error_code=e.code if hasattr(e, 'code') else 'unknown'
            )
    
    def create_subscription(self, customer_id: str, plan_id: str, 
                          payment_method_id: str = None) -> PaymentResult:
        """Create a new subscription for a customer."""
        try:
            if plan_id not in self.PLANS:
                return PaymentResult(
                    success=False,
                    message=f"Invalid plan ID: {plan_id}",
                    error_code='invalid_plan'
                )
            
            plan = self.PLANS[plan_id]
            
            subscription_data = {
                'customer': customer_id,
                'items': [{
                    'price': plan.stripe_price_id,
                }],
                'metadata': {
                    'plan_id': plan_id,
                    'plan_name': plan.name
                }
            }
            
            if payment_method_id:
                subscription_data['default_payment_method'] = payment_method_id
            
            subscription = stripe.Subscription.create(**subscription_data)
            
            return PaymentResult(
                success=True,
                message="Subscription created successfully",
                data={
                    'subscription_id': subscription.id,
                    'status': subscription.status,
                    'current_period_start': subscription.current_period_start,
                    'current_period_end': subscription.current_period_end,
                    'plan': plan.__dict__
                }
            )
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create subscription: {e}")
            return PaymentResult(
                success=False,
                message=f"Failed to create subscription: {str(e)}",
                error_code=e.code if hasattr(e, 'code') else 'unknown'
            )
    
    def update_subscription(self, subscription_id: str, new_plan_id: str) -> PaymentResult:
        """Update an existing subscription to a new plan."""
        try:
            if new_plan_id not in self.PLANS:
                return PaymentResult(
                    success=False,
                    message=f"Invalid plan ID: {new_plan_id}",
                    error_code='invalid_plan'
                )
            
            new_plan = self.PLANS[new_plan_id]
            
            # Get current subscription
            subscription = stripe.Subscription.retrieve(subscription_id)
            
            # Update subscription
            updated_subscription = stripe.Subscription.modify(
                subscription_id,
                items=[{
                    'id': subscription['items']['data'][0].id,
                    'price': new_plan.stripe_price_id,
                }],
                metadata={
                    'plan_id': new_plan_id,
                    'plan_name': new_plan.name
                }
            )
            
            return PaymentResult(
                success=True,
                message="Subscription updated successfully",
                data={
                    'subscription_id': updated_subscription.id,
                    'status': updated_subscription.status,
                    'new_plan': new_plan.__dict__
                }
            )
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to update subscription: {e}")
            return PaymentResult(
                success=False,
                message=f"Failed to update subscription: {str(e)}",
                error_code=e.code if hasattr(e, 'code') else 'unknown'
            )
    
    def cancel_subscription(self, subscription_id: str, at_period_end: bool = True) -> PaymentResult:
        """Cancel a subscription."""
        try:
            if at_period_end:
                # Cancel at the end of the current period
                subscription = stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True
                )
                message = "Subscription will be canceled at the end of the current period"
            else:
                # Cancel immediately
                subscription = stripe.Subscription.delete(subscription_id)
                message = "Subscription canceled immediately"
            
            return PaymentResult(
                success=True,
                message=message,
                data={
                    'subscription_id': subscription.id,
                    'status': subscription.status,
                    'canceled_at': subscription.canceled_at,
                    'cancel_at_period_end': subscription.cancel_at_period_end
                }
            )
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to cancel subscription: {e}")
            return PaymentResult(
                success=False,
                message=f"Failed to cancel subscription: {str(e)}",
                error_code=e.code if hasattr(e, 'code') else 'unknown'
            )
    
    def create_payment_intent(self, amount: float, currency: str = 'usd', 
                            customer_id: str = None, metadata: Dict = None) -> PaymentResult:
        """Create a payment intent for one-time payments."""
        try:
            payment_intent_data = {
                'amount': int(amount * 100),  # Convert to cents
                'currency': currency,
                'metadata': metadata or {}
            }
            
            if customer_id:
                payment_intent_data['customer'] = customer_id
            
            payment_intent = stripe.PaymentIntent.create(**payment_intent_data)
            
            return PaymentResult(
                success=True,
                message="Payment intent created successfully",
                data={
                    'payment_intent_id': payment_intent.id,
                    'client_secret': payment_intent.client_secret,
                    'amount': payment_intent.amount,
                    'currency': payment_intent.currency,
                    'status': payment_intent.status
                }
            )
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create payment intent: {e}")
            return PaymentResult(
                success=False,
                message=f"Failed to create payment intent: {str(e)}",
                error_code=e.code if hasattr(e, 'code') else 'unknown'
            )
    
    def create_setup_intent(self, customer_id: str) -> PaymentResult:
        """Create a setup intent for saving payment methods."""
        try:
            setup_intent = stripe.SetupIntent.create(
                customer=customer_id,
                usage='off_session'
            )
            
            return PaymentResult(
                success=True,
                message="Setup intent created successfully",
                data={
                    'setup_intent_id': setup_intent.id,
                    'client_secret': setup_intent.client_secret,
                    'status': setup_intent.status
                }
            )
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create setup intent: {e}")
            return PaymentResult(
                success=False,
                message=f"Failed to create setup intent: {str(e)}",
                error_code=e.code if hasattr(e, 'code') else 'unknown'
            )
    
    def get_customer_subscriptions(self, customer_id: str) -> PaymentResult:
        """Get all subscriptions for a customer."""
        try:
            subscriptions = stripe.Subscription.list(
                customer=customer_id,
                status='all'
            )
            
            subscription_data = []
            for sub in subscriptions.data:
                plan_id = sub.metadata.get('plan_id', 'unknown')
                plan = self.PLANS.get(plan_id)
                
                subscription_data.append({
                    'id': sub.id,
                    'status': sub.status,
                    'current_period_start': sub.current_period_start,
                    'current_period_end': sub.current_period_end,
                    'cancel_at_period_end': sub.cancel_at_period_end,
                    'plan_id': plan_id,
                    'plan': plan.__dict__ if plan else None
                })
            
            return PaymentResult(
                success=True,
                message="Subscriptions retrieved successfully",
                data={'subscriptions': subscription_data}
            )
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to get customer subscriptions: {e}")
            return PaymentResult(
                success=False,
                message=f"Failed to get subscriptions: {str(e)}",
                error_code=e.code if hasattr(e, 'code') else 'unknown'
            )
    
    def get_customer_payment_methods(self, customer_id: str) -> PaymentResult:
        """Get all payment methods for a customer."""
        try:
            payment_methods = stripe.PaymentMethod.list(
                customer=customer_id,
                type='card'
            )
            
            methods_data = []
            for pm in payment_methods.data:
                methods_data.append({
                    'id': pm.id,
                    'type': pm.type,
                    'card': {
                        'brand': pm.card.brand,
                        'last4': pm.card.last4,
                        'exp_month': pm.card.exp_month,
                        'exp_year': pm.card.exp_year
                    } if pm.card else None,
                    'created': pm.created
                })
            
            return PaymentResult(
                success=True,
                message="Payment methods retrieved successfully",
                data={'payment_methods': methods_data}
            )
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to get payment methods: {e}")
            return PaymentResult(
                success=False,
                message=f"Failed to get payment methods: {str(e)}",
                error_code=e.code if hasattr(e, 'code') else 'unknown'
            )
    
    def handle_webhook(self, payload: str, signature: str) -> PaymentResult:
        """Handle Stripe webhook events."""
        try:
            if not self.webhook_secret:
                return PaymentResult(
                    success=False,
                    message="Webhook secret not configured",
                    error_code='no_webhook_secret'
                )
            
            event = stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
            
            # Handle different event types
            event_type = event['type']
            event_data = event['data']['object']
            
            logger.info(f"Received webhook event: {event_type}")
            
            if event_type == 'customer.subscription.created':
                return self._handle_subscription_created(event_data)
            elif event_type == 'customer.subscription.updated':
                return self._handle_subscription_updated(event_data)
            elif event_type == 'customer.subscription.deleted':
                return self._handle_subscription_deleted(event_data)
            elif event_type == 'invoice.payment_succeeded':
                return self._handle_payment_succeeded(event_data)
            elif event_type == 'invoice.payment_failed':
                return self._handle_payment_failed(event_data)
            else:
                logger.info(f"Unhandled webhook event type: {event_type}")
                return PaymentResult(
                    success=True,
                    message=f"Event {event_type} received but not handled"
                )
            
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Webhook signature verification failed: {e}")
            return PaymentResult(
                success=False,
                message="Invalid webhook signature",
                error_code='invalid_signature'
            )
        except Exception as e:
            logger.error(f"Webhook handling error: {e}")
            return PaymentResult(
                success=False,
                message=f"Webhook handling error: {str(e)}",
                error_code='webhook_error'
            )
    
    def _handle_subscription_created(self, subscription_data: Dict) -> PaymentResult:
        """Handle subscription created webhook."""
        logger.info(f"Subscription created: {subscription_data['id']}")
        # Here you would update your database with the new subscription
        return PaymentResult(
            success=True,
            message="Subscription created webhook handled",
            data={'subscription_id': subscription_data['id']}
        )
    
    def _handle_subscription_updated(self, subscription_data: Dict) -> PaymentResult:
        """Handle subscription updated webhook."""
        logger.info(f"Subscription updated: {subscription_data['id']}")
        # Here you would update your database with the subscription changes
        return PaymentResult(
            success=True,
            message="Subscription updated webhook handled",
            data={'subscription_id': subscription_data['id']}
        )
    
    def _handle_subscription_deleted(self, subscription_data: Dict) -> PaymentResult:
        """Handle subscription deleted webhook."""
        logger.info(f"Subscription deleted: {subscription_data['id']}")
        # Here you would update your database to reflect the cancellation
        return PaymentResult(
            success=True,
            message="Subscription deleted webhook handled",
            data={'subscription_id': subscription_data['id']}
        )
    
    def _handle_payment_succeeded(self, invoice_data: Dict) -> PaymentResult:
        """Handle successful payment webhook."""
        logger.info(f"Payment succeeded for invoice: {invoice_data['id']}")
        # Here you would update your database with the successful payment
        return PaymentResult(
            success=True,
            message="Payment succeeded webhook handled",
            data={'invoice_id': invoice_data['id']}
        )
    
    def _handle_payment_failed(self, invoice_data: Dict) -> PaymentResult:
        """Handle failed payment webhook."""
        logger.warning(f"Payment failed for invoice: {invoice_data['id']}")
        # Here you would handle the failed payment (notify user, retry, etc.)
        return PaymentResult(
            success=True,
            message="Payment failed webhook handled",
            data={'invoice_id': invoice_data['id']}
        )
    
    def get_available_plans(self) -> List[Dict]:
        """Get all available subscription plans."""
        return [plan.__dict__ for plan in self.PLANS.values()]
    
    def get_plan(self, plan_id: str) -> Optional[SubscriptionPlan]:
        """Get a specific subscription plan."""
        return self.PLANS.get(plan_id)
    
    def validate_plan_limits(self, plan_id: str, devices: int, vehicles: int) -> bool:
        """Validate if usage is within plan limits."""
        plan = self.get_plan(plan_id)
        if not plan:
            return False
        
        # Check device limit
        if plan.max_devices != -1 and devices > plan.max_devices:
            return False
        
        # Check vehicle limit
        if plan.max_vehicles != -1 and vehicles > plan.max_vehicles:
            return False
        
        return True


# Usage example and testing
if __name__ == "__main__":
    # This would be used for testing the payment system
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # Initialize payment manager (requires Stripe keys in environment)
    try:
        payment_manager = StripePaymentManager()
        
        # Get available plans
        plans = payment_manager.get_available_plans()
        print("Available plans:")
        for plan in plans:
            print(f"- {plan['name']}: ${plan['price']}/{plan['interval']}")
        
        print("Stripe payment integration initialized successfully!")
        
    except Exception as e:
        print(f"Failed to initialize payment system: {e}")
        print("Make sure STRIPE_SECRET_KEY is set in environment variables")
