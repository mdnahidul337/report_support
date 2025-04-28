import os
import json
import logging
from datetime import datetime, timedelta
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

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
SETTINGS = range(1)

class BotData:
    def __init__(self):
        self.links = []
        self.last_link_number = 0
        self.report_counts = {}
        self.bot_active = True
        self.load_data()

    def save_data(self):
        data = {
            "links": self.links,
            "last_link_number": self.last_link_number,
            "report_counts": self.report_counts,
            "bot_active": self.bot_active
        }
        with open(DATA_FILE, "w") as f:
            json.dump(data, f)

    def load_data(self):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                self.links = data.get("links", [])
                self.last_link_number = data.get("last_link_number", 0)
                self.report_counts = data.get("report_counts", {})
                self.bot_active = data.get("bot_active", True)
        except FileNotFoundError:
            self.links = []
            self.last_link_number = 0
            self.report_counts = {}
            self.bot_active = True
            self.save_data()

bot_data = BotData()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("রিপোর্ট করার জন্য কোনো মেসেজে রিপ্লাই করে @admin লিখুন")

async def handle_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not bot_data.bot_active:
            return

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
        try:
            bot_member = await context.bot.get_chat_member(update.message.chat.id, context.bot.id)
            if bot_member.status not in ["administrator", "member"]:
                return
        except:
            return

        # Update report count
        user_id = reporter_user.id
        bot_data.report_counts[user_id] = bot_data.report_counts.get(user_id, 0) + 1

        # Prepare report message
        report_text = f"""
🚨 নতুন রিপোর্ট 🚨
রিপোর্টকারী: {reporter_user.mention_html()} (Report Count: {bot_data.report_counts[user_id]})
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
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=report_text,
                    reply_markup=reply_markup,
                    parse_mode="HTML"
                )
            except:
                continue

        # Send confirmation to group
        await update.message.reply_to_message.reply_text("✅ রিপোর্টটি এডমিনদের কাছে পাঠানো হয়েছে")

    except Exception as e:
        logger.error(f"Error in handle_report: {e}")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split('_')
    action = data[0]
    reported_user_id = int(data[1])
    reporter_user_id = int(data[2])

    # Update admin message
    await query.edit_message_text(
        text=f"{query.message.text}\n\nStatus: {'Accepted' if action == 'accept' else 'Rejected'}",
        parse_mode="HTML"
    )

    # Notify user
    try:
        await context.bot.send_message(
            chat_id=reporter_user_id,
            text=f"আপনার রিপোর্টটি {'গ্রহণ' if action == 'accept' else 'প্রত্যাখ্যান'} করা হয়েছে"
        )
    except Exception as e:
        logger.error(f"Error sending notification: {e}")

    # If rejected 3 times, mute user for 30 minutes
    if action == "reject":
        user_id = reporter_user_id
        if bot_data.report_counts.get(user_id, 0) >= 3:
            try:
                until_date = datetime.now() + timedelta(minutes=30)
                await context.bot.restrict_chat_member(
                    chat_id=query.message.chat_id,
                    user_id=user_id,
                    until_date=until_date,
                    permissions=None
                )
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=f"⚠️ ব্যবহারকারী {user_id} কে 30 মিনিটের জন্য মিউট করা হয়েছে (3টি মিথ্যা রিপোর্ট)"
                )
            except Exception as e:
                logger.error(f"Error muting user: {e}")

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
    bot_data.last_link_number += 1
    
    bot_data.links.append({
        'number': bot_data.last_link_number,
        'url': url,
        'date': date
    })
    
    bot_data.save_data()
    await update.message.reply_text(f"✅ লিঙ্ক #{bot_data.last_link_number} সফলভাবে যুক্ত হয়েছে!")

async def handle_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_data.bot_active:
        await update.message.reply_text("⚠️ বটটি বর্তমানে অফলাইনে আছে")
        return

    if not bot_data.links:
        await update.message.reply_text("⚠️ কোনো লিঙ্ক পাওয়া যায়নি!")
        return

    # Delete previous download messages from the same user
    try:
        if 'download_messages' not in context.chat_data:
            context.chat_data['download_messages'] = []
        
        for msg_id in context.chat_data['download_messages']:
            try:
                await context.bot.delete_message(
                    chat_id=update.message.chat_id,
                    message_id=msg_id
                )
            except:
                continue
        
        context.chat_data['download_messages'] = []
    except:
        pass

    message_text = "📥 ডাউনলোড লিঙ্কসমূহ:\n\n"
    keyboard = []
    
    for link in bot_data.links:
        message_text += f"{link['number']}.🔗 [ডাউনলোড করতে ক্লিক করুন]({link['url']}) [{link['date']}]\n"
        keyboard.append([InlineKeyboardButton(
            text=f"View Link {link['number']}", 
            url=link['url']
        )])

    reply_markup = InlineKeyboardMarkup(keyboard)
    sent_message = await update.message.reply_text(
        text=message_text,
        reply_markup=reply_markup,
        parse_mode="Markdown",
        disable_web_page_preview=True
    )
    
    # Store message ID to delete later
    if 'download_messages' not in context.chat_data:
        context.chat_data['download_messages'] = []
    context.chat_data['download_messages'].append(sent_message.message_id)

async def manage_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("⚠️ Permission Denied!")
        return

    if not bot_data.links:
        await update.message.reply_text("⚠️ কোনো লিঙ্ক পাওয়া যায়নি!")
        return

    keyboard = []
    for link in bot_data.links:
        keyboard.append([
            InlineKeyboardButton(
                f"🗑 Delete {link['number']}",
                callback_data=f"delete_{link['number']}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton("📤 Export Links", callback_data="export_links"),
        InlineKeyboardButton("📥 Import Links", callback_data="import_links")
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
    
    # Remove link
    bot_data.links = [link for link in bot_data.links if link['number'] != link_number]
    bot_data.save_data()
    
    # Edit original message
    await query.edit_message_text(
        text=f"✅ লিঙ্ক #{link_number} ডিলিট করা হয়েছে!",
        reply_markup=None
    )

async def export_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    with open("links_export.json", "w") as f:
        json.dump(bot_data.links, f)
    
    await context.bot.send_document(
        chat_id=query.message.chat_id,
        document=open("links_export.json", "rb"),
        caption="📤 লিঙ্ক এক্সপোর্ট ফাইল"
    )

async def import_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        text="📥 লিঙ্ক ইমপোর্ট করতে JSON ফাইলটি পাঠান",
        reply_markup=None
    )
    
    return SETTINGS

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.document.mime_type != "application/json":
        await update.message.reply_text("⚠️ শুধুমাত্র JSON ফাইল গ্রহণযোগ্য")
        return
    
    file = await update.message.document.get_file()
    await file.download_to_drive("links_import.json")
    
    try:
        with open("links_import.json", "r") as f:
            imported_links = json.load(f)
            
            if not isinstance(imported_links, list):
                raise ValueError("Invalid format")
            
            bot_data.links = imported_links
            bot_data.last_link_number = max([link['number'] for link in imported_links], default=0)
            bot_data.save_data()
            
            await update.message.reply_text(f"✅ {len(imported_links)} টি লিঙ্ক সফলভাবে ইমপোর্ট করা হয়েছে!")
    except Exception as e:
        await update.message.reply_text(f"❌ ফাইল ইমপোর্ট করতে সমস্যা: {str(e)}")
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ইমপোর্ট প্রক্রিয়া বাতিল করা হয়েছে")
    return ConversationHandler.END

async def bot_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("⚠️ Permission Denied!")
        return

    keyboard = [
        [
            InlineKeyboardButton(
                "🟢 বট চালু করুন" if not bot_data.bot_active else "🔴 বট বন্ধ করুন",
                callback_data="toggle_bot"
            )
        ],
        [
            InlineKeyboardButton("📊 রিপোর্ট স্ট্যাটাস", callback_data="report_stats"),
            InlineKeyboardButton("🛠️ রিসেট ডাটা", callback_data="reset_data")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"⚙️ বট সেটিংস\nবর্তমান অবস্থা: {'🟢 চালু' if bot_data.bot_active else '🔴 বন্ধ'}",
        reply_markup=reply_markup
    )

async def handle_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "toggle_bot":
        bot_data.bot_active = not bot_data.bot_active
        bot_data.save_data()
        await query.edit_message_text(
            text=f"⚙️ বট সেটিংস\nবর্তমান অবস্থা: {'🟢 চালু' if bot_data.bot_active else '🔴 বন্ধ'}",
            reply_markup=query.message.reply_markup
        )
    elif query.data == "report_stats":
        stats_text = "📊 রিপোর্ট স্ট্যাটাস:\n\n"
        for user_id, count in bot_data.report_counts.items():
            stats_text += f"👤 User {user_id}: {count} reports\n"
        await query.message.reply_text(stats_text)
    elif query.data == "reset_data":
        bot_data.links = []
        bot_data.last_link_number = 0
        bot_data.report_counts = {}
        bot_data.save_data()
        await query.edit_message_text("✅ সমস্ত ডাটা রিসেট করা হয়েছে")

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("addlink", add_link))
    application.add_handler(CommandHandler("managelinks", manage_links))
    application.add_handler(CommandHandler("settings", bot_settings))

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
    application.add_handler(CallbackQueryHandler(export_links, pattern="^export_links"))
    application.add_handler(CallbackQueryHandler(handle_settings, pattern="^(toggle_bot|report_stats|reset_data)"))

    # Conversation handler for import
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(import_links, pattern="^import_links")],
        states={
            SETTINGS: [MessageHandler(filters.Document.ALL, handle_document)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    application.add_handler(conv_handler)

    application.run_polling()

if __name__ == "__main__":
    main()
