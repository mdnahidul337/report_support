import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, MessageHandler, Filters, CallbackContext
from telegram.error import BadRequest

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
    user = message.from_user

    if chat.type not in ['group', 'supergroup']:
        return

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

    full_name = f"{user.first_name} {user.last_name}" if user.last_name else user.first_name

    message.reply_text("✅ রিপোর্টটি অ্যাডমিনদের কাছে পাঠানো হয়েছে। গ্রুপে যুক্ত থাকতে হবে।")

    try:
        admins = context.bot.get_chat_administrators(chat.id)
    except Exception as e:
        logger.error(f"Error getting admins: {e}")
        return

    report_msg = (
        f"🚨 নতুন রিপোর্ট!\n\n"
        f"📛 গ্রুপ: {chat.title}\n"
        f"👤 ব্যবহারকারী: {user.mention_html()}\n"
        f"📛 নাম: {full_name}\n"
        f"🆔 আইডি: {user.id}\n"
        f"💬 মেসেজ: {text}\n\n"
        f"👉 মেসেজ দেখতে নিচের বাটনে ক্লিক করুন"
    )

    keyboard = [
        [
            InlineKeyboardButton("মেসেজ দেখুন", url=message.link),
            InlineKeyboardButton("প্রোফাইল দেখুন", url=f"tg://user?id={user.id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    failed_admins = []
    for admin in admins:
        try:
            # Skip if trying to message the group itself
            if admin.user.id == chat.id:
                continue
                
            context.bot.send_message(
                chat_id=admin.user.id,
                text=report_msg,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
        except BadRequest as e:
            if "Chat not found" in str(e):
                logger.warning(f"Admin {admin.user.id} hasn't started chat with bot")
                failed_admins.append(admin.user.mention_html())
            else:
                logger.error(f"Error sending to admin {admin.user.id}: {e}")
        except Exception as e:
            logger.error(f"Error sending to admin {admin.user.id}: {e}")

    # Notify group about admins who didn't start chat
    if failed_admins:
        warning_msg = (
            "⚠️ নিম্নলিখিত অ্যাডমিনরা বটের সাথে চ্যাট শুরু করেননি:\n"
            + "\n".join(failed_admins) +
            "\n\nরিপোর্ট পেতে আমাকে প্রাইভেট চ্যাটে স্টার্ট করুন!"
        )
        try:
            message.reply_text(warning_msg, parse_mode="HTML")
        except BadRequest:
            logger.warning("Couldn't send admin warning to group")

def main():
    updater = Updater(TOKEN)
    dp = updater.dispatcher

    dp.add_handler(MessageHandler(
        Filters.chat_type.groups & (Filters.text | Filters.caption),
        handle_message
    ))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
