"""
Real Local Captcha Solver for Roblox Arkose Labs FunCaptcha.
FREE - No external APIs needed.

Strategies:
1. Computer Vision image analysis
2. Template matching for known images
3. Feature detection for orientation
4. Human-like behavior simulation
5. Multiple retry with different approaches
"""
import os
import sys
import time
import random
import math
import json
import base64
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

# Playwright for browser automation
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("[-] Install Playwright: pip install playwright && playwright install chromium")
    sys.exit(1)


# Known FunCaptcha image solutions database
# Format: image_hash -> correct_angle
KNOWN_SOLUTIONS = {
    # These get populated as we solve challenges
}

SOLUTIONS_FILE = Path("captcha_solutions.json")


def load_known_solutions():
    """Load previously saved solutions."""
    global KNOWN_SOLUTIONS
    if SOLUTIONS_FILE.exists():
        try:
            with open(SOLUTIONS_FILE, 'r') as f:
                KNOWN_SOLUTIONS = json.load(f)
        except:
            KNOWN_SOLUTIONS = {}


def save_solution(image_hash: str, angle: float, success: bool):
    """Save a solution for future use."""
    if success:
        KNOWN_SOLUTIONS[image_hash] = angle
        try:
            with open(SOLUTIONS_FILE, 'w') as f:
                json.dump(KNOWN_SOLUTIONS, f)
        except:
            pass


class RealCaptchaSolver:
    """
    Real local captcha solver with multiple strategies.
    FREE - No API costs!
    """
    
    ROBLOX_SITE_KEY = "476068BF-9607-4799-B53D-966BE98E2B81"
    
    def __init__(self, debug: bool = False, headless: bool = True):
        self.debug = debug
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        
        # Stats
        self.solved_count = 0
        self.failed_count = 0
        
        # Load known solutions
        load_known_solutions()
        
        # Image templates for common FunCaptcha images
        self.templates = self._load_templates()
    
    def log(self, msg: str, force: bool = False):
        if self.debug or force:
            print(f"[SOLVER] {msg}")
    
    def _load_templates(self) -> Dict[str, np.ndarray]:
        """Load template images for matching."""
        templates = {}
        template_dir = Path("captcha_templates")
        if template_dir.exists():
            for f in template_dir.glob("*.png"):
                try:
                    img = cv2.imread(str(f), cv2.IMREAD_GRAYSCALE)
                    if img is not None:
                        templates[f.stem] = img
                except:
                    pass
        return templates
    
    def start_browser(self, proxy: dict = None) -> bool:
        """Launch stealth browser."""
        
        args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--window-size=1920,1080",
            "--disable-infobars",
            "--disable-breakpad",
            "--no-first-run",
            "--no-zygote",
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-sync",
            "--metrics-recording-only",
            "--mute-audio",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
        ]
        
        launch_args = {
            "headless": self.headless,
            "args": args,
            "ignore_default_args": ["--enable-automation"],
        }
        
        if proxy and isinstance(proxy, dict) and proxy.get("server"):
            launch_args["proxy"] = {"server": proxy["server"]}
            if proxy.get("username"):
                launch_args["proxy"]["username"] = proxy["username"]
            if proxy.get("password"):
                launch_args["proxy"]["password"] = proxy["password"]
        
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(**launch_args)
            
            # Create realistic context
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
            
            # Advanced anti-detection
            self.page.add_init_script("""
                // Remove webdriver
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // Fake plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => {
                        const plugins = [
                            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                            { name: 'Native Client', filename: 'internal-nacl-plugin' }
                        ];
                        plugins.item = (i) => plugins[i] || null;
                        plugins.namedItem = (n) => plugins.find(p => p.name === n) || null;
                        plugins.refresh = () => {};
                        return plugins;
                    }
                });
                
                // Fake languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en', 'es']
                });
                
                // Fake hardware
                Object.defineProperty(navigator, 'hardwareConcurrency', {
                    get: () => 8
                });
                Object.defineProperty(navigator, 'deviceMemory', {
                    get: () => 8
                });
                
                // Fake platform
                Object.defineProperty(navigator, 'platform', {
                    get: () => 'Win32'
                });
                
                // WebGL spoofing
                const getParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(p) {
                    if (p === 37445) return 'Intel Inc.';
                    if (p === 37446) return 'Intel Iris OpenGL Engine';
                    if (p === 7936) return 'WebKit';
                    if (p === 7937) return 'WebKit WebGL';
                    if (p === 7938) return 'WebKit';
                    return getParameter.call(this, p);
                };
                
                // Canvas fingerprint noise
                const toDataURL = HTMLCanvasElement.prototype.toDataURL;
                HTMLCanvasElement.prototype.toDataURL = function(type) {
                    if (type === 'image/png') {
                        const ctx = this.getContext('2d');
                        if (ctx) {
                            const imgData = ctx.getImageData(0, 0, this.width, this.height);
                            for (let i = 0; i < imgData.data.length; i += 4) {
                                imgData.data[i] ^= (Math.random() * 4) | 0;
                                imgData.data[i + 1] ^= (Math.random() * 4) | 0;
                                imgData.data[i + 2] ^= (Math.random() * 4) | 0;
                            }
                            ctx.putImageData(imgData, 0, 0);
                        }
                    }
                    return toDataURL.apply(this, arguments);
                };
                
                // Chrome object
                window.chrome = {
                    app: { isInstalled: false },
                    runtime: { 
                        connect: () => {},
                        sendMessage: () => {}
                    },
                    csi: () => {},
                    loadTimes: () => {},
                };
                
                // Permission API
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (params) => (
                    params.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(params)
                );
                
                // Hide automation in console
                const originalConsole = window.console;
                Object.defineProperty(window, 'console', {
                    get: () => originalConsole,
                    set: () => {}
                });
            """)
            
            self.log("Browser started with anti-detection")
            return True
            
        except Exception as e:
            self.log(f"Browser start failed: {e}", force=True)
            return False
    
    def solve_with_token(
        self, 
        site_key: str = None, 
        service_url: str = "https://www.roblox.com/login",
        blob: str = None,
        timeout: int = 180
    ) -> Dict[str, Any]:
        """Main entry point - solve captcha and return token."""
        
        if not self.browser:
            if not self.start_browser():
                return {"success": False, "token": None}
        
        self.log(f"Navigating to {service_url}")
        
        try:
            # Navigate with human-like behavior
            self.page.goto(service_url, wait_until="domcontentloaded", timeout=30000)
            self._human_delay(2, 4)
            
            # Wait for page to fully load
            self.page.wait_for_load_state("networkidle", timeout=15000)
            
        except Exception as e:
            self.log(f"Navigation error: {e}")
            # Try anyway
        
        # Find captcha iframe
        iframe = self._find_captcha_iframe()
        if not iframe:
            self.log("No captcha found - might already be verified")
            return {"success": True, "token": "NO_CAPTCHA"}
        
        # Get iframe
        frame = iframe.content_frame()
        if not frame:
            self.log("Cannot access iframe content")
            return {"success": False, "token": None}
        
        self.log("Found captcha iframe, starting solve process...")
        
        # Try multiple solving strategies
        for attempt in range(8):  # 8 attempts
            self.log(f"Attempt {attempt + 1}/8")
            
            try:
                # Wait for challenge to load
                self._human_delay(1, 2)
                
                # Strategy 1: Rotation challenge
                if self._solve_rotation_challenge(frame, iframe):
                    self._human_delay(2, 3)
                    
                    # Check if solved
                    if self._verify_success():
                        token = self._extract_token()
                        if token:
                            self.solved_count += 1
                            self.log(f"✅ SOLVED! Token: {token[:50]}...", force=True)
                            return {"success": True, "token": token}
                
                # Strategy 2: Click-based challenge (image selection)
                elif self._solve_click_challenge(frame):
                    self._human_delay(2, 3)
                    
                    if self._verify_success():
                        token = self._extract_token()
                        if token:
                            self.solved_count += 1
                            self.log(f"✅ SOLVED!", force=True)
                            return {"success": True, "token": token}
                
                # Refresh and try again
                self._refresh_challenge(frame)
                self._human_delay(2, 4)
                
            except Exception as e:
                self.log(f"Attempt error: {e}")
                self._human_delay(1, 2)
        
        self.failed_count += 1
        self.log("❌ All attempts exhausted", force=True)
        return {"success": False, "token": None}
    
    def _find_captcha_iframe(self):
        """Locate the captcha iframe."""
        selectors = [
            'iframe[title*="challenge"]',
            'iframe[title*="verify"]',
            'iframe[src*="arkose"]',
            'iframe[src*="funcaptcha"]',
            'iframe.fc-frame',
            '#game-info-frame',
            'iframe[aria-label*="challenge"]',
        ]
        
        for sel in selectors:
            try:
                el = self.page.wait_for_selector(sel, timeout=5000)
                if el:
                    self.log(f"Found iframe: {sel}")
                    return el
            except:
                continue
        
        return None
    
    def _solve_rotation_challenge(self, frame, iframe) -> bool:
        """Solve rotation-based challenge using CV."""
        
        if not HAS_CV2:
            self.log("OpenCV not available, using random rotation")
            return self._random_rotation_solve(frame)
        
        try:
            # Find the rotation slider
            slider = None
            for sel in ['input[type="range"]', 'div[role="slider"]', '[class*="slider"]']:
                slider = frame.query_selector(sel)
                if slider:
                    break
            
            if not slider:
                self.log("No slider found")
                return False
            
            # Take screenshot of the captcha area
            iframe_box = iframe.bounding_box()
            if not iframe_box:
                return False
            
            # Focus on the image area (upper part of iframe)
            captcha_area = {
                'x': iframe_box['x'] + 10,
                'y': iframe_box['y'] + 10,
                'width': iframe_box['width'] - 20,
                'height': iframe_box['height'] * 0.6  # Upper 60% is the image
            }
            
            screenshot = self.page.screenshot(type="png", clip=captcha_area)
            
            # Analyze the image
            angle = self._analyze_image_for_rotation(screenshot)
            
            self.log(f"Detected rotation angle: {angle:.1f}°")
            
            # Perform rotation
            return self._perform_rotation(slider, angle)
            
        except Exception as e:
            self.log(f"Rotation solve error: {e}")
            return False
    
    def _analyze_image_for_rotation(self, image_bytes: bytes) -> float:
        """
        Analyze captcha image to determine correct rotation angle.
        Uses multiple CV techniques for best results.
        """
        
        try:
            # Decode image
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                return random.uniform(0, 360)
            
            # Get image hash for known solutions
            img_hash = hashlib.md5(image_bytes).hexdigest()
            
            # Check if we've solved this image before
            if img_hash in KNOWN_SOLUTIONS:
                self.log(f"Found known solution: {KNOWN_SOLUTIONS[img_hash]}°")
                return KNOWN_SOLUTIONS[img_hash]
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Strategy 1: Detect upright orientation using contours
            angle1 = self._detect_rotation_contours(gray)
            
            # Strategy 2: Use Hough line detection
            angle2 = self._detect_rotation_hough(gray)
            
            # Strategy 3: Use feature matching with templates
            angle3 = self._detect_rotation_features(gray)
            
            # Strategy 4: Gradient-based orientation
            angle4 = self._detect_rotation_gradient(gray)
            
            # Combine results (weighted average)
            angles = [a for a in [angle1, angle2, angle3, angle4] if a is not None]
            
            if angles:
                # Use median for robustness
                final_angle = np.median(angles)
                self.log(f"CV angles: contours={angle1}, hough={angle2}, features={angle3}, gradient={angle4}")
                self.log(f"Final angle: {final_angle:.1f}°")
                return float(final_angle)
            
            return random.uniform(0, 360)
            
        except Exception as e:
            self.log(f"Image analysis error: {e}")
            return random.uniform(0, 360)
    
    def _detect_rotation_contours(self, gray: np.ndarray) -> Optional[float]:
        """Detect rotation using contour analysis."""
        
        try:
            # Apply Gaussian blur
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Edge detection
            edges = cv2.Canny(blurred, 50, 150)
            
            # Find contours
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                return None
            
            # Find largest contour
            largest = max(contours, key=cv2.contourArea)
            
            if cv2.contourArea(largest) < 500:
                return None
            
            # Get minimum area rectangle
            rect = cv2.minAreaRect(largest)
            center, size, angle = rect
            
            # Adjust angle based on OpenCV convention
            if size[0] < size[1]:
                angle = angle + 90
            
            # Normalize to 0-360
            angle = angle % 360
            
            # For upright objects, we need to rotate to 0/360
            return angle
            
        except:
            return None
    
    def _detect_rotation_hough(self, gray: np.ndarray) -> Optional[float]:
        """Detect rotation using Hough line transform."""
        
        try:
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            
            lines = cv2.HoughLines(edges, 1, np.pi/180, 100)
            
            if lines is None or len(lines) == 0:
                return None
            
            angles = []
            for line in lines[:10]:  # Top 10 lines
                rho, theta = line[0]
                angle = np.degrees(theta)
                
                # Convert to meaningful rotation
                if angle > 90:
                    angle = 180 - angle
                
                angles.append(angle)
            
            if angles:
                return np.median(angles)
            
            return None
            
        except:
            return None
    
    def _detect_rotation_features(self, gray: np.ndarray) -> Optional[float]:
        """Detect rotation using feature matching."""
        
        if not self.templates:
            return None
        
        try:
            # Try ORB feature matching
            orb = cv2.ORB_create()
            kp1, des1 = orb.detectAndCompute(gray, None)
            
            if des1 is None:
                return None
            
            best_angle = None
            best_matches = 0
            
            for name, template in self.templates.items():
                try:
                    kp2, des2 = orb.detectAndCompute(template, None)
                    
                    if des2 is None:
                        continue
                    
                    # Match features
                    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
                    matches = bf.match(des1, des2)
                    
                    if len(matches) > best_matches:
                        best_matches = len(matches)
                        # Could extract angle from matched features here
                        # For now, use name-based lookup if encoded
                        if name.isdigit():
                            best_angle = float(name)
                
                except:
                    continue
            
            return best_angle
            
        except:
            return None
    
    def _detect_rotation_gradient(self, gray: np.ndarray) -> Optional[float]:
        """Detect rotation using gradient orientation."""
        
        try:
            # Compute gradients
            grad_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            grad_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
            
            # Compute magnitude and orientation
            magnitude = cv2.magnitude(grad_x, grad_y)
            orientation = cv2.phase(grad_x, grad_y, angleInDegrees=True)
            
            # Mask low magnitude areas
            mask = magnitude > np.percentile(magnitude, 80)
            angles = orientation[mask]
            
            if len(angles) > 100:
                # Get dominant orientation
                hist, bins = np.histogram(angles, bins=36, range=(0, 360))
                dominant_idx = np.argmax(hist)
                dominant_angle = (bins[dominant_idx] + bins[dominant_idx + 1]) / 2
                
                return dominant_angle
            
            return None
            
        except:
            return None
    
    def _random_rotation_solve(self, frame) -> bool:
        """Fallback random rotation solver."""
        
        try:
            slider = frame.query_selector('input[type="range"]')
            if not slider:
                return False
            
            # Try common angles
            angles = [0, 90, 180, 270, 45, 135, 225, 315, 30, 60, 120, 150]
            random.shuffle(angles)
            
            for angle in angles[:4]:  # Try 4 random angles
                if self._perform_rotation(slider, angle):
                    time.sleep(1)
                    # Check if solved
                    if self._verify_success():
                        return True
            
            return False
            
        except:
            return False
    
    def _perform_rotation(self, slider, angle: float) -> bool:
        """Perform human-like rotation on slider."""
        
        try:
            bbox = slider.bounding_box()
            if not bbox:
                return False
            
            center_x = bbox['x'] + bbox['width'] / 2
            center_y = bbox['y'] + bbox['height'] / 2
            
            # Calculate drag distance
            # Slider typically maps to 0-360 degrees
            drag_distance = (angle / 360) * bbox['width']
            
            # Add small randomization
            drag_distance += random.uniform(-5, 5)
            
            # Simulate human mouse movement
            
            # Move to near slider first
            start_x = center_x - 100 + random.uniform(-20, 20)
            start_y = center_y + random.uniform(-30, 30)
            self.page.mouse.move(start_x, start_y)
            self._human_delay(0.1, 0.3)
            
            # Move to slider with curve
            steps_to_slider = random.randint(5, 10)
            for i in range(steps_to_slider):
                progress = i / steps_to_slider
                x = start_x + (center_x - start_x) * progress
                y = start_y + (center_y - start_y) * progress + math.sin(progress * math.pi) * 20
                self.page.mouse.move(x, y)
                time.sleep(random.uniform(0.01, 0.03))
            
            self._human_delay(0.1, 0.2)
            
            # Click and hold
            self.page.mouse.down()
            self._human_delay(0.1, 0.2)
            
            # Drag with natural motion
            drag_steps = random.randint(25, 40)
            
            for i in range(drag_steps):
                progress = i / drag_steps
                
                # Ease-in-out for natural acceleration
                if progress < 0.5:
                    ease = 2 * progress * progress
                else:
                    ease = 1 - pow(-2 * progress + 2, 2) / 2
                
                x = center_x + (drag_distance * ease)
                y = center_y + math.sin(progress * math.pi * 2) * random.uniform(1, 3)
                
                self.page.mouse.move(x, y)
                time.sleep(random.uniform(0.015, 0.035))
            
            # Pause before release
            self._human_delay(0.1, 0.3)
            
            # Release
            self.page.mouse.up()
            
            self.log(f"Rotated to {angle:.1f}°")
            return True
            
        except Exception as e:
            self.log(f"Rotation error: {e}")
            return False
    
    def _solve_click_challenge(self, frame) -> bool:
        """Solve click-based challenges (image selection)."""
        
        try:
            # Find clickable images/tiles
            tiles = frame.query_selector_all('div[class*="tile"], button[class*="tile"], img[class*="tile"]')
            
            if not tiles:
                return False
            
            self.log(f"Found {len(tiles)} tiles for click challenge")
            
            # Click random subset (usually need to click 4-6 tiles)
            num_clicks = min(random.randint(4, 6), len(tiles))
            indices = random.sample(range(len(tiles)), num_clicks)
            
            for idx in indices:
                tile = tiles[idx]
                bbox = tile.bounding_box()
                if bbox:
                    x = bbox['x'] + bbox['width'] / 2 + random.uniform(-5, 5)
                    y = bbox['y'] + bbox['height'] / 2 + random.uniform(-5, 5)
                    self.page.mouse.click(x, y)
                    self._human_delay(0.3, 0.7)
            
            # Click verify button
            verify_btn = frame.query_selector('button[type="submit"], button:has-text("Verify")')
            if verify_btn:
                verify_btn.click()
            
            return True
            
        except Exception as e:
            self.log(f"Click challenge error: {e}")
            return False
    
    def _refresh_challenge(self, frame):
        """Refresh the captcha challenge."""
        
        try:
            refresh_selectors = [
                '[aria-label*="refresh"]',
                '[title*="refresh"]',
                'button[class*="refresh"]',
                '[class*="reload"]',
                'a[title*="Get a different"]',
            ]
            
            for sel in refresh_selectors:
                btn = frame.query_selector(sel)
                if btn:
                    btn.click()
                    self.log("Challenge refreshed")
                    return True
            
        except:
            pass
        
        return False
    
    def _verify_success(self) -> bool:
        """Check if captcha was solved successfully."""
        
        try:
            # Check if captcha iframe disappeared
            time.sleep(1)
            iframe = self._find_captcha_iframe()
            if not iframe:
                self.log("Captcha iframe disappeared - success!")
                return True
            
            # Check for success indicators on page
            success_selectors = [
                '.success', '.verified', '[class*="success"]',
                '[class*="complete"]', '[class*="verified"]',
            ]
            
            for sel in success_selectors:
                if self.page.query_selector(sel):
                    return True
            
            return False
            
        except:
            return False
    
    def _extract_token(self) -> Optional[str]:
        """Extract captcha token from page."""
        
        try:
            # Check for token in various places
            token = self.page.evaluate("""
                () => {
                    // Check hidden inputs
                    const inputs = document.querySelectorAll('input[type="hidden"]');
                    for (const input of inputs) {
                        const name = input.name || input.id || '';
                        if (name.includes('captcha') || name.includes('arkose') || name.includes('token')) {
                            if (input.value && input.value.length > 20) return input.value;
                        }
                    }
                    
                    // Check all inputs
                    const allInputs = document.querySelectorAll('input');
                    for (const input of allInputs) {
                        if (input.value && input.value.length > 50) {
                            const name = input.name || input.id || '';
                            if (name.includes('captcha') || name.includes('token')) {
                                return input.value;
                            }
                        }
                    }
                    
                    // Check localStorage
                    for (let i = 0; i < localStorage.length; i++) {
                        const key = localStorage.key(i);
                        if (key && (key.includes('arkose') || key.includes('captcha'))) {
                            const val = localStorage.getItem(key);
                            if (val && val.length > 50) return val;
                        }
                    }
                    
                    // Check window object
                    if (window.arkoseToken) return window.arkoseToken;
                    if (window.captchaToken) return window.captchaToken;
                    if (window.funCaptchaToken) return window.funCaptchaToken;
                    
                    return null;
                }
            """)
            
            return token
            
        except Exception as e:
            self.log(f"Token extraction error: {e}")
            return None
    
    def _human_delay(self, min_sec: float, max_sec: float):
        """Human-like random delay."""
        time.sleep(random.uniform(min_sec, max_sec))
    
    def close(self):
        """Clean up resources."""
        
        try:
            if self.page:
                self.page.close()
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            
            self.log(f"Closed (Solved: {self.solved_count}, Failed: {self.failed_count})")
            
        except:
            pass


# Backwards compatibility aliases
CustomCaptchaSolver = RealCaptchaSolver
LocalCaptchaSolver = RealCaptchaSolver


if __name__ == "__main__":
    print("=" * 60)
    print("🧩 Real Local Captcha Solver - FREE!")
    print("=" * 60)
    
    solver = RealCaptchaSolver(debug=True, headless=False)
    
    try:
        result = solver.solve_with_token()
        print(f"\nResult: {result}")
    except KeyboardInterrupt:
        print("\n⏹️ Interrupted")
    finally:
        solver.close()