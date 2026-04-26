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
