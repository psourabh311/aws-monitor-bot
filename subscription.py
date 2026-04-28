import os
import razorpay
from dotenv import load_dotenv

load_dotenv()

# Plans definition
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
        'features': ['Everything in Free', '5 AWS accounts', '50 alerts', '5 min checks',
                     'Weekly reports', 'Anomaly detection', 'Priority support']
    }
}


class SubscriptionManager:
    """Payment aur subscription handle karta hai"""

    def __init__(self):
        key_id = os.getenv('RAZORPAY_KEY_ID')
        key_secret = os.getenv('RAZORPAY_KEY_SECRET')

        if not key_id or not key_secret:
            raise ValueError("RAZORPAY keys .env mein nahi hain!")

        self.client = razorpay.Client(auth=(key_id, key_secret))
        self.key_id = key_id
        print("✅ SubscriptionManager ready!")

    def create_payment_link(self, user_id, plan_name, amount):
        """
        Razorpay payment link banao.
        User is link pe click karke pay karega.
        """
        try:
            # Amount paise mein hota hai Razorpay mein
            # ₹499 = 49900 paise
            amount_paise = int(amount * 100)

            payment_link = self.client.payment_link.create({
                "amount": amount_paise,
                "currency": "INR",
                "description": f"AWS Monitor Bot - {plan_name.capitalize()} Plan",
                "notes": {
                    "user_id": str(user_id),
                    "plan": plan_name
                },
                "callback_url": "https://t.me/your_bot",
                "callback_method": "get"
            })

            return payment_link['short_url'], payment_link['id']

        except Exception as e:
            print(f"❌ Payment link creation failed: {e}")
            return None, None

    def verify_payment(self, payment_link_id):
        """
        Payment hua ya nahi check karo.
        Razorpay se payment status fetch karo.
        """
        try:
            link = self.client.payment_link.fetch(payment_link_id)
            return link['status'] == 'paid'
        except Exception as e:
            print(f"❌ Payment verification failed: {e}")
            return False

    def get_plan(self, plan_name):
        """Plan details nikalo"""
        return PLANS.get(plan_name, PLANS['free'])


# Test
if __name__ == '__main__':
    try:
        sm = SubscriptionManager()
        print("\nPlans:")
        for plan_name, plan in PLANS.items():
            print(f"  {plan['name']}: ₹{plan['price']}/month")
        print("\n✅ SubscriptionManager working!")
    except Exception as e:
        print(f"❌ Error: {e}")
