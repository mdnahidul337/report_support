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

# Link storage
links = []
last_link_number = 0

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

        # Send to admins
        for admin_id in ADMIN_IDS:
            await context.bot.send_message(
                chat_id=admin_id,
                text=report_text,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )

        # Send confirmation to group
        await update.message.reply_to_message.reply_text("✅ রিপোর্টটি এডমিনদের কাছে পাঠানো হয়েছে")

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

async def add_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("⚠️ Permission Denied!")
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text("❌ Usage: /addlink <URL> <DATE>")
        return

    url = args[0]
    date = ' '.join(args[1:])
    global last_link_number
    last_link_number += 1
    
    links.append({
        'number': last_link_number,
        'url': url,
        'date': date
    })
    
    await update.message.reply_text(f"✅ লিঙ্ক #{last_link_number} সফলভাবে যুক্ত হয়েছে!")

async def handle_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not links:
        await update.message.reply_text("⚠️ কোনো লিঙ্ক পাওয়া যায়নি!")
        return

    message_text = "📥 ডাউনলোড লিঙ্কসমূহ:\n\n"
    keyboard = []
    
    for link in links:
        message_text += f"{link['number']}.🔗 [ডাউনলোড করতে ক্লিক করুন]({link['url']}) [{link['date']}]\n"
        keyboard.append([InlineKeyboardButton(
            text=f"View Link {link['number']}", 
            url=link['url']
        )])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        text=message_text,
        reply_markup=reply_markup,
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

async def manage_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("⚠️ Permission Denied!")
        return

    if not links:
        await update.message.reply_text("⚠️ কোনো লিঙ্ক পাওয়া যায়নি!")
        return

    keyboard = []
    for link in links:
        keyboard.append([
            InlineKeyboardButton(
                f"🗑 Delete {link['number']}",
                callback_data=f"delete_{link['number']}"
            )
        ])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🔗 লিঙ্ক ম্যানেজমেন্ট:",
        reply_markup=reply_markup
    )

async def delete_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    link_number = int(query.data.split('_')[1])
    global links
    
    # Remove link
    links = [link for link in links if link['number'] != link_number]
    
    # Edit original message
    await query.edit_message_text(
        text=f"✅ লিঙ্ক #{link_number} ডিলিট করা হয়েছে!",
        reply_markup=None
    )

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("addlink", add_link))
    application.add_handler(CommandHandler("managelinks", manage_links))

    # Handlers
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Entity(MessageEntity.MENTION),
        handle_report
    ))
    application.add_handler(MessageHandler(
        filters.Regex(r"(?i)download|ডাউনলোড"),
        handle_download
    ))

    # Callbacks
    application.add_handler(CallbackQueryHandler(button_click, pattern="^(accept|reject)_"))
    application.add_handler(CallbackQueryHandler(delete_link, pattern="^delete_"))

    application.run_polling()

if __name__ == "__main__":
    main()
