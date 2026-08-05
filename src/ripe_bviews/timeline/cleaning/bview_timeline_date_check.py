






import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent)) 
 
from src.ripe_bviews.download_and_parse.load_configs import load_configs
from src.ripe_bviews.read_bgpdump import BGPDumpSnapshotStats, does_bgpdump_file_exist
from src.ripe_bviews.timeline.bview_vars import get_ip_version



import datetime 




config = load_configs("ixbr.json")

#config = load_configs("AMS-IX.json")

ip_version = get_ip_version(config)

start_date = datetime.datetime.strptime(config["start_date"], "%Y-%m-%d")
end_date = datetime.datetime.strptime(config["end_date"], "%Y-%m-%d")

current_date = start_date

existing_dates = []
non_existing_dates = []

while current_date <= end_date:
    date_str = current_date.strftime("%Y-%m-%d")
    time_str = config.get("time_str", "0000")
    if does_bgpdump_file_exist(monitor_as=config["asn_and_prefix"].get("asn"),
                               monitor_prefix=config["asn_and_prefix"].get("prefix"),
                               date=date_str,
                               time=time_str,
                               rrc=config["rrc"],
                               ip_version=ip_version):
        existing_dates.append(date_str)
    else:
        non_existing_dates.append(date_str)
    current_date += datetime.timedelta(days=1) 


def group_continuous_dates(dates_list):
    """
    Group continuous dates into intervals.
    Returns a list of tuples (start_date, end_date) for each continuous interval.
    """
    if not dates_list:
        return []
    
    # Sort dates to ensure they're in order
    sorted_dates = sorted([datetime.datetime.strptime(d, "%Y-%m-%d") for d in dates_list])
    
    intervals = []
    start_date = sorted_dates[0]
    end_date = sorted_dates[0]  
    
    for i in range(1, len(sorted_dates)):
        current_date = sorted_dates[i]
        # Check if dates are consecutive
        if (current_date - end_date).days == 1:
            end_date = current_date
        else:
            # Gap found, save interval and start new one
            intervals.append((start_date, end_date))
            start_date = current_date
            end_date = current_date
    
    # Add the last interval
    intervals.append((start_date, end_date))
    
    return intervals


# Group non-existing dates into intervals
non_existing_intervals = group_continuous_dates(non_existing_dates)

print("Non Existing dates grouped by intervals:")
for start, end in non_existing_intervals:
    if start == end:
        print(f"  {start.strftime('%Y-%m-%d')} (single day)")
    else:
        print(f"  {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}")

