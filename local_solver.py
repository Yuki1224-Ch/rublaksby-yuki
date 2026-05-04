"""
Local Solver Integration Module.
Bridges the gap between the session and the real captcha solver.
Supports both 2Captcha API and local fallback methods.
"""
import threading
import time
import signal
import sys
from typing import Optional, Dict, Any

# Import the real captcha solver
try:
    from captcha_solver import (
        CaptchaSolver, 
        LocalCaptchaSolver, 
        SolverManager,
        get_solver_manager,
        configure_solver
    )
    HAS_CAPTCHA_SOLVER = True
except ImportError:
    HAS_CAPTCHA_SOLVER = False
    print("[!] captcha_solver.py not found, using legacy solver")

# Legacy import for backwards compatibility
try:
    from custom_solver import CustomCaptchaSolver
    HAS_CUSTOM_SOLVER = True
except ImportError:
    HAS_CUSTOM_SOLVER = False

# Global state
_solver_instances = {}
_solver_lock = threading.Lock()
_shutdown_event = threading.Event()
_config = {
    "api_key": None,
    "debug": False,
    "use_api": True  # Prefer API over local
}


def configure(api_key: str = None, debug: bool = False, use_api: bool = True):
    """
    Configure the captcha solver.
    
    Args:
        api_key: 2Captcha API key for reliable solving
        debug: Enable debug logging
        use_api: Prefer API solving over local methods
    """
    global _config
    _config = {
        "api_key": api_key,
        "debug": debug,
        "use_api": use_api
    }
    
    if HAS_CAPTCHA_SOLVER and api_key:
        configure_solver(api_key=api_key, debug=debug)
        print(f"[+] Captcha solver configured with API key")


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
            # Prefer API solver if configured
            if HAS_CAPTCHA_SOLVER and _config.get("api_key"):
                manager = get_solver_manager()
                _solver_instances[thread_id] = manager
            elif HAS_CUSTOM_SOLVER:
                # Legacy fallback
                _solver_instances[thread_id] = CustomCaptchaSolver(debug=_config.get("debug", False))
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
            # Get solver based on configuration
            if HAS_CAPTCHA_SOLVER and _config.get("api_key"):
                # Use API solver
                solver = CaptchaSolver(api_key=_config["api_key"], debug=_config.get("debug", False))
                
                site_key = getattr(session, 'captcha_site_key', "476068BF-9607-4799-B53D-966BE98E2B81")
                url = getattr(session, 'url', 'https://www.roblox.com/login')
                blob = getattr(session, 'captcha_blob', None) or metadata
                
                username = getattr(session, 'username', 'Unknown')
                print(f"[*] 🧠 Solving Captcha for {username} via 2Captcha API...")
                
                # Format proxy if available
                proxy = None
                proxy_dict = getattr(session, 'proxy_dict', None)
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
                
                token = solver.solve_funcaptcha(
                    site_key=site_key,
                    page_url=url,
                    blob=blob,
                    proxy=proxy
                )
                
                if token:
                    result_container['success'] = True
                    result_container['token'] = token
                else:
                    print(f"[-] ❌ API solver failed for {username}")
                    
            else:
                # Use legacy solver
                solver = get_solver_instance()
                if not solver:
                    return
                    
                if not hasattr(solver, 'browser') or not solver.browser:
                    proxy = getattr(session, 'proxy_dict', None)
                    if hasattr(solver, 'start_browser'):
                        if not solver.start_browser(proxy):
                            print("[-] Failed to start browser for solver")
                            return

                url = getattr(session, 'url', 'https://www.roblox.com/login')
                blob = getattr(session, 'captcha_blob', None) or metadata
                site_key = getattr(session, 'captcha_site_key', "476068BF-9607-4799-B53D-966BE98E2B81")
                
                username = getattr(session, 'username', 'Unknown')
                print(f"[*] 🔄 Solving Captcha for {username} via browser...")
                
                res = solver.solve_with_token(site_key, url, blob)
                
                if res.get('success'):
                    result_container['success'] = True
                    result_container['token'] = res.get('token')
                else:
                    print(f"[-] ❌ Browser solver failed for {username}")
                    
        except Exception as e:
            print(f"[-] 💥 Solver Thread Crash: {e}")
            import traceback
            traceback.print_exc()
        finally:
            event.set()

    t = threading.Thread(target=run_solver_task, daemon=True)
    t.start()
    
    completed = event.wait(timeout=180)  # 3 minutes for API solver
    
    if not completed:
        print("[-] ⏱️ Captcha Solver Timed Out (180s)")
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
            # Get solver based on configuration
            if HAS_CAPTCHA_SOLVER and _config.get("api_key"):
                # Use API solver
                solver = CaptchaSolver(api_key=_config["api_key"], debug=_config.get("debug", False))
                
                site_key = getattr(session, 'captcha_site_key', "476068BF-9607-4799-B53D-966BE98E2B81")
                url = getattr(session, 'url', 'https://www.roblox.com/login')
                blob = getattr(session, 'captcha_blob', None)
                
                username = getattr(session, 'username', 'Unknown')
                print(f"[*] 🧠 Solving Captcha for {username} via 2Captcha API...")
                
                # Format proxy if available
                proxy = None
                proxy_dict = getattr(session, 'proxy_dict', None)
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
                    
            else:
                # Use legacy solver
                solver = get_solver_instance()
                if not solver:
                    return
                    
                if hasattr(solver, 'browser') and (not solver.browser):
                    proxy = getattr(session, 'proxy_dict', None)
                    if hasattr(solver, 'start_browser'):
                        if not solver.start_browser(proxy):
                            print("[-] Failed to start browser for solver")
                            return

                url = getattr(session, 'url', 'https://www.roblox.com/login')
                blob = getattr(session, 'captcha_blob', None)
                site_key = getattr(session, 'captcha_site_key', "476068BF-9607-4799-B53D-966BE98E2B81")
                
                username = getattr(session, 'username', 'Unknown')
                print(f"[*] 🔄 Solving Captcha for {username} via browser...")
                
                res = solver.solve_with_token(site_key, url, blob)
                
                if res.get('success'):
                    result_container['success'] = True
                    result_container['token'] = res.get('token')
                    
                    if hasattr(session, 'set_captcha_token'):
                        session.set_captcha_token(result_container['token'])
                else:
                    print(f"[-] ❌ Browser solver failed for {username}")
                    
        except Exception as e:
            print(f"[-] 💥 Solver Thread Crash: {e}")
        finally:
            event.set()

    t = threading.Thread(target=run_solver_task, daemon=True)
    t.start()
    
    completed = event.wait(timeout=180)  # 3 minutes for API solver
    
    if not completed:
        print("[-] ⏱️ Captcha Solver Timed Out (180s)")
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
                elif hasattr(solver, 'cleanup'):
                    solver.cleanup()
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