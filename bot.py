import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler
)
from config import BOT_TOKEN
from sheets import (
    register_user, is_user_registered, find_users_by_plate,
    find_all_vehicles_by_user, update_user_info, delete_vehicle,
    get_existing_user_info
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define conversation states
NAME, PHONE, MODEL, PLATE = range(4)
SELECT_VEHICLE, UPDATE_FIELD, UPDATE_VALUE = range(4, 7)

# /start command
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("\U0001F44B Welcome to EV Charging Assistant! Use /register to register your vehicle.")

# /help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "\U0001F4CB Commands:\n"
        "/register - Start registration\n"
        "/my_status - View your registered vehicle(s)\n"
        "/update - Update or delete a vehicle\n"
        "/cancel - Cancel current operation"
    )

# /cancel command
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("\u274C Cancelled. You can start again with /register or /help.")
    return ConversationHandler.END

# Registration flow
async def register_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_user_registered(user_id):
        context.user_data['partial'] = True
        await update.message.reply_text("You're already registered. Let's add another vehicle. What's the car model?")
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

    if context.user_data.get('partial'):
        # use existing name & phone
        existing = get_existing_user_info(user_id)
        if not existing:
            await update.message.reply_text("❌ Could not retrieve your info. Try /register again.")
            return ConversationHandler.END
        name, phone = existing
    else:
        name = context.user_data['name']
        phone = context.user_data['phone']

    model = context.user_data['model']
    register_user(name, phone, model, plate, user_id)
    await update.message.reply_text(
        f"\U0001F389 Registered!\nName: {name}\nPhone: {phone}\nModel: {model}\nPlate: {plate}"
    )
    return ConversationHandler.END

# /my_status
async def my_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    vehicles = find_all_vehicles_by_user(user_id)
    if not vehicles:
        await update.message.reply_text("You are not registered. Use /register to get started.")
        return

    msg = "\U0001F4C4 Your registered vehicles:\n"
    for v in vehicles:
        msg += f"- {v['Car Plate']} ({v['Car Model']})\n"
    await update.message.reply_text(msg)

# Plate lookup
async def handle_plate_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.upper()
    plates = [p.strip().upper() for p in text.split()]  # space-separated
    matches = find_users_by_plate(plates)

    if matches:
        for match in matches:
            context.application.create_task(
                context.bot.send_message(
                    chat_id=match['Telegram ID'],
                    text=f"\u26A0 Someone is enquiring about your vehicle: {match['Car Plate']}"
                )
            )
        await update.message.reply_text("\u2709 Owner has been contacted.")
    else:
        await update.message.reply_text("No match found. The owner may not have registered.")

# Update flow
async def update_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    vehicles = find_all_vehicles_by_user(user_id)
    if not vehicles:
        await update.message.reply_text("You have no vehicles registered. Use /register.")
        return ConversationHandler.END

    keyboard = [[v['Car Plate']] for v in vehicles]
    context.user_data['vehicles'] = vehicles
    await update.message.reply_text(
        "Which vehicle do you want to update/delete?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    )
    return SELECT_VEHICLE

async def select_vehicle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    selected = update.message.text.upper()
    context.user_data['selected_plate'] = selected
    keyboard = [["Name"], ["Phone Number"], ["Car Plate"], ["Car Model"], ["Delete Vehicle"]]
    await update.message.reply_text(
        f"What do you want to update for {selected}?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    )
    return UPDATE_FIELD

async def choose_update_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field = update.message.text
    if field == "Delete Vehicle":
        delete_vehicle(context.user_data['selected_plate'], update.effective_user.id)
        await update.message.reply_text("\u274C Vehicle deleted.")
        return ConversationHandler.END

    context.user_data['field_to_update'] = field
    await update.message.reply_text(f"Enter new value for {field}:")
    return UPDATE_VALUE

async def perform_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text
    field = context.user_data['field_to_update']
    plate = context.user_data['selected_plate']
    user_id = update.effective_user.id

    update_user_info(plate, user_id, field, value)

    # Update all vehicles if updating name or phone
    if field in ["Name", "Phone Number"]:
        vehicles = find_all_vehicles_by_user(user_id)
        for v in vehicles:
            update_user_info(v['Car Plate'], user_id, field, value)

    await update.message.reply_text(f"✅ Updated {field} successfully.")
    return ConversationHandler.END

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    register_conv = ConversationHandler(
        entry_points=[CommandHandler('register', register_start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_model)],
            PLATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_plate)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    update_conv = ConversationHandler(
        entry_points=[CommandHandler('update', update_start)],
        states={
            SELECT_VEHICLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_vehicle)],
            UPDATE_FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_update_field)],
            UPDATE_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, perform_update)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('my_status', my_status))
    app.add_handler(register_conv)
    app.add_handler(update_conv)
    app.add_handler(CommandHandler('cancel', cancel))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_plate_lookup))

    app.run_webhook(
        listen="0.0.0.0",
        port=10000,
        url_path="webhook",
        webhook_url="https://carpark-bot-m825.onrender.com/webhook"
    )

if __name__ == '__main__':
    main()
