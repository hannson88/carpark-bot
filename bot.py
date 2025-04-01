import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes,
    ConversationHandler, CallbackContext, filters
)
from config import BOT_TOKEN
from sheets import (
    register_user,
    find_users_by_plate,
    is_user_registered,
    find_all_vehicles_by_user,
    update_user_info,
    delete_vehicle,
    get_existing_user_info
)

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# State definitions
NAME, PHONE, MODEL, PLATE = range(4)
UPDATE_SELECTION, UPDATE_FIELD, NEW_VALUE = range(4, 7)

# Start command
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to EV Charging Assistant!\n"
        "Use /register to register your vehicle.\n"
        "Use /my_status to view your vehicles.\n"
        "Use /update to update or delete a vehicle.\n"
        "Use /cancel to exit at any time.
"    )

# Help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 Commands:"\n
        "/register – Start the registration process step-by-step.\n"
        "/my_status – View your registered vehicles.\n"
        "/update – Modify or delete your vehicle details.\n"
        "/cancel – Cancel the current action.\n"
        "Just type a car plate to check for registered owners.
"    )

# Cancel handler
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Action cancelled.")
    return ConversationHandler.END

# Registration flow
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
    await update.message.reply_text("✅ Registration complete!")
    return ConversationHandler.END

# Status command
async def my_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vehicles = find_all_vehicles_by_user(update.effective_user.id)
    if not vehicles:
        await update.message.reply_text("No vehicles registered. Use /register to add one.")
        return
    msg = "🚗 Your registered vehicles:

"    for v in vehicles:
        msg += f"- {v['Car Plate']} ({v['Vehicle Type']})

"    await update.message.reply_text(msg)

# Plate lookup
async def handle_plate_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plate = update.message.text.strip().upper()
    if not plate:
        return
    logger.info(f"🔍 Plate lookup: {plate}")
    matches = find_users_by_plate([plate])
    if matches:
        for m in matches:
            user_id = m["Telegram ID"]
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🔔 Someone is looking for your car plate: {m['Car Plate']}
"            )
        await update.message.reply_text("✅ Owner has been contacted.")
    else:
        await update.message.reply_text("❌ No matching car plate found or owner not registered.")

# Update flow
async def start_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vehicles = find_all_vehicles_by_user(update.effective_user.id)
    if not vehicles:
        await update.message.reply_text("No registered vehicles to update. Use /register to add one.")
        return ConversationHandler.END
    buttons = [[v['Car Plate']] for v in vehicles]
    context.user_data['vehicles'] = vehicles
    await update.message.reply_text(
        "Which vehicle would you like to update or delete?",
        reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True)
    )
    return UPDATE_SELECTION

async def choose_update_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    selected_plate = update.message.text.upper()
    context.user_data['selected_plate'] = selected_plate
    await update.message.reply_text(
        "Choose what you would like to update:

"        "Name, Phone Number, Vehicle Type, Car Plate

"        "Or type DELETE to remove this vehicle.
"    )
    return UPDATE_FIELD

async def receive_update_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field = update.message.text
    telegram_id = update.effective_user.id
    plate = context.user_data['selected_plate']
    if field.upper() == "DELETE":
        delete_vehicle(telegram_id, plate)
        await update.message.reply_text("❌ Vehicle deleted.")
        return ConversationHandler.END
    context.user_data['field_to_update'] = field
    await update.message.reply_text(f"Enter new value for {field}:")
    return NEW_VALUE

async def apply_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_value = update.message.text
    telegram_id = update.effective_user.id
    plate = context.user_data['selected_plate']
    field = context.user_data['field_to_update']
    updated = update_user_info(telegram_id, plate, field, new_value)
    if updated:
        await update.message.reply_text("✅ Update successful.")
    else:
        await update.message.reply_text("❌ Update failed.")
    return ConversationHandler.END

# Main application setup
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    reg_conv = ConversationHandler(
        entry_points=[CommandHandler("register", start_registration)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_model)],
            PLATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_plate)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    update_conv = ConversationHandler(
        entry_points=[CommandHandler("update", start_update)],
        states={
            UPDATE_SELECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_update_field)],
            UPDATE_FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_update_value)],
            NEW_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, apply_update)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(reg_conv)
    app.add_handler(update_conv)
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("my_status", my_status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_plate_lookup))

    app.run_webhook(
        listen="0.0.0.0",
        port=10000,
        url_path="webhook",
        webhook_url="https://carpark-bot-m825.onrender.com/webhook
"    )

if __name__ == '__main__':
    main()
