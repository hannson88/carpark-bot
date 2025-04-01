
import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Set up logging
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

def is_user_registered(user_id):
    data = sheet.get_all_records()
    for row in data:
        if str(row.get("Telegram ID")) == str(user_id):
            return True
    return False

def get_user_info(user_id):
    data = sheet.get_all_records()
    for row in data:
        if str(row.get("Telegram ID")) == str(user_id):
            return row
    return None

def register_user(name, phone, model, plate, telegram_id):
    plate = plate.upper()
    sheet.append_row([name, phone, model, plate, telegram_id])
    logger.info(f"✅ Registered {name} with plate {plate}")

def find_users_by_plate(plates):
    results = []
    data = sheet.get_all_records()
    for row in data:
        car_plate = row.get("Car Plate", "").strip().upper()
        if car_plate and car_plate in plates:
            results.append(row)
    return results

def find_all_vehicles_by_user(user_id):
    results = []
    data = sheet.get_all_records()
    for row in data:
        if str(row.get("Telegram ID")) == str(user_id):
            results.append(row)
    return results
