import os
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from database import Database
from aws_monitor import AWSMonitor
from scheduler import AlertScheduler

# .env file load karo
load_dotenv()

# Database ek baar initialize karo - poore bot ke liye
db = Database()


# ─────────────────────────────────────────
# /start command
# ─────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Jab koi pehli baar bot use kare"""
    user = update.effective_user

    # User ko database mein save karo
    db.add_user(user.id, user.username, user.first_name)

    message = f"""👋 Hello {user.first_name}!

🤖 Main hoon AWS Monitor Bot.
Main tumhare AWS account ko monitor karta hoon aur alerts deta hoon.

📋 Available Commands:
/start - Ye message
/help - Saari commands
/addaccount - AWS account connect karo
/status - AWS status dekho
/setalert - Alert set karo
/listalerts - Apne alerts dekho

Shuru karne ke liye /addaccount use karo! 🚀"""

    await update.message.reply_text(message)


# ─────────────────────────────────────────
# /help command
# ─────────────────────────────────────────
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saari commands ki list"""
    message = """📚 AWS Monitor Bot - Help

🔗 Account Setup:
/addaccount - AWS account connect karo
/listaccounts - Apne accounts dekho

📊 Monitoring:
/status - EC2 instances aur CPU dekho
/costs - Aaj aur is mahine ka cost

🔔 Alerts:
/setalert - Naya alert banao
/listalerts - Apne alerts dekho

ℹ️ /addaccount se shuru karo!"""

    await update.message.reply_text(message)


# ─────────────────────────────────────────
# /addaccount command
# ─────────────────────────────────────────
async def add_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """AWS account add karne ki instructions"""

    # Agar credentials saath mein diye hain
    # Format: /addaccount <name> <access_key> <secret_key> <region>
    if len(context.args) == 4:
        account_name = context.args[0]
        access_key = context.args[1]
        secret_key = context.args[2]
        region = context.args[3]
        user_id = update.effective_user.id

        # Processing message
        msg = await update.message.reply_text("🔄 Credentials verify kar raha hoon...")

        # AWS credentials test karo pehle
        try:
            monitor = AWSMonitor(access_key, secret_key, region)
            if not monitor.test_connection():
                await msg.edit_text("❌ AWS credentials galat hain!\n\nDobara check karo aur try karo.")
                return
        except Exception as e:
            await msg.edit_text(f"❌ AWS connection failed!\n\nError: {str(e)}")
            return

        # Credentials sahi hain - database mein save karo
        account_id = db.add_aws_account(user_id, account_name, access_key, secret_key, region)

        if account_id:
            await msg.edit_text(
                f"✅ AWS Account Connected!\n\n"
                f"📝 Name: {account_name}\n"
                f"🌍 Region: {region}\n"
                f"🔒 Credentials encrypted & saved\n\n"
                f"Ab /status use karo!"
            )
            # Security ke liye original message delete karo
            await asyncio.sleep(3)
            try:
                await update.message.delete()
            except:
                pass
        else:
            await msg.edit_text("❌ Database mein save nahi hua! Try again.")

    else:
        # Instructions do
        message = """🔗 AWS Account Connect Kaise Kare:

Step 1: AWS Console → IAM → Users
Step 2: Naya user banao (programmatic access)
Step 3: Ye permissions do:
  • AmazonEC2ReadOnlyAccess
  • CloudWatchReadOnlyAccess
  • AWSCostExplorerReadOnlyAccess
Step 4: Access Key aur Secret Key copy karo

Step 5: Ye command use karo:
/addaccount <name> <access_key> <secret_key> <region>

Example:
/addaccount Production AKIA... wJalr... ap-south-1

Available Regions:
• ap-south-1 (Mumbai)
• us-east-1 (N. Virginia)
• ap-southeast-1 (Singapore)

⚠️ Credentials automatically encrypted ho jaate hain!"""

        await update.message.reply_text(message)


# ─────────────────────────────────────────
# /listaccounts command
# ─────────────────────────────────────────
async def list_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User ke saare AWS accounts dikhao"""
    user_id = update.effective_user.id
    accounts = db.get_aws_accounts(user_id)

    if not accounts:
        await update.message.reply_text(
            "❌ Koi AWS account connected nahi hai!\n\n"
            "/addaccount se add karo."
        )
        return

    message = "📋 Tumhare AWS Accounts:\n\n"
    for i, acc in enumerate(accounts, 1):
        message += f"{i}. {acc['account_name']}\n"
        message += f"   Region: {acc['aws_region']}\n"
        message += f"   ID: {acc['account_id']}\n\n"

    await update.message.reply_text(message)


# ─────────────────────────────────────────
# /status command
# ─────────────────────────────────────────
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """AWS status dikhao - EC2 instances aur CPU"""
    user_id = update.effective_user.id
    accounts = db.get_aws_accounts(user_id)

    if not accounts:
        await update.message.reply_text(
            "❌ Pehle AWS account connect karo!\n/addaccount"
        )
        return

    msg = await update.message.reply_text("🔄 AWS se data fetch kar raha hoon...")

    # Pehle account ka status dikhao
    account = accounts[0]
    creds = db.get_aws_credentials(account['account_id'])

    if not creds:
        await msg.edit_text("❌ Credentials decrypt nahi hue!")
        return

    try:
        monitor = AWSMonitor(creds['access_key'], creds['secret_key'], creds['region'])
        instances = monitor.get_ec2_instances()

        message = f"📊 {account['account_name']} Status\n"
        message += f"🌍 Region: {creds['region']}\n\n"

        if instances:
            message += f"🖥️ EC2 Instances: {len(instances)} running\n\n"
            for inst in instances[:5]:  # Max 5 dikhao
                cpu = monitor.get_cpu_utilization(inst['id'])
                cpu_str = f"{cpu}%" if cpu is not None else "N/A"
                message += f"• {inst['name']} ({inst['type']})\n"
                message += f"  CPU: {cpu_str}\n"
        else:
            message += "🖥️ Koi running EC2 instance nahi hai\n"

        message += f"\n🕐 Updated: {__import__('datetime').datetime.now().strftime('%H:%M:%S')}"
        message += "\n\nCost dekhne ke liye /costs use karo"

        await msg.edit_text(message)

    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")


# ─────────────────────────────────────────
# /costs command
# ─────────────────────────────────────────
async def costs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """AWS costs dikhao"""
    user_id = update.effective_user.id
    accounts = db.get_aws_accounts(user_id)

    if not accounts:
        await update.message.reply_text("❌ Pehle AWS account connect karo!\n/addaccount")
        return

    msg = await update.message.reply_text("🔄 Cost data fetch kar raha hoon...")

    account = accounts[0]
    creds = db.get_aws_credentials(account['account_id'])

    try:
        monitor = AWSMonitor(creds['access_key'], creds['secret_key'], creds['region'])
        today_cost = monitor.get_today_cost()
        month_cost = monitor.get_month_cost()

        message = f"💰 {account['account_name']} - Cost Report\n\n"

        if today_cost is not None:
            message += f"📅 Aaj ka cost: ${today_cost:.2f}\n"
        else:
            message += "📅 Aaj ka cost: N/A\n"

        if month_cost is not None:
            message += f"📆 Is mahine ka cost: ${month_cost:.2f}\n"
        else:
            message += "📆 Is mahine ka cost: N/A\n"

        message += "\n⚠️ Cost Explorer enable hona chahiye AWS mein"

        await msg.edit_text(message)

    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")


# ─────────────────────────────────────────
# /setalert command
# ─────────────────────────────────────────
async def set_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Alert set karo"""
    # Format: /setalert <metric> <operator> <value> <interval>
    # Example: /setalert daily_cost > 10 60

    if len(context.args) != 4:
        message = """⚙️ Alert Set Karne Ka Format:

/setalert <metric> <operator> <value> <interval_minutes>

Available Metrics:
• daily_cost - Aaj ka cost
• monthly_cost - Is mahine ka cost
• cpu_average - Average CPU %

Operators: > < >= <=

Examples:
/setalert daily_cost > 10 60
(Agar aaj ka cost $10 se zyada ho to alert - har 60 min check)

/setalert cpu_average > 80 30
(Agar CPU 80% se zyada ho to alert - har 30 min check)"""

        await update.message.reply_text(message)
        return

    metric = context.args[0]
    operator = context.args[1]
    value = context.args[2]
    interval = context.args[3]

    # Validation
    valid_metrics = ['daily_cost', 'monthly_cost', 'cpu_average']
    valid_operators = ['>', '<', '>=', '<=']

    if metric not in valid_metrics:
        await update.message.reply_text(f"❌ Invalid metric!\nValid: {', '.join(valid_metrics)}")
        return

    if operator not in valid_operators:
        await update.message.reply_text(f"❌ Invalid operator!\nValid: {', '.join(valid_operators)}")
        return

    try:
        threshold = float(value)
        check_interval = int(interval)
    except ValueError:
        await update.message.reply_text("❌ Value aur interval numbers hone chahiye!")
        return

    user_id = update.effective_user.id
    accounts = db.get_aws_accounts(user_id)

    if not accounts:
        await update.message.reply_text("❌ Pehle AWS account connect karo!\n/addaccount")
        return

    account_id = accounts[0]['account_id']
    config_id = db.add_alert(account_id, metric, threshold, operator, check_interval)

    if config_id:
        await update.message.reply_text(
            f"✅ Alert Set!\n\n"
            f"📊 Metric: {metric}\n"
            f"⚠️ Condition: {operator} {threshold}\n"
            f"⏰ Check: Har {check_interval} minute\n\n"
            f"Main tumhe notify karunga! 🔔"
        )
    else:
        await update.message.reply_text("❌ Alert save nahi hua!")


# ─────────────────────────────────────────
# /listalerts command
# ─────────────────────────────────────────
async def list_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User ke saare alerts dikhao"""
    user_id = update.effective_user.id
    alerts = db.get_user_alerts(user_id)

    if not alerts:
        await update.message.reply_text(
            "📭 Koi alert set nahi hai!\n\n"
            "/setalert se banao."
        )
        return

    message = "🔔 Tumhare Active Alerts:\n\n"
    for alert in alerts:
        message += f"ID: {alert['config_id']}\n"
        message += f"Metric: {alert['metric_name']}\n"
        message += f"Condition: {alert['comparison_operator']} {alert['threshold_value']}\n"
        message += f"Check: Har {alert['check_interval']} min\n\n"

    await update.message.reply_text(message)


# ─────────────────────────────────────────
# Error Handler
# ─────────────────────────────────────────
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Koi bhi error aaye to gracefully handle karo"""
    print(f"❌ Error: {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ Kuch galat hua! Dobara try karo."
        )


# ─────────────────────────────────────────
# MAIN - Bot Start
# ─────────────────────────────────────────
def main():
    print("🤖 AWS Monitor Bot starting...")

    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token:
        print("❌ BOT_TOKEN .env mein nahi hai!")
        return

    # Application banao
    app = Application.builder().token(bot_token).build()

    # Commands register karo
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("addaccount", add_account))
    app.add_handler(CommandHandler("listaccounts", list_accounts))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("costs", costs))
    app.add_handler(CommandHandler("setalert", set_alert))
    app.add_handler(CommandHandler("listalerts", list_alerts))

    # Error handler
    app.add_error_handler(error_handler)

    print("✅ Bot ready!")
    print("📱 Telegram pe /start bhejo")
    print("🛑 Band karne ke liye Ctrl+C\n")

    # Scheduler start karo - bot start hone ke baad
    async def post_init(application):
        scheduler = AlertScheduler(application.bot)
        scheduler.start()

    app.post_init = post_init

    # Bot chalu karo
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
