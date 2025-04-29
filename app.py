import os
import json
import logging
import sys
import re  # Added missing import
from datetime import datetime, timedelta
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
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
SPAM_LIMIT = 3
MUTE_DURATION = 10

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
        self.auto_replies = {}
        self.spam_data = {}
        self.load_data()

    def load_data(self):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                self.links = data.get("links", [])
                self.report_counts = data.get("report_counts", {})
                self.last_link_number = data.get("last_link_number", 0)
                self.user_messages = data.get("user_messages", {})
                self.auto_replies = data.get("auto_replies", {})
                self.spam_data = data.get("spam_data", {})
        except (FileNotFoundError, json.JSONDecodeError):
            self.save_data()

    def save_data(self):
        with open(DATA_FILE, "w") as f:
            json.dump({
                "links": self.links,
                "report_counts": self.report_counts,
                "last_link_number": self.last_link_number,
                "user_messages": self.user_messages,
                "auto_replies": self.auto_replies,
                "spam_data": self.spam_data
            }, f, indent=2)

bot_data = BotData()

# ------------------ Handler Functions ------------------
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

    user = update.effective_user
    chat_id = update.message.chat.id

    # Delete previous messages
    if user.id in bot_data.user_messages:
        for msg_id in bot_data.user_messages[user.id]:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except Exception as e:
                logger.error(f"মেসেজ ডিলিট ব্যর্থ: {str(e)}")
        bot_data.user_messages[user.id] = []

    # Create new message
    links_text = "📥 **ডাউনলোড লিংকসমূহ:**\n\n"
    keyboard = []
    for link in bot_data.links:
        links_text += f"{link['number']}. 🔗 [{link['date']}]({link['url']})\n"
        keyboard.append([InlineKeyboardButton(f"লিংক {link['number']}", url=link['url'])])

    reply_markup = InlineKeyboardMarkup(keyboard)
    sent_message = await update.message.reply_text(
        text=links_text,
        reply_markup=reply_markup,
        parse_mode="Markdown",
        disable_web_page_preview=True
    )
    
    # Store new message ID
    bot_data.user_messages[user.id] = [sent_message.message_id]
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
    bot_data.user_messages = {}
    bot_data.save_data()
    await query.edit_message_text("✅ সব লিংক ডিলিট করা হয়েছে!")

async def handle_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update.message.reply_to_message:
            return

        if not (update.message.text and '@admin' in update.message.text.lower()):
            return

        reporter = update.message.from_user
        reported = update.message.reply_to_message.from_user
        group_id = update.message.chat.id

        try:
            bot_member = await context.bot.get_chat_member(group_id, context.bot.id)
            if bot_member.status != "administrator":
                await update.message.reply_text("⚠️ বটকে অ্যাডমিন করুন")
                return
        except Exception as e:
            logger.error(f"Admin check failed: {str(e)}")
            return

        report_msg = f"""
🚨 **নতুন রিপোর্ট** 🚨
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

    await query.edit_message_text(f"{query.message.text}\nস্ট্যাটাস: {'✅ Accepted' if action == 'accept' else '❌ Rejected'}")

    if action == "accept":
        try:
            await context.bot.restrict_chat_member(
                chat_id=group_id,
                user_id=reported_id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=datetime.now() + timedelta(hours=2)
            )
            await context.bot.send_message(
                group_id,
                f"⛔ অভিযুক্ত ব্যবহারকারী [{reported_id}](tg://user?id={reported_id}) কে 2 ঘন্টার জন্য মিউট করা হয়েছে",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"মিউট ব্যর্থ: {str(e)}")

    elif action == "reject":
        reporter_str = str(reporter_id)
        bot_data.report_counts[reporter_str] = bot_data.report_counts.get(reporter_str, 0) + 1
        bot_data.save_data()

        if bot_data.report_counts[reporter_str] >= 3:
            try:
                await context.bot.restrict_chat_member(
                    chat_id=group_id,
                    user_id=reporter_id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=datetime.now() + timedelta(minutes=30)
                )
                await context.bot.send_message(
                    group_id,
                    f"⛔ মিথ্যা রিপোর্টের জন্য [{reporter_id}](tg://user?id={reporter_id}) কে 30 মিনিট মিউট করা হয়েছে",
                    parse_mode="Markdown"
                )
                bot_data.report_counts[reporter_str] = 0
                bot_data.save_data()
            except Exception as e:
                logger.error(f"মিউট ব্যর্থ: {str(e)}")

    try:
        await context.bot.send_message(
            reporter_id,
            f"📢 আপনার রিপোর্টটি {'গ্রহণ' if action == 'accept' else 'প্রত্যাখ্যান'} করা হয়েছে"
        )
    except Exception as e:
        logger.error(f"DM failed: {str(e)}")
        await context.bot.send_message(
            group_id,
            f"🔔 ব্যবহারকারী [{reporter_id}](tg://user?id={reporter_id}) কে নোটিফিকেশন পাঠানো যায়নি\nইউজার আইডি: `{reporter_id}`",
            parse_mode="Markdown"
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🛠️ **সকল কমান্ড:**
/start - বট শুরু করুন
/addlink <url> <date> - নতুন লিংক যোগ করুন
/managelinks - লিংক ম্যানেজ করুন
/help - সাহায্য মেনু দেখুন
/Qus <question> <answer> - অটো রিপ্লাই যোগ করুন
    """
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def add_auto_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ অনুমতি প্রত্যাখ্যান!")
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text("❌ ব্যবহার: /Qus 'প্রশ্ন' 'উত্তর'")
        return

    question = ' '.join(args[:-1])
    answer = args[-1]
    bot_data.auto_replies[question.lower()] = answer
    bot_data.save_data()
    await update.message.reply_text(f"✅ অটো রিপ্লাই যোগ করা হয়েছে:\nQ: {question}\nA: {answer}")

async def handle_auto_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    message_text = update.message.text.lower()

    current_time = datetime.now().timestamp()
    if user.id not in bot_data.spam_data:
        bot_data.spam_data[user.id] = {"messages": {}, "last_message_time": current_time}
    else:
        time_diff = current_time - bot_data.spam_data[user.id]["last_message_time"]
        if time_diff > 300:
            bot_data.spam_data[user.id] = {"messages": {}, "last_message_time": current_time}

    if message_text in bot_data.spam_data[user.id]["messages"]:
        bot_data.spam_data[user.id]["messages"][message_text] += 1
    else:
        bot_data.spam_data[user.id]["messages"][message_text] = 1

    if bot_data.spam_data[user.id]["messages"][message_text] > SPAM_LIMIT:
        try:
            await context.bot.restrict_chat_member(
                chat_id=update.message.chat.id,
                user_id=user.id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=datetime.now() + timedelta(minutes=MUTE_DURATION)
            )
            await update.message.reply_text(f"⚠️ স্পামিং এর জন্য {MUTE_DURATION} মিনিট মিউট করা হয়েছে")
            bot_data.spam_data[user.id]["messages"].clear()
        except Exception as e:
            logger.error(f"মিউট ব্যর্থ: {str(e)}")

    for question, answer in bot_data.auto_replies.items():
        if question in message_text:
            await update.message.reply_text(f"🤖 উত্তর: {answer}")
            break

def main():
    if os.name == 'posix':
        os.system("pkill -f app.py")
    else:
        os.system("taskkill /im python.exe /f")

    try:
        app = Application.builder().token(BOT_TOKEN).build()
        
        # Fixed conversation handler with proper settings
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

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("addlink", add_link))
        app.add_handler(CommandHandler("managelinks", manage_links))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("Qus", add_auto_reply))
        app.add_handler(MessageHandler(
            filters.TEXT & filters.REPLY & filters.Regex(r'@admin', re.IGNORECASE),
            handle_report
        ))
        app.add_handler(MessageHandler(
            filters.Regex(r"(?i)^download$|^ডাউনলোড$"),
            handle_download
        ))
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_auto_reply
        ))
        app.add_handler(CallbackQueryHandler(handle_button, pattern=r"^(accept|reject)_"))
        app.add_handler(conv_handler)
        app.add_handler(CallbackQueryHandler(delete_all_links, pattern="^delete_all_links"))
        app.add_handler(CallbackQueryHandler(export_links, pattern="^export_links"))

        app.run_polling()

    except KeyboardInterrupt:
        logger.info("বট বন্ধ করা হয়েছে")
        sys.exit(0)
    except Exception as e:
        logger.error(f"ক্রিটিক্যাল এরর: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
