import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes,
    ConversationHandler, filters, CallbackQueryHandler
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

# States
NAME, PHONE, MODEL, PLATE = range(4)
UPDATE_SELECTION, UPDATE_FIELD, NEW_VALUE = range(4, 7)
REPLY_MESSAGE = 10

# In-memory map for conversations
active_conversations = {}

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

# Cancel
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Action cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# Register
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
    data = context.user_data
    register_user(data['name'], data['phone'], data['model'], plate, update.effective_user.id)
    await update.message.reply_text(
        f"🎉 You are now registered!\n"
        f"Name: {data['name']}\n"
        f"Phone: {data['phone']}\n"
        f"Model: {data['model']}\n"
        f"Plate: {plate}"
    )
    return ConversationHandler.END

# My Status
async def my_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vehicles = find_all_vehicles_by_user(update.effective_user.id)
    if not vehicles:
        await update.message.reply_text("No vehicles registered. Use /register to add one.")
        return
    msg = "🚗 Your registered vehicles:\n"
    for v in vehicles:
        msg += f"- {v['Car Plate']} ({v['Vehicle Type']})\n"
    await update.message.reply_text(msg)

# Lookup
async def handle_plate_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plate = update.message.text.strip().upper()
    matches = find_users_by_plate([plate])

    if not matches:
        await update.message.reply_text("❌ No matching car plate found or owner not registered.")
        return

    requester_id = update.effective_user.id
    requester_vehicles = find_all_vehicles_by_user(requester_id)
    requester_plate = requester_vehicles[0]["Car Plate"] if requester_vehicles else "Unknown"

    for owner in matches:
        owner_id = owner["Telegram ID"]
        owner_plate = owner["Car Plate"]

        # Save conversations separately with each person's own plate
        active_conversations[owner_id] = {
            "peer_id": requester_id,
            "plate": owner_plate,
            "start_time": update.message.date.timestamp()
        }

        active_conversations[requester_id] = {
            "peer_id": owner_id,
            "plate": requester_plate,
            "start_time": update.message.date.timestamp()
        }

        await context.bot.send_message(
            chat_id=owner_id,
            text=(
                f"🔔 Someone is looking for your car plate: {plate}.\n"
                f"You can reply using the button below."
            ),
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Reply", callback_data="start_reply"),
                    InlineKeyboardButton("End Conversation", callback_data="end_convo")
                ]
            ])
        )

    # ✅ Moved outside the loop
    await update.message.reply_text("✅ Owner has been contacted.")

async def handle_button_press(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "start_reply":
        context.user_data["reply_target"] = active_conversations[user_id]["peer_id"]
        context.user_data["reply_plate"] = active_conversations[user_id]["plate"]
        await query.message.reply_text("Please type your reply:")

        # 🔥 Force user into conversation state
        context._chat_data[user_id][ConversationHandler.CONVERSATION] = REPLY_MESSAGE
        return

    elif query.data == "end_convo":
        if user_id in active_conversations:
            peer_id = active_conversations[user_id]["peer_id"]
            plate = active_conversations[user_id]["plate"]

            del active_conversations[user_id]
            if peer_id in active_conversations:
                del active_conversations[peer_id]

            await context.bot.send_message(
                chat_id=peer_id,
                text=f"❌ Conversation ended by the other party (plate: {plate})."
            )
            await query.edit_message_text("❌ You ended the conversation.")
        else:
            await query.edit_message_text("❌ No active conversation to end.")

# Reply
async def start_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        user_id = update.effective_user.id
    else:
        user_id = update.callback_query.from_user.id

    if user_id not in active_conversations:
        if update.callback_query:
            await update.callback_query.message.reply_text("You have no one to reply to right now.")
        else:
            await update.message.reply_text("You have no one to reply to right now.")
        return ConversationHandler.END

    context.user_data["reply_target"] = active_conversations[user_id]["peer_id"]
    context.user_data["reply_plate"] = active_conversations[user_id]["plate"]

    if update.callback_query:
        await update.callback_query.message.reply_text("Please type your reply:")
    else:
        await update.message.reply_text("Please type your reply:")

    return REPLY_MESSAGE

# Send the actual reply
async def send_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = update.effective_user.id
    target = context.user_data.get("reply_target")
    plate = context.user_data.get("reply_plate")

    if not target:
        await update.message.reply_text("Reply session expired or invalid.")
        return ConversationHandler.END

    # Determine sender role
    conversation = active_conversations.get(sender)
    sender_role = "Requester" if conversation and conversation.get("peer_id") == target else "Owner"

    await context.bot.send_message(
        chat_id=target,
        text=(
            f"💬 Reply from {sender_role} of plate {plate}:\n"
            f"{update.message.text}\n\n"
            f"You can reply using /reply"
        )
    )
    await update.message.reply_text("✅ Reply sent.")
    return ConversationHandler.END

# Update
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
        "Choose what you would like to update:\n"
        "Name, Phone Number, Vehicle Type, Car Plate\n"
        "Or type DELETE to remove this vehicle.",
        reply_markup=ReplyKeyboardRemove()
    )
    return UPDATE_FIELD

async def receive_update_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field = update.message.text.strip().title()
    telegram_id = update.effective_user.id
    plate = context.user_data['selected_plate']

    if field.upper() == "DELETE":
        delete_vehicle(telegram_id, plate)
        await update.message.reply_text("❌ Vehicle deleted.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    context.user_data['field_to_update'] = field
    await update.message.reply_text(f"Enter new value for {field}:", reply_markup=ReplyKeyboardRemove())
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

# Main
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

    reply_conv = ConversationHandler(
        entry_points=[CommandHandler("reply", start_reply)],
        states={
            REPLY_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_reply)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(reg_conv)
    app.add_handler(update_conv)
    app.add_handler(reply_conv)
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("my_status", my_status))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_plate_lookup))

    # Handle inline button presses (Reply / End Conversation)
    app.add_handler(CallbackQueryHandler(handle_button_press))
    
    app.run_webhook(
        listen="0.0.0.0",
        port=10000,
        url_path="webhook",
        webhook_url="https://carpark-bot-m825.onrender.com/webhook"
    )

if __name__ == '__main__':
    main()
