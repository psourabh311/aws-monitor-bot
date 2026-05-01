import asyncio
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from database import Database
from aws_monitor import AWSMonitor


class AlertScheduler:
    """
    Background mein automatically AWS check karta hai.
    1. Har 1 minute mein alerts check karta hai
    2. Har subah 9 baje daily summary bhejta hai
    """

    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.scheduler = AsyncIOScheduler()
        print("✅ AlertScheduler initialized!")

    def start(self):
        """Scheduler start karo - 3 jobs add karo"""

        # Job 1: Har 1 minute mein alerts check karo
        self.scheduler.add_job(
            self.check_all_alerts,
            'interval',
            minutes=1,
            id='alert_checker',
            name='Check All Alerts'
        )

        # Job 2: Har subah 9 baje daily summary bhejo
        self.scheduler.add_job(
            self.send_daily_summary_all,
            CronTrigger(hour=9, minute=0),
            id='daily_summary',
            name='Daily Summary'
        )

        # Job 3: Har Monday subah 9 baje weekly report bhejo
        self.scheduler.add_job(
            self.send_weekly_report_all,
            CronTrigger(day_of_week='mon', hour=9, minute=0),
            id='weekly_report',
            name='Weekly Cost Report'
        )

        # Job 4: Har 6 ghante mein cost anomaly check karo
        self.scheduler.add_job(
            self.check_cost_anomaly_all,
            'interval',
            hours=6,
            id='anomaly_checker',
            name='Cost Anomaly Check'
        )

        # Job 5: Har raat 8 baje renewal reminder check karo
        self.scheduler.add_job(
            self.check_renewal_reminders,
            CronTrigger(hour=20, minute=0),
            id='renewal_reminder',
            name='Renewal Reminder'
        )

        self.scheduler.start()
        print("✅ Scheduler started!")
        print("   - Har 1 minute mein alerts check hoga")
        print("   - Har subah 9 baje daily summary jayegi")
        print("   - Har Monday 9 baje weekly report jayegi")
        print("   - Har 6 ghante mein cost anomaly check hoga")
        print("   - Har raat 8 baje renewal reminder check hoga")

    def stop(self):
        self.scheduler.shutdown()
        print("✅ Scheduler stopped.")

    # ─────────────────────────────────────────
    # RENEWAL REMINDER
    # ─────────────────────────────────────────

    async def check_renewal_reminders(self):
        """Premium expire hone wale users ko remind karo"""
        print(f"🔔 Renewal reminders check... {datetime.now().strftime('%H:%M:%S')}")

        conn = self.db._get_conn()
        cursor = conn.cursor()
        try:
            # Users jinki premium 3 din mein expire hogi
            cursor.execute("""
                SELECT s.user_id, u.first_name, s.end_date
                FROM subscriptions s
                JOIN users u ON s.user_id = u.user_id
                WHERE s.is_active = true
                AND s.plan_name = 'premium'
                AND s.end_date BETWEEN NOW() AND NOW() + INTERVAL '3 days'
            """)
            expiring = cursor.fetchall()
        finally:
            cursor.close()
            self.db._put_conn(conn)

        for user in expiring:
            try:
                await self.send_renewal_reminder(user[0], user[1], user[2])
            except Exception as e:
                print(f"❌ Renewal reminder failed for {user[0]}: {e}")

    async def send_renewal_reminder(self, user_id, first_name, end_date):
        """User ko renewal reminder bhejo"""
        days_left = (end_date - datetime.now()).days + 1

        message = f"Your Premium subscription expires in {days_left} day(s)!\n\n"
        message += f"Expiry: {end_date.strftime('%d-%m-%Y')}\n\n"
        message += f"Renew now to keep enjoying:\n"
        message += f"- 30 min alert checks\n"
        message += f"- Weekly cost reports\n"
        message += f"- Cost anomaly detection\n"
        message += f"- PDF monthly reports\n\n"
        message += f"Tap Upgrade in the main menu to renew."

        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Renew Premium - Rs.499", callback_data="buy_premium")]
        ])

        await self.bot.send_message(
            chat_id=user_id,
            text=message,
            reply_markup=keyboard
        )
        print(f"✅ Renewal reminder sent to {first_name} ({user_id})")

    # ─────────────────────────────────────────
    # COST ANOMALY DETECTION
    # ─────────────────────────────────────────

    async def check_cost_anomaly_all(self):
        """Saare users ke liye cost anomaly check karo"""
        print(f"🔍 Cost anomaly check... {datetime.now().strftime('%H:%M:%S')}")

        conn = self.db._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT user_id, first_name FROM users")
            users = cursor.fetchall()
        finally:
            cursor.close()
            self.db._put_conn(conn)

        for user in users:
            try:
                await self.check_cost_anomaly(user[0], user[1])
            except Exception as e:
                print(f"❌ Anomaly check failed for {user[0]}: {e}")

    async def check_cost_anomaly(self, user_id, first_name):
        """
        Ek user ka cost anomaly check karo.
        Agar aaj ka cost kal se 2x zyada ho to alert bhejo.
        """
        accounts = self.db.get_aws_accounts(user_id)
        if not accounts:
            return

        account = accounts[0]
        creds = self.db.get_aws_credentials(account['account_id'])
        if not creds:
            return

        try:
            monitor = AWSMonitor(
                access_key=creds['access_key'],
                secret_key=creds['secret_key'],
                region=creds['region']
            )

            today_cost = monitor.get_today_cost()
            yesterday_cost = monitor.get_yesterday_cost()

            if today_cost is None or yesterday_cost is None:
                return

            # Agar kal ka cost $1 se kam tha to skip karo
            # (small amounts mein percentage misleading hoti hai)
            if yesterday_cost < 1.0:
                return

            # 2x threshold - agar aaj kal se double ho
            if today_cost >= yesterday_cost * 2:
                increase_percent = round(((today_cost - yesterday_cost) / yesterday_cost) * 100, 1)

                message = f"🚨 *Cost Anomaly Detected!*\n\n"
                message += f"📈 Aaj ka cost: *${today_cost:.2f}*\n"
                message += f"📉 Kal ka cost: *${yesterday_cost:.2f}*\n"
                message += f"⚠️ Increase: *{increase_percent}% ↑*\n\n"
                message += f"Kuch unusual chal raha hai!\n"
                message += f"AWS Console check karo.\n\n"
                message += f"🌍 Account: {account['account_name']}"

                await self.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode='Markdown'
                )
                print(f"🚨 Anomaly alert sent to {first_name} - Today: ${today_cost}, Yesterday: ${yesterday_cost}")
            else:
                print(f"   ✅ {first_name} - No anomaly. Today: ${today_cost}, Yesterday: ${yesterday_cost}")

        except Exception as e:
            print(f"❌ Error checking anomaly for {user_id}: {e}")

    # ─────────────────────────────────────────
    # WEEKLY REPORT
    # ─────────────────────────────────────────

    async def send_weekly_report_all(self):
        """Saare users ko weekly report bhejo"""
        print(f"📊 Weekly report bhej raha hoon... {datetime.now().strftime('%H:%M:%S')}")

        conn = self.db._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT user_id, first_name FROM users")
            users = cursor.fetchall()
        finally:
            cursor.close()
            self.db._put_conn(conn)

        for user in users:
            try:
                await self.send_weekly_report(user[0], user[1])
            except Exception as e:
                print(f"❌ Weekly report failed for {user[0]}: {e}")

    async def send_weekly_report(self, user_id, first_name):
        """Ek user ko weekly cost comparison bhejo"""
        accounts = self.db.get_aws_accounts(user_id)
        if not accounts:
            return

        account = accounts[0]
        creds = self.db.get_aws_credentials(account['account_id'])
        if not creds:
            return

        try:
            monitor = AWSMonitor(
                access_key=creds['access_key'],
                secret_key=creds['secret_key'],
                region=creds['region']
            )

            this_week, last_week = monitor.get_weekly_costs()

            if this_week is None:
                return

            # Difference calculate karo
            diff = this_week - last_week

            if last_week > 0:
                percent = round((diff / last_week) * 100, 1)
            else:
                percent = 0

            # Trend icon
            if diff > 0:
                trend = f"📈 +${diff:.2f} ({percent}% ↑) - Cost badh rahi hai!"
            elif diff < 0:
                trend = f"📉 -${abs(diff):.2f} ({abs(percent)}% ↓) - Cost kam hui! 🎉"
            else:
                trend = "➡️ Same as last week"

            message = f"📊 *Weekly Cost Report*\n"
            message += f"👋 Hello {first_name}!\n\n"
            message += f"━━━━━━━━━━━━━━━━━━\n"
            message += f"📅 This Week:  *${this_week:.2f}*\n"
            message += f"📅 Last Week:  *${last_week:.2f}*\n"
            message += f"━━━━━━━━━━━━━━━━━━\n"
            message += f"{trend}\n\n"
            message += f"🌍 Account: {account['account_name']}"

            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='Markdown'
            )
            print(f"✅ Weekly report sent to {first_name}")

        except Exception as e:
            print(f"❌ Error sending weekly report to {user_id}: {e}")

    # ─────────────────────────────────────────
    # DAILY SUMMARY
    # ─────────────────────────────────────────

    async def send_daily_summary_all(self):
        """Saare users ko daily summary bhejo"""
        print(f"🌅 Daily summary bhej raha hoon... {datetime.now().strftime('%H:%M:%S')}")

        # Database se saare users nikalo
        conn = self.db._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT user_id, first_name FROM users")
            users = cursor.fetchall()
        finally:
            cursor.close()
            self.db._put_conn(conn)

        for user in users:
            try:
                await self.send_daily_summary(user[0], user[1])
            except Exception as e:
                print(f"❌ Summary send failed for user {user[0]}: {e}")

    async def send_daily_summary(self, user_id, first_name):
        """Ek user ko daily summary bhejo"""
        accounts = self.db.get_aws_accounts(user_id)

        if not accounts:
            return  # Koi account nahi - summary mat bhejo

        account = accounts[0]
        creds = self.db.get_aws_credentials(account['account_id'])

        if not creds:
            return

        try:
            monitor = AWSMonitor(
                access_key=creds['access_key'],
                secret_key=creds['secret_key'],
                region=creds['region']
            )

            # Data fetch karo
            instances = monitor.get_ec2_instances()
            today_cost = monitor.get_today_cost()
            month_cost = monitor.get_month_cost()
            alerts = self.db.get_user_alerts(user_id)

            # Message banao
            message = f"🌅 *Good Morning {first_name}!*\n\n"
            message += f"� *Daily AWS Summary*\n"
            message += f"━━━━━━━━━━━━━━━━━━\n"
            message += f"🖥️ EC2 Instances: *{len(instances)} running*\n"

            if today_cost is not None:
                message += f"💰 Today's Cost: *${today_cost:.2f}*\n"

            if month_cost is not None:
                message += f"📆 Month so far: *${month_cost:.2f}*\n"

            message += f"🔔 Active Alerts: *{len(alerts)}*\n"
            message += f"━━━━━━━━━━━━━━━━━━\n"
            message += f"🌍 Account: {account['account_name']} ({creds['region']})\n\n"
            message += f"Have a great day! ☀️"

            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='Markdown'
            )
            print(f"✅ Daily summary sent to {first_name} ({user_id})")

        except Exception as e:
            print(f"❌ Error sending summary to {user_id}: {e}")

    # ─────────────────────────────────────────
    # ALERT CHECKER
    # ─────────────────────────────────────────

    async def check_all_alerts(self):
        """Saare active alerts check karo"""
        print(f"🔍 Alerts check kar raha hoon... {datetime.now().strftime('%H:%M:%S')}")

        alerts = self.db.get_all_active_alerts()

        if not alerts:
            print("   Koi active alert nahi hai.")
            return

        for alert in alerts:
            try:
                await self.check_single_alert(alert)
            except Exception as e:
                print(f"❌ Alert {alert['config_id']} error: {e}")

    async def check_single_alert(self, alert):
        """Ek alert check karo"""
        creds = self.db.get_aws_credentials(alert['account_id'])
        if not creds:
            return

        monitor = AWSMonitor(
            access_key=creds['access_key'],
            secret_key=creds['secret_key'],
            region=creds['region']
        )

        current_value = self.get_metric_value(monitor, alert['metric_name'])
        if current_value is None:
            return

        print(f"   {alert['metric_name']}: {current_value} {alert['comparison_operator']} {alert['threshold_value']}")

        if self.is_threshold_crossed(current_value, alert['threshold_value'], alert['comparison_operator']):
            print(f"   🚨 Alert triggered! Notifying user {alert['user_id']}")
            await self.send_alert(alert, current_value)
            # History save karo
            self.db.save_alert_history(alert['config_id'], current_value)

    def get_metric_value(self, monitor, metric_name):
        """Metric ka current value fetch karo"""
        if metric_name == 'daily_cost':
            return monitor.get_today_cost()
        elif metric_name == 'monthly_cost':
            return monitor.get_month_cost()
        elif metric_name == 'cpu_average':
            instances = monitor.get_ec2_instances()
            if not instances:
                return 0.0
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
        """Threshold cross hua ya nahi"""
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
        message = f"""🚨 *ALERT TRIGGERED!*

📊 Metric: {alert['metric_name']}
📈 Current Value: {current_value}
⚠️ Condition: {alert['comparison_operator']} {alert['threshold_value']}

🕐 Time: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}

/start se dashboard dekho."""

        try:
            await self.bot.send_message(
                chat_id=alert['user_id'],
                text=message,
                parse_mode='Markdown'
            )
            print(f"   ✅ Alert sent to user {alert['user_id']}")
        except Exception as e:
            print(f"   ❌ Alert send failed: {e}")
