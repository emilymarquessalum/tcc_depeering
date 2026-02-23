
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
import warnings

warnings.filterwarnings('ignore', category=UserWarning, message='.*Skipping download.*')
warnings.filterwarnings('ignore', category=UserWarning, message='.*Loading details from.*')
 
from src.ripe_bviews.download_and_parse.load_configs import load_configs
from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data_timeline, load_bview_data_timeline_from_configs
 
def get_variability(all_stats):
    member_counts = [stat.members for stat in all_stats]
    return np.var(member_counts)


def get_average_percentage_variability(all_stats, removed_asns_over_time=None, look_at_reachables=False):

    if removed_asns_over_time is None:
        removed_asns_over_time = []
        for i in range(1, len(all_stats)):
            removed_asns = set(all_stats[i-1].unique_reachables if look_at_reachables else all_stats[i-1].unique_members) - set(all_stats[i].unique_reachables if look_at_reachables else all_stats[i].unique_members)
            removed_asns_over_time.append(len(removed_asns))
    member_counts = [stat.reachables if look_at_reachables else stat.members for stat in all_stats]
    percentage_variability = []
    for i in range(1, len(member_counts)):
        if member_counts[i-1] > 0:
            variability = (member_counts[i-1] - member_counts[i]) / member_counts[i-1]
            percentage_variability.append(abs(variability))
    average_percentage_variability = np.mean(percentage_variability) if percentage_variability else 0

    return average_percentage_variability, removed_asns_over_time



if __name__ == "__main__":
     
  

    configs_to_test = ["ixbr.json"
                      # , "de-cix-amsterdam.json"
                       ]
    ip_version = "v6"
    for is_looking_at_reachables in [False, True]:
        for config_name in configs_to_test:
            config = load_configs(config_name)

            
            all_stats = load_bview_data_timeline_from_configs(config, ip_version=ip_version)[0]
            looking_at_reachables = is_looking_at_reachables
            percentage_variability, removed_asns_over_time = get_average_percentage_variability(all_stats, look_at_reachables=looking_at_reachables)
            print(f"{config.get('name')} Average percentage variability (looking at {'reachables' if looking_at_reachables else 'members'}): {percentage_variability:.2%}")

        