"""File and data loading utilities."""
import datetime
import os
from pathlib import Path
import json
import re
from src.caidapeeringdb.caidapeeringdb_load import download_peeringdb_dump, get_data
from definitions import ROOT_DIR

# Load configuration from JSON file
config_path = Path(__file__).parent / "config.json"
with open(config_path, 'r') as f:
    config = json.load(f)

# Extract configuration values
focused_date = config.get("focused_date")
loading_method = config.get("loading_method")
start_folder = ROOT_DIR + "caida-peeringdb/"   

def load_all_files(timeline_config):
    """Load all PeeringDB files based on configuration."""

    load_missing_files = None

    dates = []
    
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
        start_date = timeline_config.get("start_date", "20240101").replace("-", "")
        end_date = timeline_config.get("end_date", "20240401").replace("-", "")
        intervals_in_months = timeline_config.get("intervals_in_months", 0)
        intervals_in_days = timeline_config.get("intervals_in_days", 0)

        if intervals_in_months == 0 and intervals_in_days == 0:
            raise ValueError("Both intervals_in_months and intervals_in_days cannot be zero.")
        
        current_date = datetime.datetime.strptime(start_date, "%Y%m%d")
        all_files = []

        while current_date.strftime("%Y%m%d") <= end_date:

            date_to_load = current_date.strftime('%Y_%m_%d')
            dates.append(date_to_load)
            
            file_name = f"peeringdb_2_dump_{date_to_load}.json"
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

                if load_missing_files is None:
                    user_input = input("Do you want to load missing files? (y/n): ").strip().lower()
                    load_missing_files = user_input == 'y'
                if load_missing_files:
                    print("Loading missing file...")
                    try:
                        download_peeringdb_dump(date_to_load)  
                        file_path = os.path.join(start_folder, file_name)
                        if os.path.exists(file_path):
                            all_files.append(file_name)
                        else:
                            print(f"Error: File {file_name} still not found after download.")
                    except Exception as e:
                        print(f"Error downloading file for {date_to_load}: {e}")
                        print("Will try again but with a different day in the date")

                        new_date = current_date + datetime.timedelta(days=12)
                        new_date_to_load = new_date.strftime('%Y_%m_%d')
                        try:
                            download_peeringdb_dump(new_date_to_load, save_date=date_to_load)
                        except Exception as e:
                            print(f"Error downloading file for {new_date_to_load}: {e}")
                            print("Skipping this date.")


            # Increment by the specified number of months
            month = current_date.month - 1 + intervals_in_months
            year = current_date.year + month // 12
            month = month % 12 + 1
            current_date = current_date.replace(year=year, month=month)
            current_date += datetime.timedelta(days=intervals_in_days)

    return all_files, dates 


def load_all_data(config):

    all_files, _ = load_all_files(config)

    all_data = []
    dates = []
    
    for file in all_files:  
        # Extract date from filename
        match = re.search(r"peeringdb_2_dump_(.*?)\.json", file)
        if match:
            date_str = match.group(1)
            dates.append(date_str)
        else:
            continue
        
        data = get_data(file)
        all_data.append(data)

    return all_data, dates
 