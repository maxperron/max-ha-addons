import schedule
import time
import logging
import json
import os
import sys
from datetime import datetime, timedelta
from garmin_sync import GarminSync
from intervals_sync import IntervalsSync

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

        # 1. TIMEFRAMES
        today = datetime.now()
        
        # History Window (Last 3 days to Today)
        hist_start = today - timedelta(days=3)
        hist_end = today
        hist_start_str = hist_start.strftime("%Y-%m-%d")
        hist_end_str = hist_end.strftime("%Y-%m-%d")

        # Future Window (Tomorrow to T+7)
        # We can include today in future to catch today's planned workout if not completed yet?
        # Let's start from today for planned, so we see what is remaining.
        future_start = today
        future_end = today + timedelta(days=7)
        future_start_str = future_start.strftime("%Y-%m-%d")
        future_end_str = future_end.strftime("%Y-%m-%d")
        
        # 2. FETCH HISTORY (Activities & Wellness)
        # A. Actual Activities
        activities = in_svc.get_activities(hist_start_str, hist_end_str)
        
        # B. Planned Workouts (Forecast)
        planned = in_svc.get_planned_workouts(future_start_str, future_end_str)
        
        # Combine Workouts (Upserting to same sheet)
        all_workouts = []
        if activities:
            all_workouts.extend(activities)
        if planned:
            all_workouts.extend(planned)
            
        if all_workouts:
            ws.sync_workout_details(all_workouts)
        
        # C. Wellness (History Only - predictions usually not retrievable via simple wellness ep?)
        # User said "7 days plan was NOT for fitness fatigue..." so we stick to history for wellness.
        wellness = in_svc.get_wellness_data(hist_start_str, hist_end_str)
        if wellness:
            ws.sync_wellness_data(wellness)

        logger.info("Intervals Sync Completed.")
    except Exception as e:
        logger.error(f"Intervals Sync Failed: {e}")

def job_sync_weight(config):
    logger.info("Starting Weight Sync (Fitbit -> Garmin)...")
    try:
        from fitbit_sync import FitbitSync
        
        if not config.get("fitbit_client_id") or not config.get("fitbit_client_secret"):
            logger.warning("Fitbit credentials missing. Skipping weight sync.")
            return

        # 1. Init Fitbit
        # We need a token file path. Add-on usually has persistence at /data
        token_path = "/data/fitbit_token.json"
        # For local testing fallback
        if not os.path.exists("/data"):
            token_path = "fitbit_token.json"
            
        fb = FitbitSync(
            config["fitbit_client_id"], 
            config["fitbit_client_secret"], 
            config.get("fitbit_initial_refresh_token"),
            token_file=token_path
        )
        
        # 2. Get Weight
        result = fb.get_latest_weight() 
        # Check if result is tuple or None
        if result:
            weight_kg, timestamp = result
            
            # User confirmed Fitbit returns KG. No conversion needed.
            logger.info(f"Retrieved weight from Fitbit: {weight_kg} kg at {timestamp}")
            
            gs = GarminSync(config["garmin_username"], config["garmin_password"])
            gs.add_body_composition(weight_kg, timestamp)
        else:
            logger.info("No recent weight found in Fitbit.")
        else:
            logger.info("No recent weight found in Fitbit.")

    except Exception as e:
        logger.error(f"Weight Sync Failed: {e}")

def main():
    logger.info("Initializing AI Triathlon Coach Data Bridge...")
    config = load_config()
    
    interval = config.get("sync_interval_minutes", 60)
    
    # Schedule jobs
    schedule.every(interval).minutes.do(job_sync_garmin, config)
    schedule.every(interval).minutes.do(job_sync_intervals, config)
    
    # Weight sync might not need to run every hour, but consistent with others is fine.
    schedule.every(interval).minutes.do(job_sync_weight, config)
    
    # Run once on startup
    logger.info("Running initial sync...")
    job_sync_garmin(config)
    job_sync_intervals(config)
    job_sync_weight(config)
    
    logger.info(f"Scheduler started. Heartbeat every {interval} minutes.")
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
