import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes,
    ConversationHandler, filters
)
from config import BOT_TOKEN
from sheets import (
    register_user, find_users_by_plate,
    is_user_registered, find_all_vehicles_by_user
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define conversation states
NAME, PHONE, MODEL, PLATE, CONFIRM_CONTINUE = range(5)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Received /start command")
    await update.message.reply_text("👋 Welcome to EV Charging Assistant! Use /register to register your vehicle.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Received /help command")
    try:
        logger.info("Preparing to send /help response")
        await update.message.reply_text(
            "📋 Commands:\n"
            "/register – Start the registration process step-by-step.\n"
            "/mystatus – Check your registration status.\n"
            "/cancel – Cancel current operation.\n"
            "Just type car plate(s) to check for owners."
        )
        logger.info("Sent /help response successfully.")
    except Exception as e:
        logger.error(f"Error sending /help message: {e}")

async def my_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"Checking status for Telegram ID: {user_id}")
    vehicles = find_all_vehicles_by_user(user_id)
    if not vehicles:
        await update.message.reply_text("❌ You're not registered yet. Use /register to start.")
    else:
        status = "🚗 Your Registered Vehicles:\n"
        for v in vehicles:
            status += f"• {v['Vehicle Type']} - {v['Car Plate']}\n"
        await update.message.reply_text(status)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info("Received /register command")

    vehicles = find_all_vehicles_by_user(user_id)
    if vehicles:
        logger.info("User already registered. Asking for confirmation to add another.")
        context.user_data['existing_user'] = True
        context.user_data['existing_name'] = vehicles[0]['Name']
        context.user_data['existing_phone'] = vehicles[0]['Phone Number']
        await update.message.reply_text(
            "You're already registered. Would you like to register another vehicle? (yes/no)"
        )
        return CONFIRM_CONTINUE
    else:
        await update.message.reply_text("Welcome! Let's get you registered. What's your name?")
        return NAME

async def confirm_continue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    response = update.message.text.lower()
    if response == "yes":
        await update.message.reply_text("Great! What's your car model?")
        return MODEL
    elif response == "no":
        await update.message.reply_text("👍 No worries! You can type /register again later.")
        return ConversationHandler.END
    else:
        await update.message.reply_text("Please reply with 'yes' or 'no'.")
        return CONFIRM_CONTINUE

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
    plate = update.message.text.upper()
    context.user_data['plate'] = plate

    if context.user_data.get('existing_user'):
        name = context.user_data['existing_name']
        phone = context.user_data['existing_phone']
    else:
        name = context.user_data['name']
        phone = context.user_data['phone']

    model = context.user_data['model']
    telegram_id = update.effective_user.id

    try:
        register_user(name, phone, model, plate, telegram_id)
        await update.message.reply_text(
            f"🎉 You're now registered!\n"
            f"Name: {name}\nPhone: {phone}\nModel: {model}\nPlate: {plate}"
        )
    except Exception as e:
        await update.message.reply_text("❌ Error registering you. Please try again later.")
        logger.error(f"Error during registration: {e}")

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Registration cancelled. You can start again with /register.")
    return ConversationHandler.END

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('register', start)],
        states={
            CONFIRM_CONTINUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_continue)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_model)],
            PLATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_plate)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('start', start_command))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('cancel', cancel))
    application.add_handler(CommandHandler('mystatus', my_status))

    application.run_webhook(
        listen="0.0.0.0",
        port=10000,
        url_path="webhook",
        webhook_url="https://carpark-bot-m825.onrender.com/webhook"
    )

if __name__ == '__main__':
    main()