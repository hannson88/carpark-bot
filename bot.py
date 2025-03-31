import os
import logging
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)
from config import BOT_TOKEN
#from sheets import register_user, find_users_by_plate
from sheets import sheet, is_user_registered, register_user, find_users_by_plate  # Import `sheet` and `register_user` from sheets.py

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask and Telegram application
app = Flask(__name__)
application = ApplicationBuilder().token(BOT_TOKEN).build()

# Telegram webhook endpoint
@app.route("/webhook", methods=["POST"])
def webhook():
    import traceback
    import asyncio

    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, application.bot)

        async def handle_update():
            await application.initialize()
            await application.process_update(update)
            await application.shutdown()  # Optional but safe cleanup

        asyncio.run(handle_update())
        return "ok"

    except Exception as e:
        logger.error("🔥 Webhook crashed:")
        logger.error(traceback.format_exc())
        return "error", 500

def register_user(name, phone, model, plate, user_id):
    plate = plate.upper()  # Make sure the plate is stored in uppercase
    # Save user data to the Google Sheet
    sheet.append_row([name, phone, model, plate, user_id])
    logger.info(f"✅ Registered {name} with plate {plate}")


# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome to EV Charging Assistant! \n /rUse /register to register your vehicle.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📋 Commands: \n /register Name, Phone, Car Model, Car Plate \n Then just type car plate(s) to check for owners.")

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        args = ' '.join(context.args)
        name, phone, model, plate = [x.strip() for x in args.split(',')]
        register_user(name, phone, model, plate, update.effective_user.id)
        await update.message.reply_text("✅ Registration successful!")
    except Exception as e:
        logger.error(f"❌ Error in /register: {e}")
        await update.message.reply_text("❌ Usage:\\n/register Name, Phone, Car Model, Car Plate")

async def handle_plate(update: Update, context: ContextTypes.DEFAULT_TYPE):

# Check if the user is registered
    user_id = update.effective_user.id  # Get the user ID from Telegram
    if not is_user_registered(user_id):
        await update.message.reply_text("❌ You need to register first. Use /register to register.")
        return

    # If the user is registered, proceed with the plate lookup



    # Convert plates to uppercase and log the plates being searched
    plates = [x.strip().upper() for x in update.message.text.split(',')]
    logger.info(f"🚗 Searching for plates: {plates}")

    matches = find_users_by_plate(plates)
    
    if not matches:
        await update.message.reply_text("❌ No matching cars found.")
        logger.info(f"No matching plates found for: {plates}")
        return

    for match in matches:
        owner_id = int(match['Telegram ID'])
        await context.bot.send_message(
            chat_id=owner_id,
            text=f"🔌 Your EV with plate *{match['Car Plate']}* is being sought. Someone is looking for a charger.",
            parse_mode="Markdown"
        )
    await update.message.reply_text("✅ Owners notified.")

# Register handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(CommandHandler("register", register))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_plate))
