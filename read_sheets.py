import os
import json
import gspread
from google.oauth2.service_account import Credentials

# Get JSON key from environment variable
json_key = os.environ.get("GSHEET_KEY")
if not json_key:
    raise ValueError("GSHEET_KEY environment variable not set!")

# Convert JSON string to credentials
creds_dict = json.loads(json_key)
creds = Credentials.from_service_account_info(creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])

# Authorize gspread
client = gspread.authorize(creds)

# Spreadsheet ID
SPREADSHEET_ID = "1GcAWPJzaVvwS0LzO_c2wnWVlgM7Pqw2yg8aRtaMnsT0"
sheet = client.open_by_key(SPREADSHEET_ID).sheet1

# Read all rows
rows = sheet.get_all_records()
for row in rows:
    print(row)