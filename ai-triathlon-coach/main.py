import schedule
import time
import logging
import json
import os
import sys
from datetime import datetime, timedelta
import threading
import struct
import requests
from flask import Flask, request
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
        
        # 2. FETCH DATA
        
        # A. Wellness (Prioritized)
        # User requested Fitness, Fatigue, Form check.
        wellness = in_svc.get_wellness_data(hist_start_str, hist_end_str)
        if wellness:
            ws.sync_wellness_data(wellness)

        # B. Actual Activities
        activities = in_svc.get_activities(hist_start_str, hist_end_str)
        
        # C. Planned Workouts (Forecast)
        planned = in_svc.get_planned_workouts(future_start_str, future_end_str)
        
        # Combine Workouts (Upserting to same sheet)
        all_workouts = []
        if activities:
            all_workouts.extend(activities)
        if planned:
            all_workouts.extend(planned)
            
        if all_workouts:
            ws.sync_workout_details(all_workouts)

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
        # 2. Get Weight & Hydration
        # Weight
        result_weight = fb.get_latest_weight() 
        gs = GarminSync(config["garmin_username"], config["garmin_password"])

        if result_weight:
            weight_kg, timestamp = result_weight
            logger.info(f"Retrieved weight from Fitbit: {weight_kg} kg at {timestamp}")
            gs.add_body_composition(weight_kg, timestamp)
        else:
            logger.info("No recent weight found in Fitbit.")

    except Exception as e:
        logger.error(f"Weight Sync Failed: {e}")

# --- WEB SERVER FOR FITBIT ARIA ---
app = Flask(__name__)


@app.route('/scale/upload', methods=['POST'])
def aria_upload():
    """
    Handle data upload from Fitbit Aria scale.
    The scale sends data as a binary file upload with key 'dump'.
    Weight in grams is a 4-byte big-endian uint at offset 54 (0x36).
    """
    try:
        logger.info(f"Received Aria Request from {request.remote_addr}")
        
        if 'dump' in request.files:
            binary_data = request.files['dump'].read()
            logger.info(f"Received 'dump' file, size: {len(binary_data)} bytes")
            
            # Basic validation of size
            if len(binary_data) < 60:
                logger.error("Binary dump too short to contain weight data.")
                return "Error: Data too short", 400

            # Parse Weight
            # Offset 0x36 (54) is weight in grams (4-byte uint)
            try:
                weight_grams = struct.unpack('>I', binary_data[54:58])[0]
                weight_kg = round(weight_grams / 1000.0, 2)
                
                logger.info(f"Parsed Weight: {weight_grams}g ({weight_kg}kg)")
                
                # Sync to Garmin
                # We need to reload config to get credentials as they might not be globally available in this scope easily
                # actually 'load_config' is available.
                config = load_config()
                if config.get("garmin_username") and config.get("garmin_password"):
                    logger.info("Syncing weight to Garmin...")
                    gs = GarminSync(config["garmin_username"], config["garmin_password"])
                    # Use current timestamp
                    timestamp = datetime.now()
                    gs.add_body_composition(weight_kg, timestamp)
                    logger.info("Garmin Sync Successful.")
                else:
                    logger.warning("Garmin credentials missing, skipping sync.")

                return "OK", 200

            except Exception as parse_e:
                logger.error(f"Error parsing/processing weight: {parse_e}")
                return "Error processing", 500
        
        else:
            logger.warning("No 'dump' file in request.")
            return "No payload", 400
        
    except Exception as e:
        logger.error(f"Error handling Aria upload: {e}")
        return "Error", 500

def run_web_server():
    logger.info("Starting Web Server on port 8000...")
    # debug=False, use_reloader=False is important for threading
    app.run(host='0.0.0.0', port=8000, debug=False, use_reloader=False)

def main():
    logger.info("Initializing AI Triathlon Coach Data Bridge...")
    config = load_config()

    # Start Web Server in Background Thread
    server_thread = threading.Thread(target=run_web_server, daemon=True)
    server_thread.start()

    # Visual Log Clear for Add-on users
    print("\n" * 50)
    print("=" * 60)
    print("   AI TRIATHLON COACH - DATA BRIDGE STARTED")
    print(f"   Version: {config.get('version', 'Unknown')}")
    print("=" * 60)
    
    interval = config.get("sync_interval_minutes", 60)
    
    # Schedule jobs
    schedule.every(interval).minutes.do(job_sync_garmin, config)
    schedule.every(interval).minutes.do(job_sync_intervals, config)
    
    # Weight sync might not need to run every hour, but consistent with others is fine.
    schedule.every(interval).minutes.do(job_sync_weight, config)
    schedule.every(interval).minutes.do(job_sync_cronometer, config)
    
    # Run once on startup
    logger.info("Running initial sync...")
    job_sync_garmin(config)
    job_sync_intervals(config)
    job_sync_weight(config) # Assuming Fitbit is configured
    job_sync_cronometer(config)
    
    logger.info(f"Scheduler started. Heartbeat every {interval} minutes.")
    
    while True:
        schedule.run_pending()
        time.sleep(1)

def job_sync_cronometer(config):
    logger.info("Starting Cronometer Sync...")
    try:
        from cronometer_sync import CronometerSync
        
        if not config.get("cronometer_username") or not config.get("cronometer_password"):
            logger.warning("Cronometer credentials missing. Skipping sync.")
            return

        # Initialize Client
        # We can pass date range if we want incremental, but export usually gives full or recent.
        # cronometer_sync.get_servings_data defaults to full export approach if no dates.
        cs = CronometerSync(config["cronometer_username"], config["cronometer_password"])
        
        # Fetch Data
        data = cs.get_servings_data()
        
        if data:
            # Sync to Sheet
            ws = GSheetsSync(config["google_sheets_service_account_json"], config["google_sheet_id"])
            ws.sync_nutrition_log(data)
            logger.info("Cronometer Sync Completed.")
        else:
            logger.info("No data retrieved from Cronometer.")
            
    except Exception as e:
        logger.error(f"Cronometer Sync Failed: {e}")

if __name__ == "__main__":
    main()
