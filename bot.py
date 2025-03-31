import logging
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)
from config import BOT_TOKEN
from sheets import register_user

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define conversation states
NAME, PHONE, MODEL, PLATE = range(4)

# Flask app for webhook
app = Flask(__name__)

# Telegram bot application
application = ApplicationBuilder().token(BOT_TOKEN).build()

# --- Conversation Handlers ---

def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Received /register command")
    update.message.reply_text("Welcome! Let's get you registered. What's your name?")
    return NAME

def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    update.message.reply_text("Got it! What's your phone number?")
    return PHONE

def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['phone'] = update.message.text
    update.message.reply_text("Great! What's your car model?")
    return MODEL

def get_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['model'] = update.message.text
    update.message.reply_text("Nice! What's your car plate?")
    return PLATE

def get_plate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['plate'] = update.message.text.upper()
        name = context.user_data['name']
        phone = context.user_data['phone']
        model = context.user_data['model']
        plate = context.user_data['plate']
        telegram_id = update.effective_user.id

        register_user(name, phone, model, plate, telegram_id)
        update.message.reply_text(f"🎉 You're now registered!\nName: {name}\nPhone: {phone}\nModel: {model}\nPlate: {plate}")
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error during registration: {e}")
        update.message.reply_text("❌ Something went wrong during registration. Please try again later.")
        return ConversationHandler.END

def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update.message.reply_text("Registration cancelled. You can start again with /register.")
    return ConversationHandler.END

# --- Command Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Received /start command")
    await update.message.reply_text("👋 Welcome to EV Charging Assistant! Use /register to register your vehicle.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Received /help command")
    try:
        await update.message.reply_text(
            "📋 Available Commands:\n"
            "/start - Start the bot\n"
            "/register - Begin vehicle registration\n"
            "/help - List available commands"
        )
        logger.info("Sent /help response successfully.")
    except Exception as e:
        logger.error(f"Error sending /help message: {e}")

# --- Webhook Endpoint ---

@app.route("/webhook", methods=["POST"])
def webhook():
    import asyncio
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, application.bot)
        logger.info(f"Received update: {data}")

        async def process():
            await application.process_update(update)

        asyncio.run(process())
        return "ok"
    except Exception as e:
        logger.error("🔥 Webhook crashed:")
        logger.error(e)
        return "error", 500

# --- Register Handlers and Start Application ---

def main():
    conversation_handler = ConversationHandler(
        entry_points=[CommandHandler('register', start_registration)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_model)],
            PLATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_plate)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conversation_handler)
    application.add_handler(CommandHandler('start', start_command))
    application.add_handler(CommandHandler('help', help_command))

    application.run_webhook(
        listen="0.0.0.0",
        port=10000,
        url_path="webhook",
        webhook_url="https://carpark-bot-m825.onrender.com/webhook"
    )

if __name__ == '__main__':
    main()
