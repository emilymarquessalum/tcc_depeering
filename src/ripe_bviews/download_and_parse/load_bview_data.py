


import datetime
from datetime import datetime, timedelta 
import os
from pathlib import Path
import sys

import requests
from tqdm import tqdm
 

sys.path.insert(0, str(Path(__file__).parent.parent.parent)) 
 
from src.ripe_bviews.download_and_parse.download_file import get_rib_output_file_names
from src.ripe_bviews.read_bgpdump import BGPDumpSnapshotStats, read_bgpdump, read_bgpdump_from_file_options

URL_ELIXIR = os.getenv("URL_ELIXIR", "http://localhost:4000")

def load_bview_data_from_api(configs, ip_version="v4", load_from_routeviews=False):
    start_date = datetime.strptime(configs["start_date"], "%Y-%m-%d")
    end_date = datetime.strptime(configs["end_date"], "%Y-%m-%d")
    if ip_version == "v6":
        asn_and_prefix = configs["asn_and_prefix_v6"].get("asn"), configs["asn_and_prefix_v6"].get("prefix")
    else:
        asn_and_prefix = configs["asn_and_prefix"].get("asn"), configs["asn_and_prefix"].get("prefix")
    rrc = configs['routeserver-folder-name'] if load_from_routeviews else configs["rrc"]
    day_delta = timedelta(days=configs.get("day_delta", 7))
    time_str = configs.get("time_str", "0000")
    time_delta = configs.get("time_delta_hours", 0)
    path = f"{URL_ELIXIR}/bview?start_date={start_date.strftime('%Y-%m-%d')}&end_date={end_date.strftime('%Y-%m-%d')}&day_delta={day_delta.days}&time_delta={time_delta}&time_str={time_str}&rrc={rrc}&ip_version={ip_version}&asn={asn_and_prefix[0]}&prefix={asn_and_prefix[1]}"

    response = requests.get(path)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch data from API. Status code: {response.status_code}")
        return None


def load_bview_asn_data_from_collector_api(configs, origin_asn, ip_version="v4", load_from_routeviews=False):

    start_date = datetime.strptime(configs["start_date"], "%Y-%m-%d")
    end_date = datetime.strptime(configs["end_date"], "%Y-%m-%d")
    day_delta = timedelta(days=configs.get("day_delta", 7))
    time_str = configs.get("time_str", "0000")
    time_delta = configs.get("time_delta_hours", 0)
    origin_asn = origin_asn
    rrc = configs['routeserver-folder-name'] if load_from_routeviews else configs["rrc"] 
    path = f"{URL_ELIXIR}/bview?start_date={start_date.strftime('%Y-%m-%d')}&end_date={end_date.strftime('%Y-%m-%d')}&day_delta={day_delta.days}&time_delta={time_delta}&time_str={time_str}&rrc={rrc}&ip_version={ip_version}&origin_asn={origin_asn}"
 
    response = requests.get(path) 
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch data from API. Status code: {response.status_code}")
        return None


def load_bview_asn_data_timeline_from_configs(configs, origin_asn, ip_version="v4", load_from_routeviews=False):
    start_date = datetime.strptime(configs["start_date"], "%Y-%m-%d")
    end_date = datetime.strptime(configs["end_date"], "%Y-%m-%d")
    day_delta = timedelta(days=configs.get("day_delta", 7))
    time_str = configs.get("time_str", "0000") 
    return load_bview_data_timeline(start_date, end_date, (), configs['routeserver-folder-name'] if load_from_routeviews else configs["rrc"], 
                                    origin_asn=origin_asn,
                                    day_delta=day_delta, time_delta_hours=configs.get("time_delta_hours", 0), time_str=time_str, ip_version=ip_version, skip_if_missing=0, ignored_dates=[], max_iterations=None, load_from_both_routeviews_and_rrc=False)


def load_bview_data_timeline_from_configs(configs, ip_version="v4", skip_if_missing=0, ignored_dates=None,
                                          max_iterations=None,
                                          load_from_routeviews=False, load_from_both_routeviews_and_rrc=False) -> tuple[list[BGPDumpSnapshotStats], list]:
    if ip_version == "v6":
        asn_and_prefix = configs["asn_and_prefix_v6"].get("asn"), configs["asn_and_prefix_v6"].get("prefix")
    else:
        asn_and_prefix = configs["asn_and_prefix"].get("asn"), configs["asn_and_prefix"].get("prefix")
    rrc = configs['routeserver-folder-name'] if load_from_routeviews else configs["rrc"]
    if load_from_both_routeviews_and_rrc:
        rrc = [configs["rrc"], configs['routeserver-folder-name']]
        print(f"[DEBUG] load_bview_data_timeline_from_configs: load_from_both_routeviews_and_rrc is True, using rrc list: {rrc}")
    start_date = datetime.strptime(configs["start_date"], "%Y-%m-%d")
    end_date = datetime.strptime(configs["end_date"], "%Y-%m-%d")
    day_delta = timedelta(days=configs.get("day_delta", 7))
    time_str = configs.get("time_str", "0000")

    return load_bview_data_timeline(start_date, end_date, asn_and_prefix, rrc, day_delta=day_delta, time_delta_hours=configs.get("time_delta_hours", 0), time_str=time_str, ip_version=ip_version, skip_if_missing=skip_if_missing, ignored_dates=ignored_dates, max_iterations=max_iterations, load_from_both_routeviews_and_rrc=load_from_both_routeviews_and_rrc)

def get_new_date_str(current_date_str, time_delta_hours):
    date_str_to_number = int(current_date_str[:2])

    if time_delta_hours == 0:
        return current_date_str, False
    date_str_to_number += time_delta_hours 
    if date_str_to_number >= 24:
        date_str_to_number -= 24
        return str(date_str_to_number).zfill(2) + "00", True
    return str(date_str_to_number).zfill(2) + "00", False
    
def get_progress_bar_from_timeline(start_date, end_date, day_delta, rrc, ip_version):
    total_expected_snapshots = 0
    temp_date = start_date
    while temp_date < end_date:
        total_expected_snapshots += 1
        temp_date += day_delta
        # Note: If time_delta_hours alters dates, this is a close approximation.
        # tqdm handles slight variations gracefully if the count isn't 100% exact.

    # --- NEW: Initialize the progress bar ---
    return tqdm(
        total=total_expected_snapshots, 
        desc=f"Loading Snapshots for {rrc} ({ip_version})", 
        unit="snapshot",
        leave=True
    )

def load_bview_data_timeline(start_date, end_date, asn_and_prefix, rrc, 
                             origin_asn=None,
                             day_delta=None, time_delta_hours=None, time_str=None, ip_version=None, skip_if_missing=0, ignored_dates=None, max_iterations=None,
                             load_from_both_routeviews_and_rrc=False) -> tuple[list[BGPDumpSnapshotStats], list]:
    current_date = start_date
    if day_delta is None:
        day_delta = datetime.timedelta(days=7)

    if time_str is None:
        time_str = "0000"   
    
    if ignored_dates is None:
        ignored_dates = []
    
    all_stats = []

    current_date = start_date
    current_date_str = time_str
    labels = []
    consecutive_missing = 0
    
    
    progress_bar = get_progress_bar_from_timeline(start_date, end_date, day_delta, rrc, ip_version)

    snapshot_count = 0
    
    while current_date < end_date: 
        

        if max_iterations is not None and snapshot_count >= max_iterations:
            break
        snapshot_count += 1
        # Check if current date/time is in ignored_dates
        current_datetime_str = current_date.strftime("%Y%m%d") + "." + current_date_str
        if current_datetime_str in ignored_dates:
            print(f"Skipping ignored date: {current_datetime_str}")
            current_date += day_delta  
            current_date_str, date_changed = get_new_date_str(current_date_str, time_delta_hours)
            if date_changed:
                current_date += timedelta(days=1)
            progress_bar.update(1) # Advance progress bar even on skip
            continue

         
        stats = load_bview_from_context(rrc, current_date, current_date_str, time_str, asn_and_prefix, ip_version, 
                                        origin_asn,
                                        skip_if_missing=skip_if_missing)
        
        if stats is None:
            consecutive_missing += 1
            if skip_if_missing > 0 and consecutive_missing <= skip_if_missing:
                current_date += day_delta  
                current_date_str, date_changed = get_new_date_str(current_date_str, time_delta_hours)
                if date_changed:
                    current_date += timedelta(days=1)
                progress_bar.update(1) # Advance progress bar on skipped missing files
                continue
            else:
                progress_bar.close() # Clean up before throwing an error
                raise ValueError(f"Missing file after {consecutive_missing} consecutive missing files exceeded threshold of {skip_if_missing}")
        
        consecutive_missing = 0
        
        #if len(stats.unique_members) == 0:
        #    stats = all_stats[-1] if all_stats else stats
        all_stats.append(stats)
        labels.append(current_date.strftime("%Y")[2:] + "/" + current_date.strftime("%m") + "/" + current_date.strftime("%d") + " " + current_date_str)
        
        current_date += day_delta  
        current_date_str, date_changed = get_new_date_str(current_date_str, time_delta_hours)
        if date_changed:
            current_date += timedelta(days=1)
            
        # --- NEW: Update progress bar by 1 on successful load ---
        progress_bar.update(1)

    # --- NEW: Ensure progress bar completes nicely ---
    progress_bar.close()
    return all_stats, labels 

def load_bview_from_context(rrc, current_date, current_date_str, time_str, asn_and_prefix, ip_version, origin_asn=None, skip_if_missing=0):
     
    return read_bgpdump_from_file_options(asn_and_prefix[0] if len(asn_and_prefix) > 0 else "", rrc, ip_version, monitor_prefix=asn_and_prefix[1] if len(asn_and_prefix) > 1 else "", date=current_date.strftime("%Y%m%d"), time=current_date_str, skip_if_missing=(skip_if_missing > 0), origin_asn=origin_asn)
        

def load_bview_data(date, asn_and_prefix, rrc):
    return load_bview_data_timeline(date, date + timedelta(days=1), asn_and_prefix, rrc)