from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# যেই ইউজারকে প্রাইভেট মেসেজ পাঠাবো (অ্যাডমিনের ইউজার আইডি)
ADMIN_USER_ID = [6017525126, 6347226702] # এখানে তোমার অ্যাডমিনের টেলিগ্রাম আইডি বসাও

# যখন কেউ @admin মেনশন করে
async def report_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    
    if '@admin' in update.message.text.lower():
        user = update.message.from_user
        chat = update.message.chat
        message_link = f"https://t.me/c/{str(chat.id)[4:]}/{update.message.message_id}"

        # মেসেজ সাজানো
        report_message = (
            f"🚨 <b>নতুন রিপোর্ট!</b>\n\n"
            f"<b>প্রেরক:</b> {user.mention_html()}\n"
            f"<b>গ্রুপ:</b> {chat.title}\n\n"
            f"<b>বার্তা:</b>\n{update.message.text}\n"
        )

        # ইনলাইন বাটন বানানো (View বোতাম)
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔎 View", url=message_link)]]
        )

        try:
            # অ্যাডমিনের প্রাইভেট চ্যাটে মেসেজ পাঠানো
            await context.bot.send_message(
                chat_id=ADMIN_USER_ID,
                text=report_message,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            print(f"Error sending report: {e}")

# অ্যাপ রেজিস্টার করা
app = ApplicationBuilder().token("7643025446:AAHPQgytUtqHz_wB-9y-OziM8aucimPvThw").build()

# শুধুমাত্র টেক্সট মেসেজ হ্যান্ডেল করা
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), report_to_admin))

# বট চালু
app.run_polling()
