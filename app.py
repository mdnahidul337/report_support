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
    CallbackQueryHandler,
    ConversationHandler
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
        self.last_link_number = 0
        self.user_messages = {}
        self.load_data()

    def load_data(self):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                self.links = data.get("links", [])
                self.report_counts = data.get("report_counts", {})
                self.last_link_number = data.get("last_link_number", 0)
                self.user_messages = data.get("user_messages", {})
        except (FileNotFoundError, json.JSONDecodeError):
            self.save_data()

    def save_data(self):
        with open(DATA_FILE, "w") as f:
            json.dump({
                "links": self.links,
                "report_counts": self.report_counts,
                "last_link_number": self.last_link_number,
                "user_messages": self.user_messages
            }, f, indent=2)

bot_data = BotData()

# ------------------ 핸들러 ফাংশন ------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("রিপোর্ট করতে মেসেজে রিপ্লাই করে @admin লিখুন")

async def add_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ অনুমতি প্রত্যাখ্যান!")
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text("❌ ব্যবহার: /addlink <URL> <তারিখ>")
        return

    url, date = args[0], ' '.join(args[1:])
    bot_data.last_link_number += 1
    bot_data.links.append({
        "number": bot_data.last_link_number,
        "url": url,
        "date": date
    })
    bot_data.save_data()
    await update.message.reply_text(f"✅ লিংক #{bot_data.last_link_number} যোগ করা হয়েছে!")

async def handle_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    # Delete previous messages
    if user_id in bot_data.user_messages:
        for msg_id in bot_data.user_messages[user_id]:
            try:
                await context.bot.delete_message(update.message.chat.id, msg_id)
            except:
                pass
        bot_data.user_messages[user_id] = []

    # Create new message
    links_text = "📥 ডাউনলোড লিংকসমূহ:\n\n"
    keyboard = []
    for link in bot_data.links:
        links_text += f"{link['number']}.🔗 [ডাউনলোড করুন]({link['url']}) [{link['date']}]\n"
        keyboard.append([InlineKeyboardButton(f"লিংক {link['number']}", url=link['url'])])

    reply_markup = InlineKeyboardMarkup(keyboard)
    sent_message = await update.message.reply_text(
        links_text,
        reply_markup=reply_markup,
        parse_mode="Markdown",
        disable_web_page_preview=True
    )
    
    # Store message ID
    bot_data.user_messages[user_id] = [sent_message.message_id]
    bot_data.save_data()

async def manage_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ অনুমতি প্রত্যাখ্যান!")
        return

    keyboard = [
        [InlineKeyboardButton("📤 Export", callback_data="export_links"),
         InlineKeyboardButton("📥 Import", callback_data="import_links")],
        [InlineKeyboardButton("🗑️ সব ডিলিট", callback_data="delete_all_links")]
    ]
    await update.message.reply_text(
        "🔗 লিংক ম্যানেজমেন্ট:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def export_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    with open("links_export.json", "w") as f:
        json.dump(bot_data.links, f)
    
    await context.bot.send_document(
        chat_id=query.message.chat_id,
        document=open("links_export.json", "rb"),
        caption="📤 লিংক এক্সপোর্ট ফাইল"
    )

async def import_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📥 JSON ফাইল পাঠান")
    return "IMPORT_LINKS"

async def handle_import(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.document.get_file()
    await file.download_to_drive("import_temp.json")
    
    try:
        with open("import_temp.json", "r") as f:
            imported_links = json.load(f)
            bot_data.links = imported_links
            bot_data.last_link_number = max([link["number"] for link in imported_links], default=0)
            bot_data.save_data()
            await update.message.reply_text(f"✅ {len(imported_links)} টি লিংক ইম্পোর্ট করা হয়েছে!")
    except Exception as e:
        await update.message.reply_text(f"❌ ত্রুটি: {str(e)}")
    
    return ConversationHandler.END

async def delete_all_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    bot_data.links = []
    bot_data.last_link_number = 0
    bot_data.save_data()
    await query.edit_message_text("✅ সব লিংক ডিলিট করা হয়েছে!")

# ------------------ মূল অ্যাপ্লিকেশন ------------------
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Command Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addlink", add_link))
    app.add_handler(CommandHandler("managelinks", manage_links))

    # Message Handlers
    app.add_handler(MessageHandler(
        filters.TEXT & (filters.Regex(r"(?i)download|ডাউনলোড")),
        handle_download
    ))

    # Callback Handlers
    app.add_handler(CallbackQueryHandler(export_links, pattern="^export_links"))
    app.add_handler(CallbackQueryHandler(delete_all_links, pattern="^delete_all_links"))
    
    # Conversation Handler
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(import_links, pattern="^import_links")],
        states={
            "IMPORT_LINKS": [MessageHandler(filters.Document.ALL, handle_import)]
        },
        fallbacks=[]
    )
    app.add_handler(conv_handler)

    app.run_polling()

if __name__ == "__main__":
    main()
