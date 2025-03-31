
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes,
    ConversationHandler, filters
)
from config import BOT_TOKEN
from sheets import (
    register_user,
    find_users_by_plate,
    is_user_registered,
    find_user_by_telegram_id,
    find_all_vehicles_by_user
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define conversation states
NAME, PHONE, MODEL, PLATE = range(4)

# Handler functions
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Received /start command")
    await update.message.reply_text("👋 Welcome to EV Charging Assistant! Use /register to register your vehicle.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Received /help command")
    await update.message.reply_text(
        "📋 Commands:
"
        "/register – Register your vehicle step-by-step.
"
        "/cancel – Cancel an ongoing registration.
"
        "/my_status – View your registered vehicle(s).
"
        "To look up a car plate, just type the car plate (e.g., SFF1234X)."
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Received /register command")
    user_id = update.effective_user.id

    if is_user_registered(user_id):
        logger.info("User already registered. Proceeding to register second vehicle.")
        await update.message.reply_text("Registering another vehicle.
What's your car model?")
        return MODEL
    else:
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
    plate = update.message.text.upper()
    user_id = update.effective_user.id

    name = context.user_data.get('name')
    phone = context.user_data.get('phone')
    model = context.user_data.get('model')
    
    if not name or not phone:
        user_info = find_user_by_telegram_id(user_id)
        if user_info:
            name = user_info.get("Name")
            phone = user_info.get("Phone Number")

    if not name or not phone:
        await update.message.reply_text("❌ Unable to find your profile for auto-fill. Please start again with /register.")
        return ConversationHandler.END

    try:
        register_user(name, phone, model, plate, user_id)
        await update.message.reply_text(
            f"🎉 You're now registered!
"
            f"Name: {name}
Phone: {phone}
Model: {model}
Plate: {plate}"
        )
        logger.info(f"✅ Registered {name} with plate {plate}")
    except Exception as e:
        logger.error(f"Error during registration: {e}")
        await update.message.reply_text("❌ Error registering you. Please try again later.")

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Registration cancelled. You can start again with /register.")
    return ConversationHandler.END

async def my_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    vehicles = find_all_vehicles_by_user(user_id)
    if not vehicles:
        await update.message.reply_text("❗ You are not registered yet. Use /register to begin.")
    else:
        reply = "🚗 Your registered vehicles:
"
        for i, v in enumerate(vehicles, 1):
            reply += (
                f"{i}. Model: {v.get('Vehicle Type')}, Plate: {v.get('Car Plate')}, "
                f"Name: {v.get('Name')}, Phone: {v.get('Phone Number')}
"
            )
        await update.message.reply_text(reply)

async def handle_plate_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plate = update.message.text.strip().upper()
    logger.info(f"🚗 Looking up plate(s): {plate}")
    matches = find_users_by_plate([plate])

    if not matches:
        await update.message.reply_text("❌ No owner found or the car plate is not registered.")
        return

    for match in matches:
        owner_id = match.get("Telegram ID")
        if owner_id:
            try:
                await context.bot.send_message(
                    chat_id=owner_id,
                    text=f"🔔 Someone is enquiring about your vehicle with plate {plate}."
                )
            except Exception as e:
                logger.error(f"❌ Failed to notify owner: {e}")
    await update.message.reply_text("✅ Owner has been contacted.")

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
