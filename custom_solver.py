"""
Local Captcha Solver for Roblox Arkose Labs (FunCaptcha).
Uses OpenCV for image analysis and Playwright for browser automation.
"""
import os
import sys
import time
import random
import math
import json
import re
import base64
from typing import Optional, Dict, Any, Tuple, List

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    print("[!] OpenCV missing. Run: pip install opencv-python numpy")

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("[-] Playwright missing. Run: pip install playwright && playwright install chromium")
    sys.exit(1)


class LocalCaptchaSolver:
    """
    Local Captcha Solver using Computer Vision + Browser Automation.
    Solves Arkose Labs FunCaptcha rotation challenges.
    """
    
    ROBLOX_SITE_KEY = "476068BF-9607-4799-B53D-966BE98E2B81"
    
    def __init__(self, debug: bool = False, headless: bool = True):
        self.debug = debug
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        self.solved_count = 0
        self.failed_count = 0
        
    def log(self, msg: str, force: bool = False):
        if self.debug or force:
            print(f"[SOLVER] {msg}")
    
    def start_browser(self, proxy: dict = None) -> bool:
        """Launches a stealth browser."""
        
        args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--window-size=1920,1080",
            "--disable-infobars",
            "--disable-breakpad",
            "--disable-component-update",
            "--no-first-run",
            "--no-zygote",
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-sync",
            "--metrics-recording-only",
            "--mute-audio",
        ]
        
        launch_args = {
            "headless": self.headless,
            "args": args,
            "ignore_default_args": ["--enable-automation"],
        }
        
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
                timezone_id="America/New_York",
                screen={"width": 1920, "height": 1080},
            )
            
            self.page = self.context.new_page()
            
            # Anti-detection
            self.page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en'] });
                Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
                Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
                
                const getParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(p) {
                    if (p === 37445) return 'Intel Inc.';
                    if (p === 37446) return 'Intel Iris OpenGL Engine';
                    return getParameter.call(this, p);
                };
                
                window.chrome = { runtime: {} };
            """)
            
            self.log("Browser started")
            return True
            
        except Exception as e:
            self.log(f"Browser start failed: {e}", force=True)
            return False
    
    def solve_with_token(
        self, 
        site_key: str = None, 
        service_url: str = "https://www.roblox.com/login",
        blob: str = None,
        timeout: int = 120
    ) -> Dict[str, Any]:
        """Main solving entry point."""
        
        if not self.browser:
            if not self.start_browser():
                return {"success": False, "token": None}
        
        self.log(f"Navigating to {service_url}")
        
        try:
            self.page.goto(service_url, wait_until="networkidle", timeout=30000)
            time.sleep(2)
        except Exception as e:
            self.log(f"Navigation error: {e}")
            return {"success": False, "token": None}
        
        # Find captcha iframe
        iframe = self._find_iframe()
        if not iframe:
            self.log("No captcha found")
            return {"success": True, "token": "NO_CAPTCHA"}
        
        frame = iframe.content_frame()
        if not frame:
            return {"success": False, "token": None}
        
        # Solve the challenge
        for attempt in range(5):
            self.log(f"Solve attempt {attempt + 1}/5")
            
            if self._solve_rotation(frame):
                time.sleep(2)
                
                # Check if solved
                if self._check_success():
                    token = self._extract_token()
                    if token:
                        self.solved_count += 1
                        self.log(f"SUCCESS! Token: {token[:40]}...", force=True)
                        return {"success": True, "token": token}
                    return {"success": True, "token": "VISUAL_SUCCESS"}
            
            # Refresh and try again
            self._refresh_challenge(frame)
            time.sleep(2)
        
        self.failed_count += 1
        self.log("All attempts failed", force=True)
        return {"success": False, "token": None}
    
    def _find_iframe(self):
        """Find captcha iframe."""
        selectors = [
            'iframe[title*="challenge"]',
            'iframe[src*="arkose"]',
            'iframe[src*="funcaptcha"]',
            'iframe.fc-frame',
            '#game-info-frame',
        ]
        
        for sel in selectors:
            try:
                el = self.page.query_selector(sel)
                if el:
                    return el
            except:
                pass
        return None
    
    def _solve_rotation(self, frame) -> bool:
        """Solve the rotation challenge using CV."""
        
        # Wait for challenge to load
        time.sleep(2)
        
        # Find slider
        slider = None
        for sel in ['input[type="range"]', 'div[role="slider"]', '[class*="slider"]']:
            slider = frame.query_selector(sel)
            if slider:
                break
        
        if not slider:
            self.log("No slider found")
            return False
        
        # Get canvas/image area
        canvas_area = frame.query_selector('canvas, [class*="game"], [class*="challenge"]')
        
        # Take screenshot of the captcha area
        try:
            # Get the iframe position
            iframe_box = self._find_iframe().bounding_box()
            if not iframe_box:
                return False
            
            # Screenshot the captcha area
            screenshot = self.page.screenshot(type="png", clip={
                'x': iframe_box['x'],
                'y': iframe_box['y'],
                'width': iframe_box['width'],
                'height': iframe_box['height']
            })
            
            # Analyze to find rotation angle
            angle = self._analyze_rotation_angle(screenshot)
            self.log(f"Detected angle: {angle:.1f}°")
            
        except Exception as e:
            self.log(f"Screenshot error: {e}")
            angle = random.uniform(0, 360)
        
        # Perform the rotation
        return self._rotate_slider(slider, angle)
    
    def _analyze_rotation_angle(self, image_bytes: bytes) -> float:
        """Analyze image to determine correct rotation angle."""
        
        if not HAS_CV2:
            return random.uniform(0, 360)
        
        try:
            # Decode image
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                return random.uniform(0, 360)
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Edge detection
            edges = cv2.Canny(gray, 50, 150)
            
            # Find contours
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                return random.uniform(0, 360)
            
            # Find largest contour (the rotated object)
            largest = max(contours, key=cv2.contourArea)
            
            if cv2.contourArea(largest) < 500:
                return random.uniform(0, 360)
            
            # Get minimum area rectangle
            rect = cv2.minAreaRect(largest)
            center, size, angle = rect
            
            # Adjust angle
            if size[0] < size[1]:
                angle = angle + 90
            
            # Normalize to 0-360
            angle = angle % 360
            
            # The target is usually "upright" (0 or 360 degrees)
            # Calculate how much to rotate to make it upright
            if angle > 180:
                angle = 360 - angle
            
            return angle
            
        except Exception as e:
            self.log(f"CV analysis error: {e}")
            return random.uniform(0, 360)
    
    def _rotate_slider(self, slider, angle: float) -> bool:
        """Rotate the slider to the target angle."""
        
        try:
            bbox = slider.bounding_box()
            if not bbox:
                return False
            
            center_x = bbox['x'] + bbox['width'] / 2
            center_y = bbox['y'] + bbox['height'] / 2
            
            # Calculate drag distance (assuming 360° = slider width)
            # We need to rotate TO the correct angle
            target_offset = (angle / 360) * bbox['width']
            
            # Add small randomization
            target_offset += random.uniform(-3, 3)
            
            # Move to slider
            self.page.mouse.move(center_x, center_y - 20)
            time.sleep(random.uniform(0.1, 0.3))
            
            # Move to slider center
            self.page.mouse.move(center_x, center_y)
            time.sleep(random.uniform(0.1, 0.2))
            
            # Click and hold
            self.page.mouse.down()
            time.sleep(random.uniform(0.1, 0.2))
            
            # Drag with human-like motion
            steps = random.randint(20, 30)
            
            for i in range(steps):
                progress = i / steps
                
                # Ease-in-out curve
                eased = 0.5 - 0.5 * math.cos(progress * math.pi)
                
                x = center_x + (target_offset * eased)
                y = center_y + random.uniform(-2, 2)
                
                self.page.mouse.move(x, y)
                time.sleep(random.uniform(0.01, 0.03))
            
            # Release
            time.sleep(random.uniform(0.1, 0.2))
            self.page.mouse.up()
            
            self.log(f"Rotated to {angle:.1f}°")
            return True
            
        except Exception as e:
            self.log(f"Rotation error: {e}")
            return False
    
    def _refresh_challenge(self, frame):
        """Refresh the captcha challenge."""
        try:
            # Look for refresh button
            refresh_btn = frame.query_selector('[aria-label*="refresh"], [title*="refresh"], button[class*="refresh"]')
            if refresh_btn:
                refresh_btn.click()
                self.log("Challenge refreshed")
        except:
            pass
    
    def _check_success(self) -> bool:
        """Check if captcha passed."""
        try:
            # If iframe is gone, success
            if not self._find_iframe():
                return True
            
            # Check for success indicators
            success = self.page.query_selector('.success, [class*="verified"], [class*="complete"]')
            return success is not None
        except:
            return False
    
    def _extract_token(self) -> Optional[str]:
        """Extract captcha token."""
        try:
            # Check page for token
            token = self.page.evaluate("""
                () => {
                    // Check inputs
                    const inputs = document.querySelectorAll('input[name*="captcha"], input[name*="arkose"]');
                    for (const input of inputs) {
                        if (input.value && input.value.length > 20) return input.value;
                    }
                    
                    // Check localStorage
                    for (let i = 0; i < localStorage.length; i++) {
                        const key = localStorage.key(i);
                        if (key.includes('arkose') || key.includes('captcha')) {
                            const val = localStorage.getItem(key);
                            if (val && val.length > 20) return val;
                        }
                    }
                    
                    return null;
                }
            """)
            
            return token
        except:
            return None
    
    def close(self):
        """Cleanup."""
        try:
            if self.page:
                self.page.close()
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            self.log(f"Closed (solved: {self.solved_count}, failed: {self.failed_count})")
        except:
            pass


# Backwards compatibility
CustomCaptchaSolver = LocalCaptchaSolver


if __name__ == "__main__":
    print("=" * 50)
    print("🔧 Local Captcha Solver Test")
    print("=" * 50)
    
    solver = LocalCaptchaSolver(debug=True, headless=False)
    
    try:
        result = solver.solve_with_token()
        print(f"\nResult: {result}")
    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        solver.close()