import logging
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ConversationHandler,
    ContextTypes, filters
)
from config import BOT_TOKEN
from sheets import (
    register_user, is_user_registered, find_users_by_plate,
    find_all_vehicles_by_user, update_user_info, delete_vehicle,
    get_existing_user_info
)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Conversation states
NAME, PHONE, MODEL, PLATE, SELECT_PLATE, UPDATE_FIELD, NEW_VALUE = range(7)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to EV Charging Assistant!
"
        "Use /register to register your vehicle.
"
        "Use /my_status to view your registered vehicles.
"
        "Use /update to update or delete a vehicle.
"
        "Just type a car plate to notify the owner.
"
        "Use /cancel anytime to stop the process."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 Commands:
"
        "/register - Register your vehicle
"
        "/my_status - View your registered vehicles
"
        "/update - Update or delete a vehicle
"
        "/cancel - Cancel any current operation
"
        "To notify a car owner, just type the car plate."
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 Cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# Registration process
async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_user_registered(user_id):
        name, phone = get_existing_user_info(user_id)
        if name and phone:
            context.user_data['name'] = name
            context.user_data['phone'] = phone
            await update.message.reply_text("You're already registered. Just tell us your new car model:")
            return MODEL
    await update.message.reply_text("Let's register you. What's your name?")
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    await update.message.reply_text("Your phone number?")
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['phone'] = update.message.text
    await update.message.reply_text("Your car model?")
    return MODEL

async def get_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['model'] = update.message.text
    await update.message.reply_text("Car plate?")
    return PLATE

async def get_plate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    plate = update.message.text.strip().upper()
    register_user(
        context.user_data['name'],
        context.user_data['phone'],
        context.user_data['model'],
        plate,
        user_id
    )
    await update.message.reply_text(f"✅ Registered: {plate}")
    return ConversationHandler.END

# View user status
async def my_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    vehicles = find_all_vehicles_by_user(user_id)
    if not vehicles:
        await update.message.reply_text("You have no registered vehicles. Use /register to get started.")
        return
    msg = "🚗 Your Registered Vehicles:
"
    for v in vehicles:
        msg += f"- {v['Car Plate']} ({v['Vehicle Type']})
"
    await update.message.reply_text(msg)

# Plate search
async def handle_plate_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plate = update.message.text.strip().upper()
    matches = find_users_by_plate([plate])
    if not matches:
        await update.message.reply_text("❌ Car plate not found or not registered.")
        return
    for match in matches:
        context.bot.send_message(
            chat_id=match['Telegram ID'],
            text=f"📢 Someone is looking for your car: {plate}"
        )
    await update.message.reply_text("✅ Owner has been contacted.")

# Update or delete vehicle
async def update_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    vehicles = find_all_vehicles_by_user(user_id)
    if not vehicles:
        await update.message.reply_text("You have no registered vehicles.")
        return ConversationHandler.END
    buttons = [v["Car Plate"] for v in vehicles]
    context.user_data["vehicles"] = vehicles
    await update.message.reply_text("Select plate to update or delete:
" + "
".join(buttons))
    return SELECT_PLATE

async def select_plate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    selected_plate = update.message.text.strip().upper()
    context.user_data["selected_plate"] = selected_plate
    await update.message.reply_text("Type the field to update (Name, Phone Number, Vehicle Type, Car Plate), or type DELETE to remove the vehicle.")
    return UPDATE_FIELD

async def choose_update_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip().lower()
    context.user_data["update_choice"] = choice
    if choice == "delete":
        deleted = delete_vehicle(update.effective_user.id, context.user_data["selected_plate"])
        if deleted:
            await update.message.reply_text("✅ Vehicle deleted.")
        else:
            await update.message.reply_text("❌ Could not delete.")
        return ConversationHandler.END
    else:
        await update.message.reply_text(f"Enter new value for {choice}:")
        return NEW_VALUE

async def update_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field_map = {
        "name": "Name",
        "phone number": "Phone Number",
        "vehicle type": "Vehicle Type",
        "car plate": "Car Plate"
    }
    telegram_id = update.effective_user.id
    plate = context.user_data["selected_plate"]
    field = field_map.get(context.user_data["update_choice"].lower())
    value = update.message.text.strip()
    updated = update_user_info(telegram_id, plate, field, value)
    if updated:
        await update.message.reply_text(f"✅ Updated {field} to {value}")
    else:
        await update.message.reply_text("❌ Update failed.")
    return ConversationHandler.END

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("my_status", my_status))
    app.add_handler(CommandHandler("cancel", cancel))

    # Conversation for registration
    reg = ConversationHandler(
        entry_points=[CommandHandler("register", register)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_model)],
            PLATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_plate)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(reg)

    # Conversation for updates
    update_conv = ConversationHandler(
        entry_points=[CommandHandler("update", update_command)],
        states={
            SELECT_PLATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_plate)],
            UPDATE_FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_update_field)],
            NEW_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_value)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(update_conv)

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_plate_lookup))

    app.run_webhook(
        listen="0.0.0.0",
        port=10000,
        url_path="webhook",
        webhook_url="https://carpark-bot-m825.onrender.com/webhook"
    )

if __name__ == "__main__":
    main()