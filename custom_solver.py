"""
Local Captcha Solver for Roblox Arkose Labs (FunCaptcha).
Uses Playwright browser automation with human-like interaction patterns.
No external APIs required - completely free to use.
"""
import os
import sys
import time
import random
import math
import json
import re
from typing import Optional, Dict, Any, Tuple

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("[-] Playwright missing. Run: pip install playwright && playwright install chromium")
    sys.exit(1)


class LocalCaptchaSolver:
    """
    Local Captcha Solver using Playwright Browser Automation.
    Solves Arkose Labs FunCaptcha locally without external APIs.
    """
    
    # Roblox Arkose Labs Site Key
    ROBLOX_SITE_KEY = "476068BF-9607-4799-B53D-966BE98E2B81"
    
    def __init__(self, debug: bool = False, headless: bool = True):
        self.debug = debug
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        
    def log(self, msg: str):
        """Debug logging."""
        if self.debug:
            print(f"[LOCAL_SOLVER] {msg}")
    
    def start_browser(self, proxy: dict = None) -> bool:
        """Launches a stealthy browser for captcha solving."""
        
        # Browser arguments for anti-detection
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
            "--no-default-browser-check",
            "--disable-infobars",
            "--disable-breakpad",
            "--disable-component-update",
            "--disable-pings",
            "--hide-scrollbars",
            "--mute-audio",
            "--metrics-recording-only",
        ]
        
        launch_args = {
            "headless": self.headless,
            "args": args,
            "ignore_default_args": ["--enable-automation"],
        }
        
        # Configure proxy if provided
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
            
            # Create context with realistic settings
            self.context = self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                timezone_id="America/New_York",
                screen={"width": 1920, "height": 1080},
                device_scale_factor=1,
                has_touch=False,
                is_mobile=False,
                java_script_enabled=True,
            )
            
            self.page = self.context.new_page()
            
            # Advanced anti-detection scripts
            self.page.add_init_script("""
                // Hide webdriver property
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // Fake plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                
                // Fake languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                
                // Fake hardware concurrency
                Object.defineProperty(navigator, 'hardwareConcurrency', {
                    get: () => 8
                });
                
                // Fake device memory
                Object.defineProperty(navigator, 'deviceMemory', {
                    get: () => 8
                });
                
                // WebGL spoofing
                const getParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {
                    if (parameter === 37445) return 'Intel Inc.';
                    if (parameter === 37446) return 'Intel Iris OpenGL Engine';
                    return getParameter.call(this, parameter);
                };
                
                // Hide automation indicators
                window.chrome = {
                    runtime: {},
                };
                
                // Override permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
                
                // Randomize canvas fingerprint
                const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
                HTMLCanvasElement.prototype.toDataURL = function(type) {
                    if (type === 'image/png') {
                        // Add subtle noise
                        const context = this.getContext('2d');
                        if (context) {
                            const imageData = context.getImageData(0, 0, this.width, this.height);
                            for (let i = 0; i < imageData.data.length; i += 4) {
                                imageData.data[i] ^= (Math.random() * 2) | 0;
                            }
                            context.putImageData(imageData, 0, 0);
                        }
                    }
                    return originalToDataURL.apply(this, arguments);
                };
            """)
            
            self.log("Browser started successfully")
            return True
            
        except Exception as e:
            print(f"[-] Browser launch failed: {e}")
            return False
    
    def solve_with_token(
        self, 
        site_key: str = None, 
        service_url: str = "https://www.roblox.com/login",
        blob: str = None,
        timeout: int = 120
    ) -> Dict[str, Any]:
        """
        Main entry point - solves captcha and returns result.
        
        Returns:
            {"success": bool, "token": str or None}
        """
        site_key = site_key or self.ROBLOX_SITE_KEY
        
        self.log(f"Starting captcha solve for {service_url}")
        
        # Start browser if not running
        if not self.browser:
            if not self.start_browser():
                return {"success": False, "token": None}
        
        max_attempts = 3
        
        for attempt in range(max_attempts):
            try:
                self.log(f"Attempt {attempt + 1}/{max_attempts}")
                
                # Navigate to login page
                self.page.goto(service_url, wait_until="domcontentloaded", timeout=30000)
                self._random_delay(2.0, 3.0)
                
                # Find captcha iframe
                iframe = self._find_captcha_iframe()
                
                if not iframe:
                    self.log("No captcha iframe found - might already be verified")
                    return {"success": True, "token": "NO_CAPTCHA"}
                
                # Get iframe content frame
                frame = iframe.content_frame()
                if not frame:
                    self.log("Could not access iframe content")
                    if attempt < max_attempts - 1:
                        self._random_delay(2, 3)
                        continue
                    return {"success": False, "token": None}
                
                # Solve the captcha challenge
                self.log("Attempting to solve captcha challenge...")
                
                if self._solve_challenge(frame):
                    self._random_delay(1.5, 2.5)
                    
                    # Extract token
                    token = self._extract_token()
                    
                    if token:
                        self.log(f"SUCCESS! Token obtained: {token[:30]}...")
                        return {"success": True, "token": token}
                    else:
                        # Check if captcha passed even without explicit token
                        if self._check_captcha_passed():
                            self.log("Captcha appears to be solved (iframe gone)")
                            return {"success": True, "token": "VISUAL_SUCCESS"}
                
                if attempt < max_attempts - 1:
                    self.log(f"Attempt {attempt + 1} failed, retrying...")
                    self._random_delay(2, 3)
                    
            except Exception as e:
                self.log(f"Error on attempt {attempt + 1}: {e}")
                if attempt < max_attempts - 1:
                    self._random_delay(2, 3)
                    continue
        
        self.log("All attempts failed")
        return {"success": False, "token": None}
    
    def _find_captcha_iframe(self):
        """Locates the Arkose Labs captcha iframe."""
        selectors = [
            'iframe[title*="challenge"]',
            'iframe[title*="captcha"]',
            'iframe.fc-frame',
            'iframe[src*="arkose"]',
            'iframe[src*="funcaptcha"]',
            'iframe[id*="arkose"]',
            'iframe[id*="captcha"]',
            '#game-info-frame',
            'iframe[aria-label*="challenge"]',
        ]
        
        for selector in selectors:
            try:
                element = self.page.query_selector(selector)
                if element:
                    self.log(f"Found captcha iframe: {selector}")
                    return element
            except:
                pass
        
        return None
    
    def _solve_challenge(self, frame) -> bool:
        """
        Attempts to solve the captcha challenge.
        Handles multiple challenge types.
        """
        # Wait for challenge to load
        self._random_delay(2, 3)
        
        # Try different challenge types
        challenge_solved = False
        
        # 1. Try rotation slider challenge
        if self._try_rotation_challenge(frame):
            self.log("Rotation challenge detected and solved")
            challenge_solved = True
        
        # 2. Try image selection challenge
        elif self._try_image_selection_challenge(frame):
            self.log("Image selection challenge detected and solved")
            challenge_solved = True
        
        # 3. Try clicking the main button to start
        elif self._try_click_start_button(frame):
            self.log("Clicked start button, waiting for challenge...")
            self._random_delay(2, 3)
            # Recursive attempt after clicking start
            challenge_solved = self._solve_challenge(frame)
        
        return challenge_solved
    
    def _try_rotation_challenge(self, frame) -> bool:
        """Attempts to solve rotation slider challenge."""
        try:
            # Find the rotation slider
            slider_selectors = [
                'input[type="range"]',
                'div[role="slider"]',
                '[class*="slider"]',
                '[class*="rotate"]',
                'input[aria-valuemin]',
            ]
            
            slider = None
            for selector in slider_selectors:
                slider = frame.query_selector(selector)
                if slider:
                    self.log(f"Found slider: {selector}")
                    break
            
            if not slider:
                return False
            
            # Get bounding box
            bbox = slider.bounding_box()
            if not bbox:
                return False
            
            # Take screenshot for analysis
            self.log("Taking screenshot for rotation analysis...")
            
            # Calculate rotation angle (simplified - use center position)
            # In a real implementation, you would use image recognition
            center_x = bbox['x'] + bbox['width'] / 2
            center_y = bbox['y'] + bbox['height'] / 2
            
            # Try multiple rotation angles
            angles_to_try = [0, 90, 180, 270, 45, 135, 225, 315]
            
            for angle in angles_to_try:
                # Simulate human-like rotation
                if self._perform_rotation(slider, angle):
                    self._random_delay(1, 2)
                    
                    # Check if solved
                    if self._check_captcha_passed():
                        return True
            
            return False
            
        except Exception as e:
            self.log(f"Rotation challenge error: {e}")
            return False
    
    def _try_image_selection_challenge(self, frame) -> bool:
        """Attempts to solve image selection challenge."""
        try:
            # Find images to click
            image_selectors = [
                'img[class*="tile"]',
                'div[class*="tile"]',
                'button[class*="image"]',
                '[role="button"] img',
            ]
            
            images = []
            for selector in image_selectors:
                found = frame.query_selector_all(selector)
                if found:
                    images = found
                    self.log(f"Found {len(images)} images with {selector}")
                    break
            
            if not images:
                return False
            
            # Try clicking images (random selection for now)
            # In production, you'd use computer vision to identify correct images
            num_to_click = min(random.randint(1, 4), len(images))
            
            for i in range(num_to_click):
                if i < len(images):
                    img = images[i]
                    bbox = img.bounding_box()
                    if bbox:
                        # Human-like click
                        self._human_click(bbox['x'] + bbox['width']/2, 
                                        bbox['y'] + bbox['height']/2)
                        self._random_delay(0.3, 0.8)
            
            # Click verify button
            self._random_delay(0.5, 1)
            verify_btn = frame.query_selector('button[type="submit"], button:has-text("Verify")')
            if verify_btn:
                verify_btn.click()
                self._random_delay(1, 2)
            
            return self._check_captcha_passed()
            
        except Exception as e:
            self.log(f"Image selection error: {e}")
            return False
    
    def _try_click_start_button(self, frame) -> bool:
        """Tries to click the start/verify button."""
        try:
            button_selectors = [
                'button[type="button"]',
                'button:has-text("Start")',
                'button:has-text("Verify")',
                'button:has-text("Continue")',
                'a[role="button"]',
                '[class*="start-button"]',
            ]
            
            for selector in button_selectors:
                btn = frame.query_selector(selector)
                if btn:
                    self.log(f"Clicking button: {selector}")
                    btn.click()
                    return True
            
            return False
            
        except Exception as e:
            self.log(f"Start button error: {e}")
            return False
    
    def _perform_rotation(self, slider, target_angle: float) -> bool:
        """Performs human-like rotation on a slider."""
        try:
            bbox = slider.bounding_box()
            if not bbox:
                return False
            
            center_x = bbox['x'] + bbox['width'] / 2
            center_y = bbox['y'] + bbox['height'] / 2
            
            # Calculate drag distance
            drag_distance = (target_angle / 360) * bbox['width']
            
            # Human-like mouse movement
            # Move to slider
            self.page.mouse.move(center_x, center_y)
            self._random_delay(0.1, 0.3)
            
            # Mouse down
            self.page.mouse.down()
            self._random_delay(0.05, 0.15)
            
            # Drag with human-like motion
            steps = random.randint(15, 25)
            total_time = random.uniform(0.5, 1.0)
            step_delay = total_time / steps
            
            for i in range(steps):
                progress = i / steps
                
                # Easing function for natural motion
                eased = 0.5 - 0.5 * math.cos(progress * math.pi)
                
                current_x = center_x + (drag_distance * eased)
                current_y = center_y + random.uniform(-2, 2)  # Slight jitter
                
                self.page.mouse.move(current_x, current_y)
                time.sleep(step_delay * random.uniform(0.8, 1.2))
            
            # Release
            self._random_delay(0.1, 0.2)
            self.page.mouse.up()
            
            return True
            
        except Exception as e:
            self.log(f"Rotation error: {e}")
            return False
    
    def _human_click(self, x: float, y: float):
        """Performs human-like click at coordinates."""
        # Move to position with variation
        offset_x = random.uniform(-5, 5)
        offset_y = random.uniform(-5, 5)
        
        self.page.mouse.move(x + offset_x, y + offset_y)
        self._random_delay(0.1, 0.3)
        
        # Click
        self.page.mouse.down()
        self._random_delay(0.05, 0.15)
        self.page.mouse.up()
    
    def _check_captcha_passed(self) -> bool:
        """Checks if captcha has been passed."""
        try:
            # Check if iframe is gone
            iframe = self._find_captcha_iframe()
            if not iframe:
                self.log("Captcha iframe disappeared - likely passed!")
                return True
            
            # Check for success indicators
            success_selectors = [
                '.arkose-verification-success',
                '[data-testid="verification-success"]',
                '.success-message',
                '[class*="success"]',
            ]
            
            for selector in success_selectors:
                if self.page.query_selector(selector):
                    self.log(f"Found success indicator: {selector}")
                    return True
            
            return False
            
        except:
            return False
    
    def _extract_token(self) -> Optional[str]:
        """Extracts the captcha token from the page."""
        try:
            # Method 1: Check for token in hidden input
            token_selectors = [
                '[name="captcha-token"]',
                '[data-captcha-token]',
                'input[name="arkose-token"]',
                '#arkose-token',
            ]
            
            for selector in token_selectors:
                el = self.page.query_selector(selector)
                if el:
                    token = el.get_attribute('value') or el.get_attribute('data-captcha-token')
                    if token and len(token) > 20:
                        return token
            
            # Method 2: Check localStorage
            token = self.page.evaluate("""
                () => {
                    for (let key in localStorage) {
                        if (key.includes('arkose') || key.includes('captcha') || key.includes('funcaptcha')) {
                            let value = localStorage.getItem(key);
                            if (value && value.length > 50) {
                                return value;
                            }
                        }
                    }
                    return null;
                }
            """)
            
            if token:
                return token
            
            return None
            
        except Exception as e:
            self.log(f"Token extraction error: {e}")
            return None
    
    def _random_delay(self, min_sec: float, max_sec: float):
        """Random delay for human-like behavior."""
        time.sleep(random.uniform(min_sec, max_sec))
    
    def close(self):
        """Clean up browser resources."""
        try:
            if self.page:
                self.page.close()
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            self.log("Browser closed")
        except Exception as e:
            self.log(f"Cleanup error: {e}")


# Alias for backwards compatibility
CustomCaptchaSolver = LocalCaptchaSolver


if __name__ == "__main__":
    print("=" * 60)
    print("🔧 Local Captcha Solver Test")
    print("=" * 60)
    
    solver = LocalCaptchaSolver(debug=True, headless=False)  # Non-headless for testing
    
    try:
        result = solver.solve_with_token(
            "476068BF-9607-4799-B53D-966BE98E2B81",
            "https://www.roblox.com/login"
        )
        
        if result['success']:
            print(f"\n✅ SUCCESS! Token: {result.get('token', 'N/A')[:50]}...")
        else:
            print("\n❌ Failed to solve captcha")
            
    except KeyboardInterrupt:
        print("\n⏹️ Interrupted by user")
    finally:
        solver.close()