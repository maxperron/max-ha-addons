from garminconnect import Garmin
import logging
from datetime import date, timedelta

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

            # Extract fields
            # Inspect response structure carefully - using .get robustly
            
            summary_record = {
                "Date": today.isoformat(),
                "Weight": user_summary.get("totalWeight", ""), # Might be grams
                "Sleep_Score": sleep_data.get("dailySleepDTO", {}).get("sleepScoreFeedback", ""), # or sleepScore
                "Resting_HR": user_summary.get("restingHeartRate", ""),
                "Body_Battery_High": user_summary.get("maxBodyBattery", ""), # example
                "Body_Battery_Low": user_summary.get("minBodyBattery", ""),
                "Total_Calories_In": "", # Garmin usually tracks burned. Consumed comes from MFP connection if set.
                "Stress_Avg": user_summary.get("averageStressLevel", ""),
            }
            
            # HRV might be nested differently
            if hrv_data and 'hrvSummary' in hrv_data:
                summary_record["HRV_Status"] = hrv_data['hrvSummary'].get('weeklyAverage', "") # proxy
                summary_record["HRV_Last_Night"] = hrv_data['hrvSummary'].get('lastNightAvg', "")

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
            except Exception as e:
                logger.error(f"Failed to upload weight to Garmin: {e}")

    def get_hydration_data(self, date_str):
        """
        Get hydration data for a specific date (YYYY-MM-DD).
        Returns current intake in ml (int) or 0.
        """
        if not self.client:
             self.login()
        
        if self.client:
            try:
                # API usually returns a dict with 'valueInMl' or similar
                data = self.client.get_hydration_data(date_str)
                # Inspecting typical response: {'date': '...', 'valueInMl': 250, 'goalInMl': 2000}
                # Check for 'valueInMl'
                if data and 'valueInMl' in data:
                    return int(data['valueInMl'])
                return 0
            except Exception as e:
                logger.error(f"Failed to get hydration from Garmin: {e}")
                return 0
        return 0

    def add_hydration(self, quantity_ml):
        """
        Add hydration (ml) to Garmin Connect using internal API.
        """
        if not self.client:
             self.login()
        
        if self.client:
            try:
                # Use internal 'connectapi' to hit the endpoint directly
                # Endpoint: /usersummary-service/usersummary/hydration/log
                # Method: PUT
                # Body: {"valueInML": 250, "calendarDate": "YYYY-MM-DD"}
                
                today_str = date.today().isoformat()
                
                url = "/usersummary-service/usersummary/hydration/log"
                data = {
                    "valueInML": quantity_ml,
                    "calendarDate": today_str
                }
                
                # Check if connectapi exists (it should in cyberjunky lib)
                if hasattr(self.client, 'connectapi'):
                    self.client.connectapi(url, method='PUT', json=data)
                    logger.info(f"Added {quantity_ml}ml hydration to Garmin via internal API.")
                else:
                    logger.error("Garmin client does not support 'connectapi' method.")
                    
            except Exception as e:
                logger.error(f"Failed to add hydration to Garmin: {e}")
