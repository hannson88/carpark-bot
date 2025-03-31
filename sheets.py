import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Setup logger
logger = logging.getLogger(__name__)

# Define the scope for Google Sheets API
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]
SHEET_NAME = "CarParkBot"

# Authenticate and create the gspread client
CREDS = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", SCOPE)
client = gspread.authorize(CREDS)

# Open the Google Sheet
sheet = client.open(SHEET_NAME).sheet1


def is_user_registered(telegram_id):
    data = sheet.get_all_records()
    for row in data:
        if row.get("Telegram ID") == telegram_id:
            return True
    return False


def find_users_by_plate(plates):
    results = []
    data = sheet.get_all_records()
    for row in data:
        car_plate = row.get("Car Plate", "").strip().upper()
        if car_plate and car_plate in plates:
            results.append(row)
    return results


def register_user(name, phone, model, plate, telegram_id):
    plate = plate.upper()
    sheet.append_row([name, phone, model, plate, telegram_id])
    logger.info(f"✅ Registered {name} with plate {plate}")


def find_user_by_telegram_id(telegram_id):
    data = sheet.get_all_records()
    return [row for row in data if row.get("Telegram ID") == telegram_id]