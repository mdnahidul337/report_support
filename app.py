from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# এখানে তোমার অ্যাডমিনদের Telegram user ID বসাও
ADMIN_IDS = [6017525126, 6347226702]  # এখানে তোমার অ্যাডমিনদের টেলিগ্রাম ID দিবে

# রিপোর্ট ফাংশন
async def report_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    if '@admin' in message.text.lower():
        reporter = message.from_user.mention_html()
        chat = message.chat.title if message.chat.title else "Private Chat"
        text = message.text_html

        # রিপোর্ট ম্যাসেজ বানানো
        report_message = (
            f"🚨 <b>নতুন রিপোর্ট!</b>\n\n"
            f"👤 রিপোর্ট করেছেন: {reporter}\n"
            f"👥 গ্রুপ: {chat}\n\n"
            f"📝 বার্তা:\n{text}"
        )

        # সব অ্যাডমিনদের রিপোর্ট পাঠানো
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=report_message,
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"Couldn't send to admin {admin_id}: {e}")

        # রিপোর্টারের রিপ্লাই
        await message.reply_text("✅ রিপোর্টটি অ্যাডমিনদের কাছে পাঠানো হয়েছে। ধন্যবাদ।")

app = ApplicationBuilder().token('7643025446:AAHPQgytUtqHz_wB-9y-OziM8aucimPvThw').build()

# টেক্সট মেসেজে যদি @admin থাকে, তখন হ্যান্ডলার চালাবে
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), report_to_admin))

app.run_polling()
