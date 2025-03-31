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
    find_all_vehicles_by_user
)

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
            "/register – Register your vehicle step-by-step.\n"
            "/cancel – Cancel ongoing registration.\n"
            "/my_status – View your registered vehicles.\n"
            "Just type car plate(s) to check for owners."
        )
        logger.info("Sent /help response successfully.")
    except Exception as e:
        logger.error(f"Error sending /help message: {e}")

async def my_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    records = find_all_vehicles_by_user(user_id)
    if not records:
        await update.message.reply_text("You are not registered yet. Use /register to register your vehicle.")
        return

    response = "\U0001F4C4 Your Registered Vehicles:\n"
    for r in records:
        response += f"- {r['Vehicle Type']} ({r['Car Plate']})\n"
    await update.message.reply_text(response)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Received /register command")
    if is_user_registered(update.effective_user.id):
        context.user_data['repeat_user'] = True
        await update.message.reply_text("Welcome back! Let's add another car. What's the car model?")
        return MODEL
    else:
        context.user_data['repeat_user'] = False
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
    plate = context.user_data['plate']
    user_id = update.effective_user.id

    if context.user_data.get('repeat_user'):
        existing = find_all_vehicles_by_user(user_id)[0]
        name = existing['Name']
        phone = existing['Phone Number']
    else:
        name = context.user_data['name']
        phone = context.user_data['phone']

    model = context.user_data['model']

    try:
        register_user(name, phone, model, plate, user_id)
        await update.message.reply_text(
            f"\U0001F389 You're now registered!\n"
            f"Name: {name}\nPhone: {phone}\nModel: {model}\nPlate: {plate}"
        )
    except Exception as e:
        await update.message.reply_text("\u274C Error registering you. Please try again later.")
        logger.error(f"Error during registration: {e}")

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("\u274C Registration cancelled. You can start again with /register.")
    return ConversationHandler.END

async def handle_plate_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    plate_input = update.message.text.upper()
    logger.info(f"\U0001F697 Looking up plate(s): {plate_input}")

    matches = find_users_by_plate([plate_input])
    if not matches:
        await update.message.reply_text("No owner found for this car plate or the owner is not registered.")
        return

    for match in matches:
        target_id = match.get("Telegram ID")
        if target_id:
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=f"\U0001F514 Someone is enquiring about your car plate {match['Car Plate']}."
                )
            except Exception as e:
                logger.error(f"Failed to message {target_id}: {e}")

    await update.message.reply_text("\u2709\ufe0f Owner has been contacted.")

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
