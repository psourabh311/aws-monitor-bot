-- =============================================
-- AWS Monitor Bot - Database Tables
-- =============================================

-- Users table
-- Har baar koi /start kare to uska data yahan save hoga
CREATE TABLE IF NOT EXISTS users (
    user_id     BIGINT PRIMARY KEY,        -- Telegram ka unique user ID
    username    VARCHAR(100),              -- @username
    first_name  VARCHAR(100),              -- User ka naam
    created_at  TIMESTAMP DEFAULT NOW()   -- Kab join kiya
);

-- AWS Accounts table
-- User ne jo AWS account connect kiya wo yahan save hoga
CREATE TABLE IF NOT EXISTS aws_accounts (
    account_id              SERIAL PRIMARY KEY,                        -- Auto number 1,2,3...
    user_id                 BIGINT REFERENCES users(user_id),          -- Kis user ka account
    account_name            VARCHAR(100),                              -- "Production", "Testing"
    aws_region              VARCHAR(50),                               -- "ap-south-1"
    aws_access_key_encrypted TEXT,                                     -- Encrypted access key
    aws_secret_key_encrypted TEXT,                                     -- Encrypted secret key
    is_active               BOOLEAN DEFAULT true,                      -- Active hai ya nahi
    created_at              TIMESTAMP DEFAULT NOW()
);

-- Alert Configs table
-- User ne jo alerts set kiye wo yahan save honge
CREATE TABLE IF NOT EXISTS alert_configs (
    config_id           SERIAL PRIMARY KEY,
    account_id          INT REFERENCES aws_accounts(account_id),  -- Kis account ka alert
    metric_name         VARCHAR(100),                             -- "daily_cost", "cpu_average"
    threshold_value     FLOAT,                                    -- 500, 80 etc
    comparison_operator VARCHAR(10),                              -- ">", "<", ">="
    check_interval      INT,                                      -- Har kitne minutes mein check
    is_enabled          BOOLEAN DEFAULT true,
    created_at          TIMESTAMP DEFAULT NOW()
);

-- Confirm message
SELECT 'Tables created successfully!' AS status;

-- Subscriptions table
CREATE TABLE IF NOT EXISTS subscriptions (
    sub_id          SERIAL PRIMARY KEY,
    user_id         BIGINT REFERENCES users(user_id),
    plan_name       VARCHAR(20) DEFAULT 'free',
    payment_link_id VARCHAR(100),
    start_date      TIMESTAMP DEFAULT NOW(),
    end_date        TIMESTAMP,
    is_active       BOOLEAN DEFAULT true
);

-- Referral code column
ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_code VARCHAR(20) UNIQUE;

-- Referrals table
CREATE TABLE IF NOT EXISTS referrals (
    referral_id SERIAL PRIMARY KEY,
    referrer_id BIGINT REFERENCES users(user_id),
    referred_id BIGINT REFERENCES users(user_id),
    created_at  TIMESTAMP DEFAULT NOW(),
    reward_given BOOLEAN DEFAULT false
);

-- Alert History table
CREATE TABLE IF NOT EXISTS alert_history (
    history_id      SERIAL PRIMARY KEY,
    config_id       INT REFERENCES alert_configs(config_id),
    triggered_at    TIMESTAMP DEFAULT NOW(),
    triggered_value FLOAT
);

SELECT 'All tables created successfully!' AS status;
