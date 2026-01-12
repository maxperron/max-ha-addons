import gspread
from oauth2client.service_account import ServiceAccountCredentials
import logging
import json
import pandas as pd
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_fixed

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

class GSheetsSync:
    def __init__(self, service_account_payload, sheet_id):
        self.sheet_id = sheet_id
        try:
            if isinstance(service_account_payload, dict):
                self.creds_dict = service_account_payload
            else:
                self.creds_dict = json.loads(service_account_payload)
            
            self.creds = ServiceAccountCredentials.from_json_keyfile_dict(self.creds_dict, SCOPES)
            self.client = gspread.authorize(self.creds)
            self.sheet = self.client.open_by_key(self.sheet_id)
            logger.info("Successfully connected to Google Sheets.")
        except Exception as e:
            logger.error(f"Failed to connect to Google Sheets: {e}")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
    def _get_worksheet(self, title):
        try:
            return self.sheet.worksheet(title)
        except gspread.WorksheetNotFound:
            logger.info(f"Worksheet '{title}' not found. Creating it.")
            return self.sheet.add_worksheet(title=title, rows=1000, cols=20)

    def sync_daily_summary(self, data_list):
        """
        Syncs a list of dictionaries to the Daily_Summary sheet.
        Expects keys: Date, Weight, Sleep_Score, HRV_Status, Resting_HR, etc.
        Upsert logic based on 'Date'.
        """
        worksheet = self._get_worksheet("Daily_Summary")
        self._upsert_data(worksheet, data_list, key_column="Date")

    def sync_nutrition_log(self, data_list):
        """
        Syncs nutrition data.
        Upsert logic based on 'Date' AND 'Food_Item' AND 'Meal_Name' to avoid dupes,
        or better, a composite key or just timestamp. 
        For simplicity, we'll try to match on Date + Timestamp + Food_Item.
        """
        worksheet = self._get_worksheet("Nutrition_Log")
        # Composite key for nutrition: Date + Timestamp + Food_Item
        self._upsert_data(worksheet, data_list, key_column="Timestamp") 

    def sync_workout_details(self, data_list):
        """
        Syncs workout data.
        Upsert logic based on 'Date' and 'Activity_Type' or a unique external ID if available.
        For now, let's use Date + Activity_Type as a proxy for uniqueness if ID isn't clear,
        but Intervals.icu usually has an ID. Let's assume input has unique 'intervals_id' or we rely on Date+Activity.
        """
        worksheet = self._get_worksheet("Workout_Details")
        self._upsert_data(worksheet, data_list, key_column="Date")

    def _upsert_data(self, worksheet, new_data, key_column):
        """
        Generic upsert logic.
        1. Fetch existing data.
        2. Convert to DataFrame.
        3. Merge/Update with new data.
        4. Clear and rewrite sheet (simplest for consistency, though not most efficient for massive sheets).
        """
        if not new_data:
            logger.info("No data to sync.")
            return

        try:
            existing_records = worksheet.get_all_records()
            df_existing = pd.DataFrame(existing_records)
            df_new = pd.DataFrame(new_data)
            
            # Ensure Last_Fetched_At is present
            if "Last_Fetched_At" not in df_new.columns:
                 df_new["Last_Fetched_At"] = datetime.now().isoformat()

            # Normalization
            if not df_existing.empty:
                # Convert key column to string to ensure matching works
                df_existing[key_column] = df_existing[key_column].astype(str)
            df_new[key_column] = df_new[key_column].astype(str)

            if df_existing.empty:
                df_final = df_new
            else:
                # Remove rows in existing that are in new (based on key)
                # This acts as an update
                keys_to_update = df_new[key_column].unique()
                df_existing_filtered = df_existing[~df_existing[key_column].isin(keys_to_update)]
                df_final = pd.concat([df_existing_filtered, df_new], ignore_index=True)

            # Sort by Date if possible
            if "Date" in df_final.columns:
                df_final.sort_values(by="Date", ascending=False, inplace=True)
            
            # Replace NaN with empty string for GSheets
            df_final.fillna("", inplace=True)

            # Write back
            worksheet.clear()
            worksheet.update([df_final.columns.values.tolist()] + df_final.values.tolist())
            logger.info(f"Synced {len(new_data)} records to {worksheet.title}.")

        except Exception as e:
            logger.error(f"Error upserting data to {worksheet.title}: {e}")
            raise
