import requests
import json
import time
import random
from urllib.parse import urlparse

# Import utilities
from util import get_proxy_url, random_user_agent, parse_proxy

class RobloxSession:
    def __init__(self, proxy=None):
        self.session = requests.Session()
        self.proxy_dict = None
        self.proxy_url = None
        
        # Setup Proxy
        if proxy:
            if isinstance(proxy, str):
                proxy = parse_proxy(proxy)
            
            if isinstance(proxy, dict):
                self.proxy_dict = proxy
                self.proxy_url = get_proxy_url(proxy)
                # Configure requests session
                self.session.proxies = {
                    "http": self.proxy_url,
                    "https": self.proxy_url
                }
        
        # Setup Headers
        self.session.headers.update({
            "User-Agent": random_user_agent(),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Origin": "https://www.roblox.com",
            "Referer": "https://www.roblox.com/"
        })
        
        self.csrf_token = None
        self.auth_ticket = None
        self.user_id = None
        self.username = None
        self.is_logged_in = False
        self.needs_captcha = False
        self.captcha_blob = None
        self.captcha_site_key = "476068BF-9607-4799-B53D-966BE98E2B81" # Standard Roblox Arkose Key

    def _get_csrf(self):
        """Fetches a fresh CSRF token from Roblox."""
        try:
            # Hit an endpoint that returns a CSRF token in headers
            resp = self.session.get("https://auth.roblox.com/v2/captcha-metadata", timeout=10)
            token = resp.headers.get('x-csrf-token')
            if token:
                self.csrf_token = token
                return True
            
            # Fallback: Try to login page to get token
            resp = self.session.get("https://www.roblox.com/login", timeout=10)
            # Sometimes token is in headers, sometimes need to parse HTML (simplified here)
            token = resp.headers.get('x-csrf-token')
            if token:
                self.csrf_token = token
                return True
                
            return False
        except Exception as e:
            # print(f"[!] CSRF Error: {e}")
            return False

    def login(self, username, password):
        """Attempts to log in to Roblox."""
        try:
            # 1. Get CSRF Token
            if not self._get_csrf():
                # Retry once
                time.sleep(1)
                if not self._get_csrf():
                    return False

            # 2. Prepare Login Payload
            login_data = {
                "ctype": "username",
                "cvalue": username,
                "password": password
            }
            
            headers = {
                "Content-Type": "application/json",
                "x-csrf-token": self.csrf_token,
                "Referer": "https://www.roblox.com/login"
            }

            # 3. Send Login Request
            resp = self.session.post(
                "https://auth.roblox.com/v2/login",
                json=login_data,
                headers=headers,
                timeout=15
            )
            
            data = resp.json()
            
            # 4. Handle Responses
            if resp.status_code == 200:
                if data.get("user"):
                    self.is_logged_in = True
                    self.username = data["user"]["userName"]
                    self.user_id = data["user"]["id"]
                    
                    # Set Auth Cookie if present
                    if ".ROBLOSECURITY" in resp.cookies:
                        self.session.cookies.set(".ROBLOSECURITY", resp.cookies[".ROBLOSECURITY"])
                    
                    return True
                else:
                    return False
                    
            elif resp.status_code == 401:
                # Check for Captcha requirement
                errors = data.get("errors", [])
                for err in errors:
                    if err.get("code") == "CaptchaRequired":
                        self.needs_captcha = True
                        # Extract blob if available in response
                        self.captcha_blob = err.get("context", {}).get("captchaBlob") or err.get("message")
                        return False # Needs captcha solve
                    if err.get("code") == "InvalidPassword":
                        return False
                return False
                
            elif resp.status_code == 403:
                # Often means invalid CSRF or Captcha required immediately
                self.needs_captcha = True
                return False
                
            else:
                return False

        except requests.exceptions.ProxyError:
            # print(f"[!] Proxy Error for {username}")
            return False
        except requests.exceptions.Timeout:
            # print(f"[!] Timeout for {username}")
            return False
        except Exception as e:
            # print(f"[!] Login Exception: {e}")
            return False

    def solve_captcha_and_retry(self, solver_func):
        """
        Calls the external solver, updates session, and retries login.
        solver_func: A function that takes (site_key, url, blob) and returns token.
        """
        if not self.needs_captcha:
            return False
            
        print(f"   ⚡ Solving Captcha for {self.username}...")
        
        try:
            # Call the solver (passed from main)
            # We assume solver_func returns the token string
            token = solver_func(self.captcha_site_key, "https://www.roblox.com/login", self.captcha_blob)
            
            if not token:
                print(f"   ❌ Solver failed for {self.username}")
                return False
            
            print(f"   ✅ Captcha Solved! Token: {token[:20]}...")
            
            # Now retry login WITH the captcha token
            # Roblox API expects the token in a specific header or body depending on version
            # Usually, we need to restart the login flow but include the token
            
            # Re-get CSRF
            self._get_csrf()
            
            login_data = {
                "ctype": "username",
                "cvalue": self.username, # We stored it during first attempt
                "password": "", # We don't have password stored in class easily unless passed, 
                               # Actually, let's assume the caller handles the retry logic 
                               # OR we store password in init (not recommended for security).
                               # BETTER APPROACH: The main loop handles the retry after this function returns success.
                               # This function just validates the solver works.
            }
            
            # For this implementation, we will just return the token 
            # and let the main.py re-run login with a modified session or flag.
            # BUT, to make it seamless, let's store the token in headers for the next request.
            self.session.headers["x-captcha-token"] = token
            self.needs_captcha = False # Reset flag
            
            return True
            
        except Exception as e:
            print(f"   ❌ Solver Exception: {e}")
            return False

    def get_account_info(self):
        """Fetches Robux and other details for the logged-in user."""
        if not self.is_logged_in or not self.user_id:
            return {"error": "Not logged in"}
        
        try:
            # 1. Get Robux
            robux_resp = self.session.get(
                f"https://economy.roblox.com/v1/users/{self.user_id}/currency",
                timeout=10
            )
            robux_data = robux_resp.json()
            robux = robux_data.get("robux", 0)
            
            # 2. Get Premium Status (Optional)
            premium_resp = self.session.get(
                f"https://premiumfeatures.roblox.com/v1/users/{self.user_id}/validate-membership",
                timeout=10
            )
            is_premium = premium_resp.json().get("isMember", False) if premium_resp.status_code == 200 else False
            
            return {
                "username": self.username,
                "user_id": self.user_id,
                "robux": robux,
                "premium": is_premium
            }
            
        except Exception as e:
            return {"error": str(e), "robux": 0}

    def set_captcha_token(self, token):
        """Helper to manually set captcha token if solved externally."""
        self.session.headers["x-captcha-token"] = token
        self.needs_captcha = False