from garminconnect import Garmin
import logging
from datetime import date, timedelta, datetime

logger = logging.getLogger(__name__)

class GarminSync:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.client = None
        self.login()

    def login(self):
        if not self.email or not self.password:
            logger.error("Garmin email or password is empty.")
            self.client = None
            return

        # Obfuscate email for logging
        email_masked = f"{self.email[:3]}***" if self.email and len(self.email) > 3 else "Unknown"
        logger.info(f"Attempting login for Garmin user: {email_masked}")

        try:
            self.client = Garmin(self.email, self.password)
            self.client.login()
            logger.info("Garmin Connect login successful.")
        except Exception as e:
            logger.error(f"Garmin Connect login failed: {e}", exc_info=True)
            self.client = None # Ensure it is None if failed
            # Do not raise here, allow get_daily_stats to handle graceful exit or retry


    def get_daily_stats(self):
        """
        Fetches today's summary.
        """
        if not self.client:
            logger.error("Garmin client is not authenticated. Attempting login...")
            self.login()
            if not self.client:
                return []

        try:
            today = date.today()
            # Garmin lib often needs explicit reload if session stale, but we'll re-init class or use daemon loop in main
            
            # Stats (HRV, Sleep, Body Battery)
            # Note: library method names change occasionally, staying generic based on v0.1.55 usage
            
            # 1. sleep
            sleep_data = self.client.get_sleep_data(today.isoformat())
            
            # 2. heart rate / stress / body battery (usually in user summary)
            user_summary = self.client.get_user_summary(today.isoformat())

            
            # 3. HRV (might need explicit call)
            hrv_data = self.client.get_hrv_data(today.isoformat())


            # 4. Body Composition (for Weight)
            # 'user_summary' does not contain weight history. We must fetch explicit body composition.
            # Updated to handle list or dict response.
            body_comp = self.client.get_body_composition(today.isoformat())

            
            # Extract weight from body_comp
            # Usually returns a dict with 'totalAverage' -> 'weight' or a list of measurements?
            # Library often returns: {'date': '...', 'totalAverage': {'weight': 89900.0, ...}} # grams?
            # API response structure varies. Let's inspect 'body_comp'. 
            # If it's a dict with 'totalAverage':
            weight_val = None
            if isinstance(body_comp, dict) and "totalAverage" in body_comp:
                 # It might be in grams? Garmin API usually is grams for body comp.
                 # Let's check a sample or assume grams and convert if reasonable (> 1000).
                 w_g = body_comp["totalAverage"].get("weight")
                 if w_g:
                     weight_val = float(w_g) / 1000.0 # to kg
            elif isinstance(body_comp, list) and len(body_comp) > 0:
                # If list of measurements
                w_g = body_comp[-1].get("weight") # Last one?
                if w_g:
                    weight_val = float(w_g) / 1000.0
            
            # Fallback to user_summary if body_comp empty (though we know user_summary is None)
            if not weight_val and user_summary.get("totalWeight"):
                weight_val = float(user_summary.get("totalWeight"))
            
            # Convert to Lbs defaults
            # If weight_val is in KG.
            weight_lbs = None
            if weight_val:
                weight_lbs = weight_val * 2.20462

            # 5. Training Readiness
            readiness_score = None
            try:
                readiness_data = self.client.get_training_readiness(today.isoformat())

                
                 # Log structure showed a LIST of dicts. We want the latest one (sorted by timestamp?) or just the first?
                 # Log example: [{'calendarDate': '2026-01-19', 'timestamp': '2026-01-19T17:57:19.0', 'score': 72...}, {'timestamp': '2026-01-19T13:47...'}]
                 # It seems they are ordered reverse chronological (newest first). Let's take the first.
                if isinstance(readiness_data, list) and len(readiness_data) > 0:
                    readiness_score = readiness_data[0].get("score")
                elif isinstance(readiness_data, dict):
                    readiness_score = readiness_data.get("score")
            except Exception as e:
                logger.warning(f"Could not fetch Training Readiness: {e}")

            # 6. Training Status
            training_status = None
            try:
                training_status_data = self.client.get_training_status(today.isoformat())
                # Log structure: 
                # 'mostRecentTrainingStatus': {'latestTrainingStatusData': {'3505822885': {'trainingStatus': 4, 'trainingStatusFeedbackPhrase': 'MAINTAINING_2', ...}}}
                # It is nested by Device ID (!).
                
                if isinstance(training_status_data, dict):
                    mrts = training_status_data.get("mostRecentTrainingStatus", {})
                    latest_data_map = mrts.get("latestTrainingStatusData", {})
                    
                    # We need to iterate values or find keys.
                    # Or simpler: look for 'trainingStatusFeedbackPhrase' in values.
                    for device_id, device_data in latest_data_map.items():
                        if isinstance(device_data, dict):
                             # Priority to feedback phrase (e.g. "MAINTAINING_2") or usage "trainingStatus" code (4)
                             phrase = device_data.get("trainingStatusFeedbackPhrase")
                             if phrase:
                                 training_status = phrase
                                 break # Assume first valid device is good enough
            except Exception as e:
                logger.warning(f"Could not fetch Training Status: {e}")

            # 7. Hydration
            hydration_ml = None
            try:
                hydration_data = self.client.get_hydration_data(today.isoformat())

                if isinstance(hydration_data, dict):
                    hydration_ml = hydration_data.get("valueInML")
            except Exception as e:
                logger.warning(f"Could not fetch Hydration: {e}")

            # Extract fields
            # Inspect response structure carefully - using .get robustly
            
            summary_record = {
                "Date": today.isoformat(),
                "Weight": weight_lbs,
                "Sleep_Score": sleep_data.get("dailySleepDTO", {}).get("sleepScoreFeedback", None), 
                "Resting_HR": user_summary.get("restingHeartRate", None),
                "Stress_Avg": user_summary.get("averageStressLevel", None),
                "Garmin_Readiness": readiness_score,
                "Garmin_Training_Status": training_status,
                "Garmin_Hydration_ML": hydration_ml,
            }
            
            # HRV might be nested differently
            if hrv_data and 'hrvSummary' in hrv_data:
                summary_record["HRV_Last_Night"] = hrv_data['hrvSummary'].get('lastNightAvg', None)

            return [summary_record]

        except Exception as e:
            logger.error(f"Error fetching Garmin data: {e}")
            # Try re-login once?
            return []

    def add_body_composition(self, weight_kg, timestamp=None):
        """
        Uploads weight (kg) to Garmin Connect.
        """
        if not self.client:
             self.login()
        
        if self.client:
            try:
                # library `add_body_composition` signature:
                # add_body_composition(timestamp, weight, percent_fat=None, ...)
                # Note: timestamp is FIRST argument.
                
                # If timestamp is None, use now?
                # Library likely expects ISO string.
                if not timestamp:
                    from datetime import datetime
                    timestamp = datetime.now().isoformat()
                
                self.client.add_body_composition(timestamp, weight=weight_kg)
                logger.info(f"Uploaded weight {weight_kg}kg to Garmin at {timestamp}.")

            except AttributeError:
                logger.warning("Garmin library 'add_body_composition' method not found. Skipping weight upload.")
            except Exception as e:
                logger.error(f"Failed to upload weight to Garmin: {e}")


