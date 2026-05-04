"""
Real Local Captcha Solver for Roblox Arkose Labs FunCaptcha.
FREE - No external APIs needed.

Enhanced Version with:
1. Advanced Computer Vision image analysis
2. Multi-pass rotation detection
3. Deep learning-style feature extraction
4. Template matching for known images
5. Edge orientation analysis
6. Symmetry detection
7. Human-like behavior simulation
8. Learning database for known solutions
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
from collections import defaultdict

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
KNOWN_SOLUTIONS = {}

# Learning database with confidence scores
SOLUTION_DATABASE = {
    # image_hash -> {angle: float, confidence: float, attempts: int, successes: int}
}

SOLUTIONS_FILE = Path("captcha_solutions.json")
LEARNING_FILE = Path("captcha_learning.json")


def load_known_solutions():
    """Load previously saved solutions."""
    global KNOWN_SOLUTIONS, SOLUTION_DATABASE
    
    if SOLUTIONS_FILE.exists():
        try:
            with open(SOLUTIONS_FILE, 'r') as f:
                KNOWN_SOLUTIONS = json.load(f)
        except:
            KNOWN_SOLUTIONS = {}
    
    if LEARNING_FILE.exists():
        try:
            with open(LEARNING_FILE, 'r') as f:
                SOLUTION_DATABASE = json.load(f)
        except:
            SOLUTION_DATABASE = {}


def save_solution(image_hash: str, angle: float, success: bool):
    """Save a solution for future use with learning."""
    global SOLUTION_DATABASE
    
    if success:
        KNOWN_SOLUTIONS[image_hash] = angle
        
        # Update learning database
        if image_hash not in SOLUTION_DATABASE:
            SOLUTION_DATABASE[image_hash] = {
                'angle': angle,
                'confidence': 1.0,
                'attempts': 1,
                'successes': 1
            }
        else:
            entry = SOLUTION_DATABASE[image_hash]
            entry['attempts'] += 1
            entry['successes'] += 1
            # Increase confidence
            entry['confidence'] = min(1.0, entry['confidence'] + 0.1)
        
        try:
            with open(SOLUTIONS_FILE, 'w') as f:
                json.dump(KNOWN_SOLUTIONS, f, indent=2)
            with open(LEARNING_FILE, 'w') as f:
                json.dump(SOLUTION_DATABASE, f, indent=2)
        except:
            pass
    else:
        # Track failures for learning
        if image_hash not in SOLUTION_DATABASE:
            SOLUTION_DATABASE[image_hash] = {
                'angle': angle,
                'confidence': 0.5,
                'attempts': 1,
                'successes': 0
            }
        else:
            SOLUTION_DATABASE[image_hash]['attempts'] += 1
            # Decrease confidence on failure
            SOLUTION_DATABASE[image_hash]['confidence'] *= 0.8


class EnhancedCVAnalyzer:
    """Advanced computer vision analyzer for captcha images."""
    
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.template_cache = {}
    
    def log(self, msg: str):
        if self.debug:
            print(f"[CV] {msg}")
    
    def analyze_image(self, image_bytes: bytes) -> Dict[str, Any]:
        """
        Comprehensive image analysis using multiple CV techniques.
        Returns dict with angle predictions and confidence scores.
        """
        
        if not HAS_CV2:
            return {'angle': random.uniform(0, 360), 'confidence': 0.1, 'method': 'random'}
        
        try:
            # Decode image
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                return {'angle': random.uniform(0, 360), 'confidence': 0.1, 'method': 'random'}
            
            # Get image hash
            img_hash = hashlib.md5(image_bytes).hexdigest()
            
            # Check known solutions first
            if img_hash in KNOWN_SOLUTIONS:
                return {
                    'angle': KNOWN_SOLUTIONS[img_hash],
                    'confidence': 1.0,
                    'method': 'known_solution',
                    'hash': img_hash
                }
            
            # Convert to various color spaces
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
            
            # Run all detection methods
            results = []
            
            # Method 1: Contour-based rotation
            angle1, conf1 = self._detect_contour_rotation(gray)
            if conf1 > 0.3:
                results.append(('contour', angle1, conf1))
            
            # Method 2: Hough line detection
            angle2, conf2 = self._detect_hough_rotation(gray)
            if conf2 > 0.3:
                results.append(('hough', angle2, conf2))
            
            # Method 3: Edge orientation histogram
            angle3, conf3 = self._detect_edge_orientation(gray)
            if conf3 > 0.3:
                results.append(('edge_ori', angle3, conf3))
            
            # Method 4: Symmetry detection
            angle4, conf4 = self._detect_symmetry_rotation(gray)
            if conf4 > 0.3:
                results.append(('symmetry', angle4, conf4))
            
            # Method 5: Gradient structure analysis
            angle5, conf5 = self._detect_gradient_structure(gray)
            if conf5 > 0.3:
                results.append(('gradient', angle5, conf5))
            
            # Method 6: Corner detection and clustering
            angle6, conf6 = self._detect_corner_rotation(gray)
            if conf6 > 0.3:
                results.append(('corner', angle6, conf6))
            
            # Method 7: Color histogram orientation
            angle7, conf7 = self._detect_color_orientation(img, hsv)
            if conf7 > 0.3:
                results.append(('color_ori', angle7, conf7))
            
            # Method 8: Shape matching with upright templates
            angle8, conf8 = self._detect_shape_match(gray)
            if conf8 > 0.3:
                results.append(('shape', angle8, conf8))
            
            if not results:
                return {'angle': random.uniform(0, 360), 'confidence': 0.2, 'method': 'no_detection'}
            
            # Weighted average based on confidence
            total_weight = sum(r[2] for r in results)
            weighted_angle = sum(r[1] * r[2] for r in results) / total_weight
            avg_confidence = total_weight / len(results)
            
            # Find best method
            best_method = max(results, key=lambda x: x[2])
            
            # Log all results
            self.log(f"Detection results: {[(r[0], f'{r[1]:.1f}°', f'{r[2]:.2f}') for r in results]}")
            self.log(f"Final: {weighted_angle:.1f}° (confidence: {avg_confidence:.2f}, best: {best_method[0]})")
            
            return {
                'angle': weighted_angle,
                'confidence': avg_confidence,
                'method': 'weighted',
                'details': results,
                'hash': img_hash
            }
            
        except Exception as e:
            self.log(f"Analysis error: {e}")
            return {'angle': random.uniform(0, 360), 'confidence': 0.1, 'method': 'error'}
    
    def _detect_contour_rotation(self, gray: np.ndarray) -> Tuple[float, float]:
        """Detect rotation using contour analysis."""
        try:
            # Multi-scale edge detection
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(blurred, 30, 100)
            
            # Dilate to connect edges
            kernel = np.ones((3, 3), np.uint8)
            edges = cv2.dilate(edges, kernel, iterations=1)
            
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                return 0, 0
            
            # Get largest contours
            large_contours = sorted(contours, key=cv2.contourArea, reverse=True)[:3]
            
            angles = []
            for contour in large_contours:
                area = cv2.contourArea(contour)
                if area < 100:
                    continue
                
                # Minimum area rectangle
                rect = cv2.minAreaRect(contour)
                center, size, angle = rect
                
                # Adjust angle
                if size[0] < size[1]:
                    angle = angle + 90
                
                angles.append(angle % 360)
            
            if angles:
                # Use circular mean for angles
                sin_sum = sum(math.sin(math.radians(a)) for a in angles)
                cos_sum = sum(math.cos(math.radians(a)) for a in angles)
                mean_angle = math.degrees(math.atan2(sin_sum, cos_sum)) % 360
                
                confidence = min(0.9, len(angles) * 0.3)
                return mean_angle, confidence
            
            return 0, 0
            
        except Exception as e:
            self.log(f"Contour error: {e}")
            return 0, 0
    
    def _detect_hough_rotation(self, gray: np.ndarray) -> Tuple[float, float]:
        """Detect rotation using Hough line transform."""
        try:
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            
            # Standard Hough transform
            lines = cv2.HoughLines(edges, 1, np.pi/180, 80)
            
            if lines is None or len(lines) == 0:
                return 0, 0
            
            # Analyze line orientations
            angles = []
            for line in lines[:20]:
                rho, theta = line[0]
                angle = np.degrees(theta)
                
                # Vertical lines suggest upright orientation
                if 70 < angle < 110:
                    angles.append(0)
                elif angle < 45 or angle > 135:
                    # Horizontal line
                    angles.append(90)
                else:
                    # Diagonal
                    angles.append(angle - 90)
            
            if angles:
                # Find dominant angle
                hist, bins = np.histogram(angles, bins=36, range=(-180, 180))
                dominant_idx = np.argmax(hist)
                dominant_angle = (bins[dominant_idx] + bins[dominant_idx + 1]) / 2
                
                confidence = min(0.8, len(lines) / 50)
                return dominant_angle % 360, confidence
            
            return 0, 0
            
        except:
            return 0, 0
    
    def _detect_edge_orientation(self, gray: np.ndarray) -> Tuple[float, float]:
        """Detect rotation using edge orientation histogram."""
        try:
            # Compute Sobel gradients
            grad_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            grad_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
            
            # Compute magnitude and orientation
            magnitude = cv2.magnitude(grad_x, grad_y)
            orientation = cv2.phase(grad_x, grad_y, angleInDegrees=True)
            
            # Focus on strong edges
            threshold = np.percentile(magnitude, 70)
            mask = magnitude > threshold
            
            angles = orientation[mask]
            
            if len(angles) < 100:
                return 0, 0
            
            # Build orientation histogram
            hist, bins = np.histogram(angles, bins=36, range=(0, 360))
            
            # Find peaks
            peaks = []
            for i in range(len(hist)):
                if hist[i] == max(hist[max(0,i-2):min(len(hist),i+3)]):
                    peaks.append((i * 10, hist[i]))
            
            if peaks:
                # Dominant orientation
                dominant = max(peaks, key=lambda x: x[1])
                
                # Check for orthogonal structure (suggests upright)
                orthogonal_count = 0
                for angle, count in peaks:
                    if abs((angle - dominant[0]) % 180 - 90) < 20:
                        orthogonal_count += count
                
                confidence = min(0.85, orthogonal_count / len(angles) * 2)
                return dominant[0], confidence
            
            return 0, 0
            
        except:
            return 0, 0
    
    def _detect_symmetry_rotation(self, gray: np.ndarray) -> Tuple[float, float]:
        """Detect rotation using symmetry analysis."""
        try:
            h, w = gray.shape
            center = (w // 2, h // 2)
            
            best_symmetry = 0
            best_angle = 0
            
            # Test rotation angles
            for angle in range(0, 360, 15):
                # Rotate image
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                rotated = cv2.warpAffine(gray, M, (w, h))
                
                # Check horizontal symmetry
                left = rotated[:, :w//2]
                right = rotated[:, w//2:][:, ::-1]
                
                if left.shape == right.shape:
                    diff = np.abs(left.astype(float) - right.astype(float))
                    symmetry = 1 - (np.mean(diff) / 255)
                    
                    if symmetry > best_symmetry:
                        best_symmetry = symmetry
                        best_angle = angle
            
            confidence = min(0.7, best_symmetry)
            return best_angle, confidence
            
        except:
            return 0, 0
    
    def _detect_gradient_structure(self, gray: np.ndarray) -> Tuple[float, float]:
        """Detect rotation using gradient structure tensor."""
        try:
            # Compute gradients
            gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
            
            # Structure tensor components
            gxx = gx * gx
            gyy = gy * gy
            gxy = gx * gy
            
            # Average in regions
            h, w = gray.shape
            regions = []
            
            for y in range(0, h - 20, 20):
                for x in range(0, w - 20, 20):
                    rgxx = np.mean(gxx[y:y+20, x:x+20])
                    rgyy = np.mean(gyy[y:y+20, x:x+20])
                    rgxy = np.mean(gxy[y:y+20, x:x+20])
                    
                    # Local orientation
                    angle = 0.5 * np.degrees(np.arctan2(2 * rgxy, rgxx - rgyy))
                    coherence = (rgxx - rgyy)**2 + 4*rgxy**2
                    regions.append((angle, coherence))
            
            if regions:
                # Weight by coherence
                total_coherence = sum(r[1] for r in regions)
                if total_coherence > 0:
                    weighted_angle = sum(r[0] * r[1] for r in regions) / total_coherence
                    confidence = min(0.75, total_coherence / 1e8)
                    return weighted_angle % 360, confidence
            
            return 0, 0
            
        except:
            return 0, 0
    
    def _detect_corner_rotation(self, gray: np.ndarray) -> Tuple[float, float]:
        """Detect rotation using corner points."""
        try:
            # Detect corners using Shi-Tomasi
            corners = cv2.goodFeaturesToTrack(gray, 50, 0.01, 10)
            
            if corners is None or len(corners) < 4:
                return 0, 0
            
            corners = corners.reshape(-1, 2)
            
            # Find centroid
            centroid = np.mean(corners, axis=0)
            
            # Compute angles from centroid to corners
            angles = []
            for corner in corners:
                dx = corner[0] - centroid[0]
                dy = corner[1] - centroid[1]
                angle = np.degrees(np.arctan2(-dy, dx))  # Negative dy for image coords
                angles.append(angle)
            
            # Find clustering of angles (suggests structure)
            hist, bins = np.histogram(angles, bins=36, range=(-180, 180))
            
            # Check for 4-way symmetry (common in captcha images)
            peaks_90 = 0
            for i in range(36):
                if hist[i] > 0:
                    # Check if there are peaks at 90 degree intervals
                    for offset in [9, 18, 27]:  # 90, 180, 270 degrees
                        j = (i + offset) % 36
                        if hist[j] > hist[i] * 0.5:
                            peaks_90 += 1
            
            if peaks_90 > 5:
                # Strong 4-way symmetry - likely upright
                return 0, peaks_90 / 20
            
            # Otherwise use dominant angle
            dominant_idx = np.argmax(hist)
            dominant_angle = (bins[dominant_idx] + bins[dominant_idx + 1]) / 2
            
            confidence = min(0.6, len(corners) / 30)
            return (dominant_angle + 90) % 360, confidence
            
        except:
            return 0, 0
    
    def _detect_color_orientation(self, bgr: np.ndarray, hsv: np.ndarray) -> Tuple[float, float]:
        """Detect rotation using color distribution."""
        try:
            h, w = bgr.shape[:2]
            
            # Compute color moments in quadrants
            quadrants = [
                hsv[:h//2, :w//2],      # Top-left
                hsv[:h//2, w//2:],      # Top-right
                hsv[h//2:, :w//2],      # Bottom-left
                hsv[h//2:, w//2:],      # Bottom-right
            ]
            
            # Average hue in each quadrant
            hues = [np.mean(q[:,:,0]) for q in quadrants]
            sats = [np.mean(q[:,:,1]) for q in quadrants]
            
            # Check for horizontal vs vertical color gradient
            h_diff = abs(hues[0] - hues[1]) + abs(hues[2] - hues[3])
            v_diff = abs(hues[0] - hues[2]) + abs(hues[1] - hues[3])
            
            if h_diff > v_diff:
                # Horizontal gradient - might indicate rotation
                return 90, min(0.5, h_diff / 180)
            else:
                # Vertical gradient
                return 0, min(0.5, v_diff / 180)
            
        except:
            return 0, 0
    
    def _detect_shape_match(self, gray: np.ndarray) -> Tuple[float, float]:
        """Detect rotation by matching with upright shape templates."""
        try:
            # Create ideal upright shapes
            h, w = gray.shape
            
            # Simple upright rectangle template
            template = np.zeros((h, w), dtype=np.uint8)
            cv2.rectangle(template, (w//4, h//4), (3*w//4, 3*h//4), 255, -1)
            
            # Match at different rotations
            best_match = 0
            best_angle = 0
            
            for angle in range(0, 360, 30):
                M = cv2.getRotationMatrix2D((w//2, h//2), angle, 1.0)
                rotated_template = cv2.warpAffine(template, M, (w, h))
                
                result = cv2.matchTemplate(gray, rotated_template, cv2.TM_CCOEFF_NORMED)
                _, match_val, _, _ = cv2.minMaxLoc(result)
                
                if match_val > best_match:
                    best_match = match_val
                    best_angle = angle
            
            return (360 - best_angle) % 360, min(0.6, best_match)
            
        except:
            return 0, 0


class RealCaptchaSolver:
    """
    Real local captcha solver with enhanced accuracy.
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
        
        # Enhanced CV analyzer
        self.cv_analyzer = EnhancedCVAnalyzer(debug=debug)
    
    def log(self, msg: str, force: bool = False):
        if self.debug or force:
            print(f"[SOLVER] {msg}")
    
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
        timeout: int = 300
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
        
        self.log("Found captcha iframe, starting enhanced solve process...")
        
        # Try multiple solving strategies
        for attempt in range(10):  # 10 attempts for better success rate
            self.log(f"Attempt {attempt + 1}/10")
            
            try:
                # Wait for challenge to load
                self._human_delay(1, 2)
                
                # Strategy 1: Enhanced rotation challenge
                result = self._solve_rotation_enhanced(frame, iframe)
                if result['success']:
                    self._human_delay(2, 3)
                    
                    # Check if solved
                    if self._verify_success():
                        token = self._extract_token()
                        if token:
                            self.solved_count += 1
                            save_solution(result.get('hash', ''), result.get('angle', 0), True)
                            self.log(f"✅ SOLVED! Token: {token[:50]}...", force=True)
                            return {"success": True, "token": token}
                
                # Strategy 2: Click-based challenge
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
    
    def _solve_rotation_enhanced(self, frame, iframe) -> Dict[str, Any]:
        """Enhanced rotation solving with advanced CV."""
        
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
                return {'success': False}
            
            # Take screenshot of the captcha area
            iframe_box = iframe.bounding_box()
            if not iframe_box:
                return {'success': False}
            
            # Focus on the image area
            captcha_area = {
                'x': iframe_box['x'] + 10,
                'y': iframe_box['y'] + 10,
                'width': iframe_box['width'] - 20,
                'height': iframe_box['height'] * 0.6
            }
            
            screenshot = self.page.screenshot(type="png", clip=captcha_area)
            
            # Use enhanced CV analyzer
            analysis = self.cv_analyzer.analyze_image(screenshot)
            
            angle = analysis['angle']
            confidence = analysis['confidence']
            
            self.log(f"Detected angle: {angle:.1f}° (confidence: {confidence:.2f}, method: {analysis['method']})")
            
            # If confidence is low, try multiple angles
            if confidence < 0.4:
                self.log("Low confidence, trying multiple angles")
                angles_to_try = [
                    angle,
                    (angle + 90) % 360,
                    (angle + 180) % 360,
                    (angle + 270) % 360,
                ]
            else:
                angles_to_try = [angle]
            
            for test_angle in angles_to_try:
                if self._perform_rotation(slider, test_angle):
                    self._human_delay(0.5, 1)
                    
                    # Quick verification
                    if self._quick_verify():
                        return {
                            'success': True,
                            'angle': test_angle,
                            'hash': analysis.get('hash', '')
                        }
            
            return {'success': False, 'hash': analysis.get('hash', '')}
            
        except Exception as e:
            self.log(f"Enhanced rotation error: {e}")
            return {'success': False}
    
    def _quick_verify(self) -> bool:
        """Quick verification check."""
        try:
            # Check for success class
            success_el = self.page.query_selector('.success, .verified, [class*="success"]')
            return success_el is not None
        except:
            return False
    
    def _random_rotation_solve(self, frame) -> Dict[str, Any]:
        """Fallback random rotation solver."""
        
        try:
            slider = frame.query_selector('input[type="range"]')
            if not slider:
                return {'success': False}
            
            # Try common angles based on typical FunCaptcha patterns
            angles = [0, 90, 180, 270, 45, 135, 225, 315, 30, 60, 120, 150, 210, 240, 300, 330]
            random.shuffle(angles)
            
            for angle in angles[:5]:
                if self._perform_rotation(slider, angle):
                    self._human_delay(0.5, 1)
                    if self._quick_verify():
                        return {'success': True, 'angle': angle}
            
            return {'success': False}
            
        except:
            return {'success': False}
    
    def _perform_rotation(self, slider, angle: float) -> bool:
        """Perform human-like rotation on slider."""
        
        try:
            bbox = slider.bounding_box()
            if not bbox:
                return False
            
            center_x = bbox['x'] + bbox['width'] / 2
            center_y = bbox['y'] + bbox['height'] / 2
            
            # Calculate drag distance
            drag_distance = (angle / 360) * bbox['width']
            drag_distance += random.uniform(-3, 3)
            
            # Human-like mouse movement
            start_x = center_x - 100 + random.uniform(-20, 20)
            start_y = center_y + random.uniform(-30, 30)
            
            # Move to starting position with curve
            self._human_move(start_x, start_y)
            self._human_delay(0.1, 0.3)
            
            # Move to slider
            self._human_move(center_x, center_y)
            self._human_delay(0.1, 0.2)
            
            # Click and hold
            self.page.mouse.down()
            self._human_delay(0.1, 0.2)
            
            # Drag with natural motion
            self._human_drag(center_x, center_y, drag_distance)
            
            # Release
            self._human_delay(0.1, 0.3)
            self.page.mouse.up()
            
            self.log(f"Rotated to {angle:.1f}°")
            return True
            
        except Exception as e:
            self.log(f"Rotation error: {e}")
            return False
    
    def _human_move(self, target_x: float, target_y: float):
        """Move mouse to target with human-like motion."""
        current = self.page.evaluate("() => ({x: window.mouseX || 0, y: window.mouseY || 0})")
        current_x = current.get('x', 0)
        current_y = current.get('y', 0)
        
        distance = math.sqrt((target_x - current_x)**2 + (target_y - current_y)**2)
        steps = max(5, int(distance / 20))
        
        for i in range(steps):
            progress = i / steps
            # Ease-out curve
            ease = 1 - (1 - progress) ** 2
            
            x = current_x + (target_x - current_x) * ease
            y = current_y + (target_y - current_y) * ease
            
            # Add jitter
            x += random.uniform(-2, 2)
            y += random.uniform(-2, 2)
            
            self.page.mouse.move(x, y)
            time.sleep(random.uniform(0.005, 0.015))
    
    def _human_drag(self, start_x: float, start_y: float, distance: float):
        """Drag with human-like motion."""
        steps = random.randint(20, 35)
        
        for i in range(steps):
            progress = i / steps
            
            # Ease-in-out for natural acceleration
            if progress < 0.5:
                ease = 2 * progress * progress
            else:
                ease = 1 - pow(-2 * progress + 2, 2) / 2
            
            x = start_x + distance * ease
            y = start_y + math.sin(progress * math.pi * 2) * random.uniform(1, 3)
            
            self.page.mouse.move(x, y)
            time.sleep(random.uniform(0.01, 0.025))
    
    def _solve_click_challenge(self, frame) -> bool:
        """Solve click-based challenges."""
        
        try:
            tiles = frame.query_selector_all('div[class*="tile"], button[class*="tile"], img[class*="tile"]')
            
            if not tiles:
                return False
            
            self.log(f"Found {len(tiles)} tiles for click challenge")
            
            # Click random subset
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
            time.sleep(1)
            iframe = self._find_captcha_iframe()
            if not iframe:
                self.log("Captcha iframe disappeared - success!")
                return True
            
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
    print("🧩 Enhanced Real Local Captcha Solver - FREE!")
    print("=" * 60)
    
    solver = RealCaptchaSolver(debug=True, headless=False)
    
    try:
        result = solver.solve_with_token()
        print(f"\nResult: {result}")
    except KeyboardInterrupt:
        print("\n⏹️ Interrupted")
    finally:
        solver.close()