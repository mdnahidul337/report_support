import os
import json
import logging
import sys
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
        self.load_data()

    def load_data(self):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                self.links = data.get("links", [])
                self.report_counts = data.get("report_counts", {})
                self.last_link_number = data.get("last_link_number", 0)
        except (FileNotFoundError, json.JSONDecodeError):
            self.save_data()

    def save_data(self):
        with open(DATA_FILE, "w") as f:
            json.dump({
                "links": self.links,
                "report_counts": self.report_counts,
                "last_link_number": self.last_link_number
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
    if not bot_data.links:
        await update.message.reply_text("⚠️ কোনো লিংক পাওয়া যায়নি!")
        return

    # Delete previous messages
    if update.message.from_user.id in bot_data.user_messages:
        for msg_id in bot_data.user_messages[update.message.from_user.id]:
            try:
                await context.bot.delete_message(update.message.chat.id, msg_id)
            except:
                pass

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
    bot_data.user_messages[update.message.from_user.id] = [sent_message.message_id]
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
            f"📢 আপনার রিপোর্টটি {'গ্রহণ' if action == 'accept' else 'প্রত্যাখ্যান'} করা হয়েছে",
            parse_mode="Markdown"
        )

def main():
    # Kill existing processes
    if os.name == 'posix':
        os.system("pkill -f app.py")
    else:
        os.system("taskkill /im python.exe /f")

    try:
        app = Application.builder().token(BOT_TOKEN).build()
        
        # Conversation Handler
        conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(import_links, pattern="^import_links")],
            states={
                "IMPORT_LINKS": [
                    MessageHandler(
                        filters.Document.ALL & ~filters.COMMAND,
                        handle_import
                    )
                ]
            },
            fallbacks=[CommandHandler("cancel", lambda u,c: ConversationHandler.END)],
            per_message=True,
            per_chat=True,
            per_user=True
        )

        # Handlers
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("addlink", add_link))
        app.add_handler(CommandHandler("managelinks", manage_links))
        app.add_handler(MessageHandler(
            filters.TEXT & filters.Entity(MessageEntity.MENTION),
            handle_report
        ))
        app.add_handler(MessageHandler(
            filters.Regex(r"(?i)download|ডাউনলোড"),
            handle_download
        ))
        app.add_handler(CallbackQueryHandler(handle_button, pattern=r"^(accept|reject)_"))
        app.add_handler(conv_handler)
        app.add_handler(CallbackQueryHandler(delete_all_links, pattern="^delete_all_links"))
        app.add_handler(CallbackQueryHandler(export_links, pattern="^export_links"))

        # Start bot
        app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            close_loop=False,
            stop_signals=[]
        )
    except KeyboardInterrupt:
        logger.info("বট বন্ধ করা হয়েছে")
        sys.exit(0)
    except Exception as e:
        logger.error(f"ক্রিটিক্যাল এরর: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
