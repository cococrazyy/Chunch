import os
import json
import gspread
from google.oauth2.service_account import Credentials

# 1️⃣ Get JSON key from environment variable
json_key = os.environ.get("GSHEET_KEY")
if not json_key:
    raise ValueError("GSHEET_KEY environment variable not set!")

# 2️⃣ Convert JSON string to dictionary
creds_dict = json.loads(json_key)

# 3️⃣ Create credentials object
scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)

# 4️⃣ Authorize gspread client
client = gspread.authorize(creds)

# 5️⃣ Open the sheet by spreadsheet ID
SPREADSHEET_ID = "1GcAWPJzaVvwS0LzO_c2wnWVlgM7Pqw2yg8aRtaMnsT0"
sheet = client.open_by_key(SPREADSHEET_ID).sheet1

# 6️⃣ Read all rows
rows = sheet.get_all_records()

# Save directly in repo
with open("data/sheet_data.json", "w", encoding="utf-8") as f:
    json.dump(rows, f, indent=4, ensure_ascii=False)

print(f"Saved {len(rows)} rows to sheet_data.json")