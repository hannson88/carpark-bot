import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes,
    ConversationHandler, filters
)
from config import BOT_TOKEN
from sheets import (
    register_user, find_users_by_plate, is_user_registered,
    find_all_vehicles_by_user, update_user_info, delete_vehicle,
    get_existing_user_info
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Conversation states
NAME, PHONE, MODEL, PLATE = range(4)
SELECT_ACTION, SELECT_FIELD, NEW_VALUE = range(4, 7)

# /start command
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Received /start command")
    await update.message.reply_text(
        "👋 Welcome to EV Charging Assistant!
Use /register to register your vehicle.
Use /my_status to view your registrations."
    )

# /help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Received /help command")
    await update.message.reply_text(
        "📋 Commands:
"
        "/register – Register a new vehicle
"
        "/my_status – View your registered vehicles
"
        "/update – Update or delete a registered vehicle
"
        "/cancel – Cancel any ongoing action"
    )

# /register flow
async def start_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Received /register command")
    if is_user_registered(update.effective_user.id):
        context.user_data['existing_user'] = True
        await update.message.reply_text("Welcome back! Let's register another vehicle.
What is your car model?")
        return MODEL
    else:
        await update.message.reply_text("Welcome! Let's get you registered.
What's your name?")
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
    if context.user_data.get("existing_user"):
        name, phone = get_existing_user_info(user_id)
    else:
        name = context.user_data['name']
        phone = context.user_data['phone']
    model = context.user_data['model']
    register_user(name, phone, model, plate, user_id)
    await update.message.reply_text(
        f"🎉 You're now registered!
Name: {name}
Phone: {phone}
Model: {model}
Plate: {plate}"
    )
    return ConversationHandler.END

# /my_status
async def my_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    vehicles = find_all_vehicles_by_user(user_id)
    if not vehicles:
        await update.message.reply_text("You have no registered vehicles. Use /register to add one.")
        return
    msg = "🚘 Your registered vehicle(s):
"
    for v in vehicles:
        msg += f"- {v['Car Plate']} ({v['Vehicle Type']})
"
    await update.message.reply_text(msg)

# /update flow
async def start_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    vehicles = find_all_vehicles_by_user(user_id)
    if not vehicles:
        await update.message.reply_text("You have no vehicles to update. Use /register to add one.")
        return ConversationHandler.END
    context.user_data['vehicles'] = vehicles
    keyboard = [[v['Car Plate']] for v in vehicles]
    await update.message.reply_text("Select the vehicle you want to update or delete:",
                                    reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))
    return SELECT_ACTION

async def choose_update_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    selected_plate = update.message.text.upper()
    context.user_data['selected_plate'] = selected_plate
    keyboard = [['Name', 'Phone Number'], ['Vehicle Type', 'Car Plate'], ['Delete']]
    await update.message.reply_text("What do you want to update or do?",
                                    reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))
    return SELECT_FIELD

async def handle_field_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field = update.message.text
    context.user_data['field'] = field
    if field == 'Delete':
        success = delete_vehicle(update.effective_user.id, context.user_data['selected_plate'])
        msg = "✅ Vehicle deleted." if success else "❌ Vehicle not found."
        await update.message.reply_text(msg)
        return ConversationHandler.END
    await update.message.reply_text(f"What is the new value for {field}?")
    return NEW_VALUE

async def process_new_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_value = update.message.text
    success = update_user_info(update.effective_user.id,
                                context.user_data['selected_plate'],
                                context.user_data['field'],
                                new_value)
    if success:
        await update.message.reply_text("✅ Your information has been updated.")
    else:
        await update.message.reply_text("❌ Update failed. Please try again.")
    return ConversationHandler.END

# /cancel
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 Action cancelled.")
    return ConversationHandler.END

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Registration handler
    register_conv = ConversationHandler(
        entry_points=[CommandHandler("register", start_register)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_model)],
            PLATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_plate)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Update handler
    update_conv = ConversationHandler(
        entry_points=[CommandHandler("update", start_update)],
        states={
            SELECT_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_update_field)],
            SELECT_FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_field_choice)],
            NEW_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_new_value)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Add handlers
    app.add_handler(register_conv)
    app.add_handler(update_conv)
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("my_status", my_status))
    app.add_handler(CommandHandler("cancel", cancel))

    # Start webhook
    app.run_webhook(
        listen="0.0.0.0",
        port=10000,
        url_path="webhook",
        webhook_url="https://carpark-bot-m825.onrender.com/webhook"
    )

if __name__ == "__main__":
    main()