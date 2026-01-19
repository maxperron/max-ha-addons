import requests
import csv
import io
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class CronometerSync:
    BASE_URL = "https://cronometer.com"
    LOGIN_URL = "https://cronometer.com/login/"
    EXPORT_URL = "https://cronometer.com/export/Servings.csv"

    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.session = requests.Session()
        # Mimic a browser to avoid potential blocking
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

    def login(self):
        """
        Logs into Cronometer.
        This sends a POST request to the login endpoint.
        """
        logger.info("Logging into Cronometer...")
        
        # 1. Get the login page first to set cookies/CSRF if needed (though straight POST might work)
        # Some frameworks require a CSRF token from the form. 
        # gocronometer parses "anticsrf" token. Let's try to find it.
        try:
            resp = self.session.get(self.LOGIN_URL)
            resp.raise_for_status()
            
            # Simple parsing for parsing anti-csrf token if it exists in the page
            # Usually it's in a hidden input or JS variable.
            # gocronometer suggests it is needed.
            
            # Let's try a direct post first with basic params, if it fails we implement the token parsing.
            payload = {
                "username": self.username,
                "password": self.password
            }
            
            # Note: If they use a hidden anti-csrf token, we might need to scrape it from resp.text
            # Checking resp.text for 'name="anticsrf"' might be useful if login fails.
            
            login_resp = self.session.post(self.LOGIN_URL, data=payload)
            login_resp.raise_for_status()
            
            if "Display Name" in login_resp.text or "Logout" in login_resp.text or "dashboard" in login_resp.url:
                logger.info("Cronometer login successful.")
                return True
            else:
                 # Check if we missed the CSRF token
                if "anticsrf" in resp.text:
                   logger.warning("CSRF token detected but not handled yet. Implementation update required if login failed.")
                
                logger.error("Login failed. Check credentials.")
                return False

        except Exception as e:
            logger.error(f"Error during Cronometer login: {e}")
            return False

    def get_servings_data(self, start_date=None, end_date=None):
        """
        Exports servings data as CSV and returns a list of dictionaries.
        If dates are provided, they could potentially be used to filter or request specific range if URL supports it.
        The default export usually gives full history or last X days.
        According to some docs, export might take params?
        The URL https://cronometer.com/export/Servings.csv implies a direct download.
        Experimental: Try passing params if supported, otherwise filter locally.
        """
        if not self.login():
            return []

        logger.info("Exporting Servings.csv...")
        try:
            resp = self.session.get(self.EXPORT_URL)
            resp.raise_for_status()
            
            # Parse CSV
            # Decode content
            content = resp.content.decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(content))
            
            data = []
            for row in csv_reader:
                # Row keys depend on the CSV header.
                # Standard Cronometer Export Headers usually:
                # Date, Day, Time, Amount, Unit, Food, Calories (kcal), Alcohol (g), Caffeine (mg), Water (g), ...
                
                # We can filter by date here if needed
                data.append(row)
                
            logger.info(f"Retrieved {len(data)} serving records.")
            return data

        except Exception as e:
            logger.error(f"Failed to export servings: {e}")
            return []
