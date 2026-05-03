import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
                           ContextTypes, ConversationHandler, MessageHandler, filters)
from database import Database
from aws_monitor import AWSMonitor
from scheduler import AlertScheduler
from subscription import SubscriptionManager, PLANS
from report import ReportGenerator
from charts import ChartGenerator

load_dotenv()

db = Database()
sub_manager = SubscriptionManager()
report_gen = ReportGenerator()
chart_gen = ChartGenerator()

# Chart usage tracking (per week limit)
chart_usage = {}  # {user_id: {'count': 0, 'week': week_number}}

# Conversation states
ALERT_METRIC, ALERT_OPERATOR, ALERT_VALUE, ALERT_INTERVAL = range(4)

# ─────────────────────────────────────────
# KEYBOARDS
# ─────────────────────────────────────────

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("EC2 Status", callback_data="show_status"),
            InlineKeyboardButton("RDS Status", callback_data="show_rds")
        ],
        [
            InlineKeyboardButton("S3 Storage", callback_data="show_s3"),
            InlineKeyboardButton("Costs", callback_data="show_costs")
        ],
        [
            InlineKeyboardButton("Set Alert", callback_data="alert_menu"),
            InlineKeyboardButton("My Alerts", callback_data="list_alerts")
        ],
        [
            InlineKeyboardButton("My Accounts", callback_data="list_accounts"),
            InlineKeyboardButton("Add Account", callback_data="add_account_info")
        ],
        [
            InlineKeyboardButton("Upgrade", callback_data="show_upgrade"),
            InlineKeyboardButton("Help", callback_data="show_help")
        ],
        [
            InlineKeyboardButton("My Plan", callback_data="my_plan"),
            InlineKeyboardButton("Download PDF Report", callback_data="download_report")
        ],
        [
            InlineKeyboardButton("Cost Chart", callback_data="show_chart_menu"),
            InlineKeyboardButton("Refer a Friend", callback_data="show_referral")
        ]
    ])

def back_to_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Back to Menu", callback_data="main_menu")]
    ])

def account_select_keyboard(accounts, action):
    buttons = []
    for acc in accounts:
        buttons.append([
            InlineKeyboardButton(
                f"{acc['account_name']} ({acc['aws_region']})",
                callback_data=f"{action}_acc_{acc['account_id']}"
            )
        ])
    buttons.append([InlineKeyboardButton("Back to Menu", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)


# ─────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────

async def get_status_message(user_id, account_id=None):
    accounts = db.get_aws_accounts(user_id)
    if not accounts:
        return "No AWS account connected.\n\nClick /addaccount to link your AWS account and start monitoring.", back_to_menu_keyboard()

    account = next((a for a in accounts if a['account_id'] == account_id), accounts[0]) if account_id else accounts[0]
    creds = db.get_aws_credentials(account['account_id'])
    if not creds:
        return "Credentials decrypt failed!", None

    try:
        monitor = AWSMonitor(creds['access_key'], creds['secret_key'], creds['region'])
        instances = monitor.get_ec2_instances()

        from datetime import datetime
        message = f"EC2 Status - {account['account_name']}\n"
        message += f"Region: {creds['region']}\n\n"

        if instances:
            message += f"EC2 Instances: {len(instances)} running\n\n"
            for inst in instances[:5]:
                cpu = monitor.get_cpu_utilization(inst['id'])
                cpu_str = f"{cpu}%" if cpu is not None else "N/A"
                message += f"- {inst['name']} ({inst['type']}): CPU {cpu_str}\n"
            if len(instances) > 5:
                message += f"...and {len(instances) - 5} more\n"
        else:
            message += "No running EC2 instances\n"

        message += f"\nUpdated: {datetime.now().strftime('%H:%M:%S')}"

        keyboard_buttons = [
            [
                InlineKeyboardButton("Refresh", callback_data=f"status_acc_{account['account_id']}"),
                InlineKeyboardButton("Check Costs", callback_data=f"costs_acc_{account['account_id']}")
            ]
        ]
        if len(accounts) > 1:
            keyboard_buttons.append([InlineKeyboardButton("Switch Account", callback_data="select_account_status")])
        keyboard_buttons.append([InlineKeyboardButton("Back to Menu", callback_data="main_menu")])

        return message, InlineKeyboardMarkup(keyboard_buttons)

    except Exception as e:
        return f"Error: {str(e)}", back_to_menu_keyboard()


async def get_costs_message(user_id, account_id=None):
    accounts = db.get_aws_accounts(user_id)
    if not accounts:
        return "No AWS account connected.\n\nClick /addaccount to link your AWS account and start monitoring.", back_to_menu_keyboard()

    account = next((a for a in accounts if a['account_id'] == account_id), accounts[0]) if account_id else accounts[0]
    creds = db.get_aws_credentials(account['account_id'])

    try:
        monitor = AWSMonitor(creds['access_key'], creds['secret_key'], creds['region'])
        today_cost = monitor.get_today_cost()
        month_cost = monitor.get_month_cost()

        message = f"Cost Report - {account['account_name']}\n\n"
        message += f"Today: ${today_cost:.2f}\n" if today_cost is not None else "Today: N/A\n"
        message += f"This Month: ${month_cost:.2f}\n" if month_cost is not None else "This Month: N/A\n"

        keyboard_buttons = [
            [
                InlineKeyboardButton("Refresh", callback_data=f"costs_acc_{account['account_id']}"),
                InlineKeyboardButton("EC2 Status", callback_data=f"status_acc_{account['account_id']}")
            ]
        ]
        if len(accounts) > 1:
            keyboard_buttons.append([InlineKeyboardButton("Switch Account", callback_data="select_account_costs")])
        keyboard_buttons.append([InlineKeyboardButton("Back to Menu", callback_data="main_menu")])

        return message, InlineKeyboardMarkup(keyboard_buttons)

    except Exception as e:
        return f"Error: {str(e)}", back_to_menu_keyboard()


# ─────────────────────────────────────────
# /start COMMAND
# ─────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Check karo naya user hai ya returning
    existing_user = db.get_user(user.id)
    is_new = existing_user is None

    db.add_user(user.id, user.username, user.first_name)

    # Referral code check karo
    if context.args:
        referral_code = context.args[0]
        referrer_id = db.get_user_by_referral_code(referral_code)
        if referrer_id and referrer_id != user.id:
            success = db.add_referral(referrer_id, user.id)
            if success:
                await update.message.reply_text(
                    f"Welcome! You joined via referral!\n"
                    f"Both you and your friend get 7 days FREE Premium!"
                )

    if is_new:
        # Naya user - onboarding flow
        message = f"Welcome to AWS Monitor Bot, {user.first_name}!\n\n"
        message += "I help you monitor your AWS infrastructure and control costs.\n\n"
        message += "Let's get you set up in 2 simple steps:\n\n"
        message += "Step 1: Connect your AWS account\n"
        message += "Step 2: Set your first cost alert\n\n"
        message += "Ready? Let's start!"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Get Started", callback_data="onboard_step1")],
            [InlineKeyboardButton("Skip to Main Menu", callback_data="main_menu")]
        ])
        await update.message.reply_text(message, reply_markup=keyboard)
    else:
        # Returning user - seedha main menu
        message = f"Welcome back, {user.first_name}!\n\nChoose an option below:"
        await update.message.reply_text(message, reply_markup=main_menu_keyboard())


# ─────────────────────────────────────────
# CALLBACK HANDLER
# ─────────────────────────────────────────

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    if data == "main_menu":
        await query.edit_message_text(
            f"Hello {query.from_user.first_name}!\n\nChoose an option:",
            reply_markup=main_menu_keyboard()
        )

    elif data == "onboard_step1":
        # Step 1: AWS account connect karo
        message = "Step 1: Connect Your AWS Account\n\n"
        message += "You'll need:\n"
        message += "- AWS Access Key ID\n"
        message += "- AWS Secret Access Key\n"
        message += "- Your AWS Region\n\n"
        message += "Don't have these? Here's how to get them:\n\n"
        message += "1. Go to AWS Console\n"
        message += "2. Navigate to IAM > Users\n"
        message += "3. Create a new user with these policies:\n"
        message += "   - AmazonEC2ReadOnlyAccess\n"
        message += "   - CloudWatchReadOnlyAccess\n"
        message += "   - AmazonRDSReadOnlyAccess\n"
        message += "   - AmazonS3ReadOnlyAccess\n"
        message += "4. Create Access Key and copy credentials\n\n"
        message += "Then use this command:\n"
        message += "/addaccount <name> <access_key> <secret_key> <region>\n\n"
        message += "Example:\n"
        message += "/addaccount Production AKIA... wJalr... us-east-1"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("I've connected my account", callback_data="onboard_step2")],
            [InlineKeyboardButton("Skip to Main Menu", callback_data="main_menu")]
        ])
        await query.edit_message_text(message, reply_markup=keyboard)

    elif data == "onboard_step2":
        # Step 2: Pehla alert set karo
        accounts = db.get_aws_accounts(query.from_user.id)
        if not accounts:
            await query.edit_message_text(
                "It looks like you haven't connected an AWS account yet.\n\n"
                "Please use /addaccount first, then come back here.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Back", callback_data="onboard_step1")]
                ])
            )
            return

        message = "Step 2: Set Your First Alert\n\n"
        message += "I recommend setting a daily cost alert.\n"
        message += "This way you'll know if your AWS bill is getting too high.\n\n"
        message += "Click below to set a cost alert now:"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Set Cost Alert", callback_data="create_alert_step1")],
            [InlineKeyboardButton("Skip to Main Menu", callback_data="onboard_done")]
        ])
        await query.edit_message_text(message, reply_markup=keyboard)

    elif data == "onboard_done":
        message = "You're all set!\n\n"
        message += "Your AWS infrastructure is now being monitored.\n\n"
        message += "What would you like to do?"
        await query.edit_message_text(message, reply_markup=main_menu_keyboard())

    elif data == "show_status":
        await query.edit_message_text("Fetching AWS data...")
        message, keyboard = await get_status_message(user_id)
        await query.edit_message_text(message, reply_markup=keyboard)

    elif data.startswith("status_acc_"):
        account_id = int(data.split("_")[2])
        await query.edit_message_text("Fetching AWS data...")
        message, keyboard = await get_status_message(user_id, account_id)
        await query.edit_message_text(message, reply_markup=keyboard)

    elif data == "select_account_status":
        accounts = db.get_aws_accounts(user_id)
        await query.edit_message_text(
            "Select account to check:",
            reply_markup=account_select_keyboard(accounts, "status")
        )

    elif data == "show_costs":
        await query.edit_message_text("Fetching cost data...")
        message, keyboard = await get_costs_message(user_id)
        await query.edit_message_text(message, reply_markup=keyboard)

    elif data.startswith("costs_acc_"):
        account_id = int(data.split("_")[2])
        await query.edit_message_text("Fetching cost data...")
        message, keyboard = await get_costs_message(user_id, account_id)
        await query.edit_message_text(message, reply_markup=keyboard)

    elif data == "select_account_costs":
        accounts = db.get_aws_accounts(user_id)
        await query.edit_message_text(
            "Select account for costs:",
            reply_markup=account_select_keyboard(accounts, "costs")
        )

    elif data == "show_s3":
        await query.edit_message_text("Fetching S3 data...")

        accounts = db.get_aws_accounts(user_id)
        if not accounts:
            await query.edit_message_text(
                "No AWS account connected.\n\nClick /addaccount to link your AWS account and start monitoring.",
                reply_markup=back_to_menu_keyboard()
            )
            return

        account = accounts[0]
        creds = db.get_aws_credentials(account['account_id'])

        try:
            monitor = AWSMonitor(creds['access_key'], creds['secret_key'], creds['region'])
            buckets = monitor.get_s3_buckets()

            from datetime import datetime
            message = f"S3 Storage - {account['account_name']}\n\n"

            if buckets:
                message += f"{len(buckets)} Bucket(s) Found:\n\n"
                for bucket in buckets[:10]:
                    message += f"- {bucket['name']}\n"
                    message += f"  Size: {bucket['size_gb']} GB\n"
                    message += f"  Files: {bucket['object_count']:,}\n"
                    message += f"  Created: {bucket['created']}\n\n"
                if len(buckets) > 10:
                    message += f"...and {len(buckets) - 10} more buckets\n"
            else:
                message += "No S3 buckets found\n"

            message += f"\nUpdated: {datetime.now().strftime('%H:%M:%S')}"

            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Refresh", callback_data="show_s3"),
                    InlineKeyboardButton("EC2 Status", callback_data="show_status")
                ],
                [InlineKeyboardButton("Back to Menu", callback_data="main_menu")]
            ])

            await query.edit_message_text(message, reply_markup=keyboard)

        except Exception as e:
            await query.edit_message_text(f"Error: {str(e)}", reply_markup=back_to_menu_keyboard())

    elif data == "show_rds":
        await query.edit_message_text("Fetching RDS data...")

        accounts = db.get_aws_accounts(user_id)
        if not accounts:
            await query.edit_message_text(
                "No AWS account connected.\n\nClick /addaccount to link your AWS account and start monitoring.",
                reply_markup=back_to_menu_keyboard()
            )
            return

        account = accounts[0]
        creds = db.get_aws_credentials(account['account_id'])

        try:
            monitor = AWSMonitor(creds['access_key'], creds['secret_key'], creds['region'])
            rds_instances = monitor.get_rds_instances()

            from datetime import datetime
            message = f"RDS Databases - {account['account_name']}\n"
            message += f"Region: {creds['region']}\n\n"

            if rds_instances:
                message += f"{len(rds_instances)} Database(s) Found:\n\n"
                for db_inst in rds_instances:
                    status_icon = "OK" if db_inst['status'] == 'available' else "!!"
                    message += f"[{status_icon}] {db_inst['id']}\n"
                    message += f"   Engine: {db_inst['engine']}\n"
                    message += f"   Status: {db_inst['status']}\n"
                    message += f"   Class: {db_inst['instance_class']}\n"
                    message += f"   Storage: {db_inst['storage']} GB\n\n"
            else:
                message += "No RDS instances found\n"

            message += f"\nUpdated: {datetime.now().strftime('%H:%M:%S')}"

            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Refresh", callback_data="show_rds"),
                    InlineKeyboardButton("EC2 Status", callback_data="show_status")
                ],
                [InlineKeyboardButton("Back to Menu", callback_data="main_menu")]
            ])

            await query.edit_message_text(message, reply_markup=keyboard)

        except Exception as e:
            await query.edit_message_text(f"Error: {str(e)}", reply_markup=back_to_menu_keyboard())

    elif data == "alert_menu":
        accounts = db.get_aws_accounts(user_id)
        if not accounts:
            await query.edit_message_text(
                "No AWS account connected.\n\nClick /addaccount to link your AWS account and start monitoring.",
                reply_markup=back_to_menu_keyboard()
            )
            return

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Create New Alert", callback_data="create_alert_step1"),
                InlineKeyboardButton("View My Alerts", callback_data="list_alerts")
            ],
            [InlineKeyboardButton("Back to Menu", callback_data="main_menu")]
        ])
        await query.edit_message_text("Alert Management\n\nWhat would you like to do?", reply_markup=keyboard)

    elif data == "create_alert_step1":
        # Step 1: Metric choose karo
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Daily Cost", callback_data="alert_metric_daily_cost")],
            [InlineKeyboardButton("Monthly Cost", callback_data="alert_metric_monthly_cost")],
            [InlineKeyboardButton("CPU Average", callback_data="alert_metric_cpu_average")],
            [InlineKeyboardButton("Cancel", callback_data="alert_menu")]
        ])
        await query.edit_message_text(
            "Create New Alert\n\nStep 1 of 4: What do you want to monitor?",
            reply_markup=keyboard
        )

    elif data.startswith("alert_metric_"):
        # Step 2: Operator choose karo
        metric = data.replace("alert_metric_", "")
        context.user_data['alert_metric'] = metric

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Greater than (>)", callback_data="alert_op_>"),
                InlineKeyboardButton("Less than (<)", callback_data="alert_op_<")
            ],
            [
                InlineKeyboardButton("Greater or equal (>=)", callback_data="alert_op_>="),
                InlineKeyboardButton("Less or equal (<=)", callback_data="alert_op_<=")
            ],
            [InlineKeyboardButton("Cancel", callback_data="alert_menu")]
        ])
        await query.edit_message_text(
            f"Create New Alert\n\nMetric: {metric}\n\nStep 2 of 4: Choose condition:",
            reply_markup=keyboard
        )

    elif data.startswith("alert_op_"):
        # Step 3: Value type karo
        operator = data.replace("alert_op_", "")
        context.user_data['alert_operator'] = operator
        metric = context.user_data.get('alert_metric', '')
        context.user_data['waiting_for'] = 'alert_value'

        unit = "$" if "cost" in metric else "%"
        await query.edit_message_text(
            f"Create New Alert\n\n"
            f"Metric: {metric}\n"
            f"Condition: {operator}\n\n"
            f"Step 3 of 4: Enter threshold value\n"
            f"Example: 10 (means {unit}10)\n\n"
            f"Type the value and send:"
        )

    elif data.startswith("alert_interval_"):
        # Step 4 complete - save alert
        interval = int(data.replace("alert_interval_", ""))
        metric = context.user_data.get('alert_metric')
        operator = context.user_data.get('alert_operator')
        value = context.user_data.get('alert_value')

        # Plan check karo - free user sirf 360+ min use kar sakta hai
        current_plan = db.get_user_plan(user_id)
        if current_plan == 'free' and interval < 360:
            # Seedha payment window dikhao
            payment_url, link_id = sub_manager.create_payment_link(
                user_id=user_id,
                plan_name='premium',
                amount=499
            )
            if payment_url:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("Pay Now - Rs.499", url=payment_url)],
                    [InlineKeyboardButton("Payment Done", callback_data=f"verify_{link_id}")],
                    [InlineKeyboardButton("Back", callback_data="show_upgrade")]
                ])
                message = "Premium Subscription\n\n"
                message += "Plan: Premium\n"
                message += "Amount: Rs.499/month\n"
                message += "Duration: 30 days\n\n"
                message += "How to proceed:\n"
                message += "1. Click Pay Now\n"
                message += "2. Complete payment via UPI, Card or Net Banking\n"
                message += "3. Return here and click Payment Done\n\n"
                message += "Your subscription will be activated instantly after payment verification."
                await query.edit_message_text(message, reply_markup=keyboard)
            else:
                await query.edit_message_text("Payment link failed! Try again.", reply_markup=back_to_menu_keyboard())
            context.user_data.clear()
            return

        accounts = db.get_aws_accounts(user_id)
        account_id = accounts[0]['account_id']
        config_id = db.add_alert(account_id, metric, float(value), operator, interval)
        context.user_data.clear()

        if config_id:
            unit = "$" if "cost" in metric else "%"
            await query.edit_message_text(
                f"Alert Created Successfully!\n\n"
                f"Metric: {metric}\n"
                f"Condition: {operator} {unit}{value}\n"
                f"Check every: {interval} minutes\n\n"
                f"You will be notified when this condition is met.",
                reply_markup=main_menu_keyboard()
            )
        else:
            await query.edit_message_text("Failed to save alert!", reply_markup=main_menu_keyboard())

    elif data == "new_alert_info":
        pass  # handled above now

    elif data == "list_alerts":
        alerts = db.get_user_alerts(user_id)
        if not alerts:
            message = "No alerts set!\n\nUse Set Alert button to create one."
        else:
            message = "Your Active Alerts:\n\n"
            for alert in alerts:
                message += f"- {alert['metric_name']} {alert['comparison_operator']} {alert['threshold_value']}\n"
                message += f"  Check every {alert['check_interval']} min | ID: {alert['config_id']}\n\n"
            message += "To delete: /deletealert <id>"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("View Alert History", callback_data="alert_history")],
            [InlineKeyboardButton("Back to Menu", callback_data="main_menu")]
        ])
        await query.edit_message_text(message, reply_markup=keyboard)

    elif data == "alert_history":
        history = db.get_alert_history(user_id)
        if not history:
            message = "No alert history yet.\n\nAlerts will appear here when they trigger."
        else:
            message = "Alert History (Last 10):\n\n"
            for h in history:
                unit = "$" if "cost" in h['metric_name'] else "%"
                message += f"{h['metric_name']} {h['operator']} {unit}{h['threshold']}\n"
                message += f"  Triggered: {h['triggered_at'].strftime('%d-%m-%Y %H:%M')}\n"
                message += f"  Value: {unit}{h['triggered_value']}\n\n"

        await query.edit_message_text(message, reply_markup=back_to_menu_keyboard())

    elif data == "add_account_info":
        message = "Connect AWS Account\n\n"
        message += "Step 1: AWS Console > IAM > Users\n"
        message += "Step 2: Create user with programmatic access\n"
        message += "Step 3: Attach policies:\n"
        message += "  - AmazonEC2ReadOnlyAccess\n"
        message += "  - CloudWatchReadOnlyAccess\n"
        message += "  - AmazonRDSReadOnlyAccess\n"
        message += "  - AmazonS3ReadOnlyAccess\n"
        message += "  - CostExplorerAccess\n\n"
        message += "Step 4: Copy Access Key and Secret Key\n\n"
        message += "Step 5: Type this command:\n\n"
        message += "/addaccount <name> <access_key> <secret_key> <region>\n\n"
        message += "Example:\n"
        message += "/addaccount Production AKIA... wJalr... us-east-1\n\n"
        message += "Available Regions:\n"
        message += "- us-east-1 (N. Virginia)\n"
        message += "- ap-south-1 (Mumbai)\n"
        message += "- eu-west-1 (Ireland)\n"
        message += "- ap-southeast-1 (Singapore)"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Back to Menu", callback_data="main_menu")]
        ])
        await query.edit_message_text(message, reply_markup=keyboard)

    elif data == "list_accounts":
        accounts = db.get_aws_accounts(user_id)
        if not accounts:
            message = "No AWS account connected.\n\nClick /addaccount to link your AWS account and start monitoring."
            await query.edit_message_text(message, reply_markup=back_to_menu_keyboard())
        else:
            message = "Your AWS Accounts:\n\n"
            for i, acc in enumerate(accounts, 1):
                message += f"{i}. {acc['account_name']}\n"
                message += f"   Region: {acc['aws_region']}\n"
                message += f"   ID: {acc['account_id']}\n\n"
            message += "To remove an account, tap the button below."

            keyboard_buttons = []
            for acc in accounts:
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        f"Remove {acc['account_name']}",
                        callback_data=f"delete_account_{acc['account_id']}"
                    )
                ])
            keyboard_buttons.append([InlineKeyboardButton("Back to Menu", callback_data="main_menu")])
            await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard_buttons))

    elif data.startswith("delete_account_"):
        account_id = int(data.replace("delete_account_", ""))
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Yes, Remove", callback_data=f"confirm_delete_{account_id}")],
            [InlineKeyboardButton("Cancel", callback_data="list_accounts")]
        ])
        await query.edit_message_text(
            "Are you sure you want to remove this AWS account?\n\n"
            "All associated alerts will also be deleted.\n\n"
            "This action cannot be undone.",
            reply_markup=keyboard
        )

    elif data.startswith("confirm_delete_"):
        account_id = int(data.replace("confirm_delete_", ""))
        conn = db._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM alert_configs WHERE account_id = %s", (account_id,))
            cursor.execute(
                "UPDATE aws_accounts SET is_active = false WHERE account_id = %s AND user_id = %s",
                (account_id, user_id)
            )
            conn.commit()
            await query.edit_message_text(
                "AWS account removed successfully.",
                reply_markup=main_menu_keyboard()
            )
        except Exception as e:
            conn.rollback()
            await query.edit_message_text(f"Error: {str(e)}", reply_markup=back_to_menu_keyboard())
        finally:
            cursor.close()
            db._put_conn(conn)

    elif data == "my_plan":
        current_plan = db.get_user_plan(user_id)

        conn = db._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT plan_name, end_date FROM subscriptions
                WHERE user_id = %s AND is_active = true
                AND (end_date IS NULL OR end_date > NOW())
                ORDER BY start_date DESC LIMIT 1
            """, (user_id,))
            sub = cursor.fetchone()
        finally:
            cursor.close()
            db._put_conn(conn)

        message = "My Plan\n\n"
        message += f"Current Plan: {current_plan.upper()}\n\n"

        if sub and sub[1]:
            from datetime import datetime
            days_left = (sub[1] - datetime.now()).days + 1
            message += f"Expires: {sub[1].strftime('%d-%m-%Y')}\n"
            message += f"Days remaining: {days_left}\n\n"
        elif current_plan == 'free':
            message += "No expiry - Free plan\n\n"

        if current_plan == 'free':
            message += "Free Plan Limits:\n"
            message += "- 1 AWS account\n"
            message += "- 5 alerts\n"
            message += "- 6 hour check interval\n\n"
            message += "Upgrade to Premium for more features!"
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Upgrade to Premium", callback_data="show_upgrade")],
                [InlineKeyboardButton("Back to Menu", callback_data="main_menu")]
            ])
        else:
            message += "Premium Benefits:\n"
            message += "- 5 AWS accounts\n"
            message += "- 50 alerts\n"
            message += "- 30 min check interval\n"
            message += "- Weekly reports\n"
            message += "- Anomaly detection\n"
            message += "- PDF reports"
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Renew Premium", callback_data="buy_premium")],
                [InlineKeyboardButton("Back to Menu", callback_data="main_menu")]
            ])

        await query.edit_message_text(message, reply_markup=keyboard)

    elif data == "show_upgrade":
        current_plan = db.get_user_plan(user_id)
        free = PLANS['free']
        premium = PLANS['premium']

        message = f"Upgrade to Premium\n\n"
        message += f"Current plan: {current_plan.upper()}\n\n"
        message += f"FREE Plan:\n"
        for f in free['features']:
            message += f"  - {f}\n"
        message += f"\nPREMIUM - Rs.{premium['price']}/month:\n"
        for f in premium['features']:
            message += f"  - {f}\n"

        if current_plan == 'premium':
            message += "\nYou are already on Premium!"
            await query.edit_message_text(message, reply_markup=back_to_menu_keyboard())
        else:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Buy Premium - Rs.499/month", callback_data="buy_premium")],
                [InlineKeyboardButton("Back to Menu", callback_data="main_menu")]
            ])
            await query.edit_message_text(message, reply_markup=keyboard)

    elif data == "buy_premium":
        await query.edit_message_text("Generating payment link...")

        payment_url, link_id = sub_manager.create_payment_link(
            user_id=user_id,
            plan_name='premium',
            amount=499
        )

        if payment_url:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Pay Now - Rs.499", url=payment_url)],
                [InlineKeyboardButton("Payment Done", callback_data=f"verify_{link_id}")],
                [InlineKeyboardButton("Back", callback_data="show_upgrade")]
            ])
            message = "Premium Subscription\n\n"
            message += "Plan: Premium\n"
            message += "Amount: Rs.499/month\n"
            message += "Duration: 30 days\n\n"
            message += "How to proceed:\n"
            message += "1. Click Pay Now\n"
            message += "2. Complete payment via UPI, Card or Net Banking\n"
            message += "3. Return here and click Payment Done\n\n"
            message += "Your subscription will be activated instantly after payment verification."
            await query.edit_message_text(message, reply_markup=keyboard)
        else:
            await query.edit_message_text("Payment link failed! Try again.", reply_markup=back_to_menu_keyboard())

    elif data.startswith("verify_"):
        link_id = data.replace("verify_", "")
        await query.edit_message_text("Verifying payment...")

        if sub_manager.verify_payment(link_id):
            db.create_subscription(user_id, 'premium', link_id)
            message = "Payment Successful!\n\n"
            message += "Premium plan activated!\n\n"
            message += "Your benefits:\n"
            message += "- 5 AWS accounts\n"
            message += "- 50 alerts\n"
            message += "- 5 minute checks\n"
            message += "- Weekly reports\n"
            message += "- Anomaly detection\n\n"
            message += "Thank you!"
            await query.edit_message_text(message, reply_markup=main_menu_keyboard())
        else:
            await query.edit_message_text(
                "Payment not verified!\n\nComplete payment first then try again.",
                reply_markup=back_to_menu_keyboard()
            )

    elif data == "download_report":
        await query.edit_message_text("Generating PDF report... Please wait.")

        accounts = db.get_aws_accounts(user_id)
        if not accounts:
            await query.edit_message_text(
                "No AWS account connected.\n\nClick /addaccount to link your AWS account and start monitoring.",
                reply_markup=back_to_menu_keyboard()
            )
            return

        account = accounts[0]
        creds = db.get_aws_credentials(account['account_id'])

        try:
            monitor = AWSMonitor(creds['access_key'], creds['secret_key'], creds['region'])

            # Saara data fetch karo
            instances = monitor.get_ec2_instances()
            instances_with_cpu = []
            for inst in instances:
                cpu = monitor.get_cpu_utilization(inst['id'])
                inst['cpu'] = cpu or 0
                instances_with_cpu.append(inst)

            today_cost = monitor.get_today_cost()
            month_cost = monitor.get_month_cost()
            this_week, last_week = monitor.get_weekly_costs()
            rds_instances = monitor.get_rds_instances()
            s3_buckets = monitor.get_s3_buckets()

            # User data
            user = db.get_user(user_id)
            user_data = {'first_name': user['first_name'] if user else 'User'}

            # AWS data
            aws_data = {
                'account_name': account['account_name'],
                'region': creds['region'],
                'today_cost': today_cost,
                'month_cost': month_cost,
                'this_week_cost': this_week,
                'last_week_cost': last_week,
                'instances': instances_with_cpu,
                'rds_instances': rds_instances,
                's3_buckets': s3_buckets
            }

            # PDF generate karo
            pdf_buffer = report_gen.generate_monthly_report(user_data, aws_data)

            from telegram import InputFile
            from datetime import datetime
            filename = f"aws_report_{datetime.now().strftime('%B_%Y')}.pdf"

            await query.message.reply_document(
                document=InputFile(pdf_buffer, filename=filename),
                caption=f"Your AWS Monthly Report - {datetime.now().strftime('%B %Y')}"
            )

            await query.edit_message_text(
                "PDF report sent!",
                reply_markup=main_menu_keyboard()
            )

        except Exception as e:
            await query.edit_message_text(f"Error generating report: {str(e)}", reply_markup=back_to_menu_keyboard())

    elif data == "show_chart_menu":
        current_plan = db.get_user_plan(user_id)

        # Weekly usage check
        from datetime import datetime
        current_week = datetime.now().isocalendar()[1]
        user_usage = chart_usage.get(user_id, {'count': 0, 'week': current_week})

        # Reset if new week
        if user_usage['week'] != current_week:
            user_usage = {'count': 0, 'week': current_week}
            chart_usage[user_id] = user_usage

        free_limit = 1
        used = user_usage['count']
        remaining = max(0, free_limit - used) if current_plan == 'free' else 'Unlimited'

        if current_plan == 'free':
            message = f"Cost Chart\n\nFree plan: {used}/{free_limit} charts used this week\n\nChoose time range:"
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("7 Days", callback_data="chart_7"),
                    InlineKeyboardButton("30 Days", callback_data="chart_30")
                ],
                [
                    InlineKeyboardButton("⭐ 90 Days — Premium", callback_data="chart_90"),
                    InlineKeyboardButton("⭐ 180 Days — Premium", callback_data="chart_180")
                ],
                [InlineKeyboardButton("Back to Menu", callback_data="main_menu")]
            ])
        else:
            message = "Cost Chart\n\nPremium: Unlimited charts\n\nChoose time range:"
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("7 Days", callback_data="chart_7"),
                    InlineKeyboardButton("30 Days", callback_data="chart_30")
                ],
                [
                    InlineKeyboardButton("90 Days", callback_data="chart_90"),
                    InlineKeyboardButton("180 Days", callback_data="chart_180")
                ],
                [InlineKeyboardButton("Back to Menu", callback_data="main_menu")]
            ])

        await query.edit_message_text(message, reply_markup=keyboard)

    elif data.startswith("chart_"):
        days = int(data.replace("chart_", ""))
        current_plan = db.get_user_plan(user_id)

        # Premium check for 90/180 days
        if days >= 90 and current_plan == 'free':
            payment_url, link_id = sub_manager.create_payment_link(user_id, 'premium', 499)
            if payment_url:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("Pay Now - Rs.499", url=payment_url)],
                    [InlineKeyboardButton("Payment Done", callback_data=f"verify_{link_id}")],
                    [InlineKeyboardButton("Back", callback_data="show_chart_menu")]
                ])
                await query.edit_message_text(
                    "This time range requires Premium.\n\nUpgrade to access 90 and 180 day charts.",
                    reply_markup=keyboard
                )
            return

        # Weekly limit check for free users
        from datetime import datetime
        current_week = datetime.now().isocalendar()[1]
        user_usage = chart_usage.get(user_id, {'count': 0, 'week': current_week})

        if user_usage['week'] != current_week:
            user_usage = {'count': 0, 'week': current_week}

        if current_plan == 'free' and user_usage['count'] >= 1:
            payment_url, link_id = sub_manager.create_payment_link(user_id, 'premium', 499)
            if payment_url:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("Pay Now - Rs.499", url=payment_url)],
                    [InlineKeyboardButton("Payment Done", callback_data=f"verify_{link_id}")],
                    [InlineKeyboardButton("Back", callback_data="show_chart_menu")]
                ])
                await query.edit_message_text(
                    "You've used your free chart for this week.\n\nUpgrade to Premium for unlimited charts.",
                    reply_markup=keyboard
                )
            return

        await query.edit_message_text(f"Generating {days}-day cost chart...")

        accounts = db.get_aws_accounts(user_id)
        if not accounts:
            await query.edit_message_text(
                "No AWS account connected.\n\nClick /addaccount to link your AWS account.",
                reply_markup=back_to_menu_keyboard()
            )
            return

        account = accounts[0]
        creds = db.get_aws_credentials(account['account_id'])

        try:
            monitor = AWSMonitor(creds['access_key'], creds['secret_key'], creds['region'])
            cost_data = chart_gen.prepare_cost_data(monitor, days)

            if not cost_data:
                await query.edit_message_text(
                    "Not enough data to generate chart.",
                    reply_markup=back_to_menu_keyboard()
                )
                return

            period_labels = {7: 'Last 7 Days', 30: 'Last 30 Days',
                           90: 'Last 90 Days', 180: 'Last 6 Months'}
            title = f"AWS Cost Trend - {period_labels.get(days, f'Last {days} Days')}"

            chart_buf = chart_gen.generate_cost_chart(cost_data, title, period_labels.get(days, ''))

            if chart_buf:
                # Usage count update karo
                user_usage['count'] += 1
                user_usage['week'] = current_week
                chart_usage[user_id] = user_usage

                from telegram import InputFile
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("View Interactive Chart", url=f"http://13.217.96.93:5000/chart/{user_id}")],
                    [InlineKeyboardButton("Back to Menu", callback_data="main_menu")]
                ])

                await query.message.reply_photo(
                    photo=InputFile(chart_buf, filename=f'cost_chart_{days}d.png'),
                    caption=f"AWS Cost Chart - Last {days} Days\nAccount: {account['account_name']}",
                    reply_markup=keyboard
                )
                await query.edit_message_text(
                    "Chart generated!",
                    reply_markup=main_menu_keyboard()
                )
            else:
                await query.edit_message_text("Failed to generate chart!", reply_markup=back_to_menu_keyboard())

        except Exception as e:
            await query.edit_message_text(f"Error: {str(e)}", reply_markup=back_to_menu_keyboard())

    elif data == "show_referral":
        code = db.get_or_create_referral_code(user_id)
        count = db.get_referral_count(user_id)
        bot_username = os.getenv('BOT_USERNAME', 'aws_monitor_telegram_bot')

        message = f"Refer a Friend - Get Free Premium!\n\n"
        message += f"Your referral code: {code}\n\n"
        message += f"Share this link:\n"
        message += f"t.me/{bot_username}?start={code}\n\n"
        message += f"Your referrals: {count} friends joined\n"
        message += f"Rewards earned: {count * 7} days free premium\n\n"
        message += f"How it works:\n"
        message += f"1. Share your link with friends\n"
        message += f"2. Friend joins using your link\n"
        message += f"3. Both get 7 days FREE Premium!\n\n"
        message += f"No limit - more referrals = more free premium!"

        await query.edit_message_text(message, reply_markup=back_to_menu_keyboard())

    elif data == "show_help":
        message = "AWS Monitor Bot - Help\n\n"
        message += "Commands:\n"
        message += "/start - Main menu\n"
        message += "/addaccount - Connect AWS account\n"
        message += "/setalert - Create alert\n"
        message += "/deletealert - Delete alert\n\n"
        message += "Buttons:\n"
        message += "- EC2 Status - Instances and CPU\n"
        message += "- RDS Status - Database instances\n"
        message += "- Costs - Daily and monthly spending\n"
        message += "- Set Alert - Custom alerts\n"
        message += "- My Alerts - Active alerts\n"
        message += "- Add Account - Connect AWS\n"
        message += "- My Accounts - Connected accounts\n\n"
        message += "Alert Metrics:\n"
        message += "- daily_cost\n"
        message += "- monthly_cost\n"
        message += "- cpu_average"
        await query.edit_message_text(message, reply_markup=back_to_menu_keyboard())


# ─────────────────────────────────────────
# COMMANDS
# ─────────────────────────────────────────

async def handle_alert_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 3: User ne value type ki - Step 4 dikhao"""

    # Admin broadcast check pehle
    if await handle_admin_broadcast(update, context):
        return

    if context.user_data.get('waiting_for') != 'alert_value':
        return

    text = update.message.text.strip()

    try:
        value = float(text)
    except ValueError:
        await update.message.reply_text(
            "Please enter a valid number.\nExample: 10 or 5.5"
        )
        return

    context.user_data['alert_value'] = text
    context.user_data['waiting_for'] = None

    metric = context.user_data.get('alert_metric', '')
    operator = context.user_data.get('alert_operator', '')
    unit = "$" if "cost" in metric else "%"

    # Plan check karo
    current_plan = db.get_user_plan(update.effective_user.id)
    is_premium = current_plan == 'premium'

    if is_premium:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Every 30 min", callback_data="alert_interval_30"),
                InlineKeyboardButton("Every 1 hour", callback_data="alert_interval_60")
            ],
            [
                InlineKeyboardButton("Every 6 hours", callback_data="alert_interval_360"),
                InlineKeyboardButton("Every 12 hours", callback_data="alert_interval_720")
            ],
            [InlineKeyboardButton("Cancel", callback_data="alert_menu")]
        ])
        step4_msg = f"Step 4 of 4: How often should I check?"
    else:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⭐ 30 min — Premium only", callback_data="alert_interval_30"),
                InlineKeyboardButton("⭐ 1 hour — Premium only", callback_data="alert_interval_60")
            ],
            [
                InlineKeyboardButton("Every 6 hours", callback_data="alert_interval_360"),
                InlineKeyboardButton("Every 12 hours", callback_data="alert_interval_720")
            ],
            [InlineKeyboardButton("Cancel", callback_data="alert_menu")]
        ])
        step4_msg = f"Step 4 of 4: How often should I check?\n\n⭐ = Premium feature — tap to unlock"

    await update.message.reply_text(
        f"Create New Alert\n\n"
        f"Metric: {metric}\n"
        f"Condition: {operator} {unit}{text}\n\n"
        f"{step4_msg}",
        reply_markup=keyboard
    )


async def add_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 4:
        account_name = context.args[0]
        access_key = context.args[1]
        secret_key = context.args[2]
        region = context.args[3]
        user_id = update.effective_user.id

        msg = await update.message.reply_text("Verifying credentials...")

        try:
            monitor = AWSMonitor(access_key, secret_key, region)
            if not monitor.test_connection():
                await msg.edit_text("AWS credentials invalid!\n\nPlease check and try again.")
                return
        except Exception as e:
            await msg.edit_text(f"AWS connection failed!\n\nError: {str(e)}")
            return

        account_id = db.add_aws_account(user_id, account_name, access_key, secret_key, region)

        if account_id:
            await msg.edit_text(
                f"AWS Account Connected!\n\n"
                f"Name: {account_name}\n"
                f"Region: {region}\n"
                f"Credentials encrypted and saved\n\n"
                f"Use menu to check status!",
                reply_markup=main_menu_keyboard()
            )
            await asyncio.sleep(3)
            try:
                await update.message.delete()
            except:
                pass
        else:
            await msg.edit_text("Failed to save to database!")
    else:
        await update.message.reply_text(
            "Format:\n/addaccount <name> <access_key> <secret_key> <region>\n\n"
            "Example:\n/addaccount Production AKIA... wJalr... us-east-1",
            reply_markup=back_to_menu_keyboard()
        )


async def set_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 4:
        await update.message.reply_text(
            "Format:\n/setalert <metric> <operator> <value> <interval_minutes>\n\n"
            "Metrics: daily_cost, monthly_cost, cpu_average\n"
            "Operators: > < >= <=\n\n"
            "Example:\n/setalert daily_cost > 10 60",
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
        await update.message.reply_text(f"Invalid metric! Valid: {', '.join(valid_metrics)}")
        return

    if operator not in valid_operators:
        await update.message.reply_text(f"Invalid operator! Valid: {', '.join(valid_operators)}")
        return

    try:
        threshold = float(value)
        check_interval = int(interval)
    except ValueError:
        await update.message.reply_text("Value and interval must be numbers!")
        return

    user_id = update.effective_user.id
    accounts = db.get_aws_accounts(user_id)

    if not accounts:
        await update.message.reply_text("Connect AWS account first!", reply_markup=main_menu_keyboard())
        return

    account_id = accounts[0]['account_id']
    config_id = db.add_alert(account_id, metric, threshold, operator, check_interval)

    if config_id:
        await update.message.reply_text(
            f"Alert Set!\n\n"
            f"Metric: {metric}\n"
            f"Condition: {operator} {threshold}\n"
            f"Check: Every {check_interval} minutes\n\n"
            f"I will notify you!",
            reply_markup=main_menu_keyboard()
        )
    else:
        await update.message.reply_text("Failed to save alert!")


async def myplan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/myplan command - plan details dikhao"""
    user_id = update.effective_user.id
    current_plan = db.get_user_plan(user_id)

    conn = db._get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT plan_name, end_date FROM subscriptions
            WHERE user_id = %s AND is_active = true
            AND (end_date IS NULL OR end_date > NOW())
            ORDER BY start_date DESC LIMIT 1
        """, (user_id,))
        sub = cursor.fetchone()
    finally:
        cursor.close()
        db._put_conn(conn)

    message = "My Plan\n\n"
    message += f"Current Plan: {current_plan.upper()}\n\n"

    if sub and sub[1]:
        days_left = (sub[1] - datetime.now()).days + 1
        message += f"Expires: {sub[1].strftime('%d-%m-%Y')}\n"
        message += f"Days remaining: {days_left}\n\n"
    elif current_plan == 'free':
        message += "No expiry - Free plan\n\n"

    if current_plan == 'free':
        message += "Upgrade to Premium for:\n"
        message += "- 30 min alert checks\n"
        message += "- Weekly reports\n"
        message += "- Anomaly detection\n"
        message += "- PDF reports\n"
        message += "- 90/180 day charts"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Upgrade to Premium", callback_data="show_upgrade")],
            [InlineKeyboardButton("Back to Menu", callback_data="main_menu")]
        ])
    else:
        message += "Premium Benefits Active:\n"
        message += "- 30 min alert checks\n"
        message += "- Weekly reports\n"
        message += "- Anomaly detection\n"
        message += "- PDF reports\n"
        message += "- 90/180 day charts"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Renew Premium", callback_data="buy_premium")],
            [InlineKeyboardButton("Back to Menu", callback_data="main_menu")]
        ])

    await update.message.reply_text(message, reply_markup=keyboard)


async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/support command"""
    user = update.effective_user
    admin_id = int(os.getenv('ADMIN_ID', '0'))

    if context.args:
        # User ne message diya - admin ko forward karo
        support_msg = ' '.join(context.args)

        # Admin ko notify karo
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"Support Request\n\n"
                     f"From: {user.first_name} (@{user.username})\n"
                     f"ID: {user.id}\n\n"
                     f"Message: {support_msg}"
            )
            await update.message.reply_text(
                "Your message has been sent to support.\n\n"
                "We'll get back to you soon!",
                reply_markup=main_menu_keyboard()
            )
        except Exception as e:
            await update.message.reply_text("Failed to send message. Try again later.")
    else:
        await update.message.reply_text(
            "Support\n\n"
            "To contact support, use:\n"
            "/support <your message>\n\n"
            "Example:\n"
            "/support I can't connect my AWS account\n\n"
            "We typically respond within 24 hours.",
            reply_markup=main_menu_keyboard()
        )


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin panel - sirf admin access kar sakta hai"""
    user_id = update.effective_user.id
    admin_id = int(os.getenv('ADMIN_ID', '0'))

    # Access check
    if user_id != admin_id:
        await update.message.reply_text("Access Denied.")
        return

    stats = db.get_admin_stats()

    message = "Admin Panel\n\n"
    message += f"Total Users: {stats.get('total_users', 0)}\n"
    message += f"Premium Users: {stats.get('premium_users', 0)}\n"
    message += f"Free Users: {stats.get('free_users', 0)}\n\n"
    message += f"Revenue This Month: Rs.{stats.get('revenue_this_month', 0)}\n\n"
    message += f"AWS Accounts: {stats.get('total_accounts', 0)}\n"
    message += f"Active Alerts: {stats.get('active_alerts', 0)}\n\n"
    message += f"New Users Today: {stats.get('new_today', 0)}\n"
    message += f"New Users This Week: {stats.get('new_this_week', 0)}"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("View Recent Users", callback_data="admin_users")],
        [InlineKeyboardButton("Broadcast Message", callback_data="admin_broadcast")]
    ])

    await update.message.reply_text(message, reply_markup=keyboard)


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin button clicks"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    admin_id = int(os.getenv('ADMIN_ID', '0'))

    if user_id != admin_id:
        await query.edit_message_text("Access Denied.")
        return

    if query.data == "admin_users":
        users = db.get_all_users()
        message = "Recent Users (Last 20):\n\n"
        for u in users:
            plan_icon = "💎" if u['plan'] == 'premium' else "🆓"
            name = u['first_name'] or 'Unknown'
            username = f"@{u['username']}" if u['username'] else "no username"
            message += f"{plan_icon} {name} ({username})\n"
            message += f"   Joined: {u['created_at'].strftime('%d-%m-%Y')}\n\n"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Back to Admin", callback_data="admin_back")]
        ])
        await query.edit_message_text(message, reply_markup=keyboard)

    elif query.data == "admin_broadcast":
        context.user_data['admin_waiting'] = 'broadcast'
        await query.edit_message_text(
            "Broadcast Message\n\n"
            "Type your message and send.\n"
            "It will be sent to ALL users.\n\n"
            "Type /cancel to cancel."
        )

    elif query.data == "admin_back":
        stats = db.get_admin_stats()
        message = "Admin Panel\n\n"
        message += f"Total Users: {stats.get('total_users', 0)}\n"
        message += f"Premium Users: {stats.get('premium_users', 0)}\n"
        message += f"Free Users: {stats.get('free_users', 0)}\n\n"
        message += f"Revenue This Month: Rs.{stats.get('revenue_this_month', 0)}\n\n"
        message += f"AWS Accounts: {stats.get('total_accounts', 0)}\n"
        message += f"Active Alerts: {stats.get('active_alerts', 0)}\n\n"
        message += f"New Users Today: {stats.get('new_today', 0)}\n"
        message += f"New Users This Week: {stats.get('new_this_week', 0)}"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("View Recent Users", callback_data="admin_users")],
            [InlineKeyboardButton("Broadcast Message", callback_data="admin_broadcast")]
        ])
        await query.edit_message_text(message, reply_markup=keyboard)


async def handle_admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin broadcast message saare users ko bhejo"""
    if context.user_data.get('admin_waiting') != 'broadcast':
        return False

    admin_id = int(os.getenv('ADMIN_ID', '0'))
    if update.effective_user.id != admin_id:
        return False

    broadcast_text = update.message.text
    context.user_data['admin_waiting'] = None

    # Saare users nikalo
    conn = db._get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    cursor.close()
    db._put_conn(conn)

    sent = 0
    failed = 0
    for user in users:
        try:
            await context.bot.send_message(
                chat_id=user[0],
                text=f"📢 Message from AWS Monitor Bot:\n\n{broadcast_text}"
            )
            sent += 1
        except Exception:
            failed += 1

    await update.message.reply_text(
        f"Broadcast Complete!\n\nSent: {sent}\nFailed: {failed}"
    )
    return True


async def delete_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /deletealert <alert_id>")
        return

    try:
        config_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Alert ID must be a number!")
        return

    conn = db._get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM alert_configs WHERE config_id = %s", (config_id,))
        conn.commit()
        if cursor.rowcount > 0:
            await update.message.reply_text(f"Alert {config_id} deleted!", reply_markup=main_menu_keyboard())
        else:
            await update.message.reply_text("Alert not found!")
    except Exception as e:
        conn.rollback()
        await update.message.reply_text(f"Error: {e}")
    finally:
        cursor.close()
        db._put_conn(conn)


# ─────────────────────────────────────────
# ERROR HANDLER
# ─────────────────────────────────────────

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"Error: {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "Something went wrong! Please try again.",
            reply_markup=main_menu_keyboard()
        )


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────

def main():
    print("AWS Monitor Bot starting...")

    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token:
        print("BOT_TOKEN not found in .env!")
        return

    app = Application.builder().token(bot_token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addaccount", add_account))
    app.add_handler(CommandHandler("setalert", set_alert))
    app.add_handler(CommandHandler("deletealert", delete_alert))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("myplan", myplan_command))
    app.add_handler(CommandHandler("support", support_command))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_alert_value))
    app.add_error_handler(error_handler)

    async def post_init(application):
        scheduler = AlertScheduler(application.bot)
        scheduler.start()

    app.post_init = post_init

    print("Bot ready!")
    print("Send /start on Telegram")
    print("Press Ctrl+C to stop\n")

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()