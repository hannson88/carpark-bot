import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Define the scope for Google Sheets API
scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
SHEET_NAME = "CarParkBot"

# Authenticate and create the gspread client
CREDS = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", SCOPE)
client = gspread.authorize(CREDS)

# Open the Google Sheet
sheet = client.open(SHEET_NAME).sheet1

def register_user(name, phone, model, plate, telegram_id):
    plate = plate.upper()  # Ensure plate is stored in uppercase
    sheet.append_row([name, phone, model, plate, telegram_id])  # Write data to Google Sheets
    logger.info(f"✅ Registered {name} with plate {plate}")

def find_users_by_plate(plates):
    results = []
    data = sheet.get_all_records()  # Fetch all rows from the Google Sheet
    for row in data:
        car_plate = row.get('Car Plate', '').strip().upper()  # Safe access for 'Car Plate'
        if car_plate and car_plate in plates:
            results.append(row)
    return results