"""
Roblox Account Checker
======================
Flow:
1. Login with credentials
2. If captcha detected → solve via API (fast)
3. Continue and get account info

Keyboard Interrupt: Ctrl+C to stop gracefully
"""
import sys
import os
import time
import threading
import signal
import queue

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, MofNCompleteColumn
from rich.text import Text

# Import modules
from roblox import Roblox
from thread_lock import ThreadLock
from counter import Counter
from combocheck import ComboCheck
from util import get_config
from local_solver import (
    cleanup_solver,
    request_shutdown,
    is_shutdown,
    clear_shutdown,
    configure,
    get_stats
)

console = Console()
config = get_config()

# Global shutdown flag
_shutdown_requested = threading.Event()

# Output directory
os.makedirs("output", exist_ok=True)


def signal_handler(sig, frame):
    """Handle keyboard interrupt - Ctrl+C to stop."""
    global _shutdown_requested
    
    if _shutdown_requested.is_set():
        # Second Ctrl+C - force exit
        print("\n[!] Force quit!")
        os._exit(1)
    
    print("\n" + "="*50)
    print("⌨️  KEYBOARD INTERRUPT (Ctrl+C)")
    print("="*50)
    print("[!] Stopping checker gracefully...")
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
    
    console.print("\n[bold blue]" + "="*50 + "[/bold blue]")
    console.print("[bold blue]   🚀 Roblox Account Checker v4.0[/bold blue]")
    console.print("[bold blue]" + "="*50 + "[/bold blue]")
    
    # Configure captcha solver
    api_key = config.get("captcha_api_key") or config.get("2captchaKey")
    use_api = config.get("use_api_solver", True)
    debug = config.get("debug", False)
    
    # Priority: API solver (most accurate)
    if api_key:
        console.print(f"[green]🔑 2Captcha API configured: {api_key[:10]}...[/green]")
        configure(api_key=api_key, debug=debug, use_api=True, use_local=True)
    else:
        console.print("[yellow]⚠️ No API key - using local solver (free but slower)[/yellow]")
        console.print("[cyan]💡 For best results, add your 2Captcha API key to config.json[/cyan]")
        console.print("[cyan]   Get API key at: https://2captcha.com[/cyan]")
        configure(debug=debug, use_api=False, use_local=True)
    
    # Load accounts
    accounts_file = "accounts.txt"
    if not os.path.exists(accounts_file):
        console.print(f"[red]❌ No accounts.txt file found![/red]")
        console.print("[yellow]Create accounts.txt with format: username:password[/yellow]")
        return
    
    with open(accounts_file, 'r', encoding='utf-8') as f:
        accounts = [line.strip() for line in f if ':' in line]
    
    if not accounts:
        console.print("[red]❌ No accounts found in accounts.txt[/red]")
        return
    
    # Load proxies
    proxies_file = "proxies.txt"
    proxies = []
    if os.path.exists(proxies_file):
        with open(proxies_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    proxies.append(line)
    
    if not proxies:
        console.print("[yellow]⚠️ No proxies - running without proxies[/yellow]")
    
    threads = config.get("threads", 2)
    
    console.print(f"\n[green]📊 Loaded: {len(accounts)} accounts, {len(proxies)} proxies[/green]")
    console.print(f"[green]⚙️ Threads: {threads}[/green]")
    console.print(f"[green]⌨️ Press Ctrl+C to stop[/green]\n")
    
    time.sleep(2)
    
    # Setup tracking
    account_queue = queue.Queue()
    for acc in accounts:
        account_queue.put(acc)
    
    lock = ThreadLock()
    counter = Counter()
    invalid = ComboCheck("output/invalid.txt")
    checked_file = ComboCheck("output/checked.txt")
    locked = ComboCheck("output/locked.txt")
    
    # Progress bar
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40),
        MofNCompleteColumn(),
        expand=False
    )
    task_id = progress.add_task("Checking Accounts...", total=len(accounts))
    
    # Stats
    valid_count = [0]
    captcha_solved = [0]
    captcha_failed = [0]
    stats_lock = threading.Lock()
    
    def update_progress():
        with stats_lock:
            progress.update(task_id, completed=counter.value)
    
    try:
        # Start worker threads
        workers = []
        for i in range(threads):
            roblox = Roblox(lock, counter, invalid, checked_file, locked, account_queue)
            
            # Store valid count reference
            original_handle_valid = roblox.handle_valid
            def patched_handle_valid(self, *args, **kwargs):
                with stats_lock:
                    valid_count[0] += 1
                return original_handle_valid(*args, **kwargs)
            
            # Monkey patch for stats
            roblox.handle_valid = lambda *a, **k: patched_handle_valid(roblox, *a, **k)
            
            t = threading.Thread(target=roblox.check, daemon=True)
            t.start()
            workers.append(t)
        
        # Live display
        with Live(progress, refresh_per_second=4, screen=False):
            while counter.value < len(accounts):
                # Check for shutdown
                if _shutdown_requested.is_set() or is_shutdown():
                    console.print("\n[yellow]⏹️ Stopping remaining tasks...[/yellow]")
                    break
                
                update_progress()
                time.sleep(0.25)
        
        # Wait for workers to finish
        for t in workers:
            t.join(timeout=2)
        
    except KeyboardInterrupt:
        console.print("\n[red]⏹️ Interrupted by user[/red]")
    finally:
        cleanup_solver()
        
        # Print final stats
        solver_stats = get_stats()
        
        console.print(f"\n[bold]" + "="*50 + "[/bold]")
        console.print("[bold]📊 FINAL STATISTICS[/bold]")
        console.print("[bold]" + "="*50 + "[/bold]")
        
        with stats_lock:
            console.print(f"   [green]✅ Valid:[/green]       {valid_count[0]}")
            console.print(f"   [red]❌ Invalid:[/red]     {counter.value - valid_count[0]}")
            console.print(f"   [yellow]🧩 Captcha Solved:[/yellow] {solver_stats.get('total_solved', 0)}")
            console.print(f"   [red]🔓 Captcha Failed:[/red] {solver_stats.get('failed', 0)}")
            console.print(f"   [cyan]📋 Total Checked:[/cyan] {counter.value}")
        
        console.print(f"\n[green]📁 Check 'output/' folder for results[/green]")
        console.print("[green]👋 Done![/green]")


if __name__ == "__main__":
    main()