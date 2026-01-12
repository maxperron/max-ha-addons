import requests
import logging
from datetime import date, datetime, timedelta
import base64

logger = logging.getLogger(__name__)

class IntervalsSync:
    def __init__(self, api_key, athlete_id):
        self.api_key = api_key
        self.athlete_id = athlete_id
        self.base_url = f"https://intervals.icu/api/v1/athlete/{self.athlete_id}"
        
        # Basic Auth for Intervals
        # "API_KEY" corresponds to the password, username is "API_KEY" literal string usually or just standard basic auth
        # Intervals doc: use Basic Auth with separate username 'API_KEY' and password your_api_key
        auth_str = f"API_KEY:{self.api_key}"
        self.headers = {
            "Authorization": f"Basic {base64.b64encode(auth_str.encode()).decode()}"
        }

    def get_activities(self):
        """
        Fetch completed activities for last few days.
        """
        today = date.today()
        start_date = (today - timedelta(days=7)).isoformat()
        end_date = today.isoformat()
        
        url = f"{self.base_url}/activities?oldest={start_date}&newest={end_date}"
        
        try:
            resp = requests.get(url, headers=self.headers)
            resp.raise_for_status()
            activities = resp.json()
            
            records = []
            for act in activities:
                # Only process if completed or has data
                desc = act.get("description", "")
                
                record = {
                    "Date": act.get("start_date_local", "")[:10], # Extract YYYY-MM-DD
                    "Activity_Type": act.get("type", ""),
                    "Duration_Mins": (act.get("moving_time") or 0) / 60,
                    "Distance_Km": (act.get("distance") or 0) / 1000,
                    "Intervals_Description": desc, # Structured workout text usually here or in 'icu_training_load_data'
                    "Training_Load_TSS": act.get("icu_training_load") or 0,
                    "Average_HR": act.get("average_heartrate", ""),
                    "RPE": act.get("perceived_exertion", ""),
                    "Compliance_Score": "", # Intervals logic for compliance not direct in list usually
                    "Source": "Intervals.icu"
                }
                records.append(record)
            
            return records
            
        except Exception as e:
            logger.error(f"Error fetching Intervals.icu data: {e}")
            return []

    def get_wellness_data(self):
        """
        Also useful for cross-validating weight/sleep if Garmin fails or syncs here.
        """
        return []
