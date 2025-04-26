import os
import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Bot,
    MessageEntity
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
REPORT_GROUP = os.getenv("REPORT_GROUP")

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("রিপোর্ট করার জন্য কোনো মেসেজে রিপ্লাই করে @admin লিখুন")

async def handle_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.message.chat.type == "private":
            return

        if not update.message.reply_to_message:
            return

        if not any(entity.type == MessageEntity.MENTION for entity in update.message.entities):
            return

        reported_user = update.message.reply_to_message.from_user
        reporter_user = update.message.from_user
        message = update.message.reply_to_message

        # Check if bot is in group
        bot_member = await context.bot.get_chat_member(update.message.chat.id, context.bot.id)
        if bot_member.status not in ["administrator", "member"]:
            return

        # Prepare report message
        report_text = f"""
🚨 নতুন রিপোর্ট 🚨
রিপোর্টকারী: {reporter_user.mention_html()}
অভিযুক্ত ব্যবহারকারী: {reported_user.mention_html()}
গ্রুপ: {update.message.chat.title}
        """

        # Create buttons
        keyboard = [
            [
                InlineKeyboardButton("✅ Accept", callback_data=f"accept_{reported_user.id}_{reporter_user.id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{reported_user.id}_{reporter_user.id}")
            ],
            [
                InlineKeyboardButton("📩 View Message", url=message.link)
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send to admins and report group
        for admin_id in ADMIN_IDS:
            await context.bot.send_message(
                chat_id=admin_id,
                text=report_text,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )

    except Exception as e:
        logger.error(f"Error in handle_report: {e}")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split('_')
    action = data[0]
    reported_user_id = data[1]
    reporter_user_id = data[2]

    # Update admin message
    await query.edit_message_text(
        text=f"{query.message.text}\n\nStatus: {'Accepted' if action == 'accept' else 'Rejected'}",
        parse_mode="HTML"
    )

    # Notify user
    try:
        await context.bot.send_message(
            chat_id=reporter_user_id,
            text=f"আপনার রিপোর্টটি {action} করা হয়েছে"
        )
    except Exception as e:
        logger.error(f"Error sending notification: {e}")

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Commands
    application.add_handler(CommandHandler("start", start))

    # Handle @admin mentions
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Entity(MessageEntity.MENTION),
        handle_report
    ))

    # Button clicks
    application.add_handler(CallbackQueryHandler(button_click))

    application.run_polling()

if __name__ == "__main__":
    main()
