# ☁️ AWS Monitor Bot

[![Live Bot](https://img.shields.io/badge/Telegram-AWS%20Monitor%20Bot-blue?logo=telegram)](https://t.me/aws_monitor_telegram_bot)
[![GitHub](https://img.shields.io/badge/GitHub-psourabh311-black?logo=github)](https://github.com/psourabh311/aws-monitor-bot)

A production-ready Telegram bot that monitors your AWS infrastructure in real-time, sends automated alerts, and provides detailed reports.

## Try it Live

**Bot:** [t.me/aws_monitor_telegram_bot](https://t.me/aws_monitor_telegram_bot)

## Features

### Monitoring
- **EC2 Monitoring** - Track running instances and CPU utilization
- **RDS Monitoring** - Database instances status and storage
- **S3 Storage** - Bucket sizes and file counts
- **Cost Tracking** - Daily, weekly, and monthly AWS spending

### Alerts & Reports
- **Automated Alerts** - Set custom thresholds, get notified automatically
- **Daily Morning Summary** - Automatic 9 AM AWS status report
- **Weekly Cost Comparison** - Compare this week vs last week spending
- **Cost Anomaly Detection** - Alert when cost suddenly doubles
- **PDF Monthly Report** - Download detailed PDF report

### User Experience
- **Inline Buttons** - No commands to remember, just click buttons
- **Multiple AWS Accounts** - Switch between accounts easily
- **Referral System** - Invite friends, both get 7 days free premium

### Monetization
- **Freemium Model** - Free and Premium plans
- **Razorpay Integration** - UPI, cards, net banking support
- **Subscription Management** - 30-day premium subscriptions

## Tech Stack

- **Python 3.12+**
- **python-telegram-bot** - Telegram Bot API
- **Boto3** - AWS SDK (EC2, CloudWatch, Cost Explorer, RDS, S3)
- **PostgreSQL** - Database
- **APScheduler** - Background job scheduling
- **Cryptography (Fernet)** - AES-256 credentials encryption
- **ReportLab** - PDF report generation
- **Razorpay** - Payment gateway
- **AWS EC2** - 24/7 deployment with systemd

## Project Structure

```
aws-monitor-bot/
├── bot.py            # Main bot - all Telegram commands & buttons
├── database.py       # PostgreSQL operations
├── aws_monitor.py    # AWS API (EC2, CloudWatch, Cost Explorer, RDS, S3)
├── security.py       # AES-256 Encryption/Decryption
├── scheduler.py      # Background tasks (alerts, daily summary, weekly report)
├── subscription.py   # Razorpay payment & subscription management
├── report.py         # PDF report generation
├── init.sql          # Database schema
├── requirements.txt  # Python dependencies
└── .env.example      # Environment variables template
```

## Setup

### 1. Clone the repository
```bash
git clone https://github.com/psourabh311/aws-monitor-bot.git
cd aws-monitor-bot
```

### 2. Create virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
```bash
cp .env.example .env
# Edit .env with your credentials
```

### 5. Setup database
```bash
psql -U postgres -d aws_monitor_db -f init.sql
```

### 6. Run the bot
```bash
python3 bot.py
```

## Environment Variables

```
BOT_TOKEN=your_telegram_bot_token
BOT_USERNAME=your_bot_username
DB_HOST=localhost
DB_NAME=aws_monitor_db
DB_USER=postgres
DB_PASSWORD=your_db_password
ENCRYPTION_KEY=your_fernet_encryption_key
RAZORPAY_KEY_ID=your_razorpay_key_id
RAZORPAY_KEY_SECRET=your_razorpay_secret
```

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Start the bot / Main menu |
| `/addaccount` | Connect AWS account |
| `/setalert` | Create custom alert |
| `/deletealert` | Delete an alert |

## Subscription Plans

| Feature | Free | Premium (₹499/mo) |
|---------|------|-------------------|
| AWS Accounts | 1 | 5 |
| Alerts | 5 | 50 |
| Check Interval | 60 min | 5 min |
| Daily Summary | ✅ | ✅ |
| Weekly Report | ❌ | ✅ |
| Anomaly Detection | ❌ | ✅ |
| PDF Reports | ❌ | ✅ |

## AWS IAM Permissions Required

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "ec2:DescribeRegions",
        "cloudwatch:GetMetricStatistics",
        "ce:GetCostAndUsage",
        "rds:DescribeDBInstances",
        "s3:ListAllMyBuckets"
      ],
      "Resource": "*"
    }
  ]
}
```

## Deployment (AWS EC2)

```bash
# Upload files
scp -i key.pem *.py requirements.txt init.sql ubuntu@your-ec2-ip:~/

# SSH and setup
ssh -i key.pem ubuntu@your-ec2-ip
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run as systemd service (24/7)
sudo systemctl enable awsbot
sudo systemctl start awsbot
```

## License

MIT License

---

Built with Python, AWS SDK, and Telegram Bot API
