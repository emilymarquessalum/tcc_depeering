


import datetime
from datetime import datetime, timedelta 
from pathlib import Path
import sys

import requests

 

sys.path.insert(0, str(Path(__file__).parent.parent.parent)) 
 
from src.ripe_bviews.download_and_parse.download_file import get_rib_output_file_names
from src.ripe_bviews.read_bgpdump import BGPDumpSnapshotStats, read_bgpdump, read_bgpdump_from_file_options

def load_bview_data_from_api(configs, ip_version="v4"):
    start_date = datetime.strptime(configs["start_date"], "%Y-%m-%d")
    end_date = datetime.strptime(configs["end_date"], "%Y-%m-%d")
    if ip_version == "v6":
        asn_and_prefix = configs["asn_and_prefix_v6"].get("asn"), configs["asn_and_prefix_v6"].get("prefix")
    else:
        asn_and_prefix = configs["asn_and_prefix"].get("asn"), configs["asn_and_prefix"].get("prefix")
    rrc = configs["rrc"]
    day_delta = timedelta(days=configs.get("day_delta", 7))
    time_str = configs.get("time_str", "0000")
    time_delta = configs.get("time_delta_hours", 0)
    path = f"http://localhost:4000/bview?start_date={start_date.strftime('%Y-%m-%d')}&end_date={end_date.strftime('%Y-%m-%d')}&day_delta={day_delta.days}&time_delta={time_delta}&time_str={time_str}&rrc={rrc}&ip_version={ip_version}&asn={asn_and_prefix[0]}&prefix={asn_and_prefix[1]}"

    response = requests.get(path)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch data from API. Status code: {response.status_code}")
        return None

def load_bview_data_timeline_from_configs(configs, ip_version="v4", skip_if_missing=0, ignored_dates=None) -> tuple[list[BGPDumpSnapshotStats], list]:
    if ip_version == "v6":
        asn_and_prefix = configs["asn_and_prefix_v6"].get("asn"), configs["asn_and_prefix_v6"].get("prefix")
    else:
        asn_and_prefix = configs["asn_and_prefix"].get("asn"), configs["asn_and_prefix"].get("prefix")
    rrc = configs["rrc"]
    start_date = datetime.strptime(configs["start_date"], "%Y-%m-%d")
    end_date = datetime.strptime(configs["end_date"], "%Y-%m-%d")
    day_delta = timedelta(days=configs.get("day_delta", 7))
    time_str = configs.get("time_str", "0000")

    return load_bview_data_timeline(start_date, end_date, asn_and_prefix, rrc, day_delta=day_delta, time_delta_hours=configs.get("time_delta_hours", 0), time_str=time_str, ip_version=ip_version, skip_if_missing=skip_if_missing, ignored_dates=ignored_dates)

def get_new_date_str(current_date_str, time_delta_hours):
    date_str_to_number = int(current_date_str[:2])

    if time_delta_hours == 0:
        return current_date_str, False
    date_str_to_number += time_delta_hours 
    if date_str_to_number >= 24:
        date_str_to_number -= 24
        return str(date_str_to_number).zfill(2) + "00", True
    return str(date_str_to_number).zfill(2) + "00", False
    

def load_bview_data_timeline(start_date, end_date, asn_and_prefix, rrc, day_delta=None, time_delta_hours=None, time_str=None, ip_version=None, skip_if_missing=0, ignored_dates=None) -> tuple[list[BGPDumpSnapshotStats], list]:
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
    
    while current_date < end_date: 
        # Check if current date/time is in ignored_dates
        current_datetime_str = current_date.strftime("%Y%m%d") + "." + current_date_str
        if current_datetime_str in ignored_dates:
            print(f"Skipping ignored date: {current_datetime_str}")
            current_date += day_delta  
            current_date_str, date_changed = get_new_date_str(current_date_str, time_delta_hours)
            if date_changed:
                current_date += timedelta(days=1)
            continue

        output_file_names = get_rib_output_file_names(rrc, current_date.strftime("%Y%m%d"), time_str, asn_and_prefix[0], asn_and_prefix[1])
        
        
        stats = read_bgpdump_from_file_options(output_file_names, asn_and_prefix[0], rrc, ip_version, monitor_prefix=asn_and_prefix[1], date=current_date.strftime("%Y%m%d"), time=current_date_str, skip_if_missing=(skip_if_missing > 0))
        #save_details_path = append_root(f"data/{rrc}/stats_{date_str}_{time_str}.txt")
        #stats.save_details(save_details_path) 
        if stats is None:
            consecutive_missing += 1
            if skip_if_missing > 0 and consecutive_missing <= skip_if_missing:
                current_date += day_delta  
                current_date_str, date_changed = get_new_date_str(current_date_str, time_delta_hours)
                if date_changed:
                    current_date += timedelta(days=1)
                continue
            else:
                raise ValueError(f"Missing file after {consecutive_missing} consecutive missing files exceeded threshold of {skip_if_missing}: {output_file_name}")
        
        consecutive_missing = 0
        
        if len(stats.unique_members) == 0:
            stats = all_stats[-1] if all_stats else stats
        all_stats.append(stats)
        labels.append(current_date.strftime("%Y")[2:] + "/" + current_date.strftime("%m") + "/" + current_date.strftime("%d") + " " + current_date_str)
        current_date += day_delta  
        current_date_str, date_changed = get_new_date_str(current_date_str, time_delta_hours)
        if date_changed:
            current_date += timedelta(days=1)

    return all_stats, labels

def load_bview_data(date, asn_and_prefix, rrc):
    return load_bview_data_timeline(date, date + timedelta(days=1), asn_and_prefix, rrc)