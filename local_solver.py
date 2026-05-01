import threading
import time
from custom_solver import CustomCaptchaSolver

# Global solver instance to reuse the browser (faster)
_solver_instance = None

def get_solver_instance():
    global _solver_instance
    if _solver_instance is None:
        _solver_instance = CustomCaptchaSolver(debug=True)
    return _solver_instance

def solve_captcha_wrapper(session):
    """
    Runs the captcha solver in a background thread to prevent freezing.
    Returns True if solved, False otherwise.
    """
    result_container = {"success": False, "token": None}
    event = threading.Event()

    def run_solver_task():
        nonlocal result_container
        try:
            solver = get_solver_instance()
            
            # Ensure browser is running
            if not solver.browser:
                # Pass proxy if available in session
                proxy = getattr(session, 'proxy_dict', None)
                if not solver.start_browser(proxy):
                    print("[-] Failed to start browser for solver")
                    return

            # Get details from session
            url = getattr(session, 'url', 'https://www.roblox.com/login')
            blob = getattr(session, 'captcha_blob', None)
            site_key = getattr(session, 'captcha_site_key', "476068BF-9607-4799-B53D-966BE98E2B81")
            
            print(f"[*] 🧠 Solving Captcha for {getattr(session, 'username', 'Unknown')}...")
            
            # Run the actual solve
            res = solver.solve_with_token(site_key, url, blob)
            
            if res.get('success'):
                result_container['success'] = True
                result_container['token'] = res.get('token')
                
                # Inject token back into session for retry
                if hasattr(session, 'set_captcha_token'):
                    session.set_captcha_token(result_container['token'])
                    print(f"[+] ✅ Captcha Solved! Token: {result_container['token'][:20]}...")
                else:
                    print("[!] Session missing set_captcha_token method")
            else:
                print("[-] ❌ Solver returned failure")
                
        except Exception as e:
            print(f"[-] 💥 Solver Thread Crash: {e}")
            import traceback
            traceback.print_exc()
        finally:
            event.set()

    # Start the thread
    t = threading.Thread(target=run_solver_task)
    t.daemon = True
    t.start()
    
    # Wait max 45 seconds for a solution
    completed = event.wait(timeout=45)
    
    if not completed:
        print("[-] ⏱️ Captcha Solver Timed Out (45s)")
        return False
        
    return result_container['success']

def cleanup_solver():
    """Call this at the end of your program to close the browser."""
    global _solver_instance
    if _solver_instance:
        print("[*] Closing solver browser...")
        _solver_instance.close()
        _solver_instance = None