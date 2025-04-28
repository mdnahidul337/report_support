import os
import json
import logging
from datetime import datetime, timedelta
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MessageEntity,
    ChatPermissions
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackQueryHandler
)
from dotenv import load_dotenv

load_dotenv()

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(',')))
DATA_FILE = "bot_data.json"

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class BotData:
    def __init__(self):
        self.links = []
        self.report_counts = {}
        self.load_data()

    def load_data(self):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                self.links = data.get("links", [])
                self.report_counts = data.get("report_counts", {})
        except (FileNotFoundError, json.JSONDecodeError):
            self.save_data()

    def save_data(self):
        with open(DATA_FILE, "w") as f:
            json.dump({
                "links": self.links,
                "report_counts": self.report_counts
            }, f, indent=2)

bot_data = BotData()

# ------------------ 핸들러 ফাংশন ------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("রিপোর্ট করতে মেসেজে রিপ্লাই করে @admin লিখুন")

async def handle_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update.message.reply_to_message:
            return

        # Check @admin mention
        if not any(entity.type == MessageEntity.MENTION for entity in update.message.entities):
            return

        reporter = update.message.from_user
        reported = update.message.reply_to_message.from_user
        group_id = update.message.chat.id

        # Check bot's admin status
        try:
            bot_member = await context.bot.get_chat_member(group_id, context.bot.id)
            if bot_member.status != "administrator":
                await update.message.reply_text("⚠️ বটকে অ্যাডমিন করুন")
                return
        except Exception as e:
            logger.error(f"Admin check failed: {str(e)}")
            return

        # Prepare report
        report_msg = f"""
🚨 নতুন রিপোর্ট 🚨
রিপোর্টকারী: {reporter.mention_html()}
অভিযুক্ত: {reported.mention_html()}
গ্রুপ: {update.message.chat.title}
        """
        keyboard = [
            [
                InlineKeyboardButton("✅ Accept", callback_data=f"accept_{reported.id}_{reporter.id}_{group_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{reported.id}_{reporter.id}_{group_id}")
            ],
            [InlineKeyboardButton("📩 View", url=update.message.reply_to_message.link)]
        ]

        # Send to admins
        for admin_id in ADMIN_IDS:
            await context.bot.send_message(
                admin_id,
                text=report_msg,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )

        # Confirm in group
        msg = await update.message.reply_text("✅ রিপোর্ট পাঠানো হয়েছে")
        await context.bot.delete_message(update.message.chat.id, msg.message_id)

    except Exception as e:
        logger.error(f"Report error: {str(e)}")

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split('_')
    action, reported_id, reporter_id, group_id = data[0], int(data[1]), int(data[2]), int(data[3])

    # Update report status
    await query.edit_message_text(f"{query.message.text}\nস্ট্যাটাস: {'✅ Accepted' if action == 'accept' else '❌ Rejected'}")

    # Handle reject
    if action == "reject":
        reporter_str = str(reporter_id)
        bot_data.report_counts[reporter_str] = bot_data.report_counts.get(reporter_str, 0) + 1
        bot_data.save_data()

        if bot_data.report_counts[reporter_str] >= 3:
            try:
                until = datetime.now() + timedelta(minutes=30)
                await context.bot.restrict_chat_member(
                    chat_id=group_id,
                    user_id=reporter_id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=until
                )
                await context.bot.send_message(
                    group_id,
                    f"⛔ ব্যবহারকারী [{reporter_id}](tg://user?id={reporter_id}) কে 30 মিনিটের জন্য মিউট করা হয়েছে",
                    parse_mode="Markdown"
                )
                bot_data.report_counts[reporter_str] = 0
                bot_data.save_data()
            except Exception as e:
                logger.error(f"Mute error: {str(e)}")
                await query.message.reply_text(f"❌ ত্রুটি: {str(e)}")

    # Send notification
    try:
        await context.bot.send_message(
            reporter_id,
            f"📢 আপনার রিপোর্টটি {'গ্রহণ' if action == 'accept' else 'প্রত্যাখ্যান'} করা হয়েছে"
        )
    except Exception as e:
        logger.error(f"DM failed: {str(e)}")
        await context.bot.send_message(
            group_id,
            f"🔔 ব্যবহারকারী [{reporter_id}](tg://user?id={reporter_id}) কে নোটিফাই করা যায়নি",
            parse_mode="Markdown"
        )

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
