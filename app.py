import os
import json
import logging
from datetime import datetime, timedelta
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Bot,
    MessageEntity,
    ChatPermissions,
    Chat
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ConversationHandler
)
from dotenv import load_dotenv

load_dotenv()

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(',')))
REPORT_GROUP = os.getenv("REPORT_GROUP")
DATA_FILE = "bot_data.json"

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Data Manager Class
class BotDataManager:
    def __init__(self):
        self.data = {
            "links": [],
            "report_counts": {},
            "bot_active": True
        }
        self.load_data()

    def load_data(self):
        try:
            with open(DATA_FILE, "r") as f:
                self.data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.save_data()

    def save_data(self):
        with open(DATA_FILE, "w") as f:
            json.dump(self.data, f, indent=2)

bot_data = BotDataManager()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("রিপোর্ট করতে মেসেজে রিপ্লাই করে @admin লিখুন")

async def handle_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not bot_data.data["bot_active"] or not update.message.reply_to_message:
            return

        reported_user = update.message.reply_to_message.from_user
        reporter_user = update.message.from_user
        group_id = update.message.chat.id

        # Check bot's group status
        try:
            bot_member = await context.bot.get_chat_member(group_id, context.bot.id)
            if bot_member.status not in ["administrator", "member"]:
                return
        except Exception as e:
            logger.error(f"Bot check failed: {str(e)}")
            return

        # Prepare report
        report_text = f"""
🚨 নতুন রিপোর্ট 🚨
রিপোর্টকারী: {reporter_user.mention_html()}
অভিযুক্ত: {reported_user.mention_html()}
গ্রুপ: {update.message.chat.title}
        """

        # Create buttons with group ID
        keyboard = [
            [
                InlineKeyboardButton("✅ Accept", callback_data=f"accept_{reported_user.id}_{reporter_user.id}_{group_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{reported_user.id}_{reporter_user.id}_{group_id}")
            ],
            [InlineKeyboardButton("📩 View", url=update.message.reply_to_message.link)]
        ]

        # Send to admins
        for admin_id in ADMIN_IDS:
            await context.bot.send_message(
                admin_id,
                text=report_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )

        # Confirmation message
        confirmation = await update.message.reply_text("✅ রিপোর্ট পাঠানো হয়েছে")
        if context.job_queue:
            context.job_queue.run_once(
                callback=lambda ctx: ctx.bot.delete_message(ctx.job.chat_id, ctx.job.message_id),
                when=10,
                data={"chat_id": confirmation.chat_id, "message_id": confirmation.message_id}
            )

    except Exception as e:
        logger.error(f"Report error: {str(e)}")

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split('_')
    action = data[0]
    reported_id = int(data[1])
    reporter_id = int(data[2])
    group_id = int(data[3])

    # Update report status
    await query.edit_message_text(f"{query.message.text}\nস্ট্যাটাস: {'Accepted' if action == 'accept' else 'Rejected'}")

    # Handle rejection
    if action == "reject":
        reporter_str = str(reporter_id)
        bot_data.data["report_counts"][reporter_str] = bot_data.data["report_counts"].get(reporter_str, 0) + 1

        if bot_data.data["report_counts"][reporter_str] >= 3:
            try:
                # Check supergroup
                chat = await context.bot.get_chat(group_id)
                if chat.type != Chat.SUPERGROUP:
                    raise ValueError("শুধুমাত্র সুপারগ্রুপে মিউট সম্ভব")

                # Check admin
                bot_member = await context.bot.get_chat_member(group_id, context.bot.id)
                if not bot_member.status == "administrator":
                    raise PermissionError("বট অ্যাডমিন নয়")

                # Mute user
                until = datetime.now() + timedelta(minutes=30)
                await context.bot.restrict_chat_member(
                    chat_id=group_id,
                    user_id=reporter_id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=until
                )
                await context.bot.send_message(
                    group_id,
                    f"⚠️ ব্যবহারকারী {reporter_id} কে 30 মিনিটের জন্য মিউট করা হয়েছে"
                )
                bot_data.data["report_counts"][reporter_str] = 0

            except Exception as e:
                logger.error(f"Mute failed: {str(e)}")
                await context.bot.send_message(
                    query.message.chat_id,
                    f"❌ ত্রুটি: {str(e)}"
                )

        bot_data.save_data()

    # Send notification
    try:
        await context.bot.send_message(reporter_id, f"রিপোর্ট {action} হয়েছে")
    except Exception as e:
        logger.error(f"Notify failed: {str(e)}")
        await query.message.reply_text(f"⚠️ ইউজারকে নোটিফাই করা যায়নি: {str(e)}")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(
        filters.TEXT & filters.Entity(MessageEntity.MENTION),
        handle_report
    ))
    app.add_handler(CallbackQueryHandler(handle_button, pattern=r"^(accept|reject)_"))

    app.run_polling()

if __name__ == "__main__":
    main()
