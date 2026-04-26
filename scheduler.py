import asyncio
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from database import Database
from aws_monitor import AWSMonitor


class AlertScheduler:
    """
    Background mein automatically AWS check karta hai.
    Agar threshold cross ho to Telegram pe alert bhejta hai.
    """

    def __init__(self, bot):
        # Telegram bot instance - alerts bhejne ke liye
        self.bot = bot

        # Database - alert configs aur credentials ke liye
        self.db = Database()

        # AsyncIOScheduler - background timer
        # Alternative: threading.Timer - but asyncio bot ke saath better kaam karta hai
        self.scheduler = AsyncIOScheduler()

        print("✅ AlertScheduler initialized!")

    def start(self):
        """Scheduler start karo - har 1 minute mein check karega"""
        self.scheduler.add_job(
            self.check_all_alerts,       # Ye function run hoga
            'interval',                   # Type: interval based
            minutes=1,                    # Har 1 minute mein
            id='alert_checker',
            name='Check All Alerts'
        )
        self.scheduler.start()
        print("✅ Scheduler started! Har 1 minute mein alerts check hoga.")

    def stop(self):
        """Scheduler band karo"""
        self.scheduler.shutdown()
        print("✅ Scheduler stopped.")

    async def check_all_alerts(self):
        """
        Saare active alerts check karo.
        Ye function har 1 minute mein automatically chalega.
        """
        print(f"🔍 Alerts check kar raha hoon... {datetime.now().strftime('%H:%M:%S')}")

        # Database se saare active alerts nikalo
        alerts = self.db.get_all_active_alerts()

        if not alerts:
            print("   Koi active alert nahi hai.")
            return

        for alert in alerts:
            try:
                await self.check_single_alert(alert)
            except Exception as e:
                print(f"❌ Alert {alert['config_id']} check karne mein error: {e}")

    async def check_single_alert(self, alert):
        """Ek alert check karo aur zarurat padne par notify karo"""

        # AWS credentials nikalo
        creds = self.db.get_aws_credentials(alert['account_id'])
        if not creds:
            return

        # AWS Monitor initialize karo
        monitor = AWSMonitor(
            access_key=creds['access_key'],
            secret_key=creds['secret_key'],
            region=creds['region']
        )

        # Metric ki current value nikalo
        current_value = self.get_metric_value(monitor, alert['metric_name'])
        if current_value is None:
            return

        print(f"   {alert['metric_name']}: {current_value} {alert['comparison_operator']} {alert['threshold_value']}")

        # Threshold cross hua?
        if self.is_threshold_crossed(current_value, alert['threshold_value'], alert['comparison_operator']):
            print(f"   🚨 Alert triggered! Notifying user {alert['user_id']}")
            await self.send_alert(alert, current_value)

    def get_metric_value(self, monitor, metric_name):
        """Metric ka current value fetch karo AWS se"""
        if metric_name == 'daily_cost':
            return monitor.get_today_cost()
        elif metric_name == 'monthly_cost':
            return monitor.get_month_cost()
        elif metric_name == 'cpu_average':
            instances = monitor.get_ec2_instances()
            if not instances:
                return 0.0
            # Saare instances ka average CPU
            total = 0
            count = 0
            for inst in instances:
                cpu = monitor.get_cpu_utilization(inst['id'])
                if cpu is not None:
                    total += cpu
                    count += 1
            return round(total / count, 2) if count > 0 else 0.0
        return None

    def is_threshold_crossed(self, current, threshold, operator):
        """Check karo threshold cross hua ya nahi"""
        if operator == '>':
            return current > threshold
        elif operator == '<':
            return current < threshold
        elif operator == '>=':
            return current >= threshold
        elif operator == '<=':
            return current <= threshold
        return False

    async def send_alert(self, alert, current_value):
        """User ko Telegram pe alert bhejo"""
        message = f"""🚨 ALERT TRIGGERED!

📊 Metric: {alert['metric_name']}
📈 Current Value: {current_value}
⚠️ Condition: {alert['comparison_operator']} {alert['threshold_value']}

🕐 Time: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}

/status se details dekho."""

        try:
            await self.bot.send_message(
                chat_id=alert['user_id'],
                text=message
            )
            print(f"   ✅ Alert sent to user {alert['user_id']}")
        except Exception as e:
            print(f"   ❌ Alert send failed: {e}")
