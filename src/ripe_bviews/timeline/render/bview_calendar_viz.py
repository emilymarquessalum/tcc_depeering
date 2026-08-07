import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
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
        
        # Gather initial data availability info
        self.data_available = {}
        self._check_data_availability()
        
        # Create window
        self.root = tk.Tk()
        self.root.title(f"Data Availability Calendar - {config_name}")
        self.root.geometry("1000x750")
        
        # Current month being displayed
        self.current_date = self.start_date
        
        self._create_widgets()
        self._update_calendar()
    
    def _check_data_availability(self):
        """Pre-populate data availability for the config range"""
        current_date = self.start_date
        while current_date <= self.end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            self.data_available[date_str] = self._fetch_single_day_status(date_str)
            current_date += datetime.timedelta(days=1)

    def _fetch_single_day_status(self, date_str):
        """Helper to check file existence dynamically for any date"""
        time_str = self.config.get("time_str", "0000")
        return does_bgpdump_file_exist(
            monitor_as=self.config["asn_and_prefix"].get("asn"),
            monitor_prefix=self.config["asn_and_prefix"].get("prefix"),
            date=date_str,
            time=time_str,
            rrc=self.config["rrc"] if "rrc" in self.config else self.config["routeserver-folder-name"],
            ip_version=self.ip_version
        )
    
    def _on_version_change(self, event):
        """Handle IP version dropdown modification"""
        new_version = self.version_combo.get()
        self.ip_version = int(new_version.replace("v", "")) 
        
        self.data_available.clear()
        self._check_data_availability()
        self._update_calendar()

    def _find_global_boundary(self, search_direction="earliest"):
        """
        Scans global timeline for data outside the config boundaries.
        Uses binary/exponential leaps over years, months, then days for optimal performance.
        """
        # Start searching outwards from our config boundaries
        reference_date = self.start_date if search_direction == "earliest" else self.end_date
        delta_sign = -1 if search_direction == "earliest" else 1
        
        last_known_valid = None
        
        # Step 1: Check the current config baseline first
        for date_str, has_data in self.data_available.items():
            if has_data:
                d_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                if last_known_valid is None:
                    last_known_valid = d_obj
                elif search_direction == "earliest" and d_obj < last_known_valid:
                    last_known_valid = d_obj
                elif search_direction == "latest" and d_obj > last_known_valid:
                    last_known_valid = d_obj

        # Step 2: Binary / Exponential skip search out into the unknown (up to 25 years out)
        current_search = reference_date
        found_any_extrema = False
        
        # Test large jumps first (Years), then medium (Months), then fine (Days)
        for stride in [365, 30, 1]:
            while True:
                next_test = current_search + datetime.timedelta(days=delta_sign * stride)
                
                # Sanity guard boundaries (e.g., historical internet bgp data doesn't exist pre-1990 or far future)
                if next_test.year < 1995 or next_test.year > 2035:
                    break
                    
                test_str = next_test.strftime("%Y-%m-%d")
                if self._fetch_single_day_status(test_str):
                    current_search = next_test
                    last_known_valid = next_test
                    found_any_extrema = True
                else:
                    # If jumping years/months failed, drop stride down to check smaller increments
                    break
                    
        return last_known_valid

    def _jump_to_earliest(self):
        """Finds and jumps to the earliest global date with data"""
        self.root.config(cursor="watch")  # Changed "wait" to "watch"
        self.root.update()
        
        target = self._find_global_boundary(search_direction="earliest")
        
        self.root.config(cursor="")
        if target:
            self.current_date = target
            self._update_calendar()
            messagebox.showinfo("Success", f"Jumped to earliest data found: {target.strftime('%Y-%m-%d')}")
        else:
            messagebox.showwarning("Not Found", "No data records could be found anywhere globally.")

    def _jump_to_newest(self):
        """Finds and jumps to the newest global date with data"""
        self.root.config(cursor="watch")  # Changed "wait" to "watch"
        self.root.update()
        
        target = self._find_global_boundary(search_direction="latest")
        
        self.root.config(cursor="")
        if target:
            self.current_date = target
            self._update_calendar()
            messagebox.showinfo("Success", f"Jumped to newest data found: {target.strftime('%Y-%m-%d')}")
        else:
            messagebox.showwarning("Not Found", "No data records could be found anywhere globally.")
            
    def _create_widgets(self):
        """Create the UI components"""
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Standard Navigation buttons
        ttk.Button(top_frame, text="← Previous Month", command=self._prev_month).pack(side=tk.LEFT, padx=2)
        ttk.Button(top_frame, text="Next Month →", command=self._next_month).pack(side=tk.LEFT, padx=2)
        ttk.Button(top_frame, text="Today", command=self._today).pack(side=tk.LEFT, padx=2)
        
        # New Global Discovery Navigation Buttons
        ttk.Button(top_frame, text="⏮ Earliest Data", command=self._jump_to_earliest).pack(side=tk.LEFT, padx=10)
        ttk.Button(top_frame, text="⏭ Newest Data", command=self._jump_to_newest).pack(side=tk.LEFT, padx=2)
        
        self.month_label = ttk.Label(top_frame, text="", font=("Arial", 14, "bold"))
        self.month_label.pack(side=tk.LEFT, padx=20)

        # IP Version Selector Dropdown
        ttk.Label(top_frame, text="IP Version:", font=("Arial", 10)).pack(side=tk.LEFT, padx=(20, 5))
        current_v_str = f"v{self.ip_version}"
        self.version_combo = ttk.Combobox(top_frame, values=["v4", "v6"], width=5, state="readonly")
        self.version_combo.set(current_v_str if current_v_str in ["v4", "v6"] else "v4")
        self.version_combo.bind("<<ComboboxSelected>>", self._on_version_change)
        self.version_combo.pack(side=tk.LEFT, padx=5)
        
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
        
        config_bound_frame = ttk.Frame(legend_frame)
        config_bound_frame.pack(anchor=tk.W, pady=2)
        tk.Label(config_bound_frame, bg="#FFF275", width=2).pack(side=tk.LEFT)
        ttk.Label(config_bound_frame, text="Config Start / End Date").pack(side=tk.LEFT, padx=5)
        
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
        for widget in self.calendar_frame.winfo_children():
            widget.destroy()
        
        self.month_label.config(text=self.current_date.strftime("%B %Y"))
        
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for i, day in enumerate(days):
            ttk.Label(self.calendar_frame, text=day, font=("Arial", 10, "bold")).grid(
                row=0, column=i, padx=5, pady=5
            )
        
        cal = calendar.monthcalendar(self.current_date.year, self.current_date.month)
        
        for week_num, week in enumerate(cal):
            for day_num, day in enumerate(week):
                if day == 0:
                    label = tk.Label(self.calendar_frame, text="", bg="#EAEAEA", width=4, height=3)
                else:
                    date_obj = datetime.datetime(self.current_date.year, self.current_date.month, day)
                    date_str = date_obj.strftime("%Y-%m-%d")
                    
                    if date_str not in self.data_available:
                        self.data_available[date_str] = self._fetch_single_day_status(date_str)
                    
                    has_data = self.data_available.get(date_str, False)
                    font_style = ("Arial", 9)
                    
                    if date_obj.date() == self.start_date.date() or date_obj.date() == self.end_date.date():
                        bg_color = "#FFF275"
                        font_style = ("Arial", 9, "bold")
                    elif has_data:
                        bg_color = "#90EE90"
                    else:
                        bg_color = "#FFB6C6"
                    
                    label = tk.Label(
                        self.calendar_frame,
                        text=str(day),
                        bg=bg_color,
                        width=4,
                        height=3,
                        font=font_style,
                        relief=tk.RIDGE,
                        borderwidth=1,
                        cursor="hand2"
                    )
                    label.bind("<Button-1>", lambda e, d=date_str: self._on_date_click(d))
                
                label.grid(row=week_num + 1, column=day_num, padx=2, pady=2, sticky="nsew")
        
        self._update_stats()
    
    def _on_date_click(self, date_str):
        """Handle date click"""
        has_data = self.data_available.get(date_str, False)
        status = "✓ Data available" if has_data else "✗ No data"
        
        date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        range_note = "" if self.start_date <= date_obj <= self.end_date else " (Outside configured boundaries)"
        
        print(f"{date_str}: {status}{range_note} [v{self.ip_version}]")
    
    def _update_stats(self):
        """Update statistics for current month"""
        for widget in self.stats_frame.winfo_children():
            widget.destroy()
        
        year = self.current_date.year
        month = self.current_date.month
        
        available_count = 0
        missing_count = 0
        
        for day in range(1, 32):
            try:
                date_obj = datetime.datetime(year, month, day)
            except ValueError:
                break
            
            date_str = date_obj.strftime("%Y-%m-%d")
            if date_str not in self.data_available:
                self.data_available[date_str] = self._fetch_single_day_status(date_str)
                
            if self.data_available.get(date_str, False):
                available_count += 1
            else:
                missing_count += 1
        
        stats_text = f"Month Stats (All Days Shown) - Available: {available_count} | Missing: {missing_count} | Current View: v{self.ip_version}"
        ttk.Label(self.stats_frame, text=stats_text, font=("Arial", 10)).pack(anchor=tk.W)
    
    def run(self):
        """Start the calendar application"""
        self.root.mainloop()


if __name__ == "__main__":
    config_name = "ixbr.json"
    app = DataAvailabilityCalendar(config_name=config_name)
    app.run()