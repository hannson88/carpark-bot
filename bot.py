import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
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

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# States
NAME, PHONE, MODEL, PLATE = range(4)
UPDATE_SELECTION, UPDATE_FIELD, NEW_VALUE = range(4, 7)
REPLY_MESSAGE = 10

# Conversation tracking
conversations = {}

# Start command
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to EV Charging Assistant!\n"
        "Use /register to register your vehicle.\n"
        "Use /my_status to view your vehicles.\n"
        "Use /update to update or delete a vehicle.\n"
        "Use /cancel to exit at any time.\n"
    )

# Help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 Commands:\n"
        "/register – Register your vehicle step-by-step.\n"
        "/my_status – View your registered vehicles.\n"
        "/update – Modify or delete your vehicle details.\n"
        "/reply – Reply to a requester (if any).\n"
        "/end – End a current conversation.\n"
        "/cancel – Cancel the current action.\n"
        "Just type a car plate to check for registered owners."
    )

# Cancel command
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Registration cancelled. You can start again with /register.")
    return ConversationHandler.END

# Registration flow
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_user_registered(update.effective_user.id):
        context.user_data['repeat_user'] = True
        await update.message.reply_text("Welcome back! Let us add another car. What is the car model?")
        return MODEL
    else:
        context.user_data['repeat_user'] = False
        await update.message.reply_text("Welcome! Let us get you registered. What is your name?")
        return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    await update.message.reply_text("What is your phone number?")
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['phone'] = update.message.text
    await update.message.reply_text("What is your car model?")
    return MODEL

async def get_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['model'] = update.message.text
    await update.message.reply_text("What is your car plate?")
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
            f"🎉 You are now registered!\n"
            f"Name: {name}\n"
            f"Phone: {phone}\n"
            f"Model: {model}\n"
            f"Plate: {plate}"
        )
    except Exception as e:
        await update.message.reply_text("❌ Error registering you. Please try again later.")
        logger.error(f"Error during registration: {e}")

    return ConversationHandler.END

# Status
async def my_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vehicles = find_all_vehicles_by_user(update.effective_user.id)
    if not vehicles:
        await update.message.reply_text("No vehicles registered. Use /register to add one.")
        return
    msg = "🚗 Your registered vehicles:\n"
    for v in vehicles:
        msg += f"- {v['Car Plate']} ({v['Vehicle Type']})\n"
    await update.message.reply_text(msg)

# Plate lookup
async def handle_plate_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plate = update.message.text.strip().upper()
    if not plate:
        return

    logger.info(f"🔍 Plate lookup: {plate}")
    matches = find_users_by_plate([plate])
    if not matches:
        await update.message.reply_text("❌ No matching car plate found or owner not registered.")
        return

    requester_id = update.effective_user.id
    for match in matches:
        owner_id = int(match["Telegram ID"])
        conversations[owner_id] = requester_id
        conversations[requester_id] = owner_id

        await context.bot.send_message(
            chat_id=owner_id,
            text=(
                f"🔔 Someone is enquiring about your car plate {match['Car Plate']}.\n"
                f"Use /reply to respond. You can end the chat anytime with /end."
            )
        )

    await update.message.reply_text("✅ Owner has been contacted.")

# Reply feature
async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender_id = update.effective_user.id
    if sender_id not in conversations:
        await update.message.reply_text("You have no active conversations.")
        return
    await update.message.reply_text("✏️ Type your message and I will forward it to the other party.")
    return REPLY_MESSAGE

async def relay_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender_id = update.effective_user.id
    if sender_id not in conversations:
        await update.message.reply_text("❌ Conversation no longer active.")
        return ConversationHandler.END

    recipient_id = conversations[sender_id]
    try:
        await context.bot.send_message(chat_id=recipient_id, text=f"💬 Message: {update.message.text}")
        await update.message.reply_text("✅ Message sent.")
    except Exception as e:
        logger.error(f"Failed to send message: {e}")
        await update.message.reply_text("❌ Failed to send message.")

    return ConversationHandler.END

async def end_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in conversations:
        other_id = conversations[user_id]
        await context.bot.send_message(chat_id=other_id, text="🔚 The other party has ended the conversation.")
        del conversations[other_id]
        del conversations[user_id]
        await update.message.reply_text("🛑 Conversation ended.")
    else:
        await update.message.reply_text("You have no active conversation.")

# Main setup
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

    reply_conv = ConversationHandler(
        entry_points=[CommandHandler("reply", reply)],
        states={REPLY_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, relay_message)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(reply_conv)
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CommandHandler("end", end_chat))
    application.add_handler(CommandHandler("my_status", my_status))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_plate_lookup))

    application.run_webhook(
        listen="0.0.0.0",
        port=10000,
        url_path="webhook",
        webhook_url="https://carpark-bot-m825.onrender.com/webhook"
    )

if __name__ == '__main__':
    main()
