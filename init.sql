-- =============================================
-- AWS Monitor Bot - Database Schema
-- =============================================

-- Users table
-- Stores all users who have started the bot
CREATE TABLE IF NOT EXISTS users (
    user_id     BIGINT PRIMARY KEY,        -- Telegram unique user ID
    username    VARCHAR(100),              -- Telegram @username
    first_name  VARCHAR(100),              -- User's first name
    referral_code VARCHAR(20) UNIQUE,      -- Unique referral code
    created_at  TIMESTAMP DEFAULT NOW()    -- Account creation timestamp
);

-- AWS Accounts table
-- Stores connected AWS accounts with encrypted credentials
CREATE TABLE IF NOT EXISTS aws_accounts (
    account_id               SERIAL PRIMARY KEY,
    user_id                  BIGINT REFERENCES users(user_id),
    account_name             VARCHAR(100),                     -- e.g. "Production", "Testing"
    aws_region               VARCHAR(50),                      -- e.g. "us-east-1"
    aws_access_key_encrypted TEXT,                             -- AES-256 encrypted access key
    aws_secret_key_encrypted TEXT,                             -- AES-256 encrypted secret key
    is_active                BOOLEAN DEFAULT true,
    created_at               TIMESTAMP DEFAULT NOW()
);

-- Alert Configurations table
-- Stores user-defined alert rules
CREATE TABLE IF NOT EXISTS alert_configs (
    config_id           SERIAL PRIMARY KEY,
    account_id          INT REFERENCES aws_accounts(account_id),
    metric_name         VARCHAR(100),   -- e.g. "daily_cost", "cpu_average"
    threshold_value     FLOAT,          -- e.g. 10.0, 80.0
    comparison_operator VARCHAR(10),    -- e.g. ">", "<", ">="
    check_interval      INT,            -- Check frequency in minutes
    is_enabled          BOOLEAN DEFAULT true,
    created_at          TIMESTAMP DEFAULT NOW()
);

-- Subscriptions table
-- Tracks user subscription plans and payment history
CREATE TABLE IF NOT EXISTS subscriptions (
    sub_id          SERIAL PRIMARY KEY,
    user_id         BIGINT REFERENCES users(user_id),
    plan_name       VARCHAR(20) DEFAULT 'free',
    payment_link_id VARCHAR(100),
    start_date      TIMESTAMP DEFAULT NOW(),
    end_date        TIMESTAMP,
    is_active       BOOLEAN DEFAULT true
);

-- Referrals table
-- Tracks referral relationships between users
CREATE TABLE IF NOT EXISTS referrals (
    referral_id  SERIAL PRIMARY KEY,
    referrer_id  BIGINT REFERENCES users(user_id),
    referred_id  BIGINT REFERENCES users(user_id),
    created_at   TIMESTAMP DEFAULT NOW(),
    reward_given BOOLEAN DEFAULT false
);

-- Alert History table
-- Records every time an alert is triggered
CREATE TABLE IF NOT EXISTS alert_history (
    history_id      SERIAL PRIMARY KEY,
    config_id       INT REFERENCES alert_configs(config_id),
    triggered_at    TIMESTAMP DEFAULT NOW(),
    triggered_value FLOAT
);

SELECT 'All tables created successfully!' AS status;
