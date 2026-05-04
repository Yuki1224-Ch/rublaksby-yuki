"""
Captcha Solver Integration Module
==================================
Uses 2Captcha API for highest accuracy (recommended).
Local solver as fallback (free but less reliable).

Flow:
1. Login attempt detects captcha challenge
2. Call get_token() with challenge metadata
3. Solver returns token
4. Continue login with token
"""
import threading
import time
import signal
import sys
import os
import json
from typing import Optional, Dict, Any

# Import API solver (2Captcha - most reliable)
try:
    from captcha_solver import CaptchaSolver
    HAS_API_SOLVER = True
except ImportError:
    HAS_API_SOLVER = False
    print("[!] captcha_solver.py not found - API solving unavailable")

# Import local solver (free fallback)
try:
    from custom_solver import RealCaptchaSolver
    HAS_LOCAL_SOLVER = True
except ImportError:
    HAS_LOCAL_SOLVER = False
    print("[!] custom_solver.py not found - local solving unavailable")

# Global state
_solver_instances = {}
_solver_lock = threading.Lock()
_shutdown_event = threading.Event()
_config = {
    "api_key": None,
    "debug": False,
    "use_api": True,      # Default to API (most accurate)
    "use_local": True,    # Fallback to local if API fails
    "headless": True
}

# Statistics
_stats = {
    "total_solved": 0,
    "api_solved": 0,
    "local_solved": 0,
    "failed": 0
}


def configure(api_key: str = None, debug: bool = False, use_api: bool = True, 
              use_local: bool = True, headless: bool = True):
    """
    Configure the captcha solver.
    
    Args:
        api_key: 2Captcha API key (get from https://2captcha.com)
        debug: Enable debug logging
        use_api: Use 2Captcha API (recommended - 100% success)
        use_local: Use local solver as fallback (free)
        headless: Run browser in headless mode
    """
    global _config
    _config = {
        "api_key": api_key,
        "debug": debug,
        "use_api": use_api,
        "use_local": use_local,
        "headless": headless
    }
    
    if debug:
        mode = "API" if use_api else "LOCAL"
        print(f"[+] Captcha solver configured: {mode} mode")
        if api_key:
            print(f"[+] 2Captcha API key: {api_key[:10]}...")


def is_shutdown() -> bool:
    """Check if shutdown has been requested."""
    return _shutdown_event.is_set()


def request_shutdown():
    """Request a graceful shutdown."""
    _shutdown_event.set()
    print("\n[!] Shutdown requested, stopping...")


def clear_shutdown():
    """Clear the shutdown flag."""
    _shutdown_event.clear()


def get_api_solver():
    """Get or create API solver instance."""
    if not HAS_API_SOLVER:
        return None
    
    api_key = _config.get("api_key")
    if not api_key:
        return None
    
    return CaptchaSolver(api_key=api_key, debug=_config.get("debug", False))


def get_local_solver():
    """Get or create local solver instance for current thread."""
    if not HAS_LOCAL_SOLVER:
        return None
    
    thread_id = threading.get_ident()
    
    with _solver_lock:
        if thread_id not in _solver_instances:
            _solver_instances[thread_id] = RealCaptchaSolver(
                debug=_config.get("debug", False),
                headless=_config.get("headless", True)
            )
        return _solver_instances[thread_id]


def get_token(session, metadata=None) -> Optional[str]:
    """
    Get captcha token for login continuation.
    
    This is the main entry point called from roblox.py when a captcha challenge
    is detected during login.
    
    Args:
        session: Session object with proxy info
        metadata: Challenge metadata from Roblox (important for solving!)
        
    Returns:
        Captcha token or None if failed
    """
    global _stats
    
    if is_shutdown():
        print("[!] Shutdown requested, skipping captcha")
        return None
    
    # Extract info from session
    username = getattr(session, 'username', 'Unknown')
    proxy_dict = getattr(session, 'proxy_dict', None)
    
    # Format proxy for API
    proxy = None
    if proxy_dict:
        server = proxy_dict.get('server', '')
        user = proxy_dict.get('username')
        pwd = proxy_dict.get('password')
        if server:
            import re
            match = re.search(r'://([^:]+):(\d+)', server)
            if match:
                ip, port = match.groups()
                if user and pwd:
                    proxy = f"{user}:{pwd}@{ip}:{port}"
                else:
                    proxy = f"{ip}:{port}"
    
    site_key = "476068BF-9607-4799-B53D-966BE98E2B81"  # Roblox FunCaptcha key
    page_url = "https://www.roblox.com/login"
    
    # Priority 1: 2Captcha API (most reliable)
    if _config.get("use_api", True) and _config.get("api_key"):
        print(f"[*] 🌐 Solving captcha via 2Captcha API for {username}...")
        
        try:
            solver = get_api_solver()
            if solver:
                # Check balance first
                balance = solver.get_balance()
                if balance is not None and balance < 1:
                    print(f"[!] 2Captcha balance low: ${balance:.2f}")
                
                token = solver.solve_funcaptcha(
                    site_key=site_key,
                    page_url=page_url,
                    blob=metadata,  # Important: pass the blob/metadata!
                    proxy=proxy,
                    timeout=120
                )
                
                if token:
                    _stats["total_solved"] += 1
                    _stats["api_solved"] += 1
                    print(f"[+] ✅ Captcha solved by 2Captcha!")
                    return token
                else:
                    print(f"[-] ⚠️ 2Captcha failed, trying fallback...")
            else:
                print(f"[!] No API solver available")
                
        except Exception as e:
            print(f"[-] API solver error: {e}")
    
    # Priority 2: Local solver (fallback, free)
    if _config.get("use_local", True) and HAS_LOCAL_SOLVER and not is_shutdown():
        print(f"[*] 🧩 Solving captcha locally for {username}...")
        
        try:
            solver = get_local_solver()
            if solver:
                # Start browser if needed
                if not solver.browser:
                    if not solver.start_browser(proxy_dict):
                        print(f"[-] Failed to start browser")
                        _stats["failed"] += 1
                        return None
                
                result = solver.solve_with_token(
                    site_key=site_key,
                    service_url=page_url,
                    blob=metadata,
                    timeout=180
                )
                
                if result.get('success') and result.get('token'):
                    _stats["total_solved"] += 1
                    _stats["local_solved"] += 1
                    token = result['token']
                    if token != "NO_CAPTCHA":
                        print(f"[+] ✅ Captcha solved locally!")
                        return token
                    else:
                        print(f"[!] No captcha detected")
                        return None
                        
        except Exception as e:
            print(f"[-] Local solver error: {e}")
    
    _stats["failed"] += 1
    print(f"[-] ❌ Captcha solving failed for {username}")
    return None


def get_stats() -> Dict[str, int]:
    """Get solving statistics."""
    return _stats.copy()


def cleanup_solver():
    """Call this at the end of your program to close all browser instances."""
    global _solver_instances
    
    request_shutdown()
    
    with _solver_lock:
        for thread_id, solver in list(_solver_instances.items()):
            try:
                if hasattr(solver, 'close'):
                    solver.close()
            except:
                pass
        _solver_instances.clear()
    
    # Print stats
    print(f"\n[+] Captcha Stats:")
    print(f"    Total Solved: {_stats['total_solved']}")
    print(f"    API Solved:   {_stats['api_solved']}")
    print(f"    Local Solved: {_stats['local_solved']}")
    print(f"    Failed:       {_stats['failed']}")


def setup_keyboard_interrupt():
    """Setup graceful keyboard interrupt handling."""
    original_handler = None
    
    def signal_handler(sig, frame):
        print("\n" + "="*50)
        print("⌨️ KEYBOARD INTERRUPT (Ctrl+C)")
        print("="*50)
        print("[!] Stopping checker...")
        
        request_shutdown()
        
        # Give threads time to notice
        time.sleep(0.5)
        
        # Cleanup
        cleanup_solver()
        
        # Print final stats
        print(f"\n[+] Final Stats:")
        print(f"    Solved: {_stats['total_solved']}")
        print(f"    Failed: {_stats['failed']}")
        
        print("\n[+] Shutdown complete. Goodbye!")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    print("[*] Keyboard interrupt ready (Ctrl+C to stop)")


# Auto-setup keyboard interrupt on import
setup_keyboard_interrupt()


# Backwards compatibility
solve_captcha_wrapper = get_token


if __name__ == "__main__":
    print("=" * 60)
    print("🔧 Captcha Solver Configuration")
    print("=" * 60)
    
    # Check config
    config_file = "config.json"
    if os.path.exists(config_file):
        with open(config_file) as f:
            cfg = json.load(f)
        
        api_key = cfg.get("captcha_api_key") or cfg.get("2captchaKey")
        
        if api_key:
            print(f"[+] Found API key in config: {api_key[:10]}...")
            configure(api_key=api_key, debug=True)
            
            # Test API
            solver = get_api_solver()
            if solver:
                balance = solver.get_balance()
                if balance is not None:
                    print(f"[+] ✅ 2Captcha balance: ${balance:.2f}")
                else:
                    print(f"[-] ❌ Could not verify API key")
        else:
            print("[!] No API key found in config")
            print("[*] For best results, add your 2Captcha API key:")
            print('    "captcha_api_key": "YOUR_API_KEY"')
            print()
            print("[*] Get an API key at: https://2captcha.com")
    else:
        print("[!] No config.json found")