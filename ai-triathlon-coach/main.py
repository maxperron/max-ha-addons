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



# --- WEB SERVER FOR FITBIT ARIA ---
app = Flask(__name__)



# --- CRC16-CCITT (XMODEM) Implementation ---
def crc16_ccitt(data):
    """
    Calculate CRC-16-CCITT (XMODEM variant) for the given data.
    Poly: 0x1021, Init: 0x0000, RefIn: False, RefOut: False, XorOut: 0x0000
    """
    crc = 0x0000
    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            if (crc & 0x8000):
                crc = (crc << 1) ^ 0x1021
            else:
                crc = (crc << 1)
        crc &= 0xFFFF
    return crc

@app.route('/scale/upload', methods=['POST'])
def aria_upload():
    """
    Handle data upload from Fitbit Aria scale.
    The scale sends data as a binary file upload with key 'dump'.
    Weight in grams is a 4-byte big-endian uint at offset 54 (0x36).
    """
    try:
        logger.info(f"Received Aria Request from {request.remote_addr}")

        # The Aria 1 scale sends a binary payload but with Content-Type: application/x-www-form-urlencoded
        # This causes Flask to attempt to parse it as form data, which consumes the stream and leaves it empty.
        # We must read the raw stream FIRST, before accessing request.files or request.form.
        
        binary_data = request.get_data()
        logger.info(f"Read raw body: {len(binary_data)} bytes")
        
        # Determine if we have data to process
        data_packet = None
        
        # Strategy 1: Use raw body if it looks like the dump (size > 60)
        if len(binary_data) > 60:
            data_packet = binary_data
            
        # Strategy 2: If raw body looks empty/small, try request.files (maybe multipart?)
        elif 'dump' in request.files:
            # If get_data didn't consume it (unexpected but possible), try files
            logger.info("Raw body small, checking request.files['dump']...")
            data_packet = request.files['dump'].read()
            logger.info(f"Read dump file: {len(data_packet)} bytes")

        if data_packet and len(data_packet) >= 60:
            # Parse Weight
            # Offset 0x36 (54) is weight in grams (4-byte uint).
            # Blog post (fitbit-mitm) parses this as Little Endian:
            # $value = ($bytes[4] << 24) | ($bytes[3] << 16) | ($bytes[2] << 8) | $bytes[1];
            try:
                # Use Little Endian <I
                weight_grams = struct.unpack('<I', data_packet[54:58])[0]
                weight_kg = round(weight_grams / 1000.0, 2)
                
                # Attempt to identify User
                user_id = request.args.get('userId') or request.args.get('user')
                # If not in args, try binary offset 8 (common in Aria 1)
                if not user_id and len(data_packet) >= 12:
                     try:
                        user_id_int = struct.unpack('<I', data_packet[8:12])[0]
                        user_id = f"Binary:{user_id_int}"
                     except:
                        pass
                
                logger.info(f"Parsed Weight: {weight_grams}g ({weight_kg}kg) for User: {user_id}")
                
                # Sync to Garmin in Background Thread to prevent 504 Timeout on Scale
                def sync_weight_background(w_kg, conf):
                    try:
                        if conf.get("garmin_username") and conf.get("garmin_password"):
                            logger.info("Background: Syncing weight to Garmin...")
                            gs = GarminSync(conf["garmin_username"], conf["garmin_password"])
                            # Use current timestamp
                            timestamp = datetime.now().isoformat()
                            gs.add_body_composition(w_kg, timestamp)
                            logger.info("Background: Garmin Weight Sync Successful.")
                        else:
                            logger.warning("Background: Garmin credentials missing, skipping sync.")
                    except Exception as bg_e:
                        logger.error(f"Background: Error syncing weight to Garmin: {bg_e}")

                config = load_config()
                # Start the background thread
                sync_thread = threading.Thread(target=sync_weight_background, args=(weight_kg, config))
                sync_thread.start()
                logger.info(f"Started background thread for Garmin weight sync ({weight_kg}kg)")

                # Construct SUCCESS Response for Aria
                # Structure:
                #   timestamp (4 bytes)
                #   units (1 byte) - 2 = kg
                #   status (1 byte) - 0x32 (configured)
                #   unknown1 (1 byte) - 0x01
                #   user_count (4 bytes) - 0 (no users being synced back)
                #   update_available (4 bytes) - 0x03 (no)
                #   unknown2 (4 bytes) - 3
                #   unknown3 (4 bytes) - 0
                
                resp_ts = int(datetime.now().timestamp())
                
                # Build Body
                # <I (Little Endian) for 4-byte fields? Protocol says uint32.
                # Assuming Little Endian based on previous finding.
                # struct.pack format:
                # I (4), B (1), B (1), B (1), I (4), I (4), I (4), I (4)
                
                resp_body = struct.pack(
                    '<IBBBIIII',
                    resp_ts,        # current_timestamp
                    2,              # units (kg)
                    0x32,           # status (configured)
                    0x01,           # unknown1
                    0,              # user_count
                    0x03,           # update_available (no)
                    3,              # unknown2
                    0               # unknown3
                )
                
                # Calculate CRC
                crc_val = crc16_ccitt(resp_body)
                
                # Build Envelope
                # Body + CRC (2 bytes) + unknown2 (1 byte 0x66) + unknown3 (1 byte 0x00)
                # Using Big Endian '>H' for CRC as standard network byte order, despite payload being LE.
                resp_envelope = resp_body + struct.pack('>H', crc_val) + b'\x66\x00'
                
                logger.info(f"Sending binary success response ({len(resp_envelope)} bytes)")
                return resp_envelope, 200

            except Exception as parse_e:
                logger.error(f"Error parsing/processing weight: {parse_e}")
                return "Error processing", 500
        
        else:
            logger.warning(f"No valid data packet found. Raw size: {len(binary_data)}")
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
    schedule.every(interval).minutes.do(job_sync_cronometer, config)
    
    # Run once on startup
    logger.info("Running initial sync...")
    job_sync_garmin(config)
    job_sync_intervals(config)
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
