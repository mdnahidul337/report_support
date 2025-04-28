import os
import json
import logging
from datetime import datetime, timedelta
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Bot,
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
REPORT_GROUP = os.getenv("REPORT_GROUP")
DATA_FILE = "bot_data.json"

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
IMPORT_LINKS = range(1)

class BotDataManager:
    def __init__(self):
        self.data = {
            "links": [],
            "last_link_number": 0,
            "report_counts": {},
            "bot_active": True,
            "user_messages": {}
        }
        self.load_data()

    def load_data(self):
        try:
            with open(DATA_FILE, "r") as f:
                self.data = json.load(f)
                logger.info("Data loaded successfully")
        except (FileNotFoundError, json.JSONDecodeError):
            logger.warning("Data file not found or corrupted, initializing new data")
            self.save_data()

    def save_data(self):
        with open(DATA_FILE, "w") as f:
            json.dump(self.data, f, indent=2)
            logger.info("Data saved successfully")

bot_data = BotDataManager()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("রিপোর্ট করার জন্য কোনো মেসেজে রিপ্লাই করে @admin লিখুন")

async def handle_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not bot_data.data["bot_active"]:
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

        # Check bot status in group
        try:
            bot_member = await context.bot.get_chat_member(update.message.chat.id, context.bot.id)
            if bot_member.status not in ["administrator", "member"]:
                return
        except Exception as e:
            logger.error(f"Bot status check failed: {e}")
            return

        # Update report count
        reporter_id = str(reporter_user.id)
        bot_data.data["report_counts"][reporter_id] = bot_data.data["report_counts"].get(reporter_id, 0) + 1
        bot_data.save_data()

        # Prepare report message
        report_text = f"""
🚨 নতুন রিপোর্ট 🚨
রিপোর্টকারী: {reporter_user.mention_html()} (মোট রিপোর্ট: {bot_data.data["report_counts"][reporter_id]})
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
            except Exception as e:
                logger.error(f"Failed to send report to admin {admin_id}: {e}")

        # Send confirmation
        confirmation = await update.message.reply_to_message.reply_text("✅ রিপোর্টটি এডমিনদের কাছে পাঠানো হয়েছে")
        context.job_queue.run_once(delete_message, 10, data=confirmation.chat_id, name=f"delete_{confirmation.message_id}")

    except Exception as e:
        logger.error(f"Error in handle_report: {e}")

async def delete_message(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.delete_message(
        chat_id=context.job.data["chat_id"],
        message_id=context.job.data["message_id"]
    )

async def handle_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split('_')
    action = data[0]
    reported_user_id = data[1]
    reporter_user_id = data[2]

    # Update message
    new_text = f"{query.message.text}\n\nস্ট্যাটাস: {'গ্রহণ করা হয়েছে' if action == 'accept' else 'প্রত্যাখ্যান করা হয়েছে'}"
    await query.edit_message_text(text=new_text, parse_mode="HTML")

    # Notify reporter
    try:
        await context.bot.send_message(
            chat_id=reporter_user_id,
            text=f"আপনার রিপোর্টটি {'গ্রহণ' if action == 'accept' else 'প্রত্যাখ্যান'} করা হয়েছে"
        )
    except Exception as e:
        logger.error(f"Failed to notify user: {e}")

async def handle_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # ... [পূর্বের কোড অপরিবর্তিত]

        # Create buttons with GROUP ID in callback data
        keyboard = [
            [
                InlineKeyboardButton("✅ Accept", callback_data=f"accept_{reported_user.id}_{reporter_user.id}_{update.message.chat.id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{reported_user.id}_{reporter_user.id}_{update.message.chat.id}")
            ],
            [
                InlineKeyboardButton("📩 View Message", url=message.link)
            ]
        ]

        # ... [বাকি কোড অপরিবর্তিত]

async def handle_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split('_')
    action = data[0]
    reported_user_id = int(data[1])
    reporter_user_id = int(data[2])
    group_id = int(data[3])  # নতুন: গ্রুপ আইডি যোগ করা হয়েছে

    # ... [পূর্বের কোড অপরিবর্তিত]

    # Handle multiple rejections
    if action == "reject":
        reporter_id_str = str(reporter_user_id)
        
        # শুধুমাত্র রিজেক্ট হলে কাউন্ট বাড়ানো
        bot_data.data["report_counts"][reporter_id_str] = bot_data.data["report_counts"].get(reporter_id_str, 0) + 1
        bot_data.save_data()

        # ৩টি রিজেক্ট চেক
        if bot_data.data["report_counts"][reporter_id_str] >= 3:
            try:
                # বটের অ্যাডমিন স্ট্যাটাস চেক
                bot_member = await context.bot.get_chat_member(group_id, context.bot.id)
                if bot_member.status != "administrator":
                    raise Exception("বটটি এই গ্রুপে অ্যাডমিন নয়")

                # মিউট করার সময় সেটিংস
                until_date = datetime.now() + timedelta(minutes=30)
                await context.bot.restrict_chat_member(
                    chat_id=group_id,  # সঠিক গ্রুপ আইডি ব্যবহার
                    user_id=reporter_user_id,
                    permissions=ChatPermissions(
                        can_send_messages=False,
                        can_send_media_messages=False,
                        can_send_other_messages=False,
                        can_add_web_page_previews=False
                    ),
                    until_date=until_date
                )
                
                # নোটিফিকেশন পাঠানো
                await context.bot.send_message(
                    chat_id=group_id,
                    text=f"⚠️ ব্যবহারকারী [{reporter_user_id}](tg://user?id={reporter_user_id}) কে 30 মিনিটের জন্য মিউট করা হয়েছে",
                    parse_mode="Markdown"
                )
                
                # কাউন্টার রিসেট
                bot_data.data["report_counts"][reporter_id_str] = 0
                bot_data.save_data()

            except Exception as e:
                logger.error(f"মিউট ব্যর্থ: {str(e)}")
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=f"❌ ত্রুটি: {str(e)}"
                )

async def handle_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_data.data["bot_active"]:
        await update.message.reply_text("⏳ বটটি বর্তমানে অফলাইনে আছে")
        return

    user_id = str(update.effective_user.id)
    
    # Delete previous messages
    if user_id in bot_data.data["user_messages"]:
        for msg_id in bot_data.data["user_messages"][user_id]:
            try:
                await context.bot.delete_message(
                    chat_id=update.message.chat_id,
                    message_id=msg_id
                )
            except Exception as e:
                logger.error(f"Message deletion failed: {e}")
        bot_data.data["user_messages"][user_id] = []

    # Prepare new message
    links_text = "📥 ডাউনলোড লিঙ্কসমূহ:\n\n"
    keyboard = []
    for link in bot_data.data["links"]:
        links_text += f"{link['number']}.🔗 [ডাউনলোড লিংক]({link['url']}) [{link['date']}]\n"
        keyboard.append([InlineKeyboardButton(
            text=f"লিংক {link['number']}", 
            url=link['url']
        )])

    reply_markup = InlineKeyboardMarkup(keyboard)
    sent_message = await update.message.reply_text(
        text=links_text,
        reply_markup=reply_markup,
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

    # Store message ID
    if user_id not in bot_data.data["user_messages"]:
        bot_data.data["user_messages"][user_id] = []
    bot_data.data["user_messages"][user_id].append(sent_message.message_id)
    bot_data.save_data()

async def manage_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ অনুমতি প্রত্যাখ্যান করা হয়েছে!")
        return

    keyboard = [
        [InlineKeyboardButton("📤 এক্সপোর্ট লিংক", callback_data="export_links")],
        [InlineKeyboardButton("📥 ইম্পোর্ট লিংক", callback_data="import_links")],
        [InlineKeyboardButton("🗑️ সব লিংক ডিলিট করুন", callback_data="delete_all_links")]
    ]
    
    await update.message.reply_text(
        "🔗 লিংক ম্যানেজমেন্ট:", 
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    with open("links_export.json", "w") as f:
        json.dump(bot_data.data["links"], f)
    
    await context.bot.send_document(
        chat_id=query.message.chat_id,
        document=open("links_export.json", "rb"),
        caption="📤 লিংক এক্সপোর্ট ফাইল"
    )

async def handle_import(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📥 একটি JSON ফাইল পাঠান (ফাইল ফরম্যাট উদাহরণ দেখতে /sample টাইপ করুন)")
    return IMPORT_LINKS

async def handle_uploaded_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.document:
        await update.message.reply_text("❌ শুধুমাত্র JSON ফাইল গ্রহণযোগ্য")
        return ConversationHandler.END

    file = await update.message.document.get_file()
    await file.download_to_drive("temp_import.json")
    
    try:
        with open("temp_import.json", "r") as f:
            imported_data = json.load(f)
            
            if not isinstance(imported_data, list):
                raise ValueError("Invalid format")
            
            bot_data.data["links"] = imported_data
            bot_data.data["last_link_number"] = max([link["number"] for link in imported_data], default=0)
            bot_data.save_data()
            
            await update.message.reply_text(f"✅ {len(imported_data)} টি লিংক সফলভাবে ইম্পোর্ট করা হয়েছে!")
    except Exception as e:
        await update.message.reply_text(f"❌ ইম্পোর্ট ব্যর্থ: {str(e)}")
    
    return ConversationHandler.END

async def toggle_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ অনুমতি প্রত্যাখ্যান করা হয়েছে!")
        return

    bot_data.data["bot_active"] = not bot_data.data["bot_active"]
    bot_data.save_data()
    
    status = "চালু" if bot_data.data["bot_active"] else "বন্ধ"
    await update.message.reply_text(f"🔌 বট স্ট্যাটাস: {status}")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ অপারেশন বাতিল করা হয়েছে")
    return ConversationHandler.END

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("managelinks", manage_links))
    application.add_handler(CommandHandler("toggle", toggle_bot))

    # Message handlers
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Entity(MessageEntity.MENTION),
        handle_report
    ))
    application.add_handler(MessageHandler(
        filters.Regex(r"(?i)download|ডাউনলোড"),
        handle_download
    ))

    # Callback handlers
    application.add_handler(CallbackQueryHandler(handle_button_click, pattern=r"^(accept|reject)_"))
    application.add_handler(CallbackQueryHandler(handle_export, pattern="^export_links"))
    
    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_import, pattern="^import_links")],
        states={
            IMPORT_LINKS: [MessageHandler(filters.Document.FileExtension("json"), handle_uploaded_file)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    application.add_handler(conv_handler)

    application.run_polling()

if __name__ == "__main__":
    main()
