import gspread
from oauth2client.service_account import ServiceAccountCredentials

SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
SHEET_NAME = "CarParkBot"

CREDS = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", SCOPE)
client = gspread.authorize(CREDS)
sheet = client.open(SHEET_NAME).sheet1

def register_user(name, phone, model, plate, telegram_id):
    sheet.append_row([name, phone, model, plate.upper(), telegram_id])

def find_users_by_plate(plates):
    data = sheet.get_all_records()
    return [row for row in data if row['Car Plate'].strip().upper() in plates]