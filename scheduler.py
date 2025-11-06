#!/usr/bin/env python3
"""
Zillow Scraper Scheduler
Runs the scraper automatically at a specified time each day.

Usage:
    python3 scheduler.py --input properties.txt --time "03:00"
    
The script will:
1. Stay running in the background
2. Launch the scraper at the specified time daily
3. Show Chrome UI when scraping
"""

import schedule
import time
import subprocess
import argparse
import sys
from datetime import datetime
from pathlib import Path

class ScraperScheduler:
    def __init__(self, input_file, script_path, run_time):
        self.input_file = input_file
        self.script_path = script_path
        self.run_time = run_time
        self.is_running = False
        
    def run_scraper(self):
        """Execute the scraper script"""
        if self.is_running:
            print(f"⚠️ Scraper is already running, skipping this run.")
            return
        
        print(f"\n{'='*70}")
        print(f"🚀 Starting scheduled scrape at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}\n")
        
        self.is_running = True
        
        try:
            # Run the scraper in non-headless mode (Chrome UI visible)
            result = subprocess.run(
                ["python3", self.script_path, "--input", self.input_file],
                capture_output=False,  # Show output in real-time
                text=True
            )
            
            if result.returncode == 0:
                print(f"\n✅ Scraping completed successfully at {datetime.now().strftime('%H:%M:%S')}")
            else:
                print(f"\n❌ Scraping failed with exit code {result.returncode}")
                
        except Exception as e:
            print(f"\n❌ Error running scraper: {e}")
        finally:
            self.is_running = False
            
        print(f"\n{'='*70}")
        print(f"⏰ Next run scheduled for: {self.run_time} tomorrow")
        print(f"{'='*70}\n")
    
    def start(self):
        """Start the scheduler"""
        print(f"""
{'='*70}
  Zillow Scraper Scheduler Started
{'='*70}
  
  📋 Input file: {self.input_file}
  ⏰ Scheduled time: {self.run_time} daily
  🖥️  Mode: Non-headless (Chrome UI will be visible)
  
  The scheduler is now running. Press Ctrl+C to stop.
{'='*70}
""")
        
        # Schedule the job
        schedule.every().day.at(self.run_time).do(self.run_scraper)
        
        # Check if we should run immediately if time has passed today
        now = datetime.now()
        scheduled_time = datetime.strptime(self.run_time, "%H:%M").time()
        current_time = now.time()
        
        if current_time > scheduled_time:
            next_run = schedule.next_run()
            print(f"⏰ Today's run time ({self.run_time}) has passed.")
            print(f"   Next run: {next_run.strftime('%Y-%m-%d %H:%M:%S')}\n")
        else:
            next_run = schedule.next_run()
            print(f"⏰ Next run: {next_run.strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Keep the script running
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            print("\n\n⚠️ Scheduler stopped by user (Ctrl+C)")
            print("✅ Goodbye!\n")
            sys.exit(0)


def main():
    parser = argparse.ArgumentParser(
        description="Schedule Zillow scraper to run daily at a specified time",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run at 3:00 AM daily
  python3 scheduler.py --input properties.txt --time "03:00"
  
  # Run at 11:30 PM daily
  python3 scheduler.py --input properties.txt --time "23:30"
  
  # Specify custom script location
  python3 scheduler.py --input properties.txt --time "03:00" --script ./scraper.py

The scheduler will run in non-headless mode (Chrome UI visible).
        """
    )
    
    parser.add_argument(
        "--input",
        required=True,
        help="Input file with property URLs"
    )
    
    parser.add_argument(
        "--time",
        required=True,
        help='Time to run daily in HH:MM format (24-hour), e.g., "03:00" or "15:30"'
    )
    
    parser.add_argument(
        "--script",
        default="scrape_zillow_units.py",
        help="Path to the scraper script (default: scrape_zillow_units.py)"
    )
    
    args = parser.parse_args()
    
    # Validate input file exists
    if not Path(args.input).exists():
        print(f"❌ Error: Input file '{args.input}' not found")
        sys.exit(1)
    
    # Validate script exists
    if not Path(args.script).exists():
        print(f"❌ Error: Script '{args.script}' not found")
        sys.exit(1)
    
    # Validate time format
    try:
        datetime.strptime(args.time, "%H:%M")
    except ValueError:
        print(f'❌ Error: Invalid time format "{args.time}". Use HH:MM format (e.g., "03:00")')
        sys.exit(1)
    
    # Check if schedule library is installed
    try:
        import schedule
    except ImportError:
        print("❌ Error: 'schedule' library not installed")
        print("\nInstall it with:")
        print("  pip install schedule")
        sys.exit(1)
    
    # Create and start scheduler
    scheduler = ScraperScheduler(args.input, args.script, args.time)
    scheduler.start()


if __name__ == "__main__":
    main()
