import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes,
    ConversationHandler, filters
)
from config import BOT_TOKEN
from sheets import register_user  # Ensure this is imported correctly
from telegram.error import BadRequest

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define states for the conversation
NAME, PHONE, MODEL, PLATE = range(4)

# Initialize the application
application = ApplicationBuilder().token(BOT_TOKEN).build()

# Conversation flow handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Received /register command")
    await update.message.reply_text("Welcome! Let's get you registered. What's your name?")
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text  # Store name
    await update.message.reply_text("Got it! What's your phone number?")
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['phone'] = update.message.text  # Store phone number
    await update.message.reply_text("Great! What's your car model?")
    return MODEL

async def get_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['model'] = update.message.text  # Store car model
    await update.message.reply_text("Nice! What's your car plate?")
    return PLATE

async def get_plate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['plate'] = update.message.text.upper()  # Store car plate in uppercase
    name = context.user_data['name']
    phone = context.user_data['phone']
    model = context.user_data['model']
    plate = context.user_data['plate']

    # Save user data to Google Sheets
    try:
        register_user(name, phone, model, plate, update.effective_user.id)
        await update.message.reply_text(f"🎉 You're now registered! Name: {name}, Phone: {phone}, Model: {model}, Plate: {plate}")
    except Exception as e:
        await update.message.reply_text(f"❌ There was an error registering you. Please try again later.")
        logger.error(f"Error during registration: {e}")

    return ConversationHandler.END  # End the conversation

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Registration cancelled. You can start again by typing /register.")
    return ConversationHandler.END

# Command handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Received /start command")
    await update.message.reply_text("👋 Welcome to EV Charging Assistant! Use /register to register your vehicle.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Received /help command")
    try:
        await update.message.reply_text("📋 Commands: \n/register Name, Phone, Car Model, Car Plate\nThen just type car plate(s) to check for owners.")
    except BadRequest as e:
        logger.error(f"Error sending /help message: {e}")

# Main function to set up handlers and start the bot
def main():
    # Create a ConversationHandler to manage the registration steps
    conversation_handler = ConversationHandler(
        entry_points=[CommandHandler('register', start)],  # Start with /register
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_model)],
            PLATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_plate)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],  # Allow cancellation at any point
    )

    # Add the conversation handler and other command handlers to the application
    application.add_handler(conversation_handler)
    application.add_handler(CommandHandler('start', start_command))  # /start command
    application.add_handler(CommandHandler('help', help_command))  # /help command

    # Run the bot with webhook
    application.run_webhook(listen="0.0.0.0", port=10000, url_path="webhook", webhook_url="https://carpark-bot-m825.onrender.com/webhook")

if __name__ == '__main__':
    main()
