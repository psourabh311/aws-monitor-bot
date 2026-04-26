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
