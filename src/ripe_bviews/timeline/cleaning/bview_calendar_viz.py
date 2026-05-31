import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk
import calendar
import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from src.ripe_bviews.download_and_parse.load_configs import load_configs
from src.ripe_bviews.read_bgpdump import does_bgpdump_file_exist
from src.ripe_bviews.timeline.bview_vars import get_ip_version


class DataAvailabilityCalendar:
    def __init__(self, config_name="ixbr.json"):
        self.config = load_configs(config_name)
        self.ip_version = get_ip_version(self.config)
        
        self.start_date = datetime.datetime.strptime(self.config["start_date"], "%Y-%m-%d")
        self.end_date = datetime.datetime.strptime(self.config["end_date"], "%Y-%m-%d")
        
        # Gather data availability info
        self.data_available = {}
        self._check_data_availability()
        
        # Create window
        self.root = tk.Tk()
        self.root.title(f"Data Availability Calendar - {config_name}")
        self.root.geometry("900x700")
        
        # Current month being displayed
        self.current_date = self.start_date
        
        self._create_widgets()
        self._update_calendar()
    
    def _check_data_availability(self):
        """Check which dates have data available"""
        current_date = self.start_date
        time_str = self.config.get("time_str", "0000")
        
        while current_date <= self.end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            has_data = does_bgpdump_file_exist(
                monitor_as=self.config["asn_and_prefix"].get("asn"),
                monitor_prefix=self.config["asn_and_prefix"].get("prefix"),
                date=date_str,
                time=time_str,
                rrc=self.config["rrc"],
                ip_version=self.ip_version
            )
            self.data_available[date_str] = has_data
            current_date += datetime.timedelta(days=1)
    
    def _create_widgets(self):
        """Create the UI components"""
        # Top frame for navigation and info
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Navigation buttons
        ttk.Button(top_frame, text="← Previous Month", command=self._prev_month).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="Next Month →", command=self._next_month).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="Today", command=self._today).pack(side=tk.LEFT, padx=5)
        
        self.month_label = ttk.Label(top_frame, text="", font=("Arial", 14, "bold"))
        self.month_label.pack(side=tk.LEFT, padx=20)
        
        # Legend
        legend_frame = ttk.Frame(self.root)
        legend_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(legend_frame, text="Legend:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        
        has_data_frame = ttk.Frame(legend_frame)
        has_data_frame.pack(anchor=tk.W, pady=2)
        tk.Label(has_data_frame, bg="#90EE90", width=2).pack(side=tk.LEFT)
        ttk.Label(has_data_frame, text="Data available").pack(side=tk.LEFT, padx=5)
        
        no_data_frame = ttk.Frame(legend_frame)
        no_data_frame.pack(anchor=tk.W, pady=2)
        tk.Label(no_data_frame, bg="#FFB6C6", width=2).pack(side=tk.LEFT)
        ttk.Label(no_data_frame, text="No data").pack(side=tk.LEFT, padx=5)
        
        outside_frame = ttk.Frame(legend_frame)
        outside_frame.pack(anchor=tk.W, pady=2)
        tk.Label(outside_frame, bg="#CCCCCC", width=2).pack(side=tk.LEFT)
        ttk.Label(outside_frame, text="Outside date range").pack(side=tk.LEFT, padx=5)
        
        # Calendar frame
        self.calendar_frame = ttk.Frame(self.root)
        self.calendar_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Stats frame
        self.stats_frame = ttk.Frame(self.root)
        self.stats_frame.pack(fill=tk.X, padx=10, pady=10)
    
    def _prev_month(self):
        """Go to previous month"""
        self.current_date = self.current_date.replace(day=1) - datetime.timedelta(days=1)
        self._update_calendar()
    
    def _next_month(self):
        """Go to next month"""
        # Find first day of next month
        if self.current_date.month == 12:
            self.current_date = self.current_date.replace(year=self.current_date.year + 1, month=1, day=1)
        else:
            self.current_date = self.current_date.replace(month=self.current_date.month + 1, day=1)
        self._update_calendar()
    
    def _today(self):
        """Go to today's month"""
        today = datetime.datetime.now()
        self.current_date = today.replace(day=1)
        self._update_calendar()
    
    def _update_calendar(self):
        """Update the calendar display"""
        # Clear previous calendar
        for widget in self.calendar_frame.winfo_children():
            widget.destroy()
        
        # Month and year label
        self.month_label.config(text=self.current_date.strftime("%B %Y"))
        
        # Day headers
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for i, day in enumerate(days):
            ttk.Label(self.calendar_frame, text=day, font=("Arial", 10, "bold")).grid(
                row=0, column=i, padx=5, pady=5
            )
        
        # Get calendar for current month
        cal = calendar.monthcalendar(self.current_date.year, self.current_date.month)
        
        # Display dates
        for week_num, week in enumerate(cal):
            for day_num, day in enumerate(week):
                if day == 0:
                    # Day from another month
                    label = tk.Label(self.calendar_frame, text="", bg="#CCCCCC", width=4, height=3)
                else:
                    # Create date string
                    date_obj = datetime.datetime(self.current_date.year, self.current_date.month, day)
                    date_str = date_obj.strftime("%Y-%m-%d")
                    
                    # Check if date is within range and has data
                    if date_obj < self.start_date or date_obj > self.end_date:
                        bg_color = "#CCCCCC"
                        text = str(day)
                    elif self.data_available.get(date_str, False):
                        bg_color = "#90EE90"
                        text = str(day)
                    else:
                        bg_color = "#FFB6C6"
                        text = str(day)
                    
                    label = tk.Label(
                        self.calendar_frame,
                        text=text,
                        bg=bg_color,
                        width=4,
                        height=3,
                        font=("Arial", 9),
                        relief=tk.RIDGE,
                        borderwidth=1,
                        cursor="hand2"
                    )
                    label.bind("<Button-1>", lambda e, d=date_str: self._on_date_click(d))
                
                label.grid(row=week_num + 1, column=day_num, padx=2, pady=2, sticky="nsew")
        
        # Update stats
        self._update_stats()
    
    def _on_date_click(self, date_str):
        """Handle date click"""
        date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        if self.start_date <= date_obj <= self.end_date:
            has_data = self.data_available.get(date_str, False)
            status = "✓ Data available" if has_data else "✗ No data"
            print(f"{date_str}: {status}")
    
    def _update_stats(self):
        """Update statistics for current month"""
        for widget in self.stats_frame.winfo_children():
            widget.destroy()
        
        # Count available days in current month
        year = self.current_date.year
        month = self.current_date.month
        
        available_count = 0
        missing_count = 0
        
        for day in range(1, 32):
            try:
                date_obj = datetime.datetime(year, month, day)
            except ValueError:
                break
            
            if self.start_date <= date_obj <= self.end_date:
                date_str = date_obj.strftime("%Y-%m-%d")
                if self.data_available.get(date_str, False):
                    available_count += 1
                else:
                    missing_count += 1
        
        stats_text = f"Month Stats - Available: {available_count} | Missing: {missing_count}"
        ttk.Label(self.stats_frame, text=stats_text, font=("Arial", 10)).pack(anchor=tk.W)
    
    def run(self):
        """Start the calendar application"""
        self.root.mainloop()


if __name__ == "__main__":
    # You can change config_name to use different configurations
    app = DataAvailabilityCalendar(config_name="ixbr.json")
    app.run()
