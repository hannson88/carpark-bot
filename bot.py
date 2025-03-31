import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
                          ConversationHandler, ContextTypes, filters)
from config import BOT_TOKEN
from sheets import (register_user, find_users_by_plate, is_user_registered,
                    find_all_vehicles_by_user, update_user_info, mark_vehicle_deleted)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# States for registration
NAME, PHONE, MODEL, PLATE = range(4)

# States for manage command
SELECT_ACTION, SELECT_VEHICLE, UPDATE_FIELD, NEW_VALUE = range(4, 8)

user_update_context = {}

# Commands
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Received /start command")
    await update.message.reply_text("👋 Welcome to EV Charging Assistant! Use /register to register your vehicle.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Received /help command")
    await update.message.reply_text(
        "📋 Commands:\n"
        "/register – Start registration process\n"
        "/my_status – View your registered vehicle(s)\n"
        "/manage – Update or delete a registration\n"
        "/cancel – Cancel ongoing process"
    )


# Registration flow
async def start_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Received /register command")
    user_id = update.effective_user.id
    if is_user_registered(user_id):
        context.user_data['existing'] = True
        await update.message.reply_text("Welcome back! Registering a new vehicle. What's your car model?")
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
    context.user_data['plate'] = update.message.text.upper()
    name = context.user_data.get('name')
    phone = context.user_data.get('phone')

    if context.user_data.get('existing'):
        vehicles = find_all_vehicles_by_user(update.effective_user.id)
        if vehicles:
            name = vehicles[0]['Name']
            phone = vehicles[0]['Phone Number']

    model = context.user_data['model']
    plate = context.user_data['plate']
    register_user(name, phone, model, plate, update.effective_user.id)
    await update.message.reply_text("🎉 Vehicle registered!")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 Registration cancelled. Use /register to start again.")
    return ConversationHandler.END


# My status
async def my_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    vehicles = find_all_vehicles_by_user(user_id)
    if not vehicles:
        await update.message.reply_text("❌ No vehicles found. Use /register to get started.")
        return

    reply = "🚗 Your Registered Vehicles:\n"
    for v in vehicles:
        reply += f"\nModel: {v['Vehicle Type']}\nPlate: {v['Car Plate']}\n"
    await update.message.reply_text(reply)


# Manage command flow
async def start_manage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    vehicles = find_all_vehicles_by_user(user_id)
    if not vehicles:
        await update.message.reply_text("❌ No vehicles to manage. Use /register first.")
        return ConversationHandler.END

    keyboard = [[InlineKeyboardButton(f"{v['Car Plate']}", callback_data=v['Car Plate'])] for v in vehicles]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select vehicle to manage:", reply_markup=reply_markup)
    return SELECT_VEHICLE


async def select_vehicle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['selected_plate'] = query.data

    keyboard = [
        [InlineKeyboardButton("Update Name", callback_data="update_name")],
        [InlineKeyboardButton("Update Phone Number", callback_data="update_phone")],
        [InlineKeyboardButton("Update Car Plate", callback_data="update_plate")],
        [InlineKeyboardButton("Update Car Model", callback_data="update_model")],
        [InlineKeyboardButton("❌ Delete Vehicle", callback_data="delete")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Choose an action:", reply_markup=reply_markup)
    return SELECT_ACTION


async def handle_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data

    if action == "delete":
        mark_vehicle_deleted(context.user_data['selected_plate'], update.effective_user.id)
        await query.edit_message_text("✅ Vehicle deleted from your registration.")
        return ConversationHandler.END
    else:
        context.user_data['action'] = action
        await query.edit_message_text("Please send the new value:")
        return NEW_VALUE


async def handle_new_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_value = update.message.text
    action = context.user_data['action']
    plate = context.user_data['selected_plate']
    user_id = update.effective_user.id

    field_map = {
        "update_name": "Name",
        "update_phone": "Phone Number",
        "update_plate": "Car Plate",
        "update_model": "Vehicle Type"
    }
    field = field_map.get(action)

    update_user_info(user_id, plate, field, new_value)
    await update.message.reply_text("✅ Information updated successfully.")
    return ConversationHandler.END


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    reg_flow = ConversationHandler(
        entry_points=[CommandHandler('register', start_register)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_model)],
            PLATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_plate)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    manage_flow = ConversationHandler(
        entry_points=[CommandHandler('manage', start_manage)],
        states={
            SELECT_VEHICLE: [CallbackQueryHandler(select_vehicle)],
            SELECT_ACTION: [CallbackQueryHandler(handle_action)],
            NEW_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_new_value)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    app.add_handler(reg_flow)
    app.add_handler(manage_flow)
    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('my_status', my_status))
    app.add_handler(CommandHandler('cancel', cancel))

    app.run_webhook(
        listen="0.0.0.0",
        port=10000,
        url_path="webhook",
        webhook_url="https://carpark-bot-m825.onrender.com/webhook"
    )


if __name__ == '__main__':
    main()
