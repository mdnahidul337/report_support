import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, MessageHandler, Filters, CallbackContext

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = "7643025446:AAHPQgytUtqHz_wB-9y-OziM8aucimPvThw"

def handle_message(update: Update, context: CallbackContext):
    message = update.effective_message
    chat = message.chat

    # Check if message is from group
    if chat.type not in ['group', 'supergroup']:
        return

    # Check for @admin mention in text or caption
    text = message.text or message.caption
    entities = message.entities or message.caption_entities
    
    if not text or not entities:
        return

    admin_mentioned = any(
        entity.type == "mention" and text[entity.offset:entity.offset+entity.length].lower() == "@admin"
        for entity in entities
    )

    if not admin_mentioned:
        return

    # Reply in group
    message.reply_text("✅ রিপোর্টটি অ্যাডমিনদের কাছে পাঠানো হয়েছে। গ্রুপে যুক্ত থাকতে হবে।")

    # Get admins
    try:
        admins = context.bot.get_chat_administrators(chat.id)
    except Exception as e:
        logger.error(f"Error getting admins: {e}")
        return

    # Prepare report message
    report_msg = (
        f"🚨 নতুন রিপোর্ট!\n\n"
        f"📛 গ্রুপ: {chat.title}\n"
        f"👤 ব্যবহারকারী: {message.from_user.mention_html()}\n"
        f"💬 মেসেজ: {text}\n\n"
        f"👉 মেসেজ দেখতে নিচের বাটনে ক্লিক করুন"
    )

    # Create message link button
    keyboard = [[InlineKeyboardButton("ভিউ মেসেজ", url=message.link)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send to admins
    for admin in admins:
        try:
            context.bot.send_message(
                chat_id=admin.user.id,
                text=report_msg,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error sending to admin {admin.user.id}: {e}")

def main():
    updater = Updater(TOKEN)
    dp = updater.dispatcher

    # Add handler for group messages
    dp.add_handler(MessageHandler(
        Filters.chat_type.groups & (Filters.text | Filters.caption),
        handle_message
    ))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
