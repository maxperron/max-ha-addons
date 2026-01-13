import logging
from playwright.sync_api import sync_playwright
import os
import time
import pandas as pd
from datetime import datetime, date, timedelta

logger = logging.getLogger(__name__)

class LoseItSync:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.download_dir = "/tmp/loseit_downloads"
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)

    def scrape_recent_history(self):
        """
        Headless browser automation to export CSV.
        """
        data_records = []
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
                context = browser.new_context(accept_downloads=True)
                page = context.new_page()

                logger.info("Navigating to LoseIt login...")
                page.goto("https://www.loseit.com/login")
                
                # Login
                page.fill('input[name="email"]', self.email)
                page.fill('input[name="password"]', self.password)
                page.click('button:has-text("Login")') # Specific selector might need adjustment based on live DOM
                
                # Navigate to the specific Insights URL for Daily Summary
                target_url = "https://www.loseit.com/#Insights:Daily%20Summary%5EDaily%20Summary"
                logger.info(f"Navigating to {target_url}...")
                page.goto(target_url)
                
                logger.info(f"Page URL is now: {page.url}")
                page.wait_for_load_state('networkidle')
                logger.info("Page loaded (networkidle). Looking for export link...")

                # Take screenshot for debug if needed (optional, good for headless)
                # target_screenshot = os.path.join(self.download_dir, "debug_page_view.png")
                # page.screenshot(path=target_screenshot)
                # logger.info(f"Debug screenshot saved to {target_screenshot}")

                logger.info("Waiting for 'Export to spreadsheet' link...")
                # Use a more permissive selector or wait explicitly
                export_selector = 'a:has-text("Export to spreadsheet")'
                try:
                    page.wait_for_selector(export_selector, timeout=10000)
                    logger.info("Found 'Export to spreadsheet' link.")
                except Exception as e:
                    logger.error(f"Could not find export link: {e}")
                    # Attempt to dump HTML for debug
                    # logger.info(f"Page content: {page.content()[:500]}...") 
                    return []

                with page.expect_download() as download_info:
                    logger.info("Clicking export link...")
                    page.click(export_selector)

                download = download_info.value
                logger.info(f"Download initiated. Suggested filename: {download.suggested_filename}")
                
                target_path = os.path.join(self.download_dir, "loseit_export.csv")
                # Delete existing if any
                if os.path.exists(target_path):
                    os.remove(target_path)

                download.save_as(target_path)
                logger.info(f"Downloaded export saved to {target_path}")
                
                # Parse CSV
                if os.path.exists(target_path):
                    logger.info(f"Parsing CSV at {target_path}...")
                    df = pd.read_csv(target_path)
                    
                    # Log columns for debug
                    logger.info(f"CSV Columns found: {df.columns.tolist()}")

                    # Mapping based on user provided DailySummary CSV structure:
                    # Date,Name,Icon,Type,Quantity,Units,Calories,Deleted,Fat (g),Protein (g),Carbohydrates (g),Saturated Fat (g),Sugars (g),Fiber (g),Cholesterol (mg),Sodium (mg)
                    
                    # Normalize columns
                    df.columns = [c.strip() for c in df.columns]

                    for _, row in df.iterrows():
                        # Fill NA with suitable defaults
                        row = row.fillna(0)
                        
                        item_type = str(row.get("Type", "Unknown"))
                        # Filter out Exercise if we only want nutrition?
                        # User goal: "Nutrition Log". Usually excludes exercise calories burned.
                        if item_type == "Exercise":
                            continue

                        date_str = str(row.get("Date", ""))
                        name = str(row.get("Name", "Unknown"))
                        
                        # Create a unique ID/Timestamp for gsheets_sync key
                        # Using Date + Name + Type + Quantity to match unique entries
                        unique_id = f"{date_str}_{name}_{item_type}_{row.get('Quantity', 0)}"

                        record = {
                            "Date": date_str,
                            "Timestamp": unique_id, # Key for GSheets
                            "Food_Item": name,
                            "Meal_Name": item_type,
                            "Quantity": row.get("Quantity", 0),
                            "Units": str(row.get("Units", "")),
                            "Calories": row.get("Calories", 0),
                            "Fat": row.get("Fat (g)", 0),
                            "Protein": row.get("Protein (g)", 0),
                            "Carbohydrates": row.get("Carbohydrates (g)", 0),
                            "Sodium": row.get("Sodium (mg)", 0),
                            "Fiber": row.get("Fiber (g)", 0)
                        }
                        data_records.append(record)
                    
                    logger.info(f"Parsed {len(data_records)} nutrition records.")
            
            return data_records

        except Exception as e:
            logger.error(f"LoseIt scraping failed: {e}")
            return []
