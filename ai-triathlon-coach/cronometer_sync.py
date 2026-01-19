import requests
import csv
import io
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class CronometerSync:
    BASE_URL = "https://cronometer.com"
    LOGIN_URL = "https://cronometer.com/login/" # Page with the form
    LOGIN_API_URL = "https://cronometer.com/login" # API endpoint for POST (no trailing slash)
    EXPORT_URL = "https://cronometer.com/export" # Base export URL, requires parameters

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
        
        # 1. Get the login page first
        try:
            resp = self.session.get(self.LOGIN_URL)
            resp.raise_for_status()
            
            # Parse anti-csrf token
            # Looking for <input name="anticsrf" value="..."/>
            import re
            # More robust regex
            csrf_match = re.search(r'name=["\']anticsrf["\']\s+value=["\']([^"\']+)["\']', resp.text, re.IGNORECASE)
            
            anticsrf = csrf_match.group(1) if csrf_match else "" 
            
            if anticsrf:
                logger.debug("CSRF token found.")
            else:
                logger.warning("CSRF token NOT found in login page.")

            payload = {
                "username": self.username,
                "password": self.password,
                "anticsrf": anticsrf,
                "userCode": ""
            }
            
            # Add headers that might be required
            # X-Requested-With is critical for the server to treat this as an AJAX request and return JSON
            headers = {
                "Origin": self.BASE_URL,
                "Referer": self.LOGIN_URL,
                "X-Requested-With": "XMLHttpRequest"
            }
            
            # The JS posts to "/login", not "/login/"
            login_resp = self.session.post(self.LOGIN_API_URL, data=payload, headers=headers)
            login_resp.raise_for_status()
            
            # Check if login was successful
            # The JSON response for success is typically {"redirect": "https://cronometer.com/"}
            try:
                resp_json = login_resp.json()
                if "redirect" in resp_json:
                    logger.info("Cronometer login successful (JSON redirect).")
                    return True
                elif "error" in resp_json:
                    logger.error(f"Login failed. Error: {resp_json.get('error')}")
                    return False
            except ValueError:
                # If not JSON, fall back to text check (legacy/HTML response)
                pass

            if "Display Name" in login_resp.text or "Logout" in login_resp.text or "dashboard" in login_resp.url:
                logger.info("Cronometer login successful (HTML check).")
                return True
            else:
                logger.error(f"Login failed. URL: {login_resp.url}")
                # Save debug html if needed, but for now just print snippet
                snippet = login_resp.text[:500].replace("\n", " ")
                logger.error(f"Response Snippet: {snippet}")
                return False

        except Exception as e:
            logger.error(f"Error during Cronometer login: {e}")
            return False

    def get_servings_data(self, start_date=None, end_date=None):
        """
        Exports servings data as CSV and returns a list of dictionaries.
        """
        if not self.login():
            return []

        logger.info("Exporting Servings.csv...")
        try:
            # Prepare Parameters
            import datetime
            
            # Default to fetching ALL history if no start date is provided.
            # Since gsheets_sync replaces the whole sheet, we need the full dataset.
            # 2010 is a safe "start of time" for this app.
            if not start_date:
                start_date = "2010-01-01"
            
            if not end_date:
                # Set end date to tomorrow to ensure we capture everything today
                end_date = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

            # Convert to ISO/RFC3339 format which seems to be required by some versions of the API
            # e.g. 2023-01-01T00:00:00.000Z
            def to_iso(date_str):
                if "T" not in date_str:
                    return f"{date_str}T00:00:00.000Z"
                return date_str

            params = {
                "type": "servings",
                "start": to_iso(start_date),
                "end": to_iso(end_date)
            }
            
            # Add headers to mimic browser export
            headers = {
                "Origin": self.BASE_URL,
                "Referer": f"{self.BASE_URL}/",
                "X-Requested-With": "XMLHttpRequest"
            }

            resp = self.session.get(self.EXPORT_URL, params=params, headers=headers)
            resp.raise_for_status()
            
            # Parse CSV
            # Decode content
            content = resp.content.decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(content))
            
            data = []
            for row in csv_reader:
                data.append(row)
                
            logger.info(f"Retrieved {len(data)} serving records.")
            return data

        except Exception as e:
            logger.error(f"Failed to export servings: {e}")
            return []
