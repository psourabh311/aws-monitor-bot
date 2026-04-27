import os
import asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from database import Database
from aws_monitor import AWSMonitor
from scheduler import AlertScheduler

# .env file load karo
load_dotenv()

# Database ek baar initialize karo
db = Database()


# ─────────────────────────────────────────
# KEYBOARDS (Buttons)
# ─────────────────────────────────────────

def main_menu_keyboard():
    """Main menu ke buttons"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Status", callback_data="show_status"),
            InlineKeyboardButton("💰 Costs", callback_data="show_costs")
        ],
        [
            InlineKeyboardButton("🔔 Set Alert", callback_data="alert_menu"),
            InlineKeyboardButton("📋 My Alerts", callback_data="list_alerts")
        ],
        [
            InlineKeyboardButton("🔗 Add Account", callback_data="add_account_info"),
            InlineKeyboardButton("📁 My Accounts", callback_data="list_accounts")
        ],
        [
            InlineKeyboardButton("❓ Help", callback_data="show_help")
        ]
    ])

def back_to_menu_keyboard():
    """Sirf back button"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back to Menu", callback_data="main_menu")]
    ])

def status_keyboard():
    """Status screen ke buttons"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="show_status"),
            InlineKeyboardButton("💰 Check Costs", callback_data="show_costs")
        ],
        [InlineKeyboardButton("⬅️ Back to Menu", callback_data="main_menu")]
    ])

def costs_keyboard():
    """Costs screen ke buttons"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="show_costs"),
            InlineKeyboardButton("📊 Check Status", callback_data="show_status")
        ],
        [InlineKeyboardButton("⬅️ Back to Menu", callback_data="main_menu")]
    ])

def alert_menu_keyboard():
    """Alert menu ke buttons"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ New Alert", callback_data="new_alert_info"),
            InlineKeyboardButton("📋 View Alerts", callback_data="list_alerts")
        ],
        [InlineKeyboardButton("⬅️ Back to Menu", callback_data="main_menu")]
    ])


# ─────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────

async def get_status_message(user_id):
    """AWS status message banao"""
    accounts = db.get_aws_accounts(user_id)

    if not accounts:
        return "❌ Koi AWS account connected nahi hai!\n\n🔗 Add Account button use karo.", None

    account = accounts[0]
    creds = db.get_aws_credentials(account['account_id'])

    if not creds:
        return "❌ Credentials decrypt nahi hue!", None

    try:
        monitor = AWSMonitor(creds['access_key'], creds['secret_key'], creds['region'])
        instances = monitor.get_ec2_instances()

        message = f"📊 *{account['account_name']}* Status\n"
        message += f"🌍 Region: `{creds['region']}`\n\n"

        if instances:
            message += f"🖥️ *EC2 Instances:* {len(instances)} running\n\n"
            for inst in instances[:5]:
                cpu = monitor.get_cpu_utilization(inst['id'])
                cpu_str = f"{cpu}%" if cpu is not None else "N/A"
                message += f"• *{inst['name']}* ({inst['type']})\n"
                message += f"  CPU: {cpu_str}\n"
            if len(instances) > 5:
                message += f"\n_...and {len(instances) - 5} more_\n"
        else:
            message += "🖥️ Koi running EC2 instance nahi hai\n"

        from datetime import datetime
        message += f"\n🕐 Updated: {datetime.now().strftime('%H:%M:%S')}"
        return message, status_keyboard()

    except Exception as e:
        return f"❌ Error: {str(e)}", back_to_menu_keyboard()


async def get_costs_message(user_id):
    """AWS costs message banao"""
    accounts = db.get_aws_accounts(user_id)

    if not accounts:
        return "❌ Koi AWS account connected nahi hai!\n\n🔗 Add Account button use karo.", None

    account = accounts[0]
    creds = db.get_aws_credentials(account['account_id'])

    try:
        monitor = AWSMonitor(creds['access_key'], creds['secret_key'], creds['region'])
        today_cost = monitor.get_today_cost()
        month_cost = monitor.get_month_cost()

        message = f"💰 *{account['account_name']}* - Cost Report\n\n"
        message += f"📅 Aaj ka cost: *${today_cost:.2f}*\n" if today_cost is not None else "📅 Aaj ka cost: N/A\n"
        message += f"📆 Is mahine ka cost: *${month_cost:.2f}*\n" if month_cost is not None else "📆 Is mahine ka cost: N/A\n"

        return message, costs_keyboard()

    except Exception as e:
        return f"❌ Error: {str(e)}", back_to_menu_keyboard()


# ─────────────────────────────────────────
# /start COMMAND
# ─────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command - main menu dikhao"""
    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name)

    message = f"👋 *Hello {user.first_name}!*\n\n"
    message += "🤖 Main hoon *AWS Monitor Bot*\n"
    message += "Main tumhare AWS account ko monitor karta hoon aur alerts deta hoon.\n\n"
    message += "Neeche se koi option choose karo 👇"

    await update.message.reply_text(
        message,
        parse_mode='Markdown',
        reply_markup=main_menu_keyboard()
    )


# ─────────────────────────────────────────
# CALLBACK HANDLER (Button Clicks)
# ─────────────────────────────────────────

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saare button clicks yahan handle honge"""
    query = update.callback_query
    await query.answer()  # Loading animation band karo

    user_id = query.from_user.id
    data = query.data  # Kaunsa button click hua

    # ── Main Menu ──
    if data == "main_menu":
        message = f"👋 *Hello {query.from_user.first_name}!*\n\n"
        message += "Neeche se koi option choose karo 👇"
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=main_menu_keyboard()
        )

    # ── Status ──
    elif data == "show_status":
        await query.edit_message_text("🔄 AWS se data fetch kar raha hoon...")
        message, keyboard = await get_status_message(user_id)
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=keyboard
        )

    # ── Costs ──
    elif data == "show_costs":
        await query.edit_message_text("🔄 Cost data fetch kar raha hoon...")
        message, keyboard = await get_costs_message(user_id)
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=keyboard
        )

    # ── Alert Menu ──
    elif data == "alert_menu":
        message = "🔔 *Alert Management*\n\nKya karna hai?"
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=alert_menu_keyboard()
        )

    # ── New Alert Info ──
    elif data == "new_alert_info":
        message = """➕ *Naya Alert Banao*

Command use karo:
`/setalert <metric> <operator> <value> <interval>`

*Available Metrics:*
• `daily_cost` - Aaj ka cost
• `monthly_cost` - Is mahine ka cost
• `cpu_average` - Average CPU %

*Operators:* `>` `<` `>=` `<=`

*Examples:*
`/setalert daily_cost > 10 60`
_Agar aaj ka cost $10 se zyada ho - har 60 min check_

`/setalert cpu_average > 80 30`
_Agar CPU 80% se zyada ho - har 30 min check_"""

        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=back_to_menu_keyboard()
        )

    # ── List Alerts ──
    elif data == "list_alerts":
        alerts = db.get_user_alerts(user_id)

        if not alerts:
            message = "📭 Koi alert set nahi hai!\n\n/setalert se banao."
        else:
            message = "🔔 *Tumhare Active Alerts:*\n\n"
            for alert in alerts:
                message += f"*{alert['metric_name']}* {alert['comparison_operator']} {alert['threshold_value']}\n"
                message += f"⏰ Har {alert['check_interval']} min | ID: `{alert['config_id']}`\n\n"
            message += "_Alert delete karne ke liye: /deletealert <id>_"

        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=back_to_menu_keyboard()
        )

    # ── Add Account Info ──
    elif data == "add_account_info":
        message = """🔗 *AWS Account Connect Kaise Kare*

*Step 1:* AWS Console → IAM → Users
*Step 2:* Naya user banao (programmatic access)
*Step 3:* Ye permissions do:
  • AmazonEC2ReadOnlyAccess
  • CloudWatchReadOnlyAccess
  • CostExplorerAccess (custom)

*Step 4:* Access Key aur Secret Key copy karo

*Step 5:* Ye command use karo:
`/addaccount <name> <access_key> <secret_key> <region>`

*Example:*
`/addaccount Production AKIA... wJalr... ap-south-1`

⚠️ Credentials automatically encrypted ho jaate hain!"""

        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=back_to_menu_keyboard()
        )

    # ── List Accounts ──
    elif data == "list_accounts":
        accounts = db.get_aws_accounts(user_id)

        if not accounts:
            message = "📭 Koi AWS account connected nahi hai!\n\n🔗 Add Account button use karo."
        else:
            message = "📁 *Tumhare AWS Accounts:*\n\n"
            for i, acc in enumerate(accounts, 1):
                message += f"{i}. *{acc['account_name']}*\n"
                message += f"   Region: `{acc['aws_region']}`\n"
                message += f"   ID: `{acc['account_id']}`\n\n"

        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=back_to_menu_keyboard()
        )

    # ── Help ──
    elif data == "show_help":
        message = """❓ *AWS Monitor Bot - Help*

*Commands:*
/start - Main menu
/addaccount - AWS account connect karo
/setalert - Alert set karo
/deletealert - Alert delete karo

*Buttons se karo:*
• 📊 Status - EC2 instances aur CPU
• 💰 Costs - Daily aur monthly spending
• 🔔 Set Alert - Custom alerts
• 📋 My Alerts - Active alerts
• 🔗 Add Account - AWS connect
• 📁 My Accounts - Connected accounts

*Alert Metrics:*
• daily\\_cost - Aaj ka AWS cost
• monthly\\_cost - Is mahine ka cost
• cpu\\_average - Average CPU usage"""

        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=back_to_menu_keyboard()
        )


# ─────────────────────────────────────────
# COMMANDS
# ─────────────────────────────────────────

async def add_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """AWS account add karo"""
    if len(context.args) == 4:
        account_name = context.args[0]
        access_key = context.args[1]
        secret_key = context.args[2]
        region = context.args[3]
        user_id = update.effective_user.id

        msg = await update.message.reply_text("🔄 Credentials verify kar raha hoon...")

        try:
            monitor = AWSMonitor(access_key, secret_key, region)
            if not monitor.test_connection():
                await msg.edit_text("❌ AWS credentials galat hain!\n\nDobara check karo.")
                return
        except Exception as e:
            await msg.edit_text(f"❌ AWS connection failed!\n\nError: {str(e)}")
            return

        account_id = db.add_aws_account(user_id, account_name, access_key, secret_key, region)

        if account_id:
            await msg.edit_text(
                f"✅ *AWS Account Connected!*\n\n"
                f"📝 Name: {account_name}\n"
                f"🌍 Region: {region}\n"
                f"🔒 Credentials encrypted & saved\n\n"
                f"Ab neeche menu se status check karo! 👇",
                parse_mode='Markdown',
                reply_markup=main_menu_keyboard()
            )
            await asyncio.sleep(3)
            try:
                await update.message.delete()
            except:
                pass
        else:
            await msg.edit_text("❌ Database mein save nahi hua!")
    else:
        await update.message.reply_text(
            "🔗 *AWS Account Connect Karo*\n\n"
            "Format:\n`/addaccount <name> <access_key> <secret_key> <region>`\n\n"
            "Example:\n`/addaccount Production AKIA... wJalr... ap-south-1`",
            parse_mode='Markdown',
            reply_markup=back_to_menu_keyboard()
        )


async def set_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Alert set karo"""
    if len(context.args) != 4:
        await update.message.reply_text(
            "⚙️ *Alert Format:*\n\n"
            "`/setalert <metric> <operator> <value> <interval_minutes>`\n\n"
            "*Metrics:* daily\\_cost, monthly\\_cost, cpu\\_average\n"
            "*Operators:* > < >= <=\n\n"
            "*Example:*\n`/setalert daily_cost > 10 60`",
            parse_mode='Markdown',
            reply_markup=back_to_menu_keyboard()
        )
        return

    metric = context.args[0]
    operator = context.args[1]
    value = context.args[2]
    interval = context.args[3]

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
        await update.message.reply_text(
            "❌ Pehle AWS account connect karo!",
            reply_markup=main_menu_keyboard()
        )
        return

    account_id = accounts[0]['account_id']
    config_id = db.add_alert(account_id, metric, threshold, operator, check_interval)

    if config_id:
        await update.message.reply_text(
            f"✅ *Alert Set!*\n\n"
            f"📊 Metric: {metric}\n"
            f"⚠️ Condition: {operator} {threshold}\n"
            f"⏰ Check: Har {check_interval} minute\n\n"
            f"Main tumhe notify karunga! 🔔",
            parse_mode='Markdown',
            reply_markup=main_menu_keyboard()
        )
    else:
        await update.message.reply_text("❌ Alert save nahi hua!")


async def delete_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Alert delete karo"""
    if len(context.args) != 1:
        await update.message.reply_text(
            "Usage: `/deletealert <alert_id>`\n\nAlert IDs dekhne ke liye 📋 My Alerts button use karo.",
            parse_mode='Markdown'
        )
        return

    try:
        config_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Alert ID number hona chahiye!")
        return

    conn = db._get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM alert_configs WHERE config_id = %s",
            (config_id,)
        )
        conn.commit()
        if cursor.rowcount > 0:
            await update.message.reply_text(
                f"✅ Alert {config_id} deleted!",
                reply_markup=main_menu_keyboard()
            )
        else:
            await update.message.reply_text("❌ Alert nahi mila!")
    except Exception as e:
        conn.rollback()
        await update.message.reply_text(f"❌ Error: {e}")
    finally:
        cursor.close()
        db._put_conn(conn)


# ─────────────────────────────────────────
# ERROR HANDLER
# ─────────────────────────────────────────

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"❌ Error: {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ Kuch galat hua! Dobara try karo.",
            reply_markup=main_menu_keyboard()
        )


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────

def main():
    print("🤖 AWS Monitor Bot starting...")

    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token:
        print("❌ BOT_TOKEN .env mein nahi hai!")
        return

    app = Application.builder().token(bot_token).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addaccount", add_account))
    app.add_handler(CommandHandler("setalert", set_alert))
    app.add_handler(CommandHandler("deletealert", delete_alert))

    # Button clicks
    app.add_handler(CallbackQueryHandler(button_handler))

    # Error handler
    app.add_error_handler(error_handler)

    # Scheduler
    async def post_init(application):
        scheduler = AlertScheduler(application.bot)
        scheduler.start()

    app.post_init = post_init

    print("✅ Bot ready!")
    print("📱 Telegram pe /start bhejo")
    print("🛑 Band karne ke liye Ctrl+C\n")

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
