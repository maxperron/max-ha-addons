import schedule
import time
import logging
import json
import os
import sys
from datetime import datetime, timedelta
from garmin_sync import GarminSync
from intervals_sync import IntervalsSync
from loseit_sync import LoseItSync
from gsheets_sync import GSheetsSync

# Configure logging to stdout for HA Add-on visibility
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Main")

# Load Configuration
CONFIG_PATH = "/data/options.json"
# Fallback for local testing
if not os.path.exists(CONFIG_PATH):
    CONFIG_PATH = "config.yaml" # Crude fallback, really should be options.json structure

def load_config():
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Could not load config: {e}")
        return {}

def job_sync_garmin(config):
    logger.info("Starting Garmin Sync...")
    try:
        if not config.get("garmin_username"):
            logger.warning("Garmin credentials missing.")
            return

        gs = GarminSync(config["garmin_username"], config["garmin_password"])
        data = gs.get_daily_stats()
        
        # Prepare Service Account JSON: it might be a dict or a string depending on how HA parsed it
        service_account = config["google_sheets_service_account_json"]
        if isinstance(service_account, str):
            # If it's a string, it might be JSON string or just a string.
            # GSheetsSync expects the raw value to parse itself, OR a dict.
            # Let's pass it raw, GSheetsSync will handle safe parsing.
            pass
        
        ws = GSheetsSync(service_account, config["google_sheet_id"])
        ws.sync_daily_summary(data)
        logger.info("Garmin Sync Completed.")
    except Exception as e:
        logger.error(f"Garmin Sync Failed: {e}")

def job_sync_intervals(config):
    logger.info("Starting Intervals.icu Sync...")
    try:
        if not config.get("intervals_api_key"):
            logger.warning("Intervals credentials missing.")
            return

        in_svc = IntervalsSync(config["intervals_api_key"], config["intervals_athlete_id"])
        ws = GSheetsSync(config["google_sheets_service_account_json"], config["google_sheet_id"])

        # Define date range for fetching data
        # We want last 3 days (history) AND next 7 days (planned workouts)
        today = datetime.now()
        start_date = today - timedelta(days=3) 
        end_date = today + timedelta(days=7)

        # Format dates as YYYY-MM-DD strings
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")
        
        # 1. Fetch Activities
        activities = in_svc.get_activities(start_date_str, end_date_str)
        if activities:
            ws.sync_workout_details(activities) # Assuming sync_workout_details is the correct method
        
        # 2. Fetch Wellness
        wellness = in_svc.get_wellness_data(start_date_str, end_date_str)
        if wellness:
            ws.sync_wellness_data(wellness)

        logger.info("Intervals Sync Completed.")
    except Exception as e:
        logger.error(f"Intervals Sync Failed: {e}")

def job_sync_loseit(config):
    logger.info("Starting LoseIt Sync...")
    try:
        if not config.get("loseit_email"):
            logger.warning("LoseIt credentials missing.")
            return

        ls = LoseItSync(config["loseit_email"], config["loseit_password"])
        data = ls.scrape_recent_history()
        
        if data:
            ws = GSheetsSync(config["google_sheets_service_account_json"], config["google_sheet_id"])
            ws.sync_nutrition_log(data)
            logger.info("LoseIt Sync Completed.")
        else:
            logger.info("No LoseIt data found or scrape failed.")
    except Exception as e:
        logger.error(f"LoseIt Sync Failed: {e}")

def main():
    logger.info("Initializing AI Triathlon Coach Data Bridge...")
    config = load_config()
    
    interval = config.get("sync_interval_minutes", 60)
    
    # Schedule jobs
    schedule.every(interval).minutes.do(job_sync_garmin, config)
    schedule.every(interval).minutes.do(job_sync_intervals, config)
    schedule.every(interval * 6).minutes.do(job_sync_loseit, config) # Scrape less often
    
    # Run once on startup
    logger.info("Running initial sync...")
    job_sync_garmin(config)
    job_sync_intervals(config)
    job_sync_loseit(config)
    
    logger.info(f"Scheduler started. Heartbeat every {interval} minutes.")
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
