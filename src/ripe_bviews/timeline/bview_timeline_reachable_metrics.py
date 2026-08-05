


import sys
from pathlib import Path
import warnings
from progress.bar import Bar


sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from datetime import datetime, timedelta 
from src.ripe_bviews.bview_labels import get_date_range_title
from src.ripe_bviews.read_bgpdump import BGPDumpSnapshotStats
from src.ripe_bviews.download_and_parse.load_configs import load_configs, print_config
from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data_timeline_from_configs
from src.ripe_bviews.oscillations.bview_oscillation_logic import calculate_oscillation_metrics
from src.ripe_bviews.timeline.bview_vars import get_annotations, get_ip_version, get_labels_info, get_subfolder, get_title_end, get_title_start
from src.utils.graphs import create_window_with_all_rendered_graphs_this_session, plot_list_as_line_plot, plot_map_as_bar_plot, plot_stacked_line_plot, plot_list_as_bar_plot

warnings.filterwarnings('ignore', category=UserWarning, message='.*')


def calculate_average_mappings_per_reachable(all_stats: list[BGPDumpSnapshotStats]):
    """Calculate the average number of member connections per reachable AS."""
    number_of_needed_samples = min(2, len(all_stats) - 1)
    
    # Flatten the nested loop into a fast list comprehension
    count_of_mappings_per_reachable = [
        len(stat.get_all_members_that_allow_asn_to_be_reachable(reachable))
        for stat in all_stats[:number_of_needed_samples]
        for reachable in stat.unique_reachables
    ]
    
    # Using a set directly instead of sorting it just to print (sort it inside the f-string)
    unique_counts = sorted(set(count_of_mappings_per_reachable))
    average_mappings_per_reachable = sum(count_of_mappings_per_reachable) / len(count_of_mappings_per_reachable) if count_of_mappings_per_reachable else 0
    
    print(f"(samples used: {number_of_needed_samples})")
    print(f"Average number of member connections per reachable AS: {average_mappings_per_reachable:.2f}")
    print(f"Unique number of member connections per reachable AS: {unique_counts}")


def calculate_other_members_when_member_leaves(all_stats):
    """Analyze other members providing access to reachables when a member leaves the IXP."""
    count_of_other_members_of_reachable_from_reachables_whose_member_left = {}
    count_of_total_reachables_that_left_with_the_member = 0
    number_of_samples = min(2, len(all_stats) - 1)
    for i in range(1, number_of_samples + 1):
        stat = all_stats[i]
        previous_stat = all_stats[i - 1]
        lost_members = previous_stat.unique_members - stat.unique_members
        for member in lost_members:
            related_reachables = previous_stat.mappings.get(str(member), set())
            for reachable in related_reachables:
                
                if reachable not in stat.unique_reachables:  
                    count_of_total_reachables_that_left_with_the_member += 1
                    continue
                # Only consider if the reachable was NOT lost
                for other_member, other_reachables in previous_stat.mappings.items():
                    if str(other_member) != str(member) and reachable in other_reachables:
                        if reachable not in count_of_other_members_of_reachable_from_reachables_whose_member_left:
                            count_of_other_members_of_reachable_from_reachables_whose_member_left[reachable] = 0
                        count_of_other_members_of_reachable_from_reachables_whose_member_left[reachable] += 1

    average_other_members_per_reachable = sum(count_of_other_members_of_reachable_from_reachables_whose_member_left.values()) / len(count_of_other_members_of_reachable_from_reachables_whose_member_left) if count_of_other_members_of_reachable_from_reachables_whose_member_left else 0
    print(f"(samples used: {number_of_samples})")
    print(f"Average number of other members connected to a reachable AS whose member left: {average_other_members_per_reachable:.2f}")
    print(f"Total count of reachables that left with the member: {count_of_total_reachables_that_left_with_the_member}")


def calculate_average_reachables_per_member(all_stats):
    """Calculate the average number of reachable ASes each member provides access to."""
    count_of_reachables_per_member = []
    number_of_samples = min(2, len(all_stats))
    for stat in all_stats[:number_of_samples]:
        members = stat.unique_members
        for member in members:
            related_reachables = stat.mappings.get(str(member), set())
            count = len(related_reachables)
            count_of_reachables_per_member.append(count)
    average_reachables_per_member = sum(count_of_reachables_per_member) / len(count_of_reachables_per_member) if count_of_reachables_per_member else 0
    print(f"(samples used: {number_of_samples})")
    print(f"Average number of reachable ASes per member AS: {average_reachables_per_member:.2f}")
    print(f"Unique number of reachable ASes per member AS: {sorted(set(count_of_reachables_per_member))}")



def bview_reachable_metrics(all_required_data):

    config = all_required_data["config"]
    all_stats, labels_summarized, max_labels = all_required_data["timeline"]
  
  
    calculate_average_mappings_per_reachable(all_stats)
    
    #print("Finished all plotting for dates from {} to {} with interval of {} days.".format(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), day_delta.days))

    calculate_other_members_when_member_leaves(all_stats)

    
    calculate_average_reachables_per_member(all_stats)

     