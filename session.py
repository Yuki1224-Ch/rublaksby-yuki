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
            # Primary method: Get from auth metadata endpoint
            resp = self.session.get("https://auth.roblox.com/v2/captcha-metadata", timeout=10)
            token = resp.headers.get('x-csrf-token')
            if token and len(token) > 10:
                self.csrf_token = token
                return True
            
            # Fallback: Try the login page
            resp = self.session.get("https://www.roblox.com/login", timeout=10)
            token = resp.headers.get('x-csrf-token')
            if token and len(token) > 10:
                self.csrf_token = token
                return True
                
            # Last resort: Try POST to trigger CSRF header
            resp = self.session.post("https://auth.roblox.com/v2/login", json={})
            token = resp.headers.get('x-csrf-token')
            if token and len(token) > 10:
                self.csrf_token = token
                return True
                
            return False
        except Exception as e:
            # print(f"[!] CSRF Error: {e}")
            return False

    def login(self, username, password):
        """Attempts to log in to Roblox with improved API handling."""
        try:
            # 1. Get CSRF Token with multiple fallbacks
            if not self._get_csrf():
                time.sleep(1)
                if not self._get_csrf():
                    return False

            # 2. Prepare Login Payload - Roblox expects specific format
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

            # 3. Send Login Request with proper timeout
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
                # Check for Captcha requirement or invalid credentials
                errors = data.get("errors", [])
                for err in errors:
                    code = err.get("code")
                    message = err.get("message", "")
                    
                    # Captcha required - check both string and numeric codes
                    if code == "CaptchaRequired" or (isinstance(code, int) and code in [10, 13]):
                        self.needs_captcha = True
                        # Extract blob if available in response
                        self.captcha_blob = err.get("context", {}).get("captchaBlob") or err.get("message")
                        return False  # Needs captcha solve
                    
                    # Invalid password or credentials
                    if code == "InvalidPassword" or code == "InvalidCredentials" or (isinstance(code, int) and code in [1, 2]):
                        return False
                    
                    # Account locked or banned
                    if code == "AccountLocked" or code == "AccountBanned" or (isinstance(code, int) and code in [4, 5]):
                        return False
                    
                    # Rate limited - might indicate captcha needed
                    if code == "RateLimited" or (isinstance(code, int) and code == 8):
                        self.needs_captcha = True
                        return False
                        
                # Default to invalid for unknown 401 errors
                return False
                
            elif resp.status_code == 403:
                # Often means captcha required immediately
                errors = data.get("errors", [])
                for err in errors:
                    code = err.get("code")
                    if code == "CaptchaRequired" or (isinstance(code, int) and code in [10, 13]):
                        self.needs_captcha = True
                        self.captcha_blob = err.get("context", {}).get("captchaBlob")
                        return False
                
                # If we get 403 without explicit captcha code, it might still be a captcha challenge
                self.needs_captcha = True
                return False
                
            elif resp.status_code == 429:
                # Rate limited - often indicates need for captcha or proxy issue
                self.needs_captcha = True
                return False
                
            else:
                return False

        except requests.exceptions.ProxyError:
            return False
        except requests.exceptions.Timeout:
            return False
        except Exception as e:
            return False

    def solve_captcha_and_retry(self, solver_func, password=None):
        """
        Calls the external solver, updates session, and retries login.
        solver_func: A function that takes (site_key, url, blob) and returns token.
        password: The user's password for retrying login after captcha solve.
        """
        if not self.needs_captcha:
            return False
            
        print(f"   ⚡ Solving Captcha for {self.username}...")
        
        try:
            # Call the solver (passed from main)
            result = solver_func(self.captcha_site_key, "https://www.roblox.com/login", self.captcha_blob)
            
            # Handle both dict and string results
            token = None
            visual_success = False
            
            if isinstance(result, dict):
                token = result.get('token')
                visual_success = result.get('success', False) or token in ['VISUAL_SUCCESS', 'NO_CHALLENGE']
            else:
                token = result
                visual_success = token in ['VISUAL_SUCCESS', 'NO_CHALLENGE'] or (token and len(token) > 20)
            
            if not token and not visual_success:
                print(f"   ❌ Solver failed for {self.username}")
                return False
            
            if token == "NO_CHALLENGE":
                print(f"   ✅ No captcha required, retrying login...")
            elif token == "VISUAL_SUCCESS" or visual_success:
                print(f"   ✅ Captcha visually solved! Retrying login...")
            elif token:
                print(f"   ✅ Captcha Solved! Token: {token[:20]}...")
                self.session.headers["x-captcha-token"] = token
            
            # Reset captcha flag
            self.needs_captcha = False
            
            # Retry login if password is provided
            if password:
                print(f"   🔄 Retrying login for {self.username}...")
                
                # Re-get CSRF token
                self._get_csrf()
                
                login_data = {
                    "ctype": "username",
                    "cvalue": self.username,
                    "password": password
                }
                
                headers = {
                    "Content-Type": "application/json",
                    "x-csrf-token": self.csrf_token,
                    "Referer": "https://www.roblox.com/login"
                }
                
                # Add captcha token if we have one
                if hasattr(self, 'session') and 'x-captcha-token' in self.session.headers:
                    headers["x-captcha-token"] = self.session.headers['x-captcha-token']
                
                resp = self.session.post(
                    "https://auth.roblox.com/v2/login",
                    json=login_data,
                    headers=headers,
                    timeout=15
                )
                
                data = resp.json()
                
                if resp.status_code == 200 and data.get("user"):
                    self.is_logged_in = True
                    self.user_id = data["user"]["id"]
                    
                    if ".ROBLOSECURITY" in resp.cookies:
                        self.session.cookies.set(".ROBLOSECURITY", resp.cookies[".ROBLOSECURITY"])
                    
                    print(f"   ✅ Login successful after captcha solve!")
                    return True
                else:
                    # Check if we got another captcha
                    errors = data.get("errors", [])
                    for err in errors:
                        code = err.get("code")
                        if code == "CaptchaRequired" or (isinstance(code, int) and code in [10, 13]):
                            print(f"   ⚠️ Another captcha required - credentials may be invalid")
                            self.needs_captcha = True
                            return False
                    
                    # If no explicit error but login failed, check if it's actually valid
                    # Sometimes captcha was solved but account has wrong password
                    print(f"   ❌ Login retry failed - checking credentials...")
                    return False
            else:
                # No password provided, just indicate captcha was solved
                return True
            
        except Exception as e:
            print(f"   ❌ Solver Exception: {e}")
            return False

    def get_account_info(self):
        """Fetches Robux and other details for the logged-in user."""
        if not self.is_logged_in or not self.user_id:
            return {"error": "Not logged in", "robux": 0, "premium": False}
        
        try:
            # 1. Get Robux Balance
            robux_resp = self.session.get(
                f"https://economy.roblox.com/v1/users/{self.user_id}/currency",
                timeout=15
            )
            if robux_resp.status_code == 200:
                robux_data = robux_resp.json()
                robux = robux_data.get("robux", 0)
            else:
                robux = 0
            
            # 2. Get Premium Status
            is_premium = False
            try:
                premium_resp = self.session.get(
                    f"https://premiumfeatures.roblox.com/v1/users/{self.user_id}/validate-membership",
                    timeout=15
                )
                if premium_resp.status_code == 200:
                    is_premium = premium_resp.json().get("isMember", False)
            except:
                pass
            
            # 3. Get Additional Info (optional)
            try:
                info_resp = self.session.get(
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
        self.session.headers["x-captcha-token"] = token
        self.needs_captcha = False

# Alias for backwards compatibility with roblox.py
Session = RobloxSession