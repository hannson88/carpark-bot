import os
import logging
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, ConversationHandler
)
from config import BOT_TOKEN
#from sheets import register_user, find_users_by_plate
from sheets import sheet, is_user_registered, register_user, find_users_by_plate  # Import `sheet` and `register_user` from sheets.py

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask and Telegram application
app = Flask(__name__)
application = ApplicationBuilder().token(BOT_TOKEN).build()

# Define states for the conversation
NAME, PHONE, MODEL, PLATE = range(4)

# Telegram webhook endpoint
@app.route("/webhook", methods=["POST"])
def webhook():
    import traceback
    import asyncio

    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, application.bot)

        async def handle_update():
            await application.initialize()
            await application.process_update(update)
            await application.shutdown()  # Optional but safe cleanup

        asyncio.run(handle_update())
        return "ok"

    except Exception as e:
        logger.error("🔥 Webhook crashed:")
        logger.error(traceback.format_exc())
        return "error", 500

#def register_user(name, phone, model, plate, user_id):
#    plate = plate.upper()  # Make sure the plate is stored in uppercase
#    # Save user data to the Google Sheet
#    sheet.append_row([name, phone, model, plate, user_id])
#    logger.info(f"✅ Registered {name} with plate {plate}")

# Conversation flow handlers
def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update.message.reply_text("Welcome! Let's get you registered. What's your name?")
    return NAME

def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text  # Store name
    update.message.reply_text("Got it! What's your phone number?")
    return PHONE

def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['phone'] = update.message.text  # Store phone number
    update.message.reply_text("Great! What's your car model?")
    return MODEL

def get_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['model'] = update.message.text  # Store car model
    update.message.reply_text("Nice! What's your car plate?")
    return PLATE

def get_plate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['plate'] = update.message.text  # Store car plate
    name = context.user_data['name']
    phone = context.user_data['phone']
    model = context.user_data['model']
    plate = context.user_data['plate']

    # Save user data to Google Sheets
    try:
        register_user(name, phone, model, plate, update.effective_user.id)
        update.message.reply_text(f"🎉 You're now registered! Name: {name}, Phone: {phone}, Model: {model}, Plate: {plate}")
    except Exception as e:
        update.message.reply_text(f"❌ There was an error registering you. Please try again later.")
        logger.error(f"Error during registration: {e}")

    return ConversationHandler.END  # End the conversation

def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update.message.reply_text("Registration cancelled. You can start again by typing /register.")
    return ConversationHandler.END


# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome to EV Charging Assistant! Use /register to register your vehicle.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📋 Commands:\\n/register Name, Phone, Car Model, Car Plate\\nThen just type car plate(s) to check for owners.")

#async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
#    try:
#        args = ' '.join(context.args)
#        name, phone, model, plate = [x.strip() for x in args.split(',')]
#        register_user(name, phone, model, plate, update.effective_user.id)
#        await update.message.reply_text("✅ Registration successful!")
#    except Exception as e:
#        logger.error(f"❌ Error in /register: {e}")
#        await update.message.reply_text("❌ Usage:\\n/register Name, Phone, Car Model, Car Plate")

# Main function to set up handlers and start the bot
def main():
    # Create a ConversationHandler to manage the registration steps
    conversation_handler = ConversationHandler(
        entry_points=[CommandHandler('register', start)],  # Start with /register
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_model)],
            PLATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_plate)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],  # Allow cancellation at any point
    )

    # Add the conversation handler to the dispatcher
    dispatcher = application.dispatcher
    dispatcher.add_handler(conversation_handler)
    dispatcher.add_handler(CommandHandler('start', start_command))  # /start command
    dispatcher.add_handler(CommandHandler('help', help_command))  # /help command

    # Start the bot
    application.run_polling()

if __name__ == '__main__':
    main()



async def handle_plate(update: Update, context: ContextTypes.DEFAULT_TYPE):

# Check if the user is registered
    user_id = update.effective_user.id  # Get the user ID from Telegram
    if not is_user_registered(user_id):
        await update.message.reply_text("❌ You need to register first. Use /register to register.")
        return

    # If the user is registered, proceed with the plate lookup



    # Convert plates to uppercase and log the plates being searched
    plates = [x.strip().upper() for x in update.message.text.split(',')]
    logger.info(f"🚗 Searching for plates: {plates}")

    matches = find_users_by_plate(plates)
    
    if not matches:
        await update.message.reply_text("❌ No matching cars found.")
        logger.info(f"No matching plates found for: {plates}")
        return

    for match in matches:
        owner_id = int(match['Telegram ID'])
        await context.bot.send_message(
            chat_id=owner_id,
            text=f"🔌 Your EV with plate *{match['Car Plate']}* is being sought. Someone is looking for a charger.",
            parse_mode="Markdown"
        )
    await update.message.reply_text("✅ Owners notified.")

# Register handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
#application.add_handler(CommandHandler("register", register))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_plate))
