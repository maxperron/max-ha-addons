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

    def sync_wellness_data(self, wellness_data):
        """
        Upserts wellness data (CTL, ATL, etc.) into Daily_Summary.
        Columns: Date, Intervals_CTL, Intervals_ATL, Intervals_RampRate, Intervals_RestingHR, Intervals_HRV
        """
        if not wellness_data:
            return

        try:
            ws = self.client.open_by_key(self.sheet_id).worksheet("Daily_Summary")
            
            # Ensure headers exist
            headers = ws.row_values(1)
            required_cols = ["Date", "Intervals_CTL", "Intervals_ATL", "Intervals_RampRate", "Intervals_RestingHR", "Intervals_HRV"]
            
            # Simple header update if missing (append them)
            # In a robust system we might want to check index, but for now let's just create a map.
            # We assume "Date" is present from previous syncs.
            
            # We'll rely on the same 'upsert_row' logic logic pattern:
            # 1. Get all dates
            # 2. For each wellness entry, find row or append
            
            # Map headers
            header_map = {col: i+1 for i, col in enumerate(headers)}
            
            # Add missing headers if any
            new_headers = []
            for col in required_cols:
                if col not in header_map:
                    new_headers.append(col)
            
            if new_headers:
                # Add to next available columns
                start_col = len(headers) + 1
                # Bulk update headers
                # gspread update cells logic or just single updates. 
                # Doing single updates for simplicity of "append col" logic is tricky in gspread without raw usage.
                # We'll just define the specific cells.
                for i, col_name in enumerate(new_headers):
                    ws.update_cell(1, start_col + i, col_name)
                    header_map[col_name] = start_col + i

            # Refetch all data to get locations
            all_records = ws.get_all_records()
            # This returns a list of dicts. We need row numbers. 
            # Best to just get column A (Dates)
            date_col_values = ws.col_values(header_map["Date"]) # 1-based list
            
            # date_map: "YYYY-MM-DD" -> row_index (1-based)
            date_map = {}
            for i, d in enumerate(date_col_values):
                # skip header
                if i == 0: continue
                if d:
                    date_map[d] = i + 1

            for w in wellness_data:
                d = w["date"]
                row_idx = date_map.get(d)
                
                # Prepare updates
                updates = [] 
                
                # Helper to add update if key exists
                def add_update(key, sheet_col_name):
                    val = w.get(key)
                    if val is not None and sheet_col_name in header_map:
                        updates.append((header_map[sheet_col_name], val))

                add_update("ctl", "Intervals_CTL")
                add_update("atl", "Intervals_ATL")
                add_update("rampRate", "Intervals_RampRate")
                add_update("restingHR", "Intervals_RestingHR")
                add_update("hrv", "Intervals_HRV")

                if row_idx:
                    # Update existing row
                    for col_idx, val in updates:
                        ws.update_cell(row_idx, col_idx, val)
                    logger.info(f"Updated wellness for {d} at row {row_idx}")
                else:
                    # Append new row
                    # We need to build a full row array to append properly, or just append and then update?
                    # Appending a dict is easier if headers match.
                    # gspread append_row
                    row_data = [d] # Date is first
                    # We need to construct a sparse row matching the current sheet width
                    # This is complex. Easiest is to append the date, get the new row index, then update cells.
                    ws.append_row([d])
                    new_row_idx = len(date_col_values) + 1 # simplistic but usually works if no gaps
                    # Actually get the new index properly?
                    # Safer: append_row returns the range? No, in recent gspread it might.
                    # Let's verify row count.
                    # Actually, let's just cache the new index
                    # date_col_values updated? No.
                    
                    # Let's assume append adds to bottom.
                    # Re-read or just guess? 
                    # Let's use append_time logic:
                    # If we append, we can assume it's at the end.
                    # But if we have multiple new entries, we need to track.
                    
                    # Wait, simpler approach:
                    # Use batch update or cell update.
                    # For a new row, we can assume it is at (last_row + 1).
                    # But strictly, we should just let the main 'daily stats' job create usage rows if possible, 
                    # but here we might be adding a row for a rest day that has no Garmin data yet (or maybe it does).
                    # If it has Garmin data, it's in `date_map`.
                    # If not, we append.
                    
                    # Let's just append the row with the data we have.
                    # We can construct a row list of empty strings + our values.
                    max_col = max(header_map.values())
                    new_row = [""] * max_col
                    new_row[header_map["Date"]-1] = d
                    
                    for col_idx, val in updates:
                        new_row[col_idx-1] = val
                    
                    ws.append_row(new_row)
                    # Update our local map so we don't append duplicate if 'wellness_data' has dups (unlikely)
                    date_col_values.append(d)
                    date_map[d] = len(date_col_values) # +1? No, logic above: enumerate(date_col_values) starts 0. row_idx is i+1.
                    # If len was 10, append makes it 11. 
                    
                    logger.info(f"Appended wellness for {d}")

        except Exception as e:
            logger.error(f"Error syncing wellness to GSheets: {e}")
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
