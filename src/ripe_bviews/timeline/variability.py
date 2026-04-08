
import numpy as np
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
import warnings

warnings.filterwarnings('ignore', category=UserWarning, message='.*Skipping download.*')
warnings.filterwarnings('ignore', category=UserWarning, message='.*Loading details from.*')
 
from src.ripe_bviews.oscillations.bview_oscillation_logic import OscillationMetrics, calculate_oscillation_metrics
from src.ripe_bviews.download_and_parse.load_configs import load_configs, print_config
from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data_timeline_from_configs
from src.ripe_bviews.read_bgpdump import BGPDumpSnapshotStats


def get_variability(all_stats):
    member_counts = [stat.members for stat in all_stats]
    return np.var(member_counts)


def get_average_percentage_variability(all_stats: list[BGPDumpSnapshotStats], 
                                       oscillation_metrics: OscillationMetrics,
                                       removed_asns_over_time=None, look_at_reachables=False):

    if removed_asns_over_time is None:
        removed_asns_over_time = []
        for i in range(1, len(all_stats)):
            removed_asns = set(all_stats[i-1].unique_reachables if look_at_reachables else all_stats[i-1].unique_members) - set(all_stats[i].unique_reachables if look_at_reachables else all_stats[i].unique_members)
            removed_asns_over_time.append(len(removed_asns))
    
    percentage_variability = []
    all_variabilities = []
    all_consistent_variabilities = [] # variability excluding oscillating ASes
    all_consistent_percentage_variabilities = []

    variability_indexes = []
    all_variability_indexes = []

    for i in range(1, len(all_stats)):
        #if member_counts[i-1] > 0:
            current_ases = set(all_stats[i].unique_reachables if look_at_reachables else all_stats[i].unique_members)
            previous_ases = set(all_stats[i-1].unique_reachables if look_at_reachables else all_stats[i-1].unique_members)

            new_members = (current_ases - previous_ases)
            new_members_quantity = len(new_members)
            lost_members = (previous_ases - current_ases)
            lost_members_quantity = len(lost_members) 
            # it seems to be more common practice to divide 
            # by the previous total instead of current
            total_members_quantity = len(previous_ases)#len(total_members)

            new_members_excluding_oscillating = new_members - set(oscillation_metrics.get_unique_oscillating_asns())
            lost_members_excluding_oscillating = lost_members - set(oscillation_metrics.get_unique_oscillating_asns())


            variability = (new_members_quantity + lost_members_quantity) 
            variability_excluding_oscillating = (len(new_members_excluding_oscillating) + len(lost_members_excluding_oscillating))
            variability_index = (new_members_quantity - lost_members_quantity) 
            
            all_variabilities.append(variability)
            all_consistent_variabilities.append(variability_excluding_oscillating)
            all_variability_indexes.append(variability_index)

            if variability_index == 0:
                pass#print("no change")
            
            variability_excluding_oscillating_percentage = variability_excluding_oscillating / total_members_quantity if total_members_quantity else 0
            
            variability_percentage = variability / total_members_quantity if total_members_quantity else 0
            variability_index_percentage = variability_index / total_members_quantity if total_members_quantity else 0
            
            variability_indexes.append(variability_index_percentage)
            percentage_variability.append((variability_percentage))
            all_consistent_percentage_variabilities.append(variability_excluding_oscillating_percentage)
    
    
    average_variability = np.mean(all_variabilities) if all_variabilities else 0
    average_consistent_variability = np.mean(all_consistent_variabilities) if all_consistent_variabilities else 0
    average_variability_index = np.mean(all_variability_indexes) if all_variability_indexes else 0
    average_percentage_variability = np.mean(percentage_variability) if percentage_variability else 0
    average_percentage_variability_index = np.mean(variability_indexes) if variability_indexes else 0

    average_percentage_consistent_variability = np.mean(all_consistent_percentage_variabilities) if all_consistent_percentage_variabilities else 0

    return average_variability, average_consistent_variability, average_variability_index, average_percentage_variability, average_percentage_consistent_variability, average_percentage_variability_index, removed_asns_over_time



if __name__ == "__main__":
     
  

    configs_to_test = ["ixbr.json"
                      # , "de-cix-amsterdam.json"
                       ]

    for config_name in configs_to_test:
        
        config = load_configs(config_name)
        print_config(config)

        for ip_version in ["v4", "v6"]:
            print("---")
            
            all_stats = load_bview_data_timeline_from_configs(config, ip_version=ip_version)[0]


            for is_looking_at_reachables in [False, True]:
                     
                    oscillation_metrics = calculate_oscillation_metrics(all_stats, use_reachables=is_looking_at_reachables)
                    looking_at_reachables = is_looking_at_reachables
                    average_variability, average_consistent_variability, average_variability_index, average_percentage_variability, average_percentage_consistent_variability, average_percentage_variability_index, removed_asns_over_time = get_average_percentage_variability(all_stats, oscillation_metrics, look_at_reachables=looking_at_reachables)
                    
                    print(f"{config.get('name')} - IP Version: {ip_version} - Looking at {'reachables' if looking_at_reachables else 'members'}")
                    # churn both directions in % to say the value per day, AS absolute values
                    print(f"{config.get('name')} Average variability (looking at {'reachables' if looking_at_reachables else 'members'}): {average_variability:.2f} ASes")
                    # same as above but / total members 
                    print(f"{config.get('name')} Average percentage variability (looking at {'reachables' if looking_at_reachables else 'members'}): {average_percentage_variability:.2%}")
                    
                    # consistent: remove oscillating ASes from the variability
                    print(f"{config.get('name')} Average consistent variability (looking at {'reachables' if looking_at_reachables else 'members'}): {average_consistent_variability:.2f} ASes")
                    print(f"{config.get('name')} Average percentage consistent variability (looking at {'reachables' if looking_at_reachables else 'members'}): {average_percentage_consistent_variability:.2%}")
                    
                    # index: new - lost ASes, can be negative, zero or positive. Can be divided by total members to have a percentage.
                    print(f"{config.get('name')} Average variability index (looking at {'reachables' if looking_at_reachables else 'members'}): {average_variability_index:.2f} ASes")
                    print(f"{config.get('name')} Variability index (looking at {'reachables' if looking_at_reachables else 'members'}): {average_percentage_variability_index:.2%}")
                    print("---")
            