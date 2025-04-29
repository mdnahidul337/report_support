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
SPAM_LIMIT = 3  # একই মেসেজের সর্বোচ্চ সংখ্যা
MUTE_DURATION = 10  # মিনিট

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
        self.spam_data = {}  # {user_id: {"messages": {text: count}, "last_message_time": timestamp}}
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

# ------------------ নতুন ফাংশন ------------------
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
    user_id = update.message.from_user.id
    message_text = update.message.text.lower()

    # স্পাম চেক
    current_time = datetime.now().timestamp()
    if user_id not in bot_data.spam_data:
        bot_data.spam_data[user_id] = {"messages": {}, "last_message_time": current_time}
    else:
        time_diff = current_time - bot_data.spam_data[user_id]["last_message_time"]
        if time_diff > 300:  # 5 মিনিট পর রিসেট
            bot_data.spam_data[user_id] = {"messages": {}, "last_message_time": current_time}

    # মেসেজ কাউন্ট আপডেট
    if message_text in bot_data.spam_data[user_id]["messages"]:
        bot_data.spam_data[user_id]["messages"][message_text] += 1
    else:
        bot_data.spam_data[user_id]["messages"][message_text] = 1

    # স্পাম ডিটেক্ট
    if bot_data.spam_data[user_id]["messages"][message_text] > SPAM_LIMIT:
        try:
            await context.bot.restrict_chat_member(
                chat_id=update.message.chat.id,
                user_id=user_id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=datetime.now() + timedelta(minutes=MUTE_DURATION)
            )
            await update.message.reply_text(f"⚠️ স্পামিং এর জন্য {MUTE_DURATION} মিনিট মিউট করা হয়েছে")
            bot_data.spam_data[user_id]["messages"].clear()
        except Exception as e:
            logger.error(f"মিউট ব্যর্থ: {str(e)}")

    # অটো রিপ্লাই চেক
    for question, answer in bot_data.auto_replies.items():
        if question in message_text:
            await update.message.reply_text(f"🤖 উত্তর: {answer}")
            break

# ------------------ আপডেটেড ফাংশন ------------------
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split('_')
    action, reported_id, reporter_id, group_id = data[0], int(data[1]), int(data[2]), int(data[3])

    # স্ট্যাটাস আপডেট
    await query.edit_message_text(f"{query.message.text}\nস্ট্যাটাস: {'✅ Accepted' if action == 'accept' else '❌ Rejected'}")

    # Accept হলে রিপোর্টেড ইউজারকে মিউট করুন (2 ঘন্টা)
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

    # Reject হলে রিপোর্টকারীর কাউন্টার আপডেট
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

    # নোটিফিকেশন পাঠান
    try:
        await context.bot.send_message(
            reporter_id,
            f"📢 আপনার রিপোর্টটি {'গ্রহণ' if action == 'accept' else 'প্রত্যাখ্যান'} করা হয়েছে"
        )
    except Exception as e:
        logger.error(f"DM failed: {str(e)}")
        await context.bot.send_message(
            group_id,
            f"🔔 ব্যবহারকারী [{reporter_id}](tg://user?id={reporter_id}) কে নোটিফিকেশন পাঠানো যায়নি\n"
            f"ইউজার আইডি: `{reporter_id}`",
            parse_mode="Markdown"
        )

def main():
    if os.name == 'posix':
        os.system("pkill -f app.py")
    else:
        os.system("taskkill /im python.exe /f")

    try:
        app = Application.builder().token(BOT_TOKEN).build()
        
        # নতুন হ্যান্ডলার যোগ করুন
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("Qus", add_auto_reply))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_auto_reply))

        # পূর্বের সমস্ত হ্যান্ডলার
        # [পূর্বের কোড অপরিবর্তিত রাখুন]

        app.run_polling()
    except KeyboardInterrupt:
        logger.info("বট বন্ধ করা হয়েছে")
        sys.exit(0)
    except Exception as e:
        logger.error(f"ক্রিটিক্যাল এরর: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
