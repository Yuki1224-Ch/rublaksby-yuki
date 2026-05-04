"""
Local Solver Integration Module.
Bridges the gap between the session and the captcha solver.
Prioritizes local solving (free) over API services.
"""
import threading
import time
import signal
import sys
import os
from typing import Optional, Dict, Any

# Import the local captcha solver
try:
    from custom_solver import LocalCaptchaSolver, CustomCaptchaSolver
    HAS_LOCAL_SOLVER = True
except ImportError:
    HAS_LOCAL_SOLVER = False
    print("[!] custom_solver.py not found!")

# Import API solver (optional, for users who want it)
try:
    from captcha_solver import CaptchaSolver
    HAS_API_SOLVER = True
except ImportError:
    HAS_API_SOLVER = False

# Global state
_solver_instances = {}
_solver_lock = threading.Lock()
_shutdown_event = threading.Event()
_config = {
    "api_key": None,
    "debug": False,
    "use_local": True,  # Default to local solver (free)
    "headless": True
}


def configure(api_key: str = None, debug: bool = False, use_local: bool = True, headless: bool = True):
    """
    Configure the captcha solver.
    
    Args:
        api_key: Optional 2Captcha API key for fallback
        debug: Enable debug logging
        use_local: Use local solver (default True - free)
        headless: Run browser in headless mode
    """
    global _config
    _config = {
        "api_key": api_key,
        "debug": debug,
        "use_local": use_local,
        "headless": headless
    }
    
    if debug:
        mode = "LOCAL (FREE)" if use_local else "API"
        print(f"[+] Captcha solver configured: {mode} mode")


def is_shutdown() -> bool:
    """Check if shutdown has been requested."""
    return _shutdown_event.is_set()


def request_shutdown():
    """Request a graceful shutdown."""
    _shutdown_event.set()
    print("\n[!] Shutdown requested, stopping captcha operations...")


def clear_shutdown():
    """Clear the shutdown flag."""
    _shutdown_event.clear()


def get_solver_instance():
    """Get or create a solver instance for the current thread."""
    if is_shutdown():
        return None
        
    thread_id = threading.get_ident()
    
    with _solver_lock:
        if thread_id not in _solver_instances:
            # Always prefer local solver (free)
            if HAS_LOCAL_SOLVER and _config.get("use_local", True):
                _solver_instances[thread_id] = LocalCaptchaSolver(
                    debug=_config.get("debug", False),
                    headless=_config.get("headless", True)
                )
            elif HAS_API_SOLVER and _config.get("api_key"):
                _solver_instances[thread_id] = CaptchaSolver(
                    api_key=_config["api_key"],
                    debug=_config.get("debug", False)
                )
            else:
                print("[-] No captcha solver available!")
                return None
                
        return _solver_instances[thread_id]


def cleanup_thread_solver():
    """Cleanup solver for current thread."""
    thread_id = threading.get_ident()
    with _solver_lock:
        if thread_id in _solver_instances:
            solver = _solver_instances[thread_id]
            if hasattr(solver, 'close'):
                try:
                    solver.close()
                except:
                    pass
            del _solver_instances[thread_id]


def get_token(session, metadata=None) -> Optional[str]:
    """
    Legacy wrapper for backwards compatibility with roblox.py.
    Returns token string or None.
    
    Args:
        session: Session object with captcha info
        metadata: Optional challenge metadata
        
    Returns:
        Captcha token or None if failed
    """
    if is_shutdown():
        print("[!] Shutdown requested, skipping captcha")
        return None
        
    result_container = {"success": False, "token": None}
    event = threading.Event()

    def run_solver_task():
        nonlocal result_container
        
        if is_shutdown():
            event.set()
            return
            
        try:
            solver = get_solver_instance()
            if not solver:
                event.set()
                return
            
            site_key = getattr(session, 'captcha_site_key', "476068BF-9607-4799-B53D-966BE98E2B81")
            url = getattr(session, 'url', 'https://www.roblox.com/login')
            blob = getattr(session, 'captcha_blob', None) or metadata
            username = getattr(session, 'username', 'Unknown')
            
            # Local solver path
            if HAS_LOCAL_SOLVER and isinstance(solver, LocalCaptchaSolver):
                print(f"[*] 🧩 Solving Captcha locally for {username}...")
                
                # Ensure browser is running
                if not solver.browser:
                    proxy = getattr(session, 'proxy_dict', None)
                    if not solver.start_browser(proxy):
                        print(f"[-] Failed to start browser for {username}")
                        event.set()
                        return
                
                result = solver.solve_with_token(site_key, url, blob)
                
                if result.get('success'):
                    result_container['success'] = True
                    result_container['token'] = result.get('token')
                    if result.get('token'):
                        print(f"[+] ✅ Captcha solved! Token: {result['token'][:30]}...")
                else:
                    print(f"[-] ❌ Local solver failed for {username}")
            
            # API solver path (fallback)
            elif HAS_API_SOLVER and hasattr(solver, 'solve_funcaptcha'):
                print(f"[*] 🌐 Solving Captcha via API for {username}...")
                
                # Format proxy if available
                proxy = None
                proxy_dict = getattr(session, 'proxy_dict', None)
                if proxy_dict:
                    import re
                    server = proxy_dict.get('server', '')
                    user = proxy_dict.get('username')
                    pwd = proxy_dict.get('password')
                    if server:
                        match = re.search(r'://([^:]+):(\d+)', server)
                        if match:
                            ip, port = match.groups()
                            if user and pwd:
                                proxy = f"{user}:{pwd}@{ip}:{port}"
                            else:
                                proxy = f"{ip}:{port}"
                
                token = solver.solve_funcaptcha(
                    site_key=site_key,
                    page_url=url,
                    blob=blob,
                    proxy=proxy
                )
                
                if token:
                    result_container['success'] = True
                    result_container['token'] = token
                    print(f"[+] ✅ API Captcha solved!")
                else:
                    print(f"[-] ❌ API solver failed for {username}")
                    
        except Exception as e:
            print(f"[-] 💥 Solver error: {e}")
        finally:
            event.set()

    t = threading.Thread(target=run_solver_task, daemon=True)
    t.start()
    
    # Wait for result (longer timeout for local solver)
    timeout = 300 if _config.get("use_local", True) else 180  # 5 min for local
    completed = event.wait(timeout=timeout)
    
    if not completed:
        print(f"[-] ⏱️ Captcha Solver Timed Out ({timeout}s)")
        return None
        
    return result_container['token'] if result_container['success'] else None


def solve_captcha_wrapper(session) -> bool:
    """
    Runs the captcha solver in a background thread.
    Returns True if solved, False otherwise.
    
    Args:
        session: Session object with captcha info
        
    Returns:
        True if captcha was solved, False otherwise
    """
    if is_shutdown():
        print("[!] Shutdown requested, skipping captcha")
        return False
        
    result_container = {"success": False, "token": None}
    event = threading.Event()

    def run_solver_task():
        nonlocal result_container
        
        if is_shutdown():
            event.set()
            return
            
        try:
            solver = get_solver_instance()
            if not solver:
                event.set()
                return
            
            site_key = getattr(session, 'captcha_site_key', "476068BF-9607-4799-B53D-966BE98E2B81")
            url = getattr(session, 'url', 'https://www.roblox.com/login')
            blob = getattr(session, 'captcha_blob', None)
            username = getattr(session, 'username', 'Unknown')
            
            # Local solver path (preferred)
            if HAS_LOCAL_SOLVER and isinstance(solver, LocalCaptchaSolver):
                print(f"[*] 🧩 Solving Captcha locally for {username}...")
                
                # Ensure browser is running
                if not solver.browser:
                    proxy = getattr(session, 'proxy_dict', None)
                    if not solver.start_browser(proxy):
                        print(f"[-] Failed to start browser for {username}")
                        event.set()
                        return
                
                result = solver.solve_with_token(site_key, url, blob)
                
                if result.get('success'):
                    result_container['success'] = True
                    result_container['token'] = result.get('token')
                    
                    if hasattr(session, 'set_captcha_token') and result.get('token'):
                        session.set_captcha_token(result['token'])
                        preview = result['token'][:20] if len(result['token']) > 20 else result['token']
                        print(f"[+] ✅ Captcha Solved! Token: {preview}...")
                    else:
                        print(f"[+] ✅ Captcha Solved! (visual success)")
                else:
                    print(f"[-] ❌ Local solver failed for {username}")
            
            # API solver path (fallback)
            elif HAS_API_SOLVER and hasattr(solver, 'solve_funcaptcha'):
                print(f"[*] 🌐 Solving Captcha via API for {username}...")
                
                # Format proxy if available
                proxy = None
                proxy_dict = getattr(session, 'proxy_dict', None)
                if proxy_dict:
                    import re
                    server = proxy_dict.get('server', '')
                    user = proxy_dict.get('username')
                    pwd = proxy_dict.get('password')
                    if server:
                        match = re.search(r'://([^:]+):(\d+)', server)
                        if match:
                            ip, port = match.groups()
                            if user and pwd:
                                proxy = f"{user}:{pwd}@{ip}:{port}"
                            else:
                                proxy = f"{ip}:{port}"
                
                token = solver.solve_funcaptcha(
                    site_key=site_key,
                    page_url=url,
                    blob=blob,
                    proxy=proxy
                )
                
                if token:
                    result_container['success'] = True
                    result_container['token'] = token
                    
                    if hasattr(session, 'set_captcha_token'):
                        session.set_captcha_token(token)
                        preview = token[:20] if len(token) > 20 else token
                        print(f"[+] ✅ Captcha Solved! Token: {preview}...")
                else:
                    print(f"[-] ❌ API solver failed for {username}")
                    
        except Exception as e:
            print(f"[-] 💥 Solver error: {e}")
        finally:
            event.set()

    t = threading.Thread(target=run_solver_task, daemon=True)
    t.start()
    
    # Wait for result (5 minutes for local solver)
    timeout = 300 if _config.get("use_local", True) else 180
    completed = event.wait(timeout=timeout)
    
    if not completed:
        print(f"[-] ⏱️ Captcha Solver Timed Out ({timeout}s)")
        return False
        
    return result_container['success']


def cleanup_solver():
    """Call this at the end of your program to close all browser instances."""
    global _solver_instances
    
    request_shutdown()
    
    with _solver_lock:
        for thread_id, solver in list(_solver_instances.items()):
            try:
                if hasattr(solver, 'close'):
                    print(f"[*] Closing solver for thread {thread_id}...")
                    solver.close()
            except Exception as e:
                print(f"[!] Error closing solver: {e}")
        _solver_instances.clear()
    
    print("[+] All solvers cleaned up")


def setup_keyboard_interrupt():
    """Setup graceful keyboard interrupt handling."""
    def signal_handler(sig, frame):
        print("\n[!] ⌨️ Keyboard interrupt detected!")
        request_shutdown()
        
        # Give threads time to clean up
        time.sleep(1)
        
        # Force cleanup
        cleanup_solver()
        
        print("[+] Graceful shutdown complete")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    print("[*] Keyboard interrupt handler installed (Ctrl+C to stop)")


# Auto-setup keyboard interrupt on import
setup_keyboard_interrupt()