
import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)
from config import BOT_TOKEN
from sheets import (
    register_user, is_user_registered, find_users_by_plate,
    find_all_vehicles_by_user, update_user_info,
    delete_vehicle, get_existing_user_info
)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# States
NAME, PHONE, MODEL, PLATE, CHOOSING_UPDATE_VEHICLE, CHOOSING_FIELD, GET_NEW_VALUE = range(7)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to EV Charging Assistant!
"
        "Use /register to register your vehicle.
"
        "Use /my_status to view your registered cars.
"
        "Use /update to update or delete a vehicle.
"
        "Use /cancel to cancel registration at any time."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 Commands:
"
        "/register – Register your vehicle
"
        "/my_status – View your registered vehicles
"
        "/update – Update or delete your vehicle
"
        "/cancel – Cancel the registration process"
    )

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Received /register command")
    if is_user_registered(update.effective_user.id):
        context.user_data["registered"] = True
        name, phone = get_existing_user_info(update.effective_user.id)
        context.user_data["name"] = name
        context.user_data["phone"] = phone
        await update.message.reply_text("You’re already registered. Let’s register a new vehicle.
What's your car model?")
        return MODEL
    else:
        context.user_data["registered"] = False
        await update.message.reply_text("Welcome! Let's get you registered.
What's your name?")
        return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("Got it! What's your phone number?")
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["phone"] = update.message.text
    await update.message.reply_text("Great! What's your car model?")
    return MODEL

async def get_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["model"] = update.message.text
    await update.message.reply_text("Nice! What's your car plate?")
    return PLATE

async def get_plate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["plate"] = update.message.text.upper()
    register_user(
        context.user_data["name"],
        context.user_data["phone"],
        context.user_data["model"],
        context.user_data["plate"],
        update.effective_user.id
    )
    await update.message.reply_text("✅ Vehicle registered successfully!")
    return ConversationHandler.END

async def my_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vehicles = find_all_vehicles_by_user(update.effective_user.id)
    if not vehicles:
        await update.message.reply_text("You have no registered vehicles. Use /register to add one.")
        return
    msg = "🚗 Your Registered Vehicles:
"
    for v in vehicles:
        msg += f"- {v['Car Plate']} ({v['Vehicle Type']})
"
    await update.message.reply_text(msg)

async def update_vehicle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vehicles = find_all_vehicles_by_user(update.effective_user.id)
    if not vehicles:
        await update.message.reply_text("No vehicles found to update. Use /register to add one.")
        return ConversationHandler.END
    keyboard = [[v['Car Plate']] for v in vehicles]
    context.user_data["vehicles"] = vehicles
    await update.message.reply_text("Select a vehicle to update or delete:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))
    return CHOOSING_UPDATE_VEHICLE

async def choose_update_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    selected_plate = update.message.text.upper()
    context.user_data["selected_plate"] = selected_plate
    keyboard = [["Name", "Phone Number"], ["Vehicle Type", "Car Plate"], ["Delete"]]
    await update.message.reply_text("What would you like to update?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))
    return CHOOSING_FIELD

async def handle_update_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field = update.message.text
    context.user_data["field"] = field
    if field == "Delete":
        success = delete_vehicle(update.effective_user.id, context.user_data["selected_plate"])
        msg = "✅ Vehicle deleted." if success else "❌ Could not delete vehicle."
        await update.message.reply_text(msg)
        return ConversationHandler.END
    await update.message.reply_text(f"What is the new value for {field}?")
    return GET_NEW_VALUE

async def apply_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text
    success = update_user_info(
        update.effective_user.id,
        context.user_data["selected_plate"],
        context.user_data["field"],
        value
    )
    msg = "✅ Update successful!" if success else "❌ Update failed."
    await update.message.reply_text(msg)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Registration cancelled. You can start again with /register.")
    return ConversationHandler.END

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("register", register)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_model)],
            PLATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_plate)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    update_handler = ConversationHandler(
        entry_points=[CommandHandler("update", update_vehicle)],
        states={
            CHOOSING_UPDATE_VEHICLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_update_field)],
            CHOOSING_FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_update_choice)],
            GET_NEW_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, apply_update)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.add_handler(update_handler)
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("my_status", my_status))

    app.run_webhook(
        listen="0.0.0.0",
        port=10000,
        url_path="webhook",
        webhook_url="https://carpark-bot-m825.onrender.com/webhook"
    )

if __name__ == "__main__":
    main()
