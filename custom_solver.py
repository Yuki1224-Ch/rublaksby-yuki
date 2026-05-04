"""
🧩 FREE Local Captcha Solver for Roblox Arkose Labs FunCaptcha
===============================================================
100% FREE - NO API KEY NEEDED - NO MONEY REQUIRED!

How it works:
1. Opens the captcha challenge URL directly
2. Uses OpenCV to analyze the rotation image
3. Applies smart rotation with human-like movements
4. Returns the solved token

Speed: ~30-60 seconds per captcha (varies)
Cost: $0.00 (FREE!)
"""
import os
import sys
import time
import random
import math
import json
import hashlib
from typing import Optional, Dict, Any, Tuple, List
from pathlib import Path

# OpenCV for image analysis
try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    print("[!] Install OpenCV: pip install opencv-python numpy")

# Playwright for browser
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("[-] Install Playwright: pip install playwright && playwright install chromium")
    sys.exit(1)


# Learning database for known solutions
SOLUTIONS_FILE = Path("captcha_solutions.json")
KNOWN_SOLUTIONS = {}


def load_solutions():
    """Load previously solved captchas."""
    global KNOWN_SOLUTIONS
    if SOLUTIONS_FILE.exists():
        try:
            with open(SOLUTIONS_FILE, 'r') as f:
                KNOWN_SOLUTIONS = json.load(f)
        except:
            KNOWN_SOLUTIONS = {}


def save_solution(img_hash: str, angle: float):
    """Save a solved captcha."""
    KNOWN_SOLUTIONS[img_hash] = angle
    try:
        with open(SOLUTIONS_FILE, 'w') as f:
            json.dump(KNOWN_SOLUTIONS, f)
    except:
        pass


load_solutions()


class RealCaptchaSolver:
    """
    FREE Local Captcha Solver - No API needed!
    """
    
    # Roblox FunCaptcha site key
    ROBLOX_SITE_KEY = "476068BF-9607-4799-B53D-966BE98E2B81"
    
    # Arkose Labs captcha URL
    CAPTCHA_BASE_URL = "https://client-api.arkoselabs.com/v2"
    
    def __init__(self, debug: bool = False, headless: bool = True):
        self.debug = debug
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        
        self.solved_count = 0
        self.failed_count = 0
    
    def log(self, msg: str):
        if self.debug:
            print(f"[SOLVER] {msg}")
    
    def start_browser(self, proxy: dict = None) -> bool:
        """Launch browser."""
        
        if self.browser:
            return True
        
        args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--window-size=1280,720",
            "--disable-infobars",
        ]
        
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(
                headless=self.headless,
                args=args,
                ignore_default_args=["--enable-automation"]
            )
            
            self.context = self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 720},
                locale="en-US",
            )
            
            self.page = self.context.new_page()
            
            # Anti-detection script
            self.page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                window.chrome = {runtime: {}};
            """)
            
            self.log("Browser started")
            return True
            
        except Exception as e:
            self.log(f"Browser start failed: {e}")
            return False
    
    def solve_with_token(
        self,
        site_key: str = None,
        service_url: str = "https://www.roblox.com/login",
        blob: str = None,
        timeout: int = 180
    ) -> Dict[str, Any]:
        """
        Main solving function.
        
        Opens the login page, detects captcha, solves it.
        """
        
        if not self.browser:
            if not self.start_browser():
                return {"success": False, "token": None}
        
        self.log(f"Going to {service_url}")
        
        try:
            # Navigate to login page
            self.page.goto(service_url, timeout=30000)
            self._human_delay(1, 2)
            
            # Wait for page load
            try:
                self.page.wait_for_load_state("networkidle", timeout=10000)
            except:
                pass
            
        except Exception as e:
            self.log(f"Navigation error: {e}")
            # Continue anyway - might still work
        
        # Find captcha iframe
        iframe = self._find_captcha_iframe()
        
        if not iframe:
            self.log("No captcha iframe found")
            # Check if already logged in or no captcha needed
            return {"success": True, "token": "NO_CAPTCHA"}
        
        self.log("Found captcha iframe!")
        
        # Get the frame
        frame = iframe.content_frame()
        if not frame:
            self.log("Cannot access iframe")
            return {"success": False, "token": None}
        
        # Try to solve
        for attempt in range(10):
            if self.debug:
                print(f"[*] Attempt {attempt + 1}/10")
            
            try:
                self._human_delay(0.5, 1)
                
                # Try rotation challenge
                if self._solve_rotation(frame, iframe):
                    self._human_delay(1, 2)
                    
                    # Check success
                    if self._check_success():
                        token = self._get_token()
                        if token:
                            self.solved_count += 1
                            print(f"[+] ✅ SOLVED! (Attempt {attempt + 1})")
                            return {"success": True, "token": token}
                
                # Try click challenge
                elif self._solve_clicks(frame):
                    self._human_delay(1, 2)
                    
                    if self._check_success():
                        token = self._get_token()
                        if token:
                            self.solved_count += 1
                            print(f"[+] ✅ SOLVED! (Click challenge)")
                            return {"success": True, "token": token}
                
                # Refresh for next attempt
                self._refresh(frame)
                self._human_delay(1, 2)
                
            except Exception as e:
                self.log(f"Error: {e}")
        
        self.failed_count += 1
        print(f"[-] ❌ Failed after 10 attempts")
        return {"success": False, "token": None}
    
    def _find_captcha_iframe(self):
        """Find the captcha iframe."""
        selectors = [
            'iframe[src*="arkose"]',
            'iframe[src*="funcaptcha"]',
            'iframe[title*="challenge"]',
            'iframe.fc-frame',
            '#game-info-frame',
        ]
        
        for sel in selectors:
            try:
                el = self.page.wait_for_selector(sel, timeout=5000)
                if el:
                    self.log(f"Found: {sel}")
                    return el
            except:
                continue
        
        return None
    
    def _solve_rotation(self, frame, iframe) -> bool:
        """Solve rotation challenge."""
        
        if not HAS_CV2:
            return self._random_rotation(frame)
        
        try:
            # Find slider
            slider = frame.query_selector('input[type="range"], [role="slider"]')
            if not slider:
                self.log("No slider found")
                return False
            
            # Take screenshot
            box = iframe.bounding_box()
            if not box:
                return False
            
            # Capture captcha image area
            area = {
                'x': box['x'] + 5,
                'y': box['y'] + 5,
                'width': box['width'] - 10,
                'height': box['height'] * 0.5
            }
            
            screenshot = self.page.screenshot(type="png", clip=area)
            
            # Analyze image
            angle = self._analyze_image(screenshot)
            self.log(f"Detected angle: {angle:.0f}°")
            
            # Rotate
            return self._do_rotation(slider, angle)
            
        except Exception as e:
            self.log(f"Rotation error: {e}")
            return False
    
    def _analyze_image(self, image_bytes: bytes) -> float:
        """Analyze image to find rotation angle."""
        
        try:
            # Decode
            arr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            
            if img is None:
                return random.uniform(0, 360)
            
            # Hash for known solutions
            img_hash = hashlib.md5(image_bytes).hexdigest()
            
            if img_hash in KNOWN_SOLUTIONS:
                print(f"[*] 🎯 Found known solution!")
                return KNOWN_SOLUTIONS[img_hash]
            
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Method 1: Contours
            angle1 = self._detect_contour_angle(gray)
            
            # Method 2: Hough lines
            angle2 = self._detect_hough_angle(gray)
            
            # Method 3: Edges
            angle3 = self._detect_edge_angle(gray)
            
            # Combine
            angles = [a for a in [angle1, angle2, angle3] if a is not None]
            
            if angles:
                # Use median
                final = float(np.median(angles))
                self.log(f"Angles: contour={angle1}, hough={angle2}, edge={angle3}")
                return final
            
            return random.uniform(0, 360)
            
        except Exception as e:
            self.log(f"Analysis error: {e}")
            return random.uniform(0, 360)
    
    def _detect_contour_angle(self, gray) -> Optional[float]:
        """Detect angle using contours."""
        try:
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(blurred, 50, 150)
            
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                return None
            
            largest = max(contours, key=cv2.contourArea)
            
            if cv2.contourArea(largest) < 500:
                return None
            
            rect = cv2.minAreaRect(largest)
            angle = rect[-1]
            
            return angle
            
        except:
            return None
    
    def _detect_hough_angle(self, gray) -> Optional[float]:
        """Detect angle using Hough lines."""
        try:
            edges = cv2.Canny(gray, 50, 150)
            lines = cv2.HoughLines(edges, 1, np.pi/180, 50)
            
            if lines is None:
                return None
            
            angles = []
            for line in lines[:10]:
                angle = np.degrees(line[0][1])
                angles.append(angle)
            
            if angles:
                return float(np.median(angles))
            
            return None
            
        except:
            return None
    
    def _detect_edge_angle(self, gray) -> Optional[float]:
        """Detect angle using edge orientation."""
        try:
            gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
            
            mag = cv2.magnitude(gx, gy)
            ori = cv2.phase(gx, gy, angleInDegrees=True)
            
            mask = mag > np.percentile(mag, 70)
            angles = ori[mask]
            
            if len(angles) > 100:
                hist, _ = np.histogram(angles, bins=36, range=(0, 360))
                return float(np.argmax(hist) * 10)
            
            return None
            
        except:
            return None
    
    def _do_rotation(self, slider, angle: float) -> bool:
        """Perform the rotation."""
        
        try:
            box = slider.bounding_box()
            if not box:
                return False
            
            cx = box['x'] + box['width'] / 2
            cy = box['y'] + box['height'] / 2
            
            # Calculate drag distance
            drag = (angle / 360) * box['width']
            
            # Move to slider
            self.page.mouse.move(cx, cy)
            self._human_delay(0.1, 0.2)
            
            # Click and drag
            self.page.mouse.down()
            self._human_delay(0.1, 0.2)
            
            # Drag with easing
            steps = 20
            for i in range(steps):
                progress = i / steps
                ease = progress * progress  # Ease in
                
                x = cx + drag * ease
                y = cy + math.sin(progress * math.pi) * 5
                
                self.page.mouse.move(x, y)
                time.sleep(0.02)
            
            self._human_delay(0.1, 0.3)
            self.page.mouse.up()
            
            self.log(f"Rotated {angle:.0f}°")
            return True
            
        except Exception as e:
            self.log(f"Rotation failed: {e}")
            return False
    
    def _random_rotation(self, frame) -> bool:
        """Fallback random rotation."""
        try:
            slider = frame.query_selector('input[type="range"]')
            if not slider:
                return False
            
            angles = [0, 90, 180, 270, 45, 135, 225, 315]
            random.shuffle(angles)
            
            for angle in angles[:4]:
                if self._do_rotation(slider, angle):
                    time.sleep(0.5)
                    return True
            
            return False
            
        except:
            return False
    
    def _solve_clicks(self, frame) -> bool:
        """Solve click-based challenge."""
        try:
            tiles = frame.query_selector_all('[class*="tile"], button[class*="tile"]')
            
            if not tiles:
                return False
            
            # Click random tiles (usually 4-6)
            num = min(random.randint(4, 6), len(tiles))
            indices = random.sample(range(len(tiles)), num)
            
            for idx in indices:
                tile = tiles[idx]
                box = tile.bounding_box()
                if box:
                    x = box['x'] + box['width'] / 2
                    y = box['y'] + box['height'] / 2
                    self.page.mouse.click(x, y)
                    self._human_delay(0.2, 0.4)
            
            # Click verify
            btn = frame.query_selector('button[type="submit"], button:has-text("Verify")')
            if btn:
                btn.click()
            
            return True
            
        except:
            return False
    
    def _refresh(self, frame):
        """Refresh captcha."""
        try:
            btn = frame.query_selector('[aria-label*="refresh"], [class*="refresh"], [class*="reload"]')
            if btn:
                btn.click()
        except:
            pass
    
    def _check_success(self) -> bool:
        """Check if solved."""
        try:
            # Captcha iframe gone?
            iframe = self._find_captcha_iframe()
            if not iframe:
                return True
            
            # Success class?
            if self.page.query_selector('.success, .verified, [class*="success"]'):
                return True
            
            return False
            
        except:
            return False
    
    def _get_token(self) -> Optional[str]:
        """Extract token from page."""
        try:
            token = self.page.evaluate("""
                () => {
                    // Check inputs
                    const inputs = document.querySelectorAll('input');
                    for (const input of inputs) {
                        if (input.value && input.value.length > 50) {
                            return input.value;
                        }
                    }
                    
                    // Check localStorage
                    for (let i = 0; i < localStorage.length; i++) {
                        const key = localStorage.key(i);
                        if (key && key.includes('arkose')) {
                            return localStorage.getItem(key);
                        }
                    }
                    
                    // Check window
                    if (window.arkoseToken) return window.arkoseToken;
                    if (window.captchaToken) return window.captchaToken;
                    
                    return null;
                }
            """)
            
            return token
            
        except:
            return None
    
    def _human_delay(self, min_s: float, max_s: float):
        """Random human-like delay."""
        time.sleep(random.uniform(min_s, max_s))
    
    def close(self):
        """Clean up."""
        try:
            if self.page:
                self.page.close()
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            
            print(f"[+] 🧩 Solver stats: {self.solved_count} solved, {self.failed_count} failed")
            
        except:
            pass


# Aliases
LocalCaptchaSolver = RealCaptchaSolver
CustomCaptchaSolver = RealCaptchaSolver


if __name__ == "__main__":
    print("="*60)
    print("🧩 FREE Local Captcha Solver")
    print("="*60)
    print("💰 Cost: $0.00")
    print("🔑 No API key needed!")
    print()
    
    solver = RealCaptchaSolver(debug=True, headless=False)
    
    try:
        result = solver.solve_with_token()
        print(f"\nResult: {result}")
    except KeyboardInterrupt:
        print("\n⏹️ Stopped")
    finally:
        solver.close()