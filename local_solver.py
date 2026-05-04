"""
100% FREE Local Captcha Solver for Roblox
==========================================
NO API KEY NEEDED! NO MONEY REQUIRED!

This solver uses:
1. Playwright browser automation (free)
2. OpenCV image analysis (free)
3. Smart rotation detection (free)

Flow:
1. roblox.py detects captcha during login
2. Calls get_token() with challenge metadata
3. Solver opens captcha in browser, solves it
4. Returns token to continue login
"""
import threading
import time
import signal
import sys
import os
import json
from typing import Optional, Dict, Any
from pathlib import Path

# Import local solver
try:
    from custom_solver import RealCaptchaSolver
    HAS_LOCAL_SOLVER = True
except ImportError:
    HAS_LOCAL_SOLVER = False
    print("[!] custom_solver.py not found!")

# Global state
_solver_instances = {}
_solver_lock = threading.Lock()
_shutdown_event = threading.Event()
_config = {
    "debug": False,
    "headless": True,  # Set to False to watch it solve
    "max_attempts": 10
}

# Statistics
_stats = {
    "total_solved": 0,
    "failed": 0,
    "attempts": 0
}


def configure(debug: bool = False, headless: bool = True, **kwargs):
    """Configure the FREE local captcha solver."""
    global _config
    _config = {
        "debug": debug,
        "headless": headless,
        "max_attempts": kwargs.get("max_attempts", 10)
    }
    
    mode = "HEADLESS" if headless else "VISIBLE"
    print(f"[+] 🧩 FREE Local Captcha Solver configured ({mode} mode)")
    print(f"[+] 💰 Cost: $0.00 - Completely FREE!")


def is_shutdown() -> bool:
    """Check if shutdown has been requested."""
    return _shutdown_event.is_set()


def request_shutdown():
    """Request a graceful shutdown."""
    _shutdown_event.set()
    print("\n[!] Shutdown requested...")


def clear_shutdown():
    """Clear the shutdown flag."""
    _shutdown_event.clear()


def get_solver():
    """Get or create solver instance (singleton per thread)."""
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
    Main entry point - Solve captcha and return token.
    
    This is called from roblox.py when captcha is detected during login.
    
    Args:
        session: Session object (has proxy info)
        metadata: Challenge metadata from Roblox (important!)
        
    Returns:
        Captcha token or None if failed
    """
    global _stats
    
    if is_shutdown():
        print("[!] Shutdown requested, skipping captcha")
        return None
    
    if not HAS_LOCAL_SOLVER:
        print("[-] ❌ No local solver available!")
        print("[!] Install: pip install opencv-python numpy playwright")
        _stats["failed"] += 1
        return None
    
    username = getattr(session, 'username', 'Unknown')
    password = getattr(session, 'password', None)
    proxy_dict = getattr(session, 'proxy_dict', None)
    
    print(f"[*] 🧩 Solving captcha for {username} (FREE!)...")
    
    try:
        solver = get_solver()
        if not solver:
            _stats["failed"] += 1
            return None
        
        # Ensure browser is started
        if not solver.browser:
            print(f"[*] 🌐 Starting browser...")
            if not solver.start_browser(proxy_dict):
                print(f"[-] ❌ Failed to start browser")
                _stats["failed"] += 1
                return None
        
        # Solve the captcha
        # Pass credentials so solver can fill login form
        result = solver.solve_with_token(
            site_key="476068BF-9607-4799-B53D-966BE98E2B81",
            service_url="https://www.roblox.com/login",
            blob=metadata,
            timeout=180,
            username=username,
            password=password
        )
        
        _stats["attempts"] += 1
        
        if result.get('success'):
            token = result.get('token')
            if token and token != "NO_CAPTCHA":
                _stats["total_solved"] += 1
                print(f"[+] ✅ Captcha solved! (FREE!)")
                return token
            elif token == "NO_CAPTCHA":
                print(f"[!] No captcha found - account might already be verified")
                return "SKIP"
        
        print(f"[-] ❌ Captcha solving failed")
        _stats["failed"] += 1
        return None
        
    except Exception as e:
        print(f"[-] 💥 Solver error: {e}")
        _stats["failed"] += 1
        return None


def get_stats() -> Dict[str, int]:
    """Get solving statistics."""
    return _stats.copy()


def cleanup_solver():
    """Close all browser instances."""
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
    
    print(f"\n[+] 📊 Captcha Stats:")
    print(f"    ✅ Solved: {_stats['total_solved']}")
    print(f"    ❌ Failed: {_stats['failed']}")
    print(f"    💰 Cost:   $0.00 (FREE!)")


def setup_keyboard_interrupt():
    """Setup Ctrl+C to stop gracefully."""
    
    def signal_handler(sig, frame):
        print("\n" + "="*50)
        print("⌨️  KEYBOARD INTERRUPT (Ctrl+C)")
        print("="*50)
        print("[!] Stopping checker...")
        
        request_shutdown()
        time.sleep(0.5)
        cleanup_solver()
        
        print(f"\n[+] 📊 Final Stats:")
        print(f"    ✅ Solved: {_stats['total_solved']}")
        print(f"    ❌ Failed: {_stats['failed']}")
        print(f"    💰 Cost:   $0.00 (FREE!)")
        print("\n[+] 👋 Goodbye!")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    print("[*] ⌨️ Press Ctrl+C to stop anytime")


# Auto-setup keyboard interrupt
setup_keyboard_interrupt()


# Backwards compatibility
solve_captcha_wrapper = get_token


if __name__ == "__main__":
    print("="*60)
    print("🧩 FREE Local Captcha Solver")
    print("="*60)
    print()
    print("💰 Cost: $0.00 - Completely FREE!")
    print("🎯 No API key needed!")
    print()
    print("Requirements:")
    print("  pip install opencv-python numpy playwright")
    print("  playwright install chromium")
    print()
    
    # Test the solver
    print("[*] Testing solver...")
    configure(debug=True, headless=False)
    
    solver = get_solver()
    if solver:
        print("[+] ✅ Solver ready!")
        print("[*] Run main.py to start checking accounts")
    else:
        print("[-] ❌ Solver not available - check dependencies")