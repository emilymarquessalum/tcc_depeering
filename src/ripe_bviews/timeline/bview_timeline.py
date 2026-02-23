

import datetime
import os
import sys
from pathlib import Path
from time import sleep

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent)) 
from src.ripe_bviews.bview_labels import summarized_date_labels
from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data, load_bview_data_from_api, load_bview_data_timeline, load_bview_data_timeline_from_configs
from src.ripe_bviews.download_and_parse.load_configs import load_configs 
from src.ripe_bviews.oscillations.bview_oscillation_logic import calculate_oscillation_metrics 
import warnings 
from src.utils.graphs import plot_list_as_line_plot

 
warnings.filterwarnings('ignore', category=UserWarning, message='.*Skipping download.*')

ip_version = "v6"
config = load_configs("ixbr.json")
#config = load_configs("de-cix-amsterdam.json")

name = config.get("name", "Unknown")
asn_and_prefix = config["asn_and_prefix"].get("asn"), config["asn_and_prefix"].get("prefix")
if ip_version == "v4":
    asn_and_prefix = config["asn_and_prefix_v6"].get("asn"), config["asn_and_prefix_v6"].get("prefix")

rrc = config["rrc"]
start_date = datetime.datetime.strptime(config["start_date"], "%Y-%m-%d")
end_date = datetime.datetime.strptime(config["end_date"], "%Y-%m-%d")
day_delta = datetime.timedelta(days=config.get("day_delta", 7))
time_str = config.get("time_str", "0000")
time_delta_hours = config.get("time_delta_hours", 0) 

if __name__ == "__main__" and False:
    results_zipped = load_bview_data_from_api(config, ip_version=ip_version)
     

if __name__ == "__main__" and True:
    all_stats, labels = load_bview_data_timeline_from_configs(config, ip_version=ip_version)       
    member_history = [stat.members for stat in all_stats]
    reachable_history = [stat.reachables for stat in all_stats]

    as_metadata = {} 
 
    #subfolder = rrc + "_" + start_date.strftime("%Y%m%d") + "_" + end_date.strftime("%Y%m%d")   
    subfolder = rrc + "/" + ip_version + "/" + start_date.strftime("%Y%m%d") + "_" + end_date.strftime("%Y%m%d") + "_" + time_str + "/" + str(day_delta.days) + "days" + "/"
  
    ases_removed_that_did_not_come_back = []
    ases_first_removed = all_stats[0].unique_members.copy()
    for stat in all_stats[1:]:
        ases_first_removed -= stat.unique_members 
    ases_removed_that_did_not_come_back = ases_first_removed
    print(f"ASes removed that did not come back: {len(ases_removed_that_did_not_come_back)}")
    #print(ases_removed_that_did_not_come_back)

    ases_reachable_removed_that_did_not_come_back = []
    ases_first_removed_reachable = all_stats[0].unique_reachables.copy()
    for stat in all_stats[1:]:
        ases_first_removed_reachable -= stat.unique_reachables
    ases_reachable_removed_that_did_not_come_back = ases_first_removed_reachable
    print(f"Reachable ASes removed that did not come back: {len(ases_reachable_removed_that_did_not_come_back)}")
    #print(ases_reachable_removed_that_did_not_come_back)
 
    all_asns = set()
    for stat in all_stats:
        all_asns.update(stat.unique_members)
     
    members_metrics = calculate_oscillation_metrics(all_stats, use_reachables=False)
    oscillating_ases = set(members_metrics.oscillation_info.keys())
    
    print(f"Oscillating ASes (left and came back): {len(oscillating_ases)}")
 
    all_reachables = set()
    for stat in all_stats:
        all_reachables.update(stat.unique_reachables)
    
    # Use the correct oscillation calculation for reachables
    reachables_metrics = calculate_oscillation_metrics(all_stats, use_reachables=True)
    oscillating_reachables = set(reachables_metrics.oscillation_info.keys())
    
    print(f"Oscillating Reachable ASes (left and came back): {len(oscillating_reachables)}")
 
    total_member_departures = 0
    for asn in all_asns:
        presence = [asn in stat.unique_members for stat in all_stats]
        for i in range(1, len(presence)):
            if presence[i-1] and not presence[i]:  # True -> False transition (departure)
                total_member_departures += 1
    
    print(f"Total times member ASes left: {total_member_departures}")
 
    total_reachable_departures = 0
    for asn in all_reachables:
        presence = [asn in stat.unique_reachables for stat in all_stats]
        for i in range(1, len(presence)):
            if presence[i-1] and not presence[i]:  # True -> False transition (departure)
                total_reachable_departures += 1
    
    print(f"Total times reachable ASes left: {total_reachable_departures}")
    
    asn_data = []


    json_filepath = "../graphs/" + subfolder + "/bview_timeline_metrics.json"
    json_data = {
        "Oscillating_Member_ASes": len(oscillating_ases),
        "ASes removed that did not come back": len(ases_removed_that_did_not_come_back),
        "Total times member ASes left": total_member_departures,
    }
    if not os.path.exists(os.path.dirname(json_filepath)):
        os.makedirs(os.path.dirname(json_filepath))
    with open(json_filepath, "w") as json_file:
        import json
        json.dump(json_data, json_file, indent=4) 
    labels_summarized = summarized_date_labels(labels)
    max_labels=len(labels)//6
    plot_list_as_line_plot(member_history, labels_summarized,title=f'Member ASes Over Time - {name}', xlabel='Time (Months)', ylabel='Number of Member ASes', subfolder=subfolder, 
                           max_labels=max_labels)
    plot_list_as_line_plot(reachable_history, labels_summarized,title='Reachable ASes Over Time', xlabel='Time (Months)', ylabel='Number of Reachable ASes', subfolder=subfolder,
                           max_labels=max_labels)