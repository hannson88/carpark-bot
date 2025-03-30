import os
import logging
from flask import Flask, request
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from config import BOT_TOKEN
from sheets import register_user, find_users_by_plate

# Create app and bot first
application = ApplicationBuilder().token(BOT_TOKEN).build()
app = Flask(__name__)
pending_requests = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.post("/webhook")
async def webhook():
    try:
        data = request.get_json(force=True)
        logger.info(f"📥 Raw Telegram Update: {data}")
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
        return "ok"
    except Exception as e:
        import traceback
        logger.error("🔥 Webhook processing failed:")
        logger.error(traceback.format_exc())
        return "error", 500

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚗 Welcome to the Car Park Bot!\nUse /register to register your car.")

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        args = ' '.join(context.args)
        name, phone, model, plate = [x.strip() for x in args.split(',')]
        register_user(name, phone, model, plate, update.effective_user.id)
        await update.message.reply_text("✅ Registration successful!")
    except Exception as e:
        logger.error(f"❌ Error in /register: {e}")
        await update.message.reply_text("❌ Usage:\n/register Name, Phone, Car Model, Car Plate")

async def handle_plate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plates = [x.strip().upper() for x in update.message.text.split(',')]
    matches = find_users_by_plate(plates)
    if not matches:
        await update.message.reply_text("❌ No matching cars found.")
        return
    for match in matches:
        owner_id = int(match['Telegram ID'])
        await context.bot.send_message(
            chat_id=owner_id,
            text=f"🚙 Your car **{match['Car Plate']}** is parked. Someone is looking for a lot.",
            parse_mode="Markdown"
        )
    await update.message.reply_text("✅ Owners notified.")

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("register", register))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_plate))