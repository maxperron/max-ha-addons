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

pd.set_option('future.no_silent_downcasting', True)

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
            logger.info("DEBUG: No wellness data provided to sync_wellness_data")
            return

        logger.info(f"DEBUG: Syncing Wellness Data ({len(wellness_data)} records). Example first record: {wellness_data[0]}")

        # Prepare list of flat dictionaries mapping to sheet columns
        # wellness_data keys: date, ctl, atl, rampRate, weight, restingHR, hrv
        # Sheet keys: Date, Intervals_CTL, Intervals_ATL, Intervals_RampRate, Weight, Intervals_RestingHR, Intervals_HRV
        
        normalized_data = []
        for w in wellness_data:
            record = {
                "Date": w.get("date"),
                "Intervals_Fitness": w.get("ctl"),
                "Intervals_Fatigue": w.get("atl"),
                "Intervals_Form": w.get("form_absolute"),
                "Intervals_Form_Percent": w.get("form_percent"),
                "Intervals_RampRate": w.get("rampRate"),
                "Weight": w.get("weight"),
                "Intervals_RestingHR": w.get("restingHR"),
                "Intervals_HRV": w.get("hrv")
            }
            # Remove None values so they don't overwrite existing data with empty if we merge?
            # Actually, _upsert_data merges row-based. If we want partial updates (column based merge), 
            # our current _upsert_data does row-replacement for matching keys.
            # If we want to capabilities to merge columns (e.g. Garmin wrote sleep, Intervals writes CTL),
            # we need a smarter merge in _upsert_data.
            # Current _upsert_data implementation:
            # df_existing_filtered = df_existing[~df_existing[key_column].isin(keys_to_update)]
            # df_final = pd.concat([df_existing_filtered, df_new], ignore_index=True)
            # This completely REPLACES the row. This is BAD for Daily_Summary which aggregates multiple sources.
            
            # We must fix _upsert_data to MERGE data for the same key, not replace.
            normalized_data.append(record)

        worksheet = self._get_worksheet("Daily_Summary")
        self._upsert_data(worksheet, normalized_data, key_column="Date")

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


    def sync_workout_details(self, data_list):
        """
        Syncs workout data.
        Uses incremental merge to handle multiple workouts on same day and updates.
        """
        worksheet = self._get_worksheet("Workout_Details")
        # _incremental_merge_data handles deduplication by Date+Activity logic better 
        # or at least avoids the reindex error by cleaning old data for the dates first.
        self._incremental_merge_data(worksheet, data_list)

    def _upsert_data(self, worksheet, new_data, key_column):
        """
        Generic upsert logic with MERGE support.
        1. Fetch existing data.
        2. Normalize Dates in both Existing and New to ensure matching.
        3. Merge New into Existing (update columns, keep others).
        4. Write back.
        """
        if not new_data:
            logger.info("No data to sync.")
            return

        try:
            existing_records = worksheet.get_all_records()
            df_existing = pd.DataFrame(existing_records)
            df_new = pd.DataFrame(new_data)
            
            # Helper for date normalization
            def reformat_date(d):
                try:
                    if not d: return ""
                    dt = pd.to_datetime(d, errors='coerce')
                    if pd.isnull(dt): return str(d)
                    return dt.strftime("%Y-%m-%d")
                except:
                    return str(d)

            # Ensure Last_Fetched_At is present in new data
            if "Last_Fetched_At" not in df_new.columns:
                 df_new["Last_Fetched_At"] = datetime.now().isoformat()

            # Normalize New Data Dates
            if "Date" in df_new.columns:
                df_new["Date"] = df_new["Date"].apply(reformat_date)
            
            # Normalize Existing Data Dates (Migration)
            if not df_existing.empty and "Date" in df_existing.columns:
                df_existing["Date"] = df_existing["Date"].apply(reformat_date)

            logger.info(f"DEBUG: Columns in df_new: {df_new.columns.tolist()}")
            if not df_existing.empty:
                logger.info(f"DEBUG: Columns in df_existing: {df_existing.columns.tolist()}")

            # Convert key column to string
            df_new[key_column] = df_new[key_column].astype(str)
            if not df_existing.empty:
                df_existing[key_column] = df_existing[key_column].astype(str)
            
            # --- MERGE LOGIC ---
            if df_existing.empty:
                df_final = df_new
            else:
                # set index to key_column for easier updating
                df_existing.set_index(key_column, inplace=True)
                df_new.set_index(key_column, inplace=True)
                
                # Combine: update existing with new values, keep old values where new is missing
                # combine_first() updates nulls in one with values from other, but we want to overwrite.
                # update() overwrites.
                
                # However, df_new might be sparse (only some columns).
                # We want to keep columns in df_existing that are NOT in df_new.
                
                # Align columns: Add missing columns to existing (from new) and vice versa
                # Actually, simpler:
                # 1. For rows in new that are NOT in existing: append.
                # 2. For rows in new that ARE in existing: update specific fields.
                
                # Use pandas update() ?
                # df_existing.update(df_new) -> updates in place.
                # But we need to handle new rows too.
                
                # Split df_new into updates and inserts
                new_keys = df_new.index
                existing_keys = df_existing.index
                
                # Critical Fix: df_existing.update(df_new) ignores columns in df_new that are not in df_existing.
                # We must ensure df_existing has all columns from df_new.
                new_cols = df_new.columns.difference(df_existing.columns)
                if not new_cols.empty:
                    logger.info(f"DEBUG: Found new columns to add to existing sheet: {new_cols.tolist()}")
                    for col in new_cols:
                        df_existing[col] = "" # or pd.NA, "" works well for GSheets

                # Update loop
                df_existing.update(df_new)
                
                # Identify rows that are strictly new
                # (Indices in df_new that are not in df_existing)
                # Note: after update(), df_existing only contains keys it started with.
                to_append = df_new.loc[~new_keys.isin(existing_keys)]
                
                df_final = pd.concat([df_existing, to_append])
                
                # Reset index to make key_column a column again
                df_final.reset_index(inplace=True)

            # Sort by Date if possible
            if "Date" in df_final.columns:
                # We need to sort by actual date value, not the string format "Wednesday..."
                # Create temp sort col
                df_final["_sort_date"] = pd.to_datetime(df_final["Date"], format="%Y-%m-%d", errors='coerce')
                df_final.sort_values(by="_sort_date", ascending=False, inplace=True)
                df_final.drop(columns=["_sort_date"], inplace=True)
            
            # Replace NaN with empty string for GSheets
            df_final.fillna("", inplace=True)

            # Write back
            worksheet.clear()
            # Explicit A1 notation for update to ensure reliability across gspread versions
            data_to_write = [df_final.columns.values.tolist()] + df_final.values.tolist()
            worksheet.update(range_name='A1', values=data_to_write, value_input_option='USER_ENTERED')
            logger.info(f"Synced {len(new_data)} records to {worksheet.title} (merged). Final shape: {df_final.shape}")

        except Exception as e:
            logger.error(f"Error upserting data to {worksheet.title}: {e}")
            raise
    def sync_nutrition_log(self, data_list):
        """
        Syncs nutrition data from Cronometer export.
        Target Sheet: Nutrition_Log
        Columns: Food_Item, Meal_Name, Quantity, Units, Calories, Fat, Protein, Carbohydrates, Last_Fetched_At
        """
        if not data_list:
            return

        normalized_data = []
        now_str = datetime.now().isoformat()
        
        # Expected Cronometer Headers (approximate, based on standard exports)
        # Day, Date, Time, Amount, Unit, Food, Energy (kcal), Protein (g), Net Carbs (g) or Carbs (g), Fat (g), Group?
        
        for row in data_list:
            # Helper to safely get float
            def get_val(key, default="0"):
                v = row.get(key, default)
                return v if v else "0"

            # Date construction: Standard ISO YYYY-MM-DD preferred for sheets
            # Row has "Date" like "2026-01-14" usually? Or "Day"
            date_raw = row.get("Day") or row.get("Date")
            date_formatted = ""
            if date_raw:
                try:
                    # Clean up any potential ' quote chars if they exist in source
                    date_raw = str(date_raw).strip("'")
                    dt = pd.to_datetime(date_raw)
                    date_formatted = dt.strftime("%Y-%m-%d")
                except:
                    date_formatted = str(date_raw)

            # Map Columns
            # Food column might be "Food" or "Food Name" depending on export version
            food_item = row.get("Food Name") or row.get("Food") or row.get("Group") or "Unknown"

            record = {
                "Date": date_formatted, # Required for upsert logic if we use Date as key
                "Food_Item": food_item,
                "Meal_Name": row.get("Group", ""), # "Group" is often used for Meal (Breakfast, Lunch, etc)
                "Quantity": row.get("Amount", ""),
                # "Units": row.get("Unit", ""), # Removed as per user request
                "Calories": get_val("Energy (kcal)"),
                "Fat": get_val("Fat (g)"),
                "Protein": get_val("Protein (g)"),
                "Carbohydrates": get_val("Carbs (g)"),
                "Last_Fetched_At": now_str
            }
            normalized_data.append(record)
            
        worksheet = self._get_worksheet("Nutrition_Log")
        
        # Custom Sync Logic for Nutrition Log: Incremental Sync
        # 1. New data only contains today (or specific range).
        # 2. We need to KEEP history that is NOT in the new data's date range.
        # 3. But we must OVERWRITE data for dates that ARE in the new data (to handle deletions/edits).
        
        self._incremental_merge_data(worksheet, normalized_data)

    def _incremental_merge_data(self, worksheet, new_data):
        """
        Merges new data with existing sheet data.
        Strategy:
        1. Read all existing data.
        2. Identify dates present in new_data.
        3. Remove ALL rows from existing data that match those dates.
        4. Append new_data.
        5. Sort and Write.
        """
        if not new_data:
            return

        try:
            # 1. Read existing
            existing_records = worksheet.get_all_records()
            df_existing = pd.DataFrame(existing_records)
            
            # New Data DF
            df_new = pd.DataFrame(new_data)
            
            if df_existing.empty:
                # If sheet is empty, just write new
                df_final = df_new
            else:
                # 2. Identify dates in new data
                # Ensure we are comparing same types (strings YYYY-MM-DD)
                if "Date" not in df_new.columns:
                     logger.warning("New data missing Date column, cannot merge reliably. Replacing all.")
                     self._replace_all_data(worksheet, new_data)
                     return

                new_dates = df_new["Date"].unique()
                
                # 3. Remove rows from existing that match new_dates
                # Ensure existing Date column is string
                if "Date" in df_existing.columns:
                    # Filter: Keep rows where Date is NOT in new_dates
                    df_existing = df_existing[~df_existing["Date"].isin(new_dates)]
                
                # 4. Append
                df_final = pd.concat([df_existing, df_new], ignore_index=True)

            # 5. Sort and Write
            if "Date" in df_final.columns:
                df_final["_sort"] = pd.to_datetime(df_final["Date"], format="%Y-%m-%d", errors='coerce')
                df_final.sort_values(by="_sort", ascending=False, inplace=True)
                df_final.drop(columns=["_sort"], inplace=True)
                
            df_final.fillna("", inplace=True)
            
            worksheet.clear()
            data_to_write = [df_final.columns.values.tolist()] + df_final.values.tolist()
            worksheet.update(range_name='A1', values=data_to_write, value_input_option='USER_ENTERED')
            logger.info(f"Merged {len(new_data)} new records into {worksheet.title}. Total rows: {len(df_final)}")

        except Exception as e:
            logger.error(f"Failed to merge data in {worksheet.title}: {e}")
            raise
        """
        Replaces entire sheet content with new data.
        """
        if not data:
            return
            
        df = pd.DataFrame(data)
        
        # Sort by Date descending
        if "Date" in df.columns:
            df["_sort"] = pd.to_datetime(df["Date"], format="%Y-%m-%d", errors='coerce')
            df.sort_values(by="_sort", ascending=False, inplace=True)
            df.drop(columns=["_sort"], inplace=True)
            
        df.fillna("", inplace=True)
        
        try:
            worksheet.clear()
            data_to_write = [df.columns.values.tolist()] + df.values.tolist()
            # value_input_option='USER_ENTERED' forces Sheets to parse strings (dates, numbers)
            worksheet.update(range_name='A1', values=data_to_write, value_input_option='USER_ENTERED')
            logger.info(f"Replaced {worksheet.title} with {len(data)} rows.")
        except Exception as e:
            logger.error(f"Failed to replace data in {worksheet.title}: {e}")
            raise
            logger.info(f"Replaced {worksheet.title} with {len(data)} rows.")
        except Exception as e:
            logger.error(f"Failed to replace data in {worksheet.title}: {e}")
            raise
