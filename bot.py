import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes,
    ConversationHandler, filters
)
from config import BOT_TOKEN
from sheets import (
    register_user, is_user_registered, find_users_by_plate, find_all_vehicles_by_user,
    update_user_info, delete_vehicle, get_existing_user_info
)
import asyncio
from datetime import datetime, timedelta

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# State constants
NAME, PHONE, MODEL, PLATE = range(4)
UPDATE_SELECTION, UPDATE_FIELD, NEW_VALUE = range(4, 7)
REPLY_MESSAGE = 10

# In-memory conversation sessions
active_conversations = {}
conversation_timeout_minutes = 15

# Start command
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        (
            "👋 Welcome to EV Charging Assistant!\n"
            "Use /register to register your vehicle.\n"
            "Use /my_status to view your vehicles.\n"
            "Use /update to update or delete a vehicle.\n"
            "Use /cancel to exit at any time."
        )
    )

# Help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        (
            "📋 Commands:\n"
            "/register – Register your vehicle step-by-step.\n"
            "/my_status – View your registered vehicles.\n"
            "/update – Modify or delete your vehicle details.\n"
            "/cancel – Cancel the current action.\n"
            "Just type a car plate to check for registered owners."
        )
    )

# Cancel command
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ Action cancelled. Use /register or /help to continue.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

# Start registration
async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    telegram_id = update.effective_user.id
    if is_user_registered(telegram_id):
        name, phone = get_existing_user_info(telegram_id)
        context.user_data['name'] = name
        context.user_data['phone'] = phone
        await update.message.reply_text("Please enter your car model:")
        return MODEL
    else:
        await update.message.reply_text("Let us register you. What is your name?")
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
    await update.message.reply_text("What is your car plate number?")
    return PLATE

async def get_plate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plate = update.message.text.upper()
    context.user_data['plate'] = plate
    data = context.user_data
    register_user(data['name'], data['phone'], data['model'], plate, update.effective_user.id)
    await update.message.reply_text(
        (
            f"🎉 You are now registered!\n"
            f"Name: {data['name']}\n"
            f"Phone: {data['phone']}\n"
            f"Model: {data['model']}\n"
            f"Plate: {plate}"
        )
    )
    return ConversationHandler.END

# Status command
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
    matches = find_users_by_plate([plate])
    if matches:
        requester_id = update.effective_user.id
        active_conversations[requester_id] = {
            'start_time': datetime.now(),
            'partner_id': matches[0]['Telegram ID'],
            'partner_plate': plate
        }
        await context.bot.send_message(
            chat_id=matches[0]['Telegram ID'],
            text=f"🔔 Someone is asking about your car plate {plate}. You can reply directly by typing here."
        )
        await update.message.reply_text("✉️ Owner has been contacted.")
    else:
        await update.message.reply_text("❌ No matching car plate found or owner not registered.")

# Main bot setup
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    registration = ConversationHandler(
        entry_points=[CommandHandler("register", start_registration)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_model)],
            PLATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_plate)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(registration)
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("my_status", my_status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_plate_lookup))

    app.run_webhook(
        listen="0.0.0.0",
        port=10000,
        url_path="webhook",
        webhook_url="https://carpark-bot-m825.onrender.com/webhook"
    )

if __name__ == '__main__':
    main()
