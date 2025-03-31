import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes,
    ConversationHandler, filters
)
from config import BOT_TOKEN
from sheets import register_user, find_users_by_plate, is_user_registered

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define states
NAME, PHONE, MODEL, PLATE = range(4)

# Handler functions
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Received /start command")
    await update.message.reply_text("\U0001F44B Welcome to EV Charging Assistant! Use /register to register your vehicle.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Received /help command")
    try:
        logger.info("Preparing to send /help response")
        await update.message.reply_text(
            "\U0001F4CB Commands:\n"
            "/register – Start the registration process step-by-step.\n"
            "Just type car plate(s) to check for owners."
        )
        logger.info("Sent /help response successfully.")
    except Exception as e:
        logger.error(f"Error sending /help message: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Received /register command")
    await update.message.reply_text("Welcome! Let's get you registered. What's your name?")
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    await update.message.reply_text("Got it! What's your phone number?")
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['phone'] = update.message.text
    await update.message.reply_text("Great! What's your car model?")
    return MODEL

async def get_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['model'] = update.message.text
    await update.message.reply_text("Nice! What's your car plate?")
    return PLATE

async def get_plate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['plate'] = update.message.text.upper()
    name = context.user_data['name']
    phone = context.user_data['phone']
    model = context.user_data['model']
    plate = context.user_data['plate']

    try:
        register_user(name, phone, model, plate, update.effective_user.id)
        await update.message.reply_text(
            f"\U0001F389 You're now registered!\n"
            f"Name: {name}\nPhone: {phone}\nModel: {model}\nPlate: {plate}"
        )
    except Exception as e:
        await update.message.reply_text("\u274C Error registering you. Please try again later.")
        logger.error(f"Error during registration: {e}")

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Registration cancelled. You can start again with /register.")
    return ConversationHandler.END

async def handle_plate_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.upper()
    plates = [plate.strip().upper() for plate in text.split(',') if plate.strip()]
    logger.info(f"\U0001F697 Looking up plate(s): {', '.join(plates)}")

    if not is_user_registered(update.effective_user.id):
        await update.message.reply_text("\u274C You must register first using /register to use this feature.")
        return

    matches = find_users_by_plate(plates)
    if not matches:
        await update.message.reply_text("\u26A0\uFE0F No matching car plates found.")
        return

    reply_lines = []
    for match in matches:
        reply_lines.append(
            f"\U0001F4DD Contact Info:\n"
            f"Name: {match['Name']}\n"
            f"Phone: {match['Phone Number']}\n"
            f"Model: {match['Vehicle Type']}\n"
            f"Plate: {match['Car Plate']}"
        )
    await update.message.reply_text("\n\n".join(reply_lines))

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('register', start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_model)],
            PLATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_plate)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('start', start_command))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_plate_lookup))

    application.run_webhook(
        listen="0.0.0.0",
        port=10000,
        url_path="webhook",
        webhook_url="https://carpark-bot-m825.onrender.com/webhook"
    )

if __name__ == '__main__':
    main()