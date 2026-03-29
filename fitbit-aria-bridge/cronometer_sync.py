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

    GWT_BASE_URL = "https://cronometer.com/cronometer/app"
    GWT_HEADER = "2D6A926E3729946302DC68073CB0D550"
    GWT_PERMUTATION = "7B121DC5483BF272B1BC1916DA9FA963"
    GWT_MODULE_BASE = "https://cronometer.com/cronometer/"
    
    # RPC Payloads
    # GWTAuthenticate: Authenticate session to get UserID
    GWT_AUTH_PAYLOAD = "7|0|5|https://cronometer.com/cronometer/|" + GWT_HEADER + "|com.cronometer.shared.rpc.CronometerService|authenticate|java.lang.Integer/3438268394|1|2|3|4|1|5|5|-300|"
    
    # GWTGenerateAuthToken: Generate token for export. Format with (Nonce, UserID)
    GWT_TOKEN_PAYLOAD_TMPL = "7|0|8|https://cronometer.com/cronometer/|" + GWT_HEADER + "|com.cronometer.shared.rpc.CronometerService|generateAuthorizationToken|java.lang.String/2004016611|I|com.cronometer.shared.user.AuthScope/2065601159|{}|1|2|3|4|4|5|6|6|7|8|{}|3600|7|2|"

    def _gwt_request(self, payload):
        """Helper to send GWT RPC requests."""
        headers = {
            "Content-Type": "text/x-gwt-rpc; charset=UTF-8",
            "X-GWT-Permutation": self.GWT_PERMUTATION,
            "X-GWT-Module-Base": self.GWT_MODULE_BASE,
            "Referer": "https://cronometer.com/"
        }
        resp = self.session.post(self.GWT_BASE_URL, data=payload, headers=headers)
        resp.raise_for_status()
        return resp.text

    def _get_gwt_token(self):
        """
        Performs GWT authentication flow to get the export token (nonce).
        1. Authenticate to get UserID.
        2. Generate Auth Token using UserID and Session Nonce.
        """
        logger.info("Starting GWT Authentication...")
        
        # 1. Authenticate
        resp_text = self._gwt_request(self.GWT_AUTH_PAYLOAD)
        
        # Extract UserID: OK[<userid>, ...
        import re
        match = re.search(r"OK\[(\d+),", resp_text)
        if not match:
            logger.error(f"Failed to get UserID from GWT Auth. Response: {resp_text[:100]}...")
            return None
        
        user_id = match.group(1)
        logger.debug(f"GWT UserID: {user_id}")
        
        # Get Session Nonce from cookies
        sesnonce = self.session.cookies.get("sesnonce")
        if not sesnonce:
            logger.error("Session nonce cookie not found.")
            return None
            
        # 2. Generate Token
        payload = self.GWT_TOKEN_PAYLOAD_TMPL.format(sesnonce, user_id)
        resp_text = self._gwt_request(payload)
        
        # Extract Token: "//OK"... then the string literal in quotes?
        # GWT response often looks like: //OK[...,"token_string",...]
        # The go code uses regex: `"(?P<token>.*)"`
        # Let's try to find a string in quotes that looks like a token
        
        # The response structure is usually complex array.
        # Example check logic from Go: GWTTokenRegex = regexp.MustCompile("\"(?P<token>.*)\"")
        # It just grabs the first thing in quotes? That seems risky but let's try.
        token_match = re.search(r'"([^"]+)"', resp_text)
        if not token_match:
             logger.error(f"Failed to extract GWT token. Response: {resp_text[:100]}...")
             return None
             
        token = token_match.group(1)
        logger.debug(f"GWT Token generated: {token[:10]}...")
        return token

    def get_servings_data(self, start_date=None, end_date=None):
        """
        Exports servings data as CSV and returns a list of dictionaries.
        """
        if not self.login():
            return []
            
        # Perform GWT Auth to get token for export
        token = self._get_gwt_token()
        if not token:
            logger.error("Could not obtain GWT token for export.")
            return []

        logger.info("Exporting Servings using GWT token...")
        try:
            # Prepare Parameters
            import datetime
            
            # Default to fetching TODAY's data for incremental sync.
            if not start_date:
                start_date = datetime.datetime.now().strftime("%Y-%m-%d")
            
            if not end_date:
                end_date = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

            # Use simple date format? Go library uses YYYY-MM-DD.
            # Let's revert to simple format since we are using the 'nonce' method now.
            # The RFC3339 might have been a red herring for the 'export' endpoint if we were unauthorized.
            # But let's stick to what we saw in the Go code: q.Add("start", startDate.Format("2006-01-02"))
            def to_simple_date(date_str):
                 # Strip time if present
                 return date_str.split("T")[0]

            params = {
                "type": "servings",
                "start": to_simple_date(start_date),
                "end": to_simple_date(end_date),
                "nonce": token,
                "generate": "servings" # Go library uses 'generate' param, not 'type'?
                # Go code: q.Add("generate", "servings")
                # Go code also hits APIExportURL = "https://cronometer.com/export"
                # It does NOT use 'type'.
            }
            
            # The Go library sends: nonce, generate, start, end.
            
            # Add headers to mimic browser export
            headers = {
                "Origin": self.BASE_URL,
                "Referer": f"{self.BASE_URL}/",
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
