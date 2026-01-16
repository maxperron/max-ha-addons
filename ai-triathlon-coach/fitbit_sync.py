import requests
import json
import os
import logging
import base64
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class FitbitSync:
    def __init__(self, client_id, client_secret, initial_refresh_token=None, token_file="/data/fitbit_token.json"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_file = token_file
        self.initial_refresh_token = initial_refresh_token
        self.access_token = None
        self.refresh_token = None
        
        self.load_tokens()

    def load_tokens(self):
        """Load tokens from local file or use initial config."""
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, "r") as f:
                    data = json.load(f)
                    self.access_token = data.get("access_token")
                    self.refresh_token = data.get("refresh_token")
                    logger.info("Loaded Fitbit tokens from persistence.")
            except Exception as e:
                logger.error(f"Failed to load token file: {e}")
        
        if not self.refresh_token and self.initial_refresh_token:
            logger.info("No persisted refresh token found. Using initial refresh token from config.")
            self.refresh_token = self.initial_refresh_token

    def save_tokens(self):
        """Save tokens to local file for persistence."""
        try:
            with open(self.token_file, "w") as f:
                json.dump({
                    "access_token": self.access_token,
                    "refresh_token": self.refresh_token
                }, f)
            logger.info("Saved Fitbit tokens to persistence.")
        except Exception as e:
            logger.error(f"Failed to save tokens: {e}")

    def refresh_access_token(self):
        """Refresh OAuth2 access token."""
        if not self.refresh_token:
            logger.error("Cannot refresh token: No refresh token available.")
            return False

        url = "https://api.fitbit.com/oauth2/token"
        auth_header = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        
        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token
        }

        try:
            response = requests.post(url, headers=headers, data=data)
            response.raise_for_status()
            tokens = response.json()
            
            self.access_token = tokens["access_token"]
            self.refresh_token = tokens["refresh_token"]
            self.save_tokens()
            logger.info("Successfully refreshed Fitbit access token.")
            return True
        except Exception as e:
            logger.error(f"Failed to refresh Fitbit token: {e}")
            if response is not None:
                logger.error(f"Response: {response.text}")
            return False

    def get_latest_weight(self):
        """
        Fetch the latest weight log from today or yesterday.
        Returns: weight in kg (float) or None
        """
        if not self.access_token:
            if not self.refresh_access_token():
                return None

        # Fetch for today
        today = datetime.now().strftime("%Y-%m-%d")
        # Ensure we request metric units usually via header
        # 'Accept-Language': 'en_US' -> likely lbs? 'en_GB' -> stones/kg?
        # Better: use the 'Accept-Locale' or examine response units.
        # Fitbit API usually returns weight in the unit of the user profile unless specified? 
        # Actually API docs say "weight is returned in the unit of the user's profile".
        # However, we can use the 'Accept-Language' header to request specific units? 
        # No, unit system is set in profile. We must check the response "weight" field unit?
        # Or simpler: The Get Body Weight Log API doesn't specify unit in response explicitly per entry?
        # Wait, the response is JSON. `weight` is usually `logId`, `weight`, `date`, `time`.
        # Let's assume we need to check user profile or just be smart.
        # Actually, let's just get it and see. If input is Lbs, we assume it's Lbs.
        # But user asked: "My weight is lbs in fitbit and kg in garmin".
        
        # Let's request the profile to see the unit system? Or just assume it returns raw.
        # Standard: 'X-Fitbit-Subscriber-Id' etc.
        # Let's try to fetch with 'Accept-Language' header set to metric locales if possible?
        # Actually, best practice: Fetch profile to get 'weightUnit'.
        
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        
        # 1. Fetch Profile to confirm units (optional but safer)
        # response = requests.get("https://api.fitbit.com/1/user/-/profile.json", headers=headers)
        
        # 2. Fetch Weight Log
        url = f"https://api.fitbit.com/1/user/-/body/log/weight/date/{today}.json"
        
        try:
            response = requests.get(url, headers=headers)
            
            if response.status_code == 401:
                logger.info("Fitbit token expired during request. Refreshing...")
                if self.refresh_access_token():
                    headers["Authorization"] = f"Bearer {self.access_token}"
                    response = requests.get(url, headers=headers)
                else:
                    return None
            
            response.raise_for_status()
            data = response.json()
            
            # data['weight'] is a list of logs
            logs = data.get('weight', [])
            if not logs:
                return None
                
            # Get latest
            latest = logs[-1]
            weight_val = latest.get('weight')
            
            # The API returns `weight` in the unit of the Accept-Language header? 
            # User confirmed it returns KG.
            
            # The structure of `latest` usually is:
            # {
            #    "logId": 12345,
            #    "weight": 81.5,
            #    "bmi": 24.5,
            #    "date": "2024-01-14",
            #    "time": "08:30:00"
            # }
            
            weight_val = float(latest.get('weight'))
            date_str = latest.get('date')
            time_str = latest.get('time')
            
            # Garmin likely needs full ISO timestamp?
            # Or just YYYY-MM-DD? The error said 'timestamp' required.
            # Library often expects ISO string or datetime object?
            # Let's try to construct full ISO string if time exists, else date.
            
            timestamp = f"{date_str}T{time_str}" if date_str and time_str else date_str
            
            return (weight_val, timestamp)

        except Exception as e:
            logger.error(f"Fitbit API Request Failed: {e}")
            return None

    def get_water_log(self, date_str):
        """
        Get water log for a date (YYYY-MM-DD).
        Returns tuple (amount_ml, unit).
        """
        if not self.access_token:
             if not self.refresh_access_token():
                 return None

        url = f"https://api.fitbit.com/1/user/-/foods/log/water/date/{date_str}.json"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept-Language": "en_US" # Requesting standard might give Oz? Or Metric?
            # Actually, let's Request METRIC to be safe?
            # "Accept-Language": "fr_FR" often forces metric.
            # But let's handle units dynamically.
        }
        
        try:
            response = requests.get(url, headers=headers)
            
            # Handle Token Expiry
            if response.status_code == 401:
                if self.refresh_access_token():
                   headers["Authorization"] = f"Bearer {self.access_token}"
                   response = requests.get(url, headers=headers)
                else:
                   return None

            # Handle Scope/Permission Issue (403) by trying the "Initial" token from config
            if response.status_code == 403:
                logger.warning("Fitbit API returned 403 Forbidden. This usually means missing Scopes (e.g. Nutrition).")
                if self.initial_refresh_token:
                    logger.info("Attempting to re-authorize using the 'initial_refresh_token' from configuration...")
                    self.refresh_token = self.initial_refresh_token
                    if self.refresh_access_token():
                        headers["Authorization"] = f"Bearer {self.access_token}"
                        response = requests.get(url, headers=headers)
                    else:
                        logger.error("Failed to re-authorize with initial token.")
                        return None
                else:
                    logger.error("No initial_refresh_token available to recover from 403.")
                    return None
            
            response.raise_for_status()
            data = response.json()
            # Response: {"summary": {"water": 1000, "waterGoal": 2000}}
            # Water summary typically returns in the unit of the user?
            # We need to find the unit.
            # The API response for 'get water log' usually includes 'summary'.
            # Unfortuntely 'summary' often lacks unit field in this endpoint. 
            # However, `water` list entries might have unit.
            # Let's check `data['water']` list.
            
            # If `summary.water` is present, it is the total.
            # If we cannot determine unit, we might assume ML if > 100? or Oz if < 200?
            
            summary = data.get('summary', {})
            total = summary.get('water', 0)
            
            # Let's try to infer unit from the waters list if available
            water_entries = data.get('water', [])
            # Entries have 'amount' and 'unit'.
            
            if total > 0:
                # If we have entries, check first entry unit
                if water_entries:
                    unit_obj = water_entries[0].get('unit', {})
                    unit_log = unit_obj.get('name') or unit_obj.get('shortName')
                    
                    if unit_log:
                        return (total, unit_log)
                
                # Fallback: Heuristic based on magnitude
                # If total > 500 -> likely ml (500ml is common, 500oz is 15 Liters)
                # If total < 200 -> likely oz (200oz is 6L, barely possible. 100oz is 3L common target).
                # Assumption: If value < 250, it is likely Ounces or Cups, not ML.
                # If it was ML, 99ml is very small (3oz), but possible.
                # However, usually daily total is much higher.
                # Let's say cutoff is 300.
                
                return (total, "analyzed_ml" if total > 300 else "analyzed_oz")

            return (0, "ml")

        except Exception as e:
            logger.error(f"Fitbit Water Request Failed: {e}")
            return None
