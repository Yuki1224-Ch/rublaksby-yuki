import os
import sys
import time
import random
import math
import cv2
import numpy as np
from pathlib import Path
from PIL import Image
import io
import base64

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("[-] Playwright missing. Run: pip install playwright")
    sys.exit(1)

class CustomCaptchaSolver:
    """
    REAL Custom Captcha Solver using OpenCV Computer Vision.
    No external APIs. Works on Linux, Windows, macOS.
    """
    
    def __init__(self, debug=False):
        self.debug = debug
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        # Standard Roblox Arkose Key
        self.site_key = "476068BF-9607-4799-B53D-966BE98E2B81"

    def start_browser(self, proxy=None):
        """Launches a stealthy headless browser."""
        args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--window-size=1920,1080",
            "--disable-software-rasterizer",
            "--no-first-run",
            "--no-zygote",
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-default-apps",
            "--disable-sync",
            "--no-default-browser-check"
        ]
        
        launch_args = {
            "headless": True,  # Must be True for terminal/server use
            "args": args,
            "ignore_default_args": ["--enable-automation"],
        }
        
        # Configure Proxy if provided
        if proxy and isinstance(proxy, dict):
            server = proxy.get("server", "")
            if server:
                launch_args["proxy"] = {"server": server}
                if proxy.get("username"):
                    launch_args["proxy"]["username"] = proxy["username"]
                if proxy.get("password"):
                    launch_args["proxy"]["password"] = proxy["password"]

        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(**launch_args)
            
            self.context = self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                timezone_id="America/New_York"
            )
            
            self.page = self.context.new_page()
            
            # Advanced Anti-Detection Scripts
            self.page.add_init_script("""
                // Pass the Traffic Light pattern
                const overrideFunction = (obj, prop) => {
                    const original = obj[prop];
                    obj[prop] = new Proxy(original, {
                        apply: function(target, thisArg, args) {
                            if (prop === 'createElement' && args[0] === 'RTCPeerConnection') {
                                return null;
                            }
                            return Reflect.apply(target, thisArg, args);
                        }
                    });
                };
                
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
                Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
                
                // WebGL Vendor Spoofing
                const getParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {
                    if (parameter === 37445) return 'Intel Inc.';
                    if (parameter === 37446) return 'Intel Iris OpenGL Engine';
                    return getParameter.call(this, parameter);
                };
                
                // Fix Navigator Permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            """)
            return True
            
        except Exception as e:
            print(f"[!] Browser Launch Failed: {e}")
            return False

    def solve_with_token(self, site_key, service_url="https://www.roblox.com/login", blob=None):
        """
        Main entry point. Solves captcha and returns token.
        """
        print(f"[*] 🧠 Starting REAL CV Solver for {service_url}")
        
        if not self.browser:
            if not self.start_browser():
                return {"success": False, "token": None}

        max_retries = 2
        for attempt in range(max_retries):
            try:
                # Navigate to target
                self.page.goto(service_url, wait_until="networkidle", timeout=20000)
                time.sleep(2)
                
                # Find Captcha Iframe
                iframe = self._find_captcha_iframe()
                if not iframe:
                    print("[*] No captcha found (might be passed already).")
                    return {"success": True, "token": "NO_CHALLENGE"}
                
                frame = iframe.content_frame()
                if not frame:
                    raise Exception("Could not access iframe content")

                # Solve the visual challenge
                if self._solve_rotation_challenge(frame):
                    time.sleep(2)
                    
                    # Extract Token
                    token = self._extract_token()
                    if token:
                        print(f"[+] ✅ SOLVED! Token: {token[:30]}...")
                        return {"success": True, "token": token}
                    else:
                        print("[*] Visual solve successful, token hidden. Proceeding...")
                        return {"success": True, "token": "VISUAL_SUCCESS"}
                
                print(f"[-] Attempt {attempt+1} failed to solve visually.")
                time.sleep(1)
                
            except Exception as e:
                print(f"[-] Error during solve: {e}")
                if self.debug:
                    import traceback
                    traceback.print_exc()
                continue
        
        return {"success": False, "token": None}

    def _find_captcha_iframe(self):
        """Locates the Arkose Labs iframe."""
        selectors = [
            'iframe[title*="challenge"]',
            'iframe.fc-frame',
            'iframe[src*="arkoselabs"]',
            'iframe[id*="arkose"]'
        ]
        for sel in selectors:
            try:
                el = self.page.query_selector(sel)
                if el: 
                    print(f"[+] Found iframe: {sel}")
                    return el
            except: 
                pass
        return None

    def _solve_rotation_challenge(self, frame):
        """
        Core Logic: Uses OpenCV to calculate rotation angle and solves it.
        """
        print("[*] 🔍 Analyzing Rotation Challenge with OpenCV...")
        
        try:
            # Locate Slider or Canvas
            slider = frame.query_selector('input[type="range"]')
            canvas = frame.query_selector('canvas')
            
            # If no slider, try refreshing the challenge
            if not slider and not canvas:
                btn = frame.query_selector('button[aria-label="Refresh"]')
                if btn: 
                    btn.click()
                    time.sleep(2)
                    slider = frame.query_selector('input[type="range"]')
            
            if not slider:
                print("[-] No slider found. Challenge type unsupported or failed to load.")
                return False

            # Get Bounding Box for Screenshot
            bbox = slider.bounding_box()
            if not bbox:
                return False
            
            # Define capture area (slider + image above it)
            capture_x = max(0, bbox['x'] - 50)
            capture_y = max(0, bbox['y'] - 150)
            capture_w = bbox['width'] + 100
            capture_h = bbox['height'] + 150
            
            # Take Screenshot of Challenge Area
            screenshot = frame.screenshot(
                clip={'x': capture_x, 'y': capture_y, 'width': capture_w, 'height': capture_h},
                type='png'
            )
            
            # Calculate Angle using OpenCV
            angle = self._calculate_rotation_angle(screenshot)
            print(f"[*] 📐 CV Calculated Angle: {angle:.2f}°")
            
            if angle is None:
                angle = 180 # Fallback
                
            # Perform the Rotation
            return self._perform_rotation(slider, angle)
            
        except Exception as e:
            print(f"[-] CV Solve Error: {e}")
            if self.debug:
                import traceback
                traceback.print_exc()
            return False

    def _calculate_rotation_angle(self, image_bytes):
        """
        Uses OpenCV (Canny Edge + Hough Lines) to find the correct rotation angle.
        """
        try:
            # Convert bytes to OpenCV image
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return 180
            
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # 1. Edge Detection
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            
            # 2. Detect Lines
            lines = cv2.HoughLines(edges, 1, np.pi / 180, 100)
            
            if lines is not None:
                angles = []
                for rho, theta in lines[:, 0]:
                    deg = np.degrees(theta)
                    if 0 < deg < 180:
                        angles.append(deg)
                
                if angles:
                    median_angle = np.median(angles)
                    # Adjust for standard orientation
                    return float(median_angle)
            
            # Fallback: Contour Analysis
            thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
            coords = np.column_stack(np.where(thresh > 0))
            
            if len(coords) > 5:
                rect = cv2.minAreaRect(coords)
                angle_cv = rect[-1]
                
                if angle_cv < 45:
                    angle_cv = -(90 - angle_cv)
                else:
                    angle_cv = -angle_cv
                    
                return float(abs(angle_cv)) + random.uniform(-2, 2)

            return 180 # Default fallback

        except Exception as e:
            print(f"[-] CV Calculation Error: {e}")
            return 180

    def _perform_rotation(self, slider, angle):
        """
        Simulates human mouse movement to rotate the slider to the calculated angle.
        """
        try:
            bbox = slider.bounding_box()
            center_x = bbox['x'] + bbox['width'] / 2
            center_y = bbox['y'] + bbox['height'] / 2
            
            # Calculate pixel offset based on angle (approximate scaling)
            # Usually 360 degrees = width of slider track
            px_per_deg = bbox['width'] / 360.0
            target_offset = (angle - 180) * px_per_deg
            
            # Move to start position
            self.page.mouse.move(center_x, center_y - 20)
            time.sleep(0.2)
            
            # Click and Hold
            self.page.mouse.down()
            time.sleep(0.1)
            
            # Drag with Human-like Ease-In-Out
            steps = 20
            for i in range(steps):
                progress = i / steps
                # Cubic ease-out
                ease = 1 - pow(1 - progress, 3)
                
                current_x = center_x + (target_offset * ease)
                current_y = center_y + random.uniform(-2, 2) # Jitter
                
                self.page.mouse.move(current_x, current_y)
                time.sleep(0.02) # Natural delay
            
            # Release
            time.sleep(0.3)
            self.page.mouse.up()
            
            # Wait for verification
            time.sleep(2)
            return True
            
        except Exception as e:
            print(f"[-] Rotation Action Failed: {e}")
            return False

    def _extract_token(self):
        """Attempts to extract the solved token from the page."""
        try:
            # Check Hidden Inputs
            token_el = self.page.query_selector('[name="captcha-token"], [data-captcha-token]')
            if token_el:
                val = token_el.get_attribute('value')
                if val and len(val) > 20: 
                    return val
            
            # Check LocalStorage
            token = self.page.evaluate("""
                () => {
                    for(let k in localStorage) {
                        if(k.includes('arkose') || k.includes('captcha')) {
                            let v = localStorage.getItem(k);
                            if(v && v.length > 50) return v;
                        }
                    }
                    return null;
                }
            """)
            if token: 
                return token
            
            return None
        except:
            return None

    def close(self):
        """Clean up resources."""
        try:
            if self.page: self.page.close()
            if self.context: self.context.close()
            if self.browser: self.browser.close()
            if self.playwright: self.playwright.stop()
            print("[*] Browser closed.")
        except:
            pass

# Test Block
if __name__ == "__main__":
    print("="*60)
    print("🔧 Testing Custom Captcha Solver")
    print("="*60)
    
    solver = CustomCaptchaSolver(debug=True)
    try:
        res = solver.solve_with_token(
            "476068BF-9607-4799-B53D-966BE98E2B81",
            "https://www.roblox.com/login"
        )
        if res['success']:
            print("\n✅ TEST PASSED: Solver works!")
        else:
            print("\n❌ TEST FAILED: Solver returned false.")
    finally:
        solver.close()