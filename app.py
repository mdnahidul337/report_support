from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler

# লগিং চালু
logging.basicConfig(level=logging.INFO)

# গ্রুপ আইডি এবং অ্যাডমিন ইউজার আইডি লিস্ট
GROUP_ID =   # তোমার গ্রুপের ID
# এখানে তোমার অ্যাডমিনদের Telegram user ID বসাও
ADMIN_IDS = [6017525126, 6347226702]  # এখানে তোমার অ্যাডমিনদের টেলিগ্রাম ID দিবে

# @admin tag দেখলে
async def report_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.lower()

    # যদি @admin থাকে মেসেজে
    if '@admin' in text:
        user = update.message.from_user
        chat = update.message.chat

        # ইউজার গ্রুপে আছে কি না চেক করা
        try:
            member = await context.bot.get_chat_member(GROUP_ID, user.id)
            if member.status not in ['member', 'administrator', 'creator']:
                await update.message.reply_text("⚠️ রিপোর্ট করতে হলে আপনাকে গ্রুপে যুক্ত থাকতে হবে।")
                return
        except Exception as e:
            await update.message.reply_text("⚠️ রিপোর্ট করতে হলে আপনাকে গ্রুপে যুক্ত থাকতে হবে।")
            return

        # View Button তৈরি করা
        view_button = InlineKeyboardMarkup([
            [InlineKeyboardButton("👁️ View Message", url=f"https://t.me/c/{str(GROUP_ID)[4:]}/{update.message.message_id}")]
        ])

        # রিপোর্ট মেসেজ তৈরি
        report_message = (
            f"🚨 *নতুন রিপোর্ট!* 🚨\n\n"
            f"👤 রিপোর্টকারী: [{user.full_name}](tg://user?id={user.id})\n"
            f"💬 বার্তা:\n{update.message.text}\n\n"
            f"📍 [গ্রুপে মেসেজ দেখুন](https://t.me/c/{str(GROUP_ID)[4:]}/{update.message.message_id})"
        )

        # প্রাইভেট চ্যাটে রিপোর্ট পাঠানো
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=report_message,
            parse_mode="Markdown",
            reply_markup=view_button
        )

        # ইউজারকে উত্তর
        await update.message.reply_text("✅ আপনার রিপোর্ট সফলভাবে অ্যাডমিনদের কাছে পাঠানো হয়েছে। ধন্যবাদ!", quote=True)

# /start কমান্ড
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 স্বাগতম! @admin ব্যবহার করে সমস্যা রিপোর্ট করুন।")

# মেইন অ্যাপ
app = ApplicationBuilder().token('YOUR_BOT_TOKEN').build()

# হ্যান্ডলার যোগ করা
app.add_handler(CommandHandler('start', start_command))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), report_to_admin))

app.run_polling()
