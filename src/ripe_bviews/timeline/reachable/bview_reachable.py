

from src.ripe_bviews.oscillations.bview_oscillation_logic import calculate_oscillation_metrics 
from src.ripe_bviews.read_bgpdump import BGPDumpSnapshotStats
from src.utils.graphs import plot_list_as_bar_plot, plot_map_as_bar_plot




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
