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
        if str(row.get("Telegram ID")) == str(user_id) and not row.get("Car Plate", "").endswith("_delete"):
            results.append(row)
    return results

def update_user_info(telegram_id, car_plate, field, new_value):
    car_plate = car_plate.upper()
    all_data = sheet.get_all_records()
    logger.info(f"Attempting to update {field} for plate {car_plate} by user {telegram_id}")

    for i, row in enumerate(all_data, start=2):  # start=2 to account for header row
        logger.debug(f"Row {i}: {row}")
        if row.get('Telegram ID') == telegram_id and row.get('Car Plate', '').upper() == car_plate:
            col_index = {
                'Name': 1,
                'Phone Number': 2,
                'Vehicle Type': 3,
                'Car Plate': 4
            }.get(field)
            if col_index:
                sheet.update_cell(i, col_index, new_value)
                logger.info(f"✅ Updated {field} for {car_plate} to {new_value}")

                # If updating name or phone, update across all vehicles
                if field in ["Name", "Phone Number"]:
                    for j, r in enumerate(all_data, start=2):
                        if r.get('Telegram ID') == telegram_id:
                            sheet.update_cell(j, col_index, new_value)
                return True

    logger.warning(f"❌ Could not find record to update for {car_plate}")
    return False

def delete_vehicle(telegram_id, car_plate):
    car_plate = car_plate.upper()
    all_data = sheet.get_all_records()
    for i, row in enumerate(all_data, start=2):
        if row.get('Telegram ID') == telegram_id and row.get('Car Plate', '').upper() == car_plate:
            sheet.update_cell(i, 4, car_plate + "_delete")
            sheet.update_cell(i, 5, str(telegram_id) + "_delete")
            logger.info(f"❌ Marked {car_plate} as deleted")
            return True
    logger.warning(f"❌ Could not find record to delete for {car_plate}")
    return False

def get_existing_user_info(telegram_id):
    data = sheet.get_all_records()
    for row in data:
        if row.get('Telegram ID') == telegram_id and not str(row.get("Car Plate", "")).endswith("_delete"):
            return row.get("Name"), row.get("Phone Number")
    return None, None
