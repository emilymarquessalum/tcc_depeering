"""File and data loading utilities."""
import datetime
import os
from pathlib import Path
import json


# Load configuration from JSON file
config_path = Path(__file__).parent / "config.json"
with open(config_path, 'r') as f:
    config = json.load(f)

# Extract configuration values
focused_date = config.get("focused_date")
loading_method = config.get("loading_method")
start_folder = config.get("start_folder")


def load_all_files(timeline_config):
    """Load all PeeringDB files based on configuration."""
    if loading_method == "all":
        date_skips = timeline_config.get("date_skips", 3)
        all_files = [
            f for f in os.listdir(start_folder)
            if f.startswith("peeringdb_2_dump_") and f.endswith(".json")
        ]
        all_files.sort()

        if date_skips > 1:
            all_files = all_files[::date_skips]

        if focused_date:
            all_files = [file for file in all_files if focused_date in file]
    else:
        start_date = timeline_config.get("start_date", "20240101")
        end_date = timeline_config.get("end_date", "20240401")
        intervals_in_months = timeline_config.get("intervals_in_months", 3)
        current_date = datetime.datetime.strptime(start_date, "%Y%m%d")
        all_files = []

        while current_date.strftime("%Y%m%d") <= end_date:
            file_name = f"peeringdb_2_dump_{current_date.strftime('%Y_%m_%d')}.json"
            alternative_date = current_date + datetime.timedelta(days=5)
            file_name_replacement = f"peeringdb_2_dump_{alternative_date.strftime('%Y_%m_%d')}.json"

            all_file_names = [file_name, file_name_replacement]
            file_found = False
            for fname in all_file_names:
                if os.path.exists(os.path.join(start_folder, fname)):
                    all_files.append(fname)
                    file_found = True
                    break
            if not file_found:  
                print(f"Warning: File {file_name} not found in {start_folder}")

            # Increment by the specified number of months
            month = current_date.month - 1 + intervals_in_months
            year = current_date.year + month // 12
            month = month % 12 + 1
            current_date = current_date.replace(year=year, month=month)

    return all_files
