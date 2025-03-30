import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Define the scope for the Google Sheets API
scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

# Authenticate and create a gspread client
credentials = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
client = gspread.authorize(credentials)

# Open the spreadsheet
sheet = client.open('Car Park Data').sheet1  # Replace with the name of your sheet
