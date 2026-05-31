


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

def check_reachable_lost_routes_categories(all_stats, labels_summarized, config, title_start, title_end, subfolder, max_labels, should_remove_prepend=True):
    """Categorize reachables into groups based on AS path length changes when they lost routes."""
    reachable_lost_routes_but_still_in_ixp_with_same_as_path_length = []
    reachable_lost_routes_but_still_in_ixp_with_worse_as_path_length = []
    reachable_lost_routes_but_still_in_ixp_with_better_as_path_length = []
    reachable_lost_all_routes = []
    reachable_lost_but_members_still_connected = []
    
    # for index i, the number of reachables that lost routes but still in IXP with same/worse/better AS path length is calculated by comparing the reachables and their providing members in stat i with the previous stat (i-1)
    all_counts_reachable_lost_routes_but_still_in_ixp_with_same_as_path_length: list[int] = []
    all_counts_reachable_lost_routes_but_still_in_ixp_with_worse_as_path_length: list[int] = []
    all_counts_reachable_lost_routes_but_still_in_ixp_with_better_as_path_length: list[int] = []
    
    # for index i, a map that tells us for map[i][n] the number of reachables that have a path length change of n (compared to previous stat) among the reachables that lost routes but still in IXP at index i 
    all_reachable_lost_routes_but_still_in_ixp_linked_to_path_length_change: list[
        dict
    ] = []

    all_counts_reachable_lost_all_members: list[int] = []
    all_counts_reachable_lost_but_members_still_connected: list[int] = []
    
    # Routes lost because members left the IXP
    all_counts_routes_lost_by_member_departure: list[int] = []
    # Routes lost but the member is still in the IXP
    all_counts_routes_lost_member_still_present: list[int] = []
    
    for i, stat in enumerate(all_stats[1:], 1):
        previous_stat: BGPDumpSnapshotStats = all_stats[i - 1]
        
        prev_map = previous_stat.get_all_reachables_to_members_map() 
        curr_map = stat.get_all_reachables_to_members_map()

        lost_routes_same_as_path_count = 0
        lost_routes_worse_as_path_count = 0
        lost_routes_better_as_path_count = 0
        lost_all_count = 0
        lost_but_members_still_connected_count = 0
        routes_lost_by_member_departure_count = 0
        routes_lost_member_still_present_count = 0
        path_length_changes: dict[int, int] = {}
        
        all_previously_reachable = previous_stat.unique_reachables
        
        for reachable in all_previously_reachable:
            prev_members = prev_map.get(reachable, set())
            if not prev_members:
                continue
                
            curr_members = curr_map.get(reachable, set())
            prev_count = len(prev_members)
            curr_count = len(curr_members)
            
            if curr_count < prev_count:
                if curr_count > 0:
                    # Get AS path lengths for previous and current members
                    prev_as_paths = []
                    curr_as_paths = []
                    
                    for member in prev_members:
                        member_reachables = previous_stat.mappings.get(str(member), [])
                        for reach_info in member_reachables:
                            if reach_info.get("reachable") == reachable:
                                as_path = reach_info.get("as_path", [])
                                # remove prepend
                                if should_remove_prepend and len(as_path) > 1:
                                    as_path = [asn for idx, asn in enumerate(as_path) if idx == 0 or asn != as_path[idx - 1]]
                                as_path_length = len(as_path) if as_path else 0
                                prev_as_paths.append(as_path_length)
                    
                    for member in curr_members:
                        member_reachables = stat.mappings.get(str(member), [])
                        for reach_info in member_reachables:
                            if reach_info.get("reachable") == reachable:
                                as_path = reach_info.get("as_path", [])
                                if should_remove_prepend and len(as_path) > 1:
                                    as_path = [asn for idx, asn in enumerate(as_path) if idx == 0 or asn != as_path[idx - 1]]
                                as_path_length = len(as_path) if as_path else 0
                                curr_as_paths.append(as_path_length)
                    
                    # Compare minimum AS path lengths
                    min_prev_as_path = min(prev_as_paths) if prev_as_paths else 0
                    min_curr_as_path = min(curr_as_paths) if curr_as_paths else 0
                    
                    # Calculate the change in AS path length
                    as_path_length_change =  min_prev_as_path - min_curr_as_path
                    path_length_changes[as_path_length_change] = path_length_changes.get(as_path_length_change, 0) + 1
                    # no change
                    if min_curr_as_path == min_prev_as_path:
                        lost_routes_same_as_path_count += 1
                        reachable_lost_routes_but_still_in_ixp_with_same_as_path_length.append(reachable)
                    # current as path is worse (longer) than previous
                    elif min_curr_as_path > min_prev_as_path:
                        lost_routes_worse_as_path_count += 1
                        reachable_lost_routes_but_still_in_ixp_with_worse_as_path_length.append(reachable)
                    # current as path is better (shorter) than previous
                    else:
                        lost_routes_better_as_path_count += 1
                        reachable_lost_routes_but_still_in_ixp_with_better_as_path_length.append(reachable)
                    # Routes were lost but reachable still has members (curr_count > 0)
                    routes_lost_member_still_present_count += 1
                else:  
                    # Reachable completely lost (curr_count == 0)
                    # Check if at least one member that provided access is still a member
                    at_least_one_member_still_connected = any(int(member) in stat.unique_members for member in prev_members)
                    if at_least_one_member_still_connected:
                        lost_but_members_still_connected_count += 1
                        routes_lost_member_still_present_count += 1
                        reachable_lost_but_members_still_connected.append(reachable)
                    else:
                        # All members were lost, so this reachable lost all routes from members
                        lost_all_count += 1
                        routes_lost_by_member_departure_count += 1
                        reachable_lost_all_routes.append(reachable)

        all_reachable_lost_routes_but_still_in_ixp_linked_to_path_length_change.append(path_length_changes)

        all_counts_reachable_lost_routes_but_still_in_ixp_with_same_as_path_length.append(lost_routes_same_as_path_count)
        all_counts_reachable_lost_routes_but_still_in_ixp_with_worse_as_path_length.append(lost_routes_worse_as_path_count)
        all_counts_reachable_lost_routes_but_still_in_ixp_with_better_as_path_length.append(lost_routes_better_as_path_count)
        all_counts_reachable_lost_all_members.append(lost_all_count)
        all_counts_reachable_lost_but_members_still_connected.append(lost_but_members_still_connected_count)
        all_counts_routes_lost_by_member_departure.append(routes_lost_by_member_departure_count)
        all_counts_routes_lost_member_still_present.append(routes_lost_member_still_present_count)
    
    start_date = datetime.strptime(config["start_date"], "%Y-%m-%d")
    end_date = datetime.strptime(config["end_date"], "%Y-%m-%d")

    total_route_loss_map = {}
    for map in all_reachable_lost_routes_but_still_in_ixp_linked_to_path_length_change:
        for change, count in map.items():
            total_route_loss_map[change] = total_route_loss_map.get(change, 0) + count
    
    if 0 in total_route_loss_map:
        del total_route_loss_map[0]


    title_start = title_start + " (Prepend filtered)" if should_remove_prepend else " (With prepend)"

    plot_map_as_bar_plot(total_route_loss_map, title=f"Total Route Loss by AS Path Length Change - {get_ip_version(config)} - {get_date_range_title(start_date, end_date)}", xlabel="AS Path Length Change", ylabel="Count of Reachable ASes", subfolder=subfolder )
     
     
    plot_list_as_bar_plot(
        ["Still in IXP (Same AS Path Length)", 
                         "Still in IXP (Worse AS Path Length)",
                         "Still in IXP (Better AS Path Length)",
                         "Lost (Members Still Connected)",
                         "Lost All Routes from Members"],
                       y= 
        [sum(all_counts_reachable_lost_routes_but_still_in_ixp_with_same_as_path_length), 
                           sum(all_counts_reachable_lost_routes_but_still_in_ixp_with_worse_as_path_length),
                           sum(all_counts_reachable_lost_routes_but_still_in_ixp_with_better_as_path_length),
                           sum(all_counts_reachable_lost_but_members_still_connected),
                           sum(all_counts_reachable_lost_all_members)], 
                        title=title_start + f"Count of Reachable ASes that Lost Routes - {get_ip_version(config)} - {get_date_range_title(start_date, end_date)}", 
                        xlabel="Date",  
                        ylabel="Count of Reachable ASes", subfolder=subfolder, max_labels=max_labels)
    plot_list_as_bar_plot(
        [
            "Still in IXP (Same AS Path Length)", 
                         "Still in IXP (Worse AS Path Length)",
                         "Still in IXP (Better AS Path Length)",
        ],
        [sum(all_counts_reachable_lost_routes_but_still_in_ixp_with_same_as_path_length),
         sum(all_counts_reachable_lost_routes_but_still_in_ixp_with_worse_as_path_length),
         sum(all_counts_reachable_lost_routes_but_still_in_ixp_with_better_as_path_length)],
         title=title_start+f"Count of Reachable ASes that Lost Routes but Still in IXP with Different AS Path Lengths - {get_ip_version(config)} - {get_date_range_title(start_date, end_date)}",
            xlabel="Date",
            ylabel="Count of Reachable ASes", subfolder=subfolder, max_labels=max_labels,
            use_colors=True,
            use_rotated_labels=False
    )
    plot_list_as_bar_plot(
         [
            "Still in IXP (Same AS Path Length)", 
                         "Still in IXP (Worse AS Path Length)",
                         "Still in IXP (Better AS Path Length)",
        ],
         [
            sum(set(all_counts_reachable_lost_routes_but_still_in_ixp_with_same_as_path_length)),
         sum(set(all_counts_reachable_lost_routes_but_still_in_ixp_with_worse_as_path_length)),
         sum(set(all_counts_reachable_lost_routes_but_still_in_ixp_with_better_as_path_length))
         ],
         title=title_start+f"Count of Unique Reachable ASes that Lost Routes but Still in IXP with Different AS Path Lengths - {get_ip_version(config)} - {get_date_range_title(start_date, end_date)}",
            xlabel="Date",
            ylabel="Count of Reachable ASes", subfolder=subfolder, max_labels=max_labels,
            use_colors=True,
            use_rotated_labels=False
    )
    plot_stacked_line_plot([all_counts_reachable_lost_routes_but_still_in_ixp_with_same_as_path_length, 
                           all_counts_reachable_lost_routes_but_still_in_ixp_with_worse_as_path_length,
                           all_counts_reachable_lost_routes_but_still_in_ixp_with_better_as_path_length,
                           all_counts_reachable_lost_but_members_still_connected,
                           all_counts_reachable_lost_all_members],
                        ["Still in IXP (Has another with Same AS Path Length)", 
                         "Still in IXP (Has another with Worse AS Path Length)",
                         "Still in IXP (Has another with Better AS Path Length)",
                         "Lost (Members Still Connected)",
                         "Lost All Routes from Members"],
                        x_labels=labels_summarized[1:], 
                        title=title_start + f"Reachable ASes that Lost Routes over Time - {get_ip_version(config)} - {get_date_range_title(start_date, end_date)}", 
                        xlabel="Date", 
                        ylabel="Count of Reachable ASes", subfolder=subfolder,  max_labels=max_labels)
    plot_stacked_line_plot(
        [all_counts_reachable_lost_routes_but_still_in_ixp_with_same_as_path_length, 
         all_counts_reachable_lost_routes_but_still_in_ixp_with_worse_as_path_length,
         all_counts_reachable_lost_routes_but_still_in_ixp_with_better_as_path_length],
        ["Still in IXP (Has another with Same AS Path Length)", 
         "Still in IXP (Has another with Worse AS Path Length)",
         "Still in IXP (Has another with Better AS Path Length)"],
        x_labels=labels_summarized[1:],
        title=title_start + f"Reachable ASes that Lost Routes but Still in IXP with Different AS Path Lengths - {get_ip_version(config)} - {get_date_range_title(start_date, end_date)}", 
        xlabel="Date", 
        ylabel="Count of Reachable ASes", subfolder=subfolder,  max_labels=max_labels
    )
    plot_stacked_line_plot(
        [all_counts_reachable_lost_but_members_still_connected, all_counts_reachable_lost_all_members],
        ["Lost Reachable (Members Still Connected)", "Lost all Members"],
        x_labels=labels_summarized[1:],
        title=title_start + f"Reachable ASes that Lost Routes - Lost but Members Still Connected vs Lost All Routes - {get_ip_version(config)} - {get_date_range_title(start_date, end_date)}", 
        xlabel="Date", 
        ylabel="Count of Reachable ASes", subfolder=subfolder,  max_labels=max_labels
    )

    plot_stacked_line_plot(
        [
            all_counts_routes_lost_by_member_departure,
            all_counts_routes_lost_member_still_present
        ],
        [
            "Routes lost by member departure",
            "Routes lost but member still present"
        ],
        x_labels=labels_summarized[1:],
        title=title_start + f"Routes Lost by Member Departure vs Routes Lost but Member Still Present - {get_ip_version(config)} - {get_date_range_title(start_date, end_date)}",
        xlabel="Date",
        ylabel="Count of Routes Lost", subfolder=subfolder, max_labels=max_labels
    )

    print(f"\n--- Reachables that Lost Routes ---")
    print(f"Reachable ASes that lost routes but still have other members (same AS path length): {len(reachable_lost_routes_but_still_in_ixp_with_same_as_path_length)}")
    print(f"Reachable ASes that lost routes but still have other members (worse AS path length): {len(reachable_lost_routes_but_still_in_ixp_with_worse_as_path_length)}")
    print(f"Reachable ASes that lost routes but still have other members (better AS path length): {len(reachable_lost_routes_but_still_in_ixp_with_better_as_path_length)}")
    print(f"Reachable ASes that were lost but members they were connected to are still members: {len(reachable_lost_but_members_still_connected)}")
    print(f"Reachable ASes that lost all routes from members: {len(reachable_lost_all_routes)}")


def calculate_average_mappings_per_reachable(all_stats):
    """Calculate the average number of member connections per reachable AS."""
    count_of_mappings_per_reachable = []
    number_of_needed_samples = min(2, len(all_stats) - 1)
    for stat in all_stats[:number_of_needed_samples]:
        reachables = stat.unique_reachables
        for reachable in reachables:
            related_members = stat.get_all_members_that_allow_asn_to_be_reachable(reachable)
            count = len(related_members)
            count_of_mappings_per_reachable.append(count)
    average_mappings_per_reachable = sum(count_of_mappings_per_reachable) / len(count_of_mappings_per_reachable) if count_of_mappings_per_reachable else 0
    print(f"(samples used: {number_of_needed_samples})")
    print(f"Average number of member connections per reachable AS: {average_mappings_per_reachable:.2f}")
    print(f"Unique number of member connections per reachable AS: {sorted(set(count_of_mappings_per_reachable))}")


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



class ReachableOscillationCameBackMetrics:
    def __init__(self, came_back_with_same_members, came_back_with_different_members, came_back_with_only_new_members):
        self.came_back_with_same_members: ReachableLeftAndCameBackASPathInfo  = came_back_with_same_members
        self.came_back_with_different_members: ReachableLeftAndCameBackASPathInfo = came_back_with_different_members
        self.came_back_with_only_new_members: ReachableLeftAndCameBackASPathInfo = came_back_with_only_new_members

    def summed_same_members(self):
        same_members_same_as_path = self.came_back_with_same_members.came_back_with_same_length
        same_members_better_as_path = self.came_back_with_same_members.came_back_with_better_length
        same_members_worse_as_path = self.came_back_with_same_members.came_back_with_worse_length
        return len(same_members_same_as_path) + len(same_members_better_as_path) + len(same_members_worse_as_path)  

    def summed_different_members(self):
        different_members_same_as_path = self.came_back_with_different_members.came_back_with_same_length
        different_members_better_as_path = self.came_back_with_different_members.came_back_with_better_length
        different_members_worse_as_path = self.came_back_with_different_members.came_back_with_worse_length
        return len(different_members_same_as_path) + len(different_members_better_as_path) + len(different_members_worse_as_path)
    
    def summed_only_new_members(self):
        only_new_members_same_as_path = self.came_back_with_only_new_members.came_back_with_same_length
        only_new_members_better_as_path = self.came_back_with_only_new_members.came_back_with_better_length
        only_new_members_worse_as_path = self.came_back_with_only_new_members.came_back_with_worse_length
        return len(only_new_members_same_as_path) + len(only_new_members_better_as_path) + len(only_new_members_worse_as_path)

    def get_all_came_back_categories(self):
        return [
            self.came_back_with_same_members,
            self.came_back_with_different_members,
            self.came_back_with_only_new_members
        ]

    def print_and_plot(self, title_start, title_end, subfolder):

        
        plot_list_as_bar_plot(
           [
                "Same Members",
                "Different Members",
                "Only New Members"
            ] ,
            y=[
                self.summed_same_members(), 
                self.summed_different_members(),
                self.summed_only_new_members()
            ],
            title=title_start + "Count of Oscillating Reachable ASes - By how they came back" + title_end,
            subfolder=subfolder
        )
        all_categories = self.get_all_came_back_categories()

        total_net = 0
        for category in all_categories:
            total_net += category.get_net_as_path_length_change_counts()
            category.print_came_back_categories()
            category.plot_came_back_categories(title_start=title_start, title_end=title_end, subfolder=subfolder)
            category.plot_came_back_length_changes(title_start=title_start, title_end=title_end, subfolder=subfolder)
            print("---") 
        print("Total from all categories")
        print(f"Net AS path length change: {total_net}")



class ReachableLeftAndCameBackASPathInfo:
    def __init__(self,
                  category_name,
                  came_back_linked_to_path_length_change,
                  came_back_with_same_path,
                  came_back_with_same_length, came_back_with_better_length, came_back_with_worse_length):
        
        self.category_name = category_name
        self.came_back_linked_to_path_length_change = came_back_linked_to_path_length_change
        self.came_back_with_same_length = came_back_with_same_length
        self.came_back_with_same_path = came_back_with_same_path
        self.came_back_with_better_length = came_back_with_better_length
        self.came_back_with_worse_length = came_back_with_worse_length
    
    def get_net_as_path_length_change_counts(self):
        change_counts = 0
        for item in self.came_back_linked_to_path_length_change:
            change = item["change"]

            change_counts += change
        return change_counts

    def print_came_back_categories(self):
    
        total = len(self.came_back_with_same_length) + len(self.came_back_with_better_length) + len(self.came_back_with_worse_length)
        print(f"\n--- {self.category_name} ---")
        print(f"Total: {total}")
        print(f"with same AS path length: {len(self.came_back_with_same_length)}")
        print(f"with same AS path: {len(self.came_back_with_same_path)}")
        print(f"with better AS path length: {len(self.came_back_with_better_length)}")
        print(f"with worse AS path length: {len(self.came_back_with_worse_length)}")
        print(f"Net AS path length change (sum of all changes): {self.get_net_as_path_length_change_counts()}")
 
    def plot_came_back_categories(self, title_start, title_end, subfolder):
        plot_list_as_bar_plot(
            ["Same AS Path Length", "Better AS Path Length", "Worse AS Path Length"],
            [len(self.came_back_with_same_length), len(self.came_back_with_better_length), len(self.came_back_with_worse_length)],
            title=title_start + "AS Path Length Categories for Reachables that Left and Came Back with " + self.category_name + title_end,
            xlabel="AS Path Length Change Category",
            ylabel="Count of Reachables",
            subfolder=subfolder
        ) 

    def plot_came_back_length_changes(self, title_start, title_end, subfolder):

        length_changes = {}

        for item in self.came_back_linked_to_path_length_change:
            change = item["change"]
            if change not in length_changes:
                length_changes[change] = 0
            length_changes[change] += 1

        plot_map_as_bar_plot(
            length_changes,
            title=title_start + "AS Path Length Changes (Shortest Path) for Oscillating Reachables with " + self.category_name + title_end,
            ylabel="Count of Reachables", 
            xlabel="Path-Length Change (Previous - Current, n>0 is better)", 
            use_colors=True,
            subfolder=subfolder
        )

def get_came_back_through_count_categories(category_name, matched_reachables) -> ReachableLeftAndCameBackASPathInfo:

    came_back_with_same_length: list = []
    came_back_with_same_path: list = []
    came_back_with_better_length: list = []
    came_back_with_worse_length: list = []
    came_back_linked_to_path_length_change: list = []
    
    for r in matched_reachables:
        previous_shortest_path_length = r.get("previous_shortest_path_length")
        current_shortest_path_length = r.get("current_shortest_path_length")
        if previous_shortest_path_length is not None and current_shortest_path_length is not None:
            if current_shortest_path_length == previous_shortest_path_length:
                came_back_with_same_length.append(r)
                if r["previous_shortest_path"] == r["current_shortest_path"]:
                    came_back_with_same_path.append(r) 
                continue
            came_back_linked_to_path_length_change.append(
                {
                    "reachable": r,
                    "previous_shortest_path_length": previous_shortest_path_length,
                    "current_shortest_path_length": current_shortest_path_length,
                    "change": previous_shortest_path_length - current_shortest_path_length,
                    "previous_shortest_path": r.get("previous_shortest_path"),
                    "current_shortest_path": r.get("current_shortest_path")
                }
            )
            if current_shortest_path_length < previous_shortest_path_length:
                came_back_with_better_length.append(r)
            else:
                came_back_with_worse_length.append(r)
    result = ReachableLeftAndCameBackASPathInfo(
        category_name=category_name,
        came_back_linked_to_path_length_change=came_back_linked_to_path_length_change,
        came_back_with_same_length=came_back_with_same_length,
        came_back_with_better_length=came_back_with_better_length,
        came_back_with_worse_length=came_back_with_worse_length,
        came_back_with_same_path=came_back_with_same_path
    )
    return result
    #return came_back_with_same_length, came_back_with_better_length, came_back_with_worse_length



def get_came_back_metrics_from_reachables_that_left_and_came_back(reachable_oscillation_metrics, all_stats, remove_prepend=True) -> dict:
    reachables_left_and_came_back = {}
     
    for reachable_asn, osc_info in reachable_oscillation_metrics.oscillation_info.items():
        start_idx = osc_info.get("start_idx")
        end_idx = osc_info.get("end_idx")
        
        if start_idx is None or end_idx is None:
            continue
 
        prev_idx = max(0, start_idx - 1)
        previous_stat = all_stats[prev_idx]
        current_stat = all_stats[end_idx]
         
        prev_m = previous_stat.get_all_members_that_allow_asn_to_be_reachable(reachable_asn)
        curr_m = current_stat.get_all_members_that_allow_asn_to_be_reachable(reachable_asn)
        
        if not prev_m: 
            continue 
        reachables_left_and_came_back[reachable_asn] = { 
            "lost_members": prev_m - curr_m,
            "new_members": curr_m - prev_m,
            "still_members": prev_m & curr_m,
            "oscillations": osc_info["oscillations"],
            "previous_shortest_path_length": previous_stat.get_shortest_as_path_length_for_reachable(reachable_asn, remove_prepend)[0],
            "current_shortest_path_length": current_stat.get_shortest_as_path_length_for_reachable(reachable_asn, remove_prepend)[0],
            "current_shortest_path": current_stat.get_shortest_as_path_length_for_reachable(reachable_asn, remove_prepend)[1],
            "previous_shortest_path": previous_stat.get_shortest_as_path_length_for_reachable(reachable_asn, remove_prepend)[1]
        }

    return reachables_left_and_came_back


def calculate_reachables_oscillation_came_back_info(all_stats: list[BGPDumpSnapshotStats], title_start: str, title_end: str, subfolder: str) -> ReachableOscillationCameBackMetrics:
    """Analyze reachables that left and came back, tracking member changes during oscillation."""
    # Use the existing oscillation logic for reachables
    reachable_oscillation_metrics = calculate_oscillation_metrics(all_stats, use_reachables=True )
    
    print(f"Total reachables that oscillated (left and came back): {len(reachable_oscillation_metrics.oscillation_info)}")

    reachables_left_and_came_back = get_came_back_metrics_from_reachables_that_left_and_came_back(reachable_oscillation_metrics, all_stats,
    remove_prepend=True)

    came_back_through_any_members = get_came_back_through_count_categories(
        "Any Members",
        [r for r in reachables_left_and_came_back.values()]
    )

    came_back_through_any_members.plot_came_back_length_changes(title_start=title_start, title_end=title_end, subfolder=subfolder)
    came_back_through_any_members.print_came_back_categories()

    came_back_through_only_same_members = get_came_back_through_count_categories(
        "Only Same Members",
        [r for r in reachables_left_and_came_back.values() 
        # no changes in members detected
        if not r["new_members"] and r["still_members"] and not r["lost_members"]]
    )

    came_back_through_different_members = get_came_back_through_count_categories(
        "Different Members",
        [r for r in reachables_left_and_came_back.values() 
        # any change in members detected (either lost or new members)                                    
        if r["new_members"] or r["lost_members"]]
    )

    came_back_through_only_new_members = get_came_back_through_count_categories(
        "Only New Members",
        [r for r in reachables_left_and_came_back.values()
        # only new members providing access, all previous members lost                                      
        if r["new_members"] and not r["still_members"]]
    )

    
    
    all_metrics = ReachableOscillationCameBackMetrics( 
        came_back_with_same_members=came_back_through_only_same_members,
        came_back_with_different_members=came_back_through_different_members,
        came_back_with_only_new_members=came_back_through_only_new_members
    )

    print(f"\n--- Reachables that Left and Came Back ---") 
    
    all_metrics.print_and_plot(title_start=title_start,title_end=title_end, subfolder=subfolder)

    return all_metrics

def calculate_routes_oscillation_info(all_stats: list[BGPDumpSnapshotStats], title_start: str, title_end: str, subfolder: str):

    """Analyze routes that were lost and came back, tracking AS path length changes during oscillation."""
    route_oscillation_metrics = calculate_oscillation_metrics(all_stats, use_reachables=False, calculate_routes=True)
 
    bar = Bar(max=len(route_oscillation_metrics.route_oscillation_info))
    oscillations_start_over_time = [0 for _ in range(len(route_oscillation_metrics.route_oscillation_info))]


    for osc_info in route_oscillation_metrics.route_oscillation_info:
        bar.next()
        start_id = osc_info.get("start_idx")
            
        if start_id is not None and 0 <= start_id < len(oscillations_start_over_time):
            oscillations_start_over_time[start_id] += 1
        else:
            raise ValueError(f"Invalid start_idx {start_id} in oscillation info: {osc_info}")
    
    bar.finish()

    plot_list_as_line_plot(
        [i for i in range(len(route_oscillation_metrics.route_oscillation_info))],
        y=oscillations_start_over_time,
        title=title_start + "Count of Oscillating Routes Start oscillation" + title_end,
        xlabel="Date",
        ylabel="Count of Routes",
        subfolder=subfolder,
        max_labels=30
    ) 


def bview_reachable_metrics():
    config = load_configs("ixbr.json")
    
    title_start = get_title_start(config) 
    title_end = get_title_end(config)
    ip_version = get_ip_version(config)
    
    print_config(config, ip_version=ip_version)
    subfolder = get_subfolder(config, ip_version) + "/reachable_metrics/"

    all_stats, labels = load_bview_data_timeline_from_configs(config, ip_version=ip_version)     

    labels_summarized, max_labels = get_labels_info(labels)

    metrics = calculate_oscillation_metrics(all_stats) 

    metrics.load_oscillating_lists()
     
    start_date = datetime.strptime(config["start_date"], "%Y-%m-%d")
    end_date = datetime.strptime(config["end_date"], "%Y-%m-%d")
    day_delta = timedelta(days=config.get("day_delta", 7)) 
        

    need_to_check_reachable_depeering_categories = True
    need_to_calculate_oscillating_reachables = False 
    need_to_calculate_oscillating_routes = False
    need_to_calculate_average_number_of_reachables_a_member_gives_access_to = False
    need_to_calculate_other_members_of_reachable_from_reachables_whose_member_left = False
    need_to_calculate_average_mappings_count__per_reachable = False

    # Analyze reachables that lost routes in two categories
    if need_to_check_reachable_depeering_categories:        
        # categories: 
        # 1) lost routes but still in IXP with same AS path length, 
        # 2) lost routes but still in IXP with worse AS path length, 
        # 3) lost routes but still in IXP with better AS path length, 
        # 4) lost but members still connected, 
        # 5) lost all routes from members
        check_reachable_lost_routes_categories(all_stats, labels_summarized, config, title_start,title_end, subfolder, max_labels)

    # Calculate average number of member connections per reachable AS
    if need_to_calculate_average_mappings_count__per_reachable:
        calculate_average_mappings_per_reachable(all_stats)
    
    print("Finished all plotting for dates from {} to {} with interval of {} days.".format(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), day_delta.days))

    # Analyze other members providing access when a member leaves
    if need_to_calculate_other_members_of_reachable_from_reachables_whose_member_left:
        calculate_other_members_when_member_leaves(all_stats)

    # Calculate average number of reachable ASes per member
    if need_to_calculate_average_number_of_reachables_a_member_gives_access_to:
        calculate_average_reachables_per_member(all_stats)

    # Analyze reachables that oscillated (left and came back)
    if need_to_calculate_oscillating_reachables:
        calculate_reachables_oscillation_came_back_info(all_stats, title_start, title_end, subfolder)

    if need_to_calculate_oscillating_routes:
        calculate_routes_oscillation_info(all_stats, title_start, title_end, subfolder)

if __name__ == "__main__":
    bview_reachable_metrics()
    create_window_with_all_rendered_graphs_this_session()