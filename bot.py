import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes,
    ConversationHandler, filters
)
from config import BOT_TOKEN
from sheets import register_user, find_users_by_plate, is_user_registered, find_user_by_telegram_id

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define states
NAME, PHONE, MODEL, PLATE, CONFIRM_REGISTER = range(5)

# Handler functions
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
            "/cancel – Cancel the registration process.\n"
            "/my_status – Show your registered vehicle(s).\n"
            "Just type car plate(s) to check for owners."
        )
        logger.info("Sent /help response successfully.")
    except Exception as e:
        logger.error(f"Error sending /help message: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Received /register command")
    user_id = update.effective_user.id
    existing_vehicles = find_user_by_telegram_id(user_id)

    if existing_vehicles:
        response = "🚗 You already have the following registered vehicle(s):\n"
        for vehicle in existing_vehicles:
            response += (
                f"- {vehicle['Car Plate']} ({vehicle['Vehicle Type']})\n"
            )
        response += "\nWould you like to register another vehicle? (yes/no)"
        await update.message.reply_text(response)
        return CONFIRM_REGISTER
    else:
        await update.message.reply_text("Welcome! Let's get you registered. What's your name?")
        return NAME

async def confirm_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if text in ['y', 'yes']:
        await update.message.reply_text("Great! What's your name?")
        return NAME
    elif text in ['n', 'no']:
        await update.message.reply_text("👍 Registration cancelled. You can register later using /register.")
        return ConversationHandler.END
    else:
        await update.message.reply_text("❓ Please reply with 'yes' or 'no'.")
        return CONFIRM_REGISTER

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

async def handle_plate_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip().upper().split()
    logger.info(f"🚗 Looking up plate(s): {' '.join(query)}")
    matches = find_users_by_plate(query)

    if matches:
        for match in matches:
            try:
                owner_id = match['Telegram ID']
                await context.bot.send_message(
                    chat_id=owner_id,
                    text=(
                        f"👀 Someone is enquiring about your vehicle {match['Car Plate']}!\n"
                        f"Please be aware and take necessary action."
                    )
                )
            except Exception as e:
                logger.error(f"Error sending message to car owner: {e}")

        await update.message.reply_text("✅ The car owner has been contacted.")
    else:
        await update.message.reply_text("❌ No matching car plate found or the owner is not registered.")

async def my_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    vehicles = find_user_by_telegram_id(user_id)
    if vehicles:
        message = "🚘 Your registered vehicle(s):\n"
        for v in vehicles:
            message += f"- {v['Car Plate']} ({v['Vehicle Type']})\n"
        await update.message.reply_text(message)
    else:
        await update.message.reply_text("❗ You have not registered any vehicles yet. Use /register to start.")

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('register', start)],
        states={
            CONFIRM_REGISTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_register)],
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
    application.add_handler(CommandHandler('cancel', cancel))
    application.add_handler(CommandHandler('my_status', my_status))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_plate_lookup))

    application.run_webhook(
        listen="0.0.0.0",
        port=10000,
        url_path="webhook",
        webhook_url="https://carpark-bot-m825.onrender.com/webhook"
    )

if __name__ == '__main__':
    main()
