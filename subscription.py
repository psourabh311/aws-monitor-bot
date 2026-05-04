import os
import razorpay
from dotenv import load_dotenv

load_dotenv()

# Subscription plan definitions
PLANS = {
    'free': {
        'name': 'Free',
        'price': 0,
        'max_accounts': 1,
        'max_alerts': 5,
        'check_interval': 60,
        'features': ['Basic monitoring', 'Daily summary', '1 AWS account', '5 alerts']
    },
    'premium': {
        'name': 'Premium',
        'price': 499,
        'max_accounts': 5,
        'max_alerts': 50,
        'check_interval': 5,
        'features': [
            'Everything in Free',
            '5 AWS accounts',
            '50 alerts',
            '5 min checks',
            'Weekly reports',
            'Anomaly detection',
            'PDF reports',
            '90/180 day charts',
            'Priority support'
        ]
    }
}


class SubscriptionManager:
    """Handles Razorpay payment processing and subscription management"""

    def __init__(self):
        key_id = os.getenv('RAZORPAY_KEY_ID')
        key_secret = os.getenv('RAZORPAY_KEY_SECRET')

        if not key_id or not key_secret:
            raise ValueError("RAZORPAY keys are missing from .env file!")

        self.client = razorpay.Client(auth=(key_id, key_secret))
        self.key_id = key_id
        print("SubscriptionManager ready!")

    def create_payment_link(self, user_id, plan_name, amount):
        """
        Create a Razorpay payment link for a subscription.
        Amount is in INR (e.g., 499 for Rs.499).
        Returns: (payment_url, link_id) or (None, None) on failure
        """
        try:
            # Razorpay requires amount in paise (1 INR = 100 paise)
            amount_paise = int(amount * 100)

            payment_link = self.client.payment_link.create({
                "amount": amount_paise,
                "currency": "INR",
                "description": f"AWS Monitor Bot - {plan_name.capitalize()} Plan",
                "notes": {
                    "user_id": str(user_id),
                    "plan": plan_name
                },
                "callback_url": "https://t.me/aws_monitor_telegram_bot",
                "callback_method": "get"
            })

            return payment_link['short_url'], payment_link['id']

        except Exception as e:
            print(f"Payment link creation failed: {e}")
            return None, None

    def verify_payment(self, payment_link_id):
        """
        Verify if a payment has been completed.
        Returns True if payment status is 'paid'.
        """
        try:
            link = self.client.payment_link.fetch(payment_link_id)
            return link['status'] == 'paid'
        except Exception as e:
            print(f"Payment verification failed: {e}")
            return False

    def get_plan(self, plan_name):
        """Get plan details by plan name"""
        return PLANS.get(plan_name, PLANS['free'])


# Run this file directly to test
if __name__ == '__main__':
    try:
        sm = SubscriptionManager()
        print("\nAvailable Plans:")
        for plan_name, plan in PLANS.items():
            print(f"  {plan['name']}: Rs.{plan['price']}/month")
        print("\nSubscriptionManager working!")
    except Exception as e:
        print(f"Error: {e}")
