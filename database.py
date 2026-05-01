import os
import psycopg2
from psycopg2 import pool
from dotenv import load_dotenv
from security import SecurityManager

# .env file load karo
load_dotenv()

class Database:
    """PostgreSQL se saare kaam karta hai"""

    def __init__(self):
        # Security manager - credentials encrypt/decrypt ke liye
        self.security = SecurityManager()

        # Database connection pool banao
        # Min 1, Max 10 connections ready rehenge
        try:
            self.pool = psycopg2.pool.SimpleConnectionPool(
                1, 10,
                host=os.getenv('DB_HOST', 'localhost'),
                database=os.getenv('DB_NAME', 'aws_monitor_db'),
                user=os.getenv('DB_USER', 'postgres'),
                password=os.getenv('DB_PASSWORD')
            )
            print("✅ Database connected!")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            raise

    def _get_conn(self):
        """Pool se ek connection lo"""
        return self.pool.getconn()

    def _put_conn(self, conn):
        """Connection wapas pool mein do"""
        self.pool.putconn(conn)

    # ─────────────────────────────────────────
    # USER OPERATIONS
    # ─────────────────────────────────────────

    def add_user(self, user_id, username, first_name):
        """Naya user save karo - agar already hai to ignore karo"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO users (user_id, username, first_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id) DO NOTHING
            """, (user_id, username, first_name))
            conn.commit()
            print(f"✅ User saved: {first_name}")
            return True
        except Exception as e:
            conn.rollback()
            print(f"❌ Error saving user: {e}")
            return False
        finally:
            cursor.close()
            self._put_conn(conn)

    def get_user(self, user_id):
        """User ka data nikalo"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT user_id, username, first_name FROM users WHERE user_id = %s",
                (user_id,)
            )
            row = cursor.fetchone()
            if row:
                return {'user_id': row[0], 'username': row[1], 'first_name': row[2]}
            return None
        except Exception as e:
            print(f"❌ Error fetching user: {e}")
            return None
        finally:
            cursor.close()
            self._put_conn(conn)

    # ─────────────────────────────────────────
    # AWS ACCOUNT OPERATIONS
    # ─────────────────────────────────────────

    def add_aws_account(self, user_id, account_name, access_key, secret_key, region):
        """AWS account encrypted form mein save karo"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            # Credentials encrypt karo pehle
            encrypted_access = self.security.encrypt(access_key)
            encrypted_secret = self.security.encrypt(secret_key)

            cursor.execute("""
                INSERT INTO aws_accounts
                    (user_id, account_name, aws_access_key_encrypted, aws_secret_key_encrypted, aws_region)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING account_id
            """, (user_id, account_name, encrypted_access, encrypted_secret, region))

            account_id = cursor.fetchone()[0]
            conn.commit()
            print(f"✅ AWS account saved! ID: {account_id}")
            return account_id
        except Exception as e:
            conn.rollback()
            print(f"❌ Error saving AWS account: {e}")
            return None
        finally:
            cursor.close()
            self._put_conn(conn)

    def get_aws_accounts(self, user_id):
        """User ke saare AWS accounts nikalo"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT account_id, account_name, aws_region
                FROM aws_accounts
                WHERE user_id = %s AND is_active = true
            """, (user_id,))
            rows = cursor.fetchall()
            accounts = []
            for row in rows:
                accounts.append({
                    'account_id': row[0],
                    'account_name': row[1],
                    'aws_region': row[2]
                })
            return accounts
        except Exception as e:
            print(f"❌ Error fetching accounts: {e}")
            return []
        finally:
            cursor.close()
            self._put_conn(conn)

    def get_aws_credentials(self, account_id):
        """Encrypted credentials nikalo aur decrypt karke do"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT aws_access_key_encrypted, aws_secret_key_encrypted, aws_region
                FROM aws_accounts
                WHERE account_id = %s AND is_active = true
            """, (account_id,))
            row = cursor.fetchone()
            if row:
                return {
                    'access_key': self.security.decrypt(row[0]),
                    'secret_key': self.security.decrypt(row[1]),
                    'region': row[2]
                }
            return None
        except Exception as e:
            print(f"❌ Error fetching credentials: {e}")
            return None
        finally:
            cursor.close()
            self._put_conn(conn)

    # ─────────────────────────────────────────
    # ALERT OPERATIONS
    # ─────────────────────────────────────────

    def add_alert(self, account_id, metric_name, threshold, operator, interval):
        """Naya alert config save karo"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO alert_configs
                    (account_id, metric_name, threshold_value, comparison_operator, check_interval)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING config_id
            """, (account_id, metric_name, threshold, operator, interval))
            config_id = cursor.fetchone()[0]
            conn.commit()
            print(f"✅ Alert saved! ID: {config_id}")
            return config_id
        except Exception as e:
            conn.rollback()
            print(f"❌ Error saving alert: {e}")
            return None
        finally:
            cursor.close()
            self._put_conn(conn)

    def get_user_alerts(self, user_id):
        """User ke saare alerts nikalo"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT ac.config_id, ac.metric_name, ac.threshold_value,
                       ac.comparison_operator, ac.check_interval
                FROM alert_configs ac
                JOIN aws_accounts aa ON ac.account_id = aa.account_id
                WHERE aa.user_id = %s AND ac.is_enabled = true
            """, (user_id,))
            rows = cursor.fetchall()
            alerts = []
            for row in rows:
                alerts.append({
                    'config_id': row[0],
                    'metric_name': row[1],
                    'threshold_value': row[2],
                    'comparison_operator': row[3],
                    'check_interval': row[4]
                })
            return alerts
        except Exception as e:
            print(f"❌ Error fetching alerts: {e}")
            return []
        finally:
            cursor.close()
            self._put_conn(conn)

    def get_all_active_alerts(self):
        """Scheduler ke liye - saare active alerts nikalo"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT ac.config_id, ac.account_id, ac.metric_name,
                       ac.threshold_value, ac.comparison_operator,
                       ac.check_interval, aa.user_id
                FROM alert_configs ac
                JOIN aws_accounts aa ON ac.account_id = aa.account_id
                WHERE ac.is_enabled = true AND aa.is_active = true
            """)
            rows = cursor.fetchall()
            alerts = []
            for row in rows:
                alerts.append({
                    'config_id': row[0],
                    'account_id': row[1],
                    'metric_name': row[2],
                    'threshold_value': row[3],
                    'comparison_operator': row[4],
                    'check_interval': row[5],
                    'user_id': row[6]
                })
            return alerts
        except Exception as e:
            print(f"❌ Error fetching active alerts: {e}")
            return []
        finally:
            cursor.close()
            self._put_conn(conn)

    # ─────────────────────────────────────────
    # SUBSCRIPTION OPERATIONS
    # ─────────────────────────────────────────

    def get_user_plan(self, user_id):
        """User ka current plan nikalo - default free"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT plan_name FROM subscriptions
                WHERE user_id = %s AND is_active = true
                AND (end_date IS NULL OR end_date > NOW())
                ORDER BY start_date DESC LIMIT 1
            """, (user_id,))
            row = cursor.fetchone()
            return row[0] if row else 'free'
        except Exception as e:
            print(f"❌ Error fetching plan: {e}")
            return 'free'
        finally:
            cursor.close()
            self._put_conn(conn)

    def create_subscription(self, user_id, plan_name, payment_link_id):
        """Naya subscription create karo"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            from datetime import datetime, timedelta
            end_date = datetime.now() + timedelta(days=30)

            # Purana subscription deactivate karo
            cursor.execute("""
                UPDATE subscriptions SET is_active = false
                WHERE user_id = %s
            """, (user_id,))

            # Naya subscription add karo
            cursor.execute("""
                INSERT INTO subscriptions
                    (user_id, plan_name, payment_link_id, end_date)
                VALUES (%s, %s, %s, %s)
                RETURNING sub_id
            """, (user_id, plan_name, payment_link_id, end_date))

            sub_id = cursor.fetchone()[0]
            conn.commit()
            print(f"✅ Subscription created! ID: {sub_id}")
            return sub_id
        except Exception as e:
            conn.rollback()
            print(f"❌ Error creating subscription: {e}")
            return None
        finally:
            cursor.close()
            self._put_conn(conn)

    # ─────────────────────────────────────────
    # REFERRAL OPERATIONS
    # ─────────────────────────────────────────

    def get_or_create_referral_code(self, user_id):
        """User ka referral code nikalo ya banao"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            # Check karo code already hai
            cursor.execute(
                "SELECT referral_code FROM users WHERE user_id = %s",
                (user_id,)
            )
            row = cursor.fetchone()
            if row and row[0]:
                return row[0]

            # Naya code banao
            import random
            import string
            user = self.get_user(user_id)
            name_part = (user['first_name'][:6].upper() if user else 'USER')
            random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            code = f"{name_part}_{random_part}"

            cursor.execute(
                "UPDATE users SET referral_code = %s WHERE user_id = %s",
                (code, user_id)
            )
            conn.commit()
            return code
        except Exception as e:
            conn.rollback()
            print(f"❌ Error with referral code: {e}")
            return None
        finally:
            cursor.close()
            self._put_conn(conn)

    def get_user_by_referral_code(self, code):
        """Referral code se user nikalo"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT user_id FROM users WHERE referral_code = %s",
                (code,)
            )
            row = cursor.fetchone()
            return row[0] if row else None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None
        finally:
            cursor.close()
            self._put_conn(conn)

    def add_referral(self, referrer_id, referred_id):
        """Referral record add karo aur dono ko reward do"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            # Check karo already referred nahi hai
            cursor.execute(
                "SELECT referral_id FROM referrals WHERE referred_id = %s",
                (referred_id,)
            )
            if cursor.fetchone():
                return False  # Already referred

            # Referral save karo
            cursor.execute("""
                INSERT INTO referrals (referrer_id, referred_id, reward_given)
                VALUES (%s, %s, true)
            """, (referrer_id, referred_id))

            # Dono ko 7 days free premium do
            from datetime import datetime, timedelta
            end_date = datetime.now() + timedelta(days=7)

            for uid in [referrer_id, referred_id]:
                cursor.execute("""
                    INSERT INTO subscriptions (user_id, plan_name, end_date)
                    VALUES (%s, 'premium', %s)
                    ON CONFLICT DO NOTHING
                """, (uid, end_date))

            conn.commit()
            print(f"✅ Referral added! {referrer_id} referred {referred_id}")
            return True
        except Exception as e:
            conn.rollback()
            print(f"❌ Error adding referral: {e}")
            return False
        finally:
            cursor.close()
            self._put_conn(conn)

    def get_referral_count(self, user_id):
        """User ne kitne log refer kiye"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT COUNT(*) FROM referrals WHERE referrer_id = %s",
                (user_id,)
            )
            return cursor.fetchone()[0]
        except Exception as e:
            print(f"❌ Error: {e}")
            return 0
        finally:
            cursor.close()
            self._put_conn(conn)

    def close(self):
        """Sab connections band karo"""
        self.pool.closeall()
        print("✅ Database connections closed")


# Test
if __name__ == '__main__':
    print("Testing Database...\n")
    db = Database()

    # User add karo
    db.add_user(123456789, "test_user", "Test User")

    # User nikalo
    user = db.get_user(123456789)
    print(f"User found: {user}")

    print("\n✅ Database working perfectly!")
    db.close()
