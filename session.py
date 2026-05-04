import json
import time
import random
from urllib.parse import urlparse

# Try curl_cffi first (better for Roblox), fallback to requests
try:
    from curl_cffi import requests as cffi_requests
    HAS_CFFI = True
except ImportError:
    HAS_CFFI = False
    import requests as cffi_requests
    print("[!] Install curl_cffi for better accuracy: pip install curl_cffi")

# Import utilities
from util import get_proxy_url, random_user_agent, parse_proxy


class RobloxSession:
    """Roblox session with browser impersonation for high accuracy."""
    
    def __init__(self, proxy=None):
        # Create session with browser impersonation
        if HAS_CFFI:
            self._session = cffi_requests.Session(impersonate="chrome131")
        else:
            self._session = cffi_requests.Session()
        
        self.proxy_dict = None
        self.proxy_url = None
        self._impersonate = "chrome131" if HAS_CFFI else None
        
        # Expose session attributes directly for compatibility
        self.headers = self._session.headers
        self.cookies = self._session.cookies
        
        # Setup Proxy
        if proxy:
            if isinstance(proxy, str):
                proxy = parse_proxy(proxy)
            
            if isinstance(proxy, dict):
                self.proxy_dict = proxy
                self.proxy_url = get_proxy_url(proxy)
                # Configure requests session
                self._session.proxies = {
                    "http": self.proxy_url,
                    "https": self.proxy_url
                }
        
        # Setup Headers (Chrome 131)
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Origin": "https://www.roblox.com",
            "Referer": "https://www.roblox.com/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "sec-ch-ua": '"Chromium";v="131", "Google Chrome";v="131", "Not_A.Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        })
        
        self.csrf_token = None
        self.auth_ticket = None
        self.user_id = None
        self.username = None
        self.is_logged_in = False
        self.needs_captcha = False
        self.captcha_blob = None
        self.captcha_site_key = "476068BF-9607-4799-B53D-966BE98E2B81"
    
    # Proxy methods for HTTP requests (for compatibility with roblox.py)
    def get(self, url, **kwargs):
        """Make a GET request."""
        return self._session.get(url, **kwargs)
    
    def post(self, url, **kwargs):
        """Make a POST request."""
        return self._session.post(url, **kwargs)
    
    def put(self, url, **kwargs):
        """Make a PUT request."""
        return self._session.put(url, **kwargs)
    
    def delete(self, url, **kwargs):
        """Make a DELETE request."""
        return self._session.delete(url, **kwargs)

    def _get_csrf(self, max_retries=2):
        """Fetches a fresh CSRF token from Roblox with multiple endpoint fallbacks."""
        attempt = 0
        while attempt < max_retries:
            try:
                # Method 1: Get from auth metadata endpoint
                resp = self._session.get("https://auth.roblox.com/v2/captcha-metadata", timeout=10)
                token = resp.headers.get('x-csrf-token')
                if token and len(token) > 10:
                    self.csrf_token = token
                    return True
                
                # Method 2: Try POST to /v2/login with empty body
                resp = self._session.post("https://auth.roblox.com/v2/login", json={}, timeout=10)
                token = resp.headers.get('x-csrf-token')
                if token and len(token) > 10:
                    self.csrf_token = token
                    return True
                
                # Method 3: Try signup page
                resp = self._session.get("https://www.roblox.com/signup", timeout=10)
                token = resp.headers.get('x-csrf-token')
                if token and len(token) > 10:
                    self.csrf_token = token
                    return True
                    
            except Exception as e:
                pass
            
            attempt += 1
            if attempt < max_retries:
                time.sleep(0.5)
        
        return False

    def get_initial_cookies(self):
        """Visit Roblox homepage to get initial cookies."""
        try:
            resp = self._session.get("https://www.roblox.com/", timeout=10)
            return resp.status_code == 200
        except:
            return False

    def login(self, username: str, password: str, sai: str = None) -> dict:
        """
        Attempt to login with credentials.
        Returns dict with status and any challenge info.
        """
        # Get initial cookies
        self.get_initial_cookies()
        
        # Get CSRF token
        self._get_csrf()
        if self.csrf_token:
            self._session.headers["x-csrf-token"] = self.csrf_token
        
        # Determine ctype
        ctype = "Email" if "@" in username else "Username"
        
        # Build payload
        payload = {
            "ctype": ctype,
            "cvalue": username,
            "password": password,
        }
        
        if sai:
            payload["secureAuthenticationIntent"] = sai
        
        # Try login
        resp = self._session.post("https://auth.roblox.com/v2/login", json=payload, timeout=15)
        data = resp.json() if resp.text else {}
        
        # Handle CSRF retry
        if resp.status_code == 403 and "CSRF" in resp.text:
            csrf = resp.headers.get("x-csrf-token")
            if csrf:
                self._session.headers["x-csrf-token"] = csrf
                resp = self._session.post("https://auth.roblox.com/v2/login", json=payload, timeout=15)
                data = resp.json() if resp.text else {}
        
        result = {
            "status_code": resp.status_code,
            "data": data,
            "success": False,
            "needs_captcha": False,
            "needs_2fa": False,
            "challenge_id": None,
            "challenge_metadata": None,
        }
        
        if resp.status_code == 200 and "user" in data:
            result["success"] = True
            result["user_id"] = data["user"]["id"]
            result["username"] = data["user"].get("username", username)
            self.is_logged_in = True
            self.user_id = result["user_id"]
            self.username = result["username"]
        elif "challengeId" in data:
            result["needs_captcha"] = True
            result["challenge_id"] = data["challengeId"]
            result["challenge_metadata"] = data.get("challengeMetadata", "{}")
            self.needs_captcha = True
            self.captcha_blob = result["challenge_metadata"]
        elif "twoStepVerification" in data:
            result["needs_2fa"] = True
        elif "errors" in data:
            errors = data["errors"]
            for err in errors:
                code = err.get("code", -1)
                if code == 0:
                    # Check if it's captcha challenge
                    if "Challenge" in err.get("message", ""):
                        result["needs_captcha"] = True
                    elif "users" in err.get("fieldData", ""):
                        result["multi_factor"] = True
                elif code in [17, 23, 24]:
                    result["needs_2fa"] = True
        
        return result

    def get_account_info(self):
        """Fetches Robux and other details for the logged-in user."""
        if not self.is_logged_in or not self.user_id:
            return {"error": "Not logged in", "robux": 0, "premium": False}
        
        try:
            # Get Robux Balance
            robux_resp = self._session.get(
                f"https://economy.roblox.com/v1/users/{self.user_id}/currency",
                timeout=15
            )
            if robux_resp.status_code == 200:
                robux_data = robux_resp.json()
                robux = robux_data.get("robux", 0)
            else:
                robux = 0
            
            # Get Premium Status
            is_premium = False
            try:
                premium_resp = self._session.get(
                    f"https://premiumfeatures.roblox.com/v1/users/{self.user_id}/validate-membership",
                    timeout=15
                )
                if premium_resp.status_code == 200:
                    is_premium = premium_resp.json().get("isMember", False)
            except:
                pass
            
            # Get Additional Info
            try:
                info_resp = self._session.get(
                    f"https://users.roblox.com/v1/users/{self.user_id}",
                    timeout=15
                )
                if info_resp.status_code == 200:
                    info_data = info_resp.json()
                    display_name = info_data.get("displayName", self.username)
                else:
                    display_name = self.username
            except:
                display_name = self.username
            
            return {
                "username": self.username,
                "display_name": display_name,
                "user_id": self.user_id,
                "robux": robux,
                "premium": is_premium
            }
            
        except Exception as e:
            return {"error": str(e), "robux": 0, "premium": False}

    def set_captcha_token(self, token):
        """Helper to manually set captcha token if solved externally."""
        self._session.headers["x-captcha-token"] = token
        self.needs_captcha = False


# Alias for backwards compatibility with roblox.py
Session = RobloxSession


# Static method for random session creation (used by roblox.py)
def random_session():
    """Create a new session without proxy."""
    return RobloxSession(proxy=None)


# Add as class method
RobloxSession.random_session = staticmethod(random_session)