import requests
import logging
import base64
from datetime import date, datetime, timedelta

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

    def get_activities(self, start_date_str, end_date_str):
        """
        Fetch activities for a specific date range.
        params: start_date_str (YYYY-MM-DD), end_date_str (YYYY-MM-DD)
        """
        url = f"{self.base_url}/activities?oldest={start_date_str}&newest={end_date_str}"
        
        try:
            resp = requests.get(url, headers=self.headers)
            resp.raise_for_status()
            activities = resp.json()
            
            clean_activities = []
            for act in activities:
                # data["description"] is the "comment" on the completed activity
                # data["workout_doc"]["description"] is the structured workout description (steps)
                # We prefer the planned description if available, else the comment.
                planned_desc = act.get("workout_doc", {}).get("description", "")
                actual_desc = act.get("description", "")
                final_desc = planned_desc if planned_desc else actual_desc

                clean_activities.append({
                    "Date": act.get("start_date_local", "")[:10], # Extract YYYY-MM-DD
                    "Activity_Type": act.get("type", ""),
                    "Duration_Mins": (act.get("moving_time") or 0) / 60,
                    "Distance_Km": (act.get("distance") or 0) / 1000,
                    "Intervals_Description": final_desc, 
                    "Training_Load_TSS": act.get("icu_training_load") or 0,
                    "Average_HR": act.get("average_heartrate", ""),
                    "RPE": act.get("perceived_exertion", ""),
                    # Internal fields for syncing if needed, though GSheets sync uses specific keys above
                    # "moving_time": (act.get("moving_time") or 0),
                    # "distance": (act.get("distance") or 0),
                    # "icu_training_load": (act.get("icu_training_load") or 0),
                    # "description": final_desc,
                    "Source": "Intervals.icu"
                })
            return clean_activities
            
        except Exception as e:
            logger.error(f"Error fetching Intervals.icu data: {e}")
            return []

    def get_wellness_data(self, start_date_str, end_date_str):
        """
        Fetches wellness data (CTL, ATL, Ramp Rate, etc.) for a date range.
        Endpoint: /api/v1/athlete/{athleteId}/wellness?oldest=...&newest=...
        """
        url = f"{self.base_url}/wellness"
        params = {
            "oldest": start_date_str,
            "newest": end_date_str
        }
        
        logger.info(f"Fetching Intervals.icu wellness data from {start_date_str} to {end_date_str}...")
        try:
            resp = requests.get(url, headers=self.headers, params=params)
            resp.raise_for_status()
            data = resp.json()
            
            clean_wellness = []
            for entry in data:
                # Intervals wellness objects have "id" as "YYYY-MM-DD"
                date_str = entry.get("id")
                if not date_str:
                    continue
                    
                clean_wellness.append({
                    "date": date_str,
                    "ctl": entry.get("ctl"),
                    "atl": entry.get("atl"),
                    "rampRate": entry.get("rampRate"),
                    "restingHR": entry.get("restingHR"),
                    "hrv": entry.get("hrv"),
                    "source": "Intervals.icu"
                })
            
            logger.info(f"Fetched {len(clean_wellness)} wellness entries.")
            return clean_wellness

        except Exception as e:
            logger.error(f"Error fetching Intervals wellness data: {e}")
            return []

    def get_planned_workouts(self, start_date_str, end_date_str):
        """
        Fetch planned workouts (events) for a specific date range.
        param: start_date_str (YYYY-MM-DD), end_date_str (YYYY-MM-DD)
        """
        url = f"{self.base_url}/events?oldest={start_date_str}&newest={end_date_str}"
        
        logger.info(f"Fetching Intervals.icu planned workouts from {start_date_str} to {end_date_str}...")
        try:
            resp = requests.get(url, headers=self.headers)
            resp.raise_for_status()
            events = resp.json()
            
            clean_workouts = []
            for evt in events:
                # Filter for workouts (category usually 'WORKOUT' or type is populated)
                # Some events might be notes or other things.
                # Check if it has a type (Run, Ride, Swim, etc.)
                if not evt.get("type"):
                    continue
                
                # Description logic for planned workouts:
                # Usually in 'description' field directly with structured steps text.
                desc = evt.get("description", "")
                
                clean_workouts.append({
                    "Date": evt.get("start_date_local", "")[:10],
                    "Activity_Type": evt.get("type", ""),
                    "Duration_Mins": (evt.get("moving_time") or 0) / 60,
                    "Distance_Km": (evt.get("distance") or 0) / 1000,
                    "Intervals_Description": desc, 
                    "Training_Load_TSS": evt.get("icu_training_load") or 0,
                    "Average_HR": "", # Planned usually doesn't have HR unless predicted?
                    "RPE": "",
                    "Source": "Intervals.icu (Planned)"
                })
            
            logger.info(f"Fetched {len(clean_workouts)} planned workouts.")
            return clean_workouts
            
        except Exception as e:
            logger.error(f"Error fetching Intervals planned workouts: {e}")
            return []
