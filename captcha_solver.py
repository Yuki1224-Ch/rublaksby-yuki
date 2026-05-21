"""
Real Captcha Solver using 2Captcha API for Arkose Labs (FunCaptcha).
This is the industry-standard approach for solving Roblox captchas.
"""
import requests
import time
import json
import threading
from typing import Optional, Dict, Any

class CaptchaSolver:
    """
    Real captcha solver using 2Captcha API.
    Supports Arkose Labs (FunCaptcha) which Roblox uses.
    """
    
    # Roblox Arkose Labs site key
    ROBLOX_SITE_KEY = "476068BF-9607-4799-B53D-966BE98E2B81"
    
    def __init__(self, api_key: str, debug: bool = False):
        """
        Initialize the solver with 2Captcha API key.
        
        Args:
            api_key: Your 2captcha.com API key
            debug: Enable debug logging
        """
        self.api_key = api_key
        self.debug = debug
        self.base_url = "https://2captcha.com"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        
    def log(self, message: str):
        """Debug logging."""
        if self.debug:
            print(f"[CAPTCHA] {message}")
    
    def solve_funcaptcha(
        self,
        site_key: str = None,
        page_url: str = "https://www.roblox.com/login",
        blob: str = None,
        proxy: str = None,
        timeout: int = 180
    ) -> Optional[str]:
        """
        Solve Arkose Labs FunCaptcha using 2Captcha API.
        
        Args:
            site_key: Arkose Labs public key (defaults to Roblox key)
            page_url: URL where captcha appears
            blob: Optional blob data from Roblox
            proxy: Optional proxy string (user:pass@ip:port)
            timeout: Maximum time to wait for solution
            
        Returns:
            Solved token or None if failed
        """
        site_key = site_key or self.ROBLOX_SITE_KEY
        
        self.log(f"Solving FunCaptcha for {page_url}")
        self.log(f"Site key: {site_key}")
        
        # Build request parameters
        params = {
            "key": self.api_key,
            "method": "funcaptcha",
            "publickey": site_key,
            "pageurl": page_url,
            "json": 1
        }
        
        # Add blob if provided (important for Roblox)
        if blob:
            params["data"] = blob
            self.log(f"Blob data provided: {blob[:50]}..." if len(blob) > 50 else f"Blob: {blob}")
        
        # Add proxy if provided
        if proxy:
            params["proxy"] = proxy
            params["proxytype"] = "HTTP"
            self.log(f"Using proxy: {proxy}")
        
        # Step 1: Submit captcha to 2captcha
        try:
            submit_url = f"{self.base_url}/in.php"
            response = self.session.get(submit_url, params=params, timeout=30)
            data = response.json()
            
            if data.get("status") != 1:
                error = data.get("request", "Unknown error")
                print(f"[-] 2Captcha submit failed: {error}")
                return None
            
            task_id = data.get("request")
            self.log(f"Task submitted: {task_id}")
            
        except requests.exceptions.RequestException as e:
            print(f"[-] 2Captcha submit error: {e}")
            return None
        except json.JSONDecodeError:
            print(f"[-] 2Captcha returned invalid JSON")
            return None
        
        # Step 2: Poll for result
        result_url = f"{self.base_url}/res.php"
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            time.sleep(5)  # Wait between polls
            
            try:
                poll_params = {
                    "key": self.api_key,
                    "action": "get",
                    "id": task_id,
                    "json": 1
                }
                
                response = self.session.get(result_url, params=poll_params, timeout=30)
                data = response.json()
                
                status = data.get("status")
                request = data.get("request")
                
                if status == 1:
                    # Success!
                    self.log(f"Solved in {time.time() - start_time:.1f}s")
                    print(f"[+] ✅ Captcha solved by 2Captcha!")
                    return request
                
                elif status == 0:
                    # Still processing or error
                    if request == "CAPCHA_NOT_READY":
                        self.log("Still processing...")
                        continue
                    else:
                        print(f"[-] 2Captcha error: {request}")
                        return None
                        
            except requests.exceptions.RequestException as e:
                self.log(f"Poll error: {e}")
                continue
            except json.JSONDecodeError:
                self.log("Invalid JSON in poll response")
                continue
        
        print(f"[-] Captcha solving timed out after {timeout}s")
        return None
    
    def get_balance(self) -> Optional[float]:
        """Check 2Captcha account balance."""
        try:
            url = f"{self.base_url}/res.php"
            params = {
                "key": self.api_key,
                "action": "getbalance",
                "json": 1
            }
            response = self.session.get(url, params=params, timeout=10)
            data = response.json()
            
            if data.get("status") == 1:
                balance = float(data.get("request", 0))
                return balance
            return None
        except:
            return None


class LocalCaptchaSolver:
    """
    Local captcha solver that tries multiple approaches:
    1. Browser-based visual solving (for simple captchas)
    2. Fallback strategies
    
    Note: For Roblox Arkose Labs captchas, use CaptchaSolver with 2Captcha API.
    This local solver is a fallback for when API is unavailable.
    """
    
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.browser = None
        
    def solve_with_browser(self, site_key: str, page_url: str, blob: str = None) -> Optional[str]:
        """
        Attempt to solve captcha using browser automation.
        This is less reliable than API-based solving.
        """
        try:
            from playwright.sync_api import sync_playwright
            
            self.log("Starting browser-based solver...")
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )
                page = context.new_page()
                
                # Navigate to page
                page.goto(page_url, wait_until="networkidle")
                
                # Wait for captcha iframe
                iframe = page.wait_for_selector('iframe[src*="arkose"]', timeout=10000)
                
                if iframe:
                    frame = iframe.content_frame()
                    
                    # Try to interact with captcha
                    # Note: Arkose Labs captchas are specifically designed to prevent this
                    # This approach rarely works for FunCaptcha
                    
                    # Wait and see if captcha auto-solves (sometimes happens)
                    time.sleep(5)
                    
                    # Check for success
                    captcha_gone = page.query_selector('iframe[src*="arkose"]') is None
                    
                    if captcha_gone:
                        self.log("Captcha may have auto-resolved")
                        return "BROWSER_SUCCESS"
                
                browser.close()
                
        except ImportError:
            self.log("Playwright not installed")
        except Exception as e:
            self.log(f"Browser solver error: {e}")
        
        return None
    
    def log(self, message: str):
        if self.debug:
            print(f"[LOCAL_SOLVER] {message}")


# Thread-safe solver manager
class SolverManager:
    """
    Manages captcha solving with thread safety.
    Supports both API and local solving.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.solver = None
        self.local_solver = None
        self.config = {}
        self._initialized = True
        
    def configure(self, api_key: str = None, debug: bool = False):
        """Configure the solver with API key."""
        self.config = {
            "api_key": api_key,
            "debug": debug
        }
        
        if api_key:
            self.solver = CaptchaSolver(api_key=api_key, debug=debug)
            balance = self.solver.get_balance()
            if balance is not None:
                print(f"[+] 2Captcha balance: ${balance:.2f}")
            else:
                print("[!] Warning: Could not verify 2Captcha balance")
        
        self.local_solver = LocalCaptchaSolver(debug=debug)
    
    def solve(self, site_key: str, page_url: str, blob: str = None, proxy: str = None) -> Optional[str]:
        """
        Solve captcha using best available method.
        
        Priority:
        1. 2Captcha API (most reliable)
        2. Local browser solver (fallback)
        """
        # Try API solver first
        if self.solver:
            print(f"[*] 🧠 Solving captcha via 2Captcha API...")
            token = self.solver.solve_funcaptcha(
                site_key=site_key,
                page_url=page_url,
                blob=blob,
                proxy=proxy
            )
            if token:
                return token
            print("[!] 2Captcha failed, trying local fallback...")
        
        # Fallback to local solver
        if self.local_solver:
            print("[*] 🔄 Attempting local browser solver...")
            token = self.local_solver.solve_with_browser(
                site_key=site_key,
                page_url=page_url,
                blob=blob
            )
            if token:
                return token
        
        print("[-] ❌ All captcha solving methods failed")
        return None


# Global solver instance
_solver_manager = None
_solver_lock = threading.Lock()

def get_solver_manager() -> SolverManager:
    """Get the global solver manager instance."""
    global _solver_manager
    with _solver_lock:
        if _solver_manager is None:
            _solver_manager = SolverManager()
        return _solver_manager

def solve_captcha(
    site_key: str = None,
    page_url: str = "https://www.roblox.com/login",
    blob: str = None,
    proxy: str = None,
    api_key: str = None
) -> Optional[str]:
    """
    Main entry point for captcha solving.
    
    Args:
        site_key: Arkose Labs site key (defaults to Roblox)
        page_url: URL where captcha appears
        blob: Optional blob data
        proxy: Optional proxy string
        api_key: 2Captcha API key (optional, can be set via configure)
        
    Returns:
        Solved token or None
    """
    manager = get_solver_manager()
    
    if api_key and not manager.solver:
        manager.configure(api_key=api_key)
    
    site_key = site_key or CaptchaSolver.ROBLOX_SITE_KEY
    
    return manager.solve(
        site_key=site_key,
        page_url=page_url,
        blob=blob,
        proxy=proxy
    )


def configure_solver(api_key: str, debug: bool = False):
    """Configure the global solver with API key."""
    manager = get_solver_manager()
    manager.configure(api_key=api_key, debug=debug)


if __name__ == "__main__":
    import sys
    
    print("=" * 60)
    print("🔧 Captcha Solver Test")
    print("=" * 60)
    
    # Check for API key
    if len(sys.argv) > 1:
        api_key = sys.argv[1]
        print(f"[*] Testing with API key: {api_key[:10]}...")
        
        solver = CaptchaSolver(api_key=api_key, debug=True)
        balance = solver.get_balance()
        
        if balance is not None:
            print(f"[+] ✅ Valid API key! Balance: ${balance:.2f}")
        else:
            print("[-] ❌ Invalid API key or connection error")
    else:
        print("[!] No API key provided")
        print("[*] Usage: python captcha_solver.py YOUR_2CAPTCHA_API_KEY")
        print()
        print("[*] To get an API key:")
        print("    1. Sign up at https://2captcha.com")
        print("    2. Add funds to your account")
        print("    3. Get your API key from settings")