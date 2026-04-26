# ☁️ AWS Monitor Bot

A Telegram bot that monitors your AWS infrastructure in real-time and sends automated alerts.

## Features

- **EC2 Monitoring** - Track running instances and CPU utilization
- **Cost Tracking** - Daily and monthly AWS spending via Cost Explorer
- **Automated Alerts** - Set custom thresholds and get notified automatically
- **Encrypted Storage** - AWS credentials stored with AES-256 encryption
- **24/7 Monitoring** - Background scheduler checks every minute

## Tech Stack

- **Python 3.12+**
- **python-telegram-bot** - Telegram Bot API
- **Boto3** - AWS SDK for Python
- **PostgreSQL** - Database
- **APScheduler** - Background job scheduling
- **Cryptography (Fernet)** - Credentials encryption
- **AWS EC2** - Deployment

## Project Structure

```
aws-monitor-bot/
├── bot.py            # Main bot - all Telegram commands
├── database.py       # PostgreSQL operations
├── aws_monitor.py    # AWS API integration (EC2, CloudWatch, Cost Explorer)
├── security.py       # Encryption/Decryption
├── scheduler.py      # Background alert checker
├── init.sql          # Database schema
├── requirements.txt  # Python dependencies
└── .env.example      # Environment variables template
```

## Setup

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/aws-monitor-bot.git
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
DB_HOST=localhost
DB_NAME=aws_monitor_db
DB_USER=postgres
DB_PASSWORD=your_db_password
ENCRYPTION_KEY=your_fernet_encryption_key
```

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Start the bot |
| `/help` | Show all commands |
| `/addaccount` | Connect AWS account |
| `/listaccounts` | View connected accounts |
| `/status` | EC2 instances and CPU usage |
| `/costs` | Daily and monthly costs |
| `/setalert` | Create custom alert |
| `/listalerts` | View active alerts |

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
        "ce:GetCostAndUsage"
      ],
      "Resource": "*"
    }
  ]
}
```

## Deployment (AWS EC2)

```bash
# Copy files to EC2
scp -i key.pem *.py requirements.txt init.sql ubuntu@your-ec2-ip:~/

# SSH into EC2
ssh -i key.pem ubuntu@your-ec2-ip

# Setup and run as service
sudo systemctl enable awsbot
sudo systemctl start awsbot
```

## Roadmap

- [ ] Inline keyboard buttons
- [ ] Daily summary reports
- [ ] Multiple AWS account support
- [ ] RDS monitoring
- [ ] S3 storage monitoring
- [ ] Premium subscription (Razorpay)
- [ ] PDF reports
- [ ] Web dashboard

## License

MIT License
