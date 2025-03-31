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
NAME, PHONE, MODEL, PLATE = range(4)

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
            "/mystatus – View your registered vehicles.\n"
            "Just type a car plate to notify the owner.\n"
            "Type /cancel anytime to stop registration."
        )
        logger.info("Sent /help response successfully.")
    except Exception as e:
        logger.error(f"Error sending /help message: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Received /register command")
    await update.message.reply_text("Welcome! Let's get you registered.\nWhat's your name?\n(You can type /cancel to stop at any time.)")
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    await update.message.reply_text("Got it! What's your phone number?\n(You can type /cancel to stop at any time.)")
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['phone'] = update.message.text
    await update.message.reply_text("Great! What's your car model?\n(You can type /cancel to stop at any time.)")
    return MODEL

async def get_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['model'] = update.message.text
    await update.message.reply_text("Nice! What's your car plate?\n(You can type /cancel to stop at any time.)")
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
    await update.message.reply_text("❌ Registration cancelled. You can start again anytime by typing /register.")
    return ConversationHandler.END

async def handle_plate_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.upper().strip()
    plates = [plate.strip().upper() for plate in text.split(',')]
    logger.info(f"🚗 Looking up plate(s): {', '.join(plates)}")

    matches = find_users_by_plate(plates)
    if not matches:
        await update.message.reply_text("❌ No registered owner found for that plate.")
        return

    for match in matches:
        user_id = match['Telegram ID']
        name = match['Name']
        plate = match['Car Plate']

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"👋 Someone is looking for the owner of plate {plate}."
            )
        except Exception as e:
            logger.error(f"❌ Failed to notify {user_id}: {e}")

    await update.message.reply_text("✅ Owner has been contacted.")

async def my_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    records = find_user_by_telegram_id(user_id)

    if not records:
        await update.message.reply_text("ℹ️ You haven't registered any vehicles yet. Use /register to get started.")
        return

    status_msg = "🚗 Your registered vehicles:\n"
    for r in records:
        status_msg += (
            f"- Name: {r['Name']}\n"
            f"  Phone: {r['Phone Number']}\n"
            f"  Model: {r['Vehicle Type']}\n"
            f"  Plate: {r['Car Plate']}\n\n"
        )
    await update.message.reply_text(status_msg)

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
    application.add_handler(CommandHandler('mystatus', my_status))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_plate_lookup))

    application.run_webhook(
        listen="0.0.0.0",
        port=10000,
        url_path="webhook",
        webhook_url="https://carpark-bot-m825.onrender.com/webhook"
    )

if __name__ == '__main__':
    main()