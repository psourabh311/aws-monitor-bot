import os
import psycopg2
from psycopg2 import pool
from dotenv import load_dotenv
from security import SecurityManager

# Load environment variables
load_dotenv()

class Database:
    """Handles all PostgreSQL database operations"""

    def __init__(self):
        # Initialize security manager for credential encryption/decryption
        self.security = SecurityManager()

        # Create connection pool (min 1, max 10 connections)
        try:
            self.pool = psycopg2.pool.SimpleConnectionPool(
                1, 10,
                host=os.getenv('DB_HOST', 'localhost'),
                database=os.getenv('DB_NAME', 'aws_monitor_db'),
                user=os.getenv('DB_USER', 'postgres'),
                password=os.getenv('DB_PASSWORD')
            )
            print("Database connected!")
        except Exception as e:
            print(f"Database connection failed: {e}")
            raise

    def _get_conn(self):
        """Get a connection from the pool"""
        return self.pool.getconn()

    def _put_conn(self, conn):
        """Return a connection back to the pool"""
        self.pool.putconn(conn)

    # ─────────────────────────────────────────
    # USER OPERATIONS
    # ─────────────────────────────────────────

    def add_user(self, user_id, username, first_name):
        """Save a new user - ignore if already exists"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO users (user_id, username, first_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id) DO NOTHING
            """, (user_id, username, first_name))
            conn.commit()
            print(f"User saved: {first_name}")
            return True
        except Exception as e:
            conn.rollback()
            print(f"Error saving user: {e}")
            return False
        finally:
            cursor.close()
            self._put_conn(conn)

    def get_user(self, user_id):
        """Fetch user data by user_id"""
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
            print(f"Error fetching user: {e}")
            return None
        finally:
            cursor.close()
            self._put_conn(conn)

    # ─────────────────────────────────────────
    # AWS ACCOUNT OPERATIONS
    # ─────────────────────────────────────────

    def add_aws_account(self, user_id, account_name, access_key, secret_key, region):
        """Save AWS account with encrypted credentials"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            # Encrypt credentials before storing
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
            print(f"AWS account saved! ID: {account_id}")
            return account_id
        except Exception as e:
            conn.rollback()
            print(f"Error saving AWS account: {e}")
            return None
        finally:
            cursor.close()
            self._put_conn(conn)

    def get_aws_accounts(self, user_id):
        """Get all active AWS accounts for a user"""
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
            print(f"Error fetching accounts: {e}")
            return []
        finally:
            cursor.close()
            self._put_conn(conn)

    def get_aws_credentials(self, account_id):
        """Fetch and decrypt AWS credentials for an account"""
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
            print(f"Error fetching credentials: {e}")
            return None
        finally:
            cursor.close()
            self._put_conn(conn)

    # ─────────────────────────────────────────
    # ALERT OPERATIONS
    # ─────────────────────────────────────────

    def add_alert(self, account_id, metric_name, threshold, operator, interval):
        """Save a new alert configuration"""
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
            print(f"Alert saved! ID: {config_id}")
            return config_id
        except Exception as e:
            conn.rollback()
            print(f"Error saving alert: {e}")
            return None
        finally:
            cursor.close()
            self._put_conn(conn)

    def get_user_alerts(self, user_id):
        """Get all active alerts for a user"""
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
            print(f"Error fetching alerts: {e}")
            return []
        finally:
            cursor.close()
            self._put_conn(conn)

    def get_all_active_alerts(self):
        """Get all active alerts across all users (used by scheduler)"""
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
            print(f"Error fetching active alerts: {e}")
            return []
        finally:
            cursor.close()
            self._put_conn(conn)

    # ─────────────────────────────────────────
    # SUBSCRIPTION OPERATIONS
    # ─────────────────────────────────────────

    def get_user_plan(self, user_id):
        """Get user's current subscription plan (defaults to free)"""
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
            print(f"Error fetching plan: {e}")
            return 'free'
        finally:
            cursor.close()
            self._put_conn(conn)

    def create_subscription(self, user_id, plan_name, payment_link_id):
        """Create a new subscription after successful payment"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            from datetime import datetime, timedelta
            end_date = datetime.now() + timedelta(days=30)

            # Deactivate existing subscription
            cursor.execute("""
                UPDATE subscriptions SET is_active = false
                WHERE user_id = %s
            """, (user_id,))

            # Create new subscription
            cursor.execute("""
                INSERT INTO subscriptions
                    (user_id, plan_name, payment_link_id, end_date)
                VALUES (%s, %s, %s, %s)
                RETURNING sub_id
            """, (user_id, plan_name, payment_link_id, end_date))

            sub_id = cursor.fetchone()[0]
            conn.commit()
            print(f"Subscription created! ID: {sub_id}")
            return sub_id
        except Exception as e:
            conn.rollback()
            print(f"Error creating subscription: {e}")
            return None
        finally:
            cursor.close()
            self._put_conn(conn)

    # ─────────────────────────────────────────
    # REFERRAL OPERATIONS
    # ─────────────────────────────────────────

    def get_or_create_referral_code(self, user_id):
        """Get existing referral code or generate a new one"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            # Check if code already exists
            cursor.execute(
                "SELECT referral_code FROM users WHERE user_id = %s",
                (user_id,)
            )
            row = cursor.fetchone()
            if row and row[0]:
                return row[0]

            # Generate new referral code
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
            print(f"Error with referral code: {e}")
            return None
        finally:
            cursor.close()
            self._put_conn(conn)

    def get_user_by_referral_code(self, code):
        """Find user by referral code"""
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
            print(f"Error: {e}")
            return None
        finally:
            cursor.close()
            self._put_conn(conn)

    def add_referral(self, referrer_id, referred_id):
        """Record a referral and grant 7 days free premium to both users"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            # Check if already referred
            cursor.execute(
                "SELECT referral_id FROM referrals WHERE referred_id = %s",
                (referred_id,)
            )
            if cursor.fetchone():
                return False  # Already referred

            # Save referral record
            cursor.execute("""
                INSERT INTO referrals (referrer_id, referred_id, reward_given)
                VALUES (%s, %s, true)
            """, (referrer_id, referred_id))

            # Grant 7 days free premium to both users
            from datetime import datetime, timedelta
            end_date = datetime.now() + timedelta(days=7)

            for uid in [referrer_id, referred_id]:
                cursor.execute("""
                    INSERT INTO subscriptions (user_id, plan_name, end_date)
                    VALUES (%s, 'premium', %s)
                    ON CONFLICT DO NOTHING
                """, (uid, end_date))

            conn.commit()
            print(f"Referral added! {referrer_id} referred {referred_id}")
            return True
        except Exception as e:
            conn.rollback()
            print(f"Error adding referral: {e}")
            return False
        finally:
            cursor.close()
            self._put_conn(conn)

    def get_referral_count(self, user_id):
        """Get total number of successful referrals by a user"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT COUNT(*) FROM referrals WHERE referrer_id = %s",
                (user_id,)
            )
            return cursor.fetchone()[0]
        except Exception as e:
            print(f"Error: {e}")
            return 0
        finally:
            cursor.close()
            self._put_conn(conn)

    # ─────────────────────────────────────────
    # ALERT HISTORY
    # ─────────────────────────────────────────

    def save_alert_history(self, config_id, triggered_value):
        """Save a record when an alert is triggered"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO alert_history (config_id, triggered_value)
                VALUES (%s, %s)
            """, (config_id, triggered_value))
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Error saving alert history: {e}")
        finally:
            cursor.close()
            self._put_conn(conn)

    def get_alert_history(self, user_id, limit=10):
        """Get alert trigger history for a user"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT ah.history_id, ac.metric_name, ac.comparison_operator,
                       ac.threshold_value, ah.triggered_value, ah.triggered_at
                FROM alert_history ah
                JOIN alert_configs ac ON ah.config_id = ac.config_id
                JOIN aws_accounts aa ON ac.account_id = aa.account_id
                WHERE aa.user_id = %s
                ORDER BY ah.triggered_at DESC
                LIMIT %s
            """, (user_id, limit))
            rows = cursor.fetchall()
            history = []
            for row in rows:
                history.append({
                    'metric_name': row[1],
                    'operator': row[2],
                    'threshold': row[3],
                    'triggered_value': row[4],
                    'triggered_at': row[5]
                })
            return history
        except Exception as e:
            print(f"Error fetching alert history: {e}")
            return []
        finally:
            cursor.close()
            self._put_conn(conn)

    # ─────────────────────────────────────────
    # ADMIN OPERATIONS
    # ─────────────────────────────────────────

    def get_admin_stats(self):
        """Get bot statistics for admin dashboard"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            stats = {}

            # Total users
            cursor.execute("SELECT COUNT(*) FROM users")
            stats['total_users'] = cursor.fetchone()[0]

            # Premium users
            cursor.execute("""
                SELECT COUNT(DISTINCT user_id) FROM subscriptions
                WHERE is_active = true AND plan_name = 'premium'
                AND (end_date IS NULL OR end_date > NOW())
            """)
            stats['premium_users'] = cursor.fetchone()[0]

            # Free users
            stats['free_users'] = stats['total_users'] - stats['premium_users']

            # Total active AWS accounts
            cursor.execute("SELECT COUNT(*) FROM aws_accounts WHERE is_active = true")
            stats['total_accounts'] = cursor.fetchone()[0]

            # Active alerts
            cursor.execute("SELECT COUNT(*) FROM alert_configs WHERE is_enabled = true")
            stats['active_alerts'] = cursor.fetchone()[0]

            # New users today
            cursor.execute("""
                SELECT COUNT(*) FROM users
                WHERE created_at >= NOW() - INTERVAL '24 hours'
            """)
            stats['new_today'] = cursor.fetchone()[0]

            # New users this week
            cursor.execute("""
                SELECT COUNT(*) FROM users
                WHERE created_at >= NOW() - INTERVAL '7 days'
            """)
            stats['new_this_week'] = cursor.fetchone()[0]

            # Revenue this month
            cursor.execute("""
                SELECT COUNT(*), SUM(
                    CASE plan_name
                        WHEN 'premium' THEN 499
                        ELSE 0
                    END
                )
                FROM subscriptions
                WHERE start_date >= DATE_TRUNC('month', NOW())
            """)
            row = cursor.fetchone()
            stats['revenue_this_month'] = int(row[1] or 0)
            stats['subscriptions_this_month'] = int(row[0] or 0)

            # Total revenue all time
            cursor.execute("""
                SELECT SUM(
                    CASE plan_name
                        WHEN 'premium' THEN 499
                        ELSE 0
                    END
                )
                FROM subscriptions
                WHERE plan_name = 'premium'
            """)
            total_rev = cursor.fetchone()[0]
            stats['total_revenue'] = int(total_rev or 0)

            return stats

        except Exception as e:
            print(f"Error fetching admin stats: {e}")
            return {}
        finally:
            cursor.close()
            self._put_conn(conn)

    def get_all_users(self):
        """Get list of recent users (last 20)"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT u.user_id, u.username, u.first_name, u.created_at,
                       COALESCE(s.plan_name, 'free') as plan
                FROM users u
                LEFT JOIN subscriptions s ON u.user_id = s.user_id
                    AND s.is_active = true
                    AND (s.end_date IS NULL OR s.end_date > NOW())
                ORDER BY u.created_at DESC
                LIMIT 20
            """)
            rows = cursor.fetchall()
            users = []
            for row in rows:
                users.append({
                    'user_id': row[0],
                    'username': row[1],
                    'first_name': row[2],
                    'created_at': row[3],
                    'plan': row[4]
                })
            return users
        except Exception as e:
            print(f"Error fetching users: {e}")
            return []
        finally:
            cursor.close()
            self._put_conn(conn)

    def close(self):
        """Close all database connections"""
        self.pool.closeall()
        print("Database connections closed")


# Run this file directly to test database connection
if __name__ == '__main__':
    print("Testing Database...\n")
    db = Database()

    db.add_user(123456789, "test_user", "Test User")
    user = db.get_user(123456789)
    print(f"User found: {user}")

    print("\nDatabase working perfectly!")
    db.close()
