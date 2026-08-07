from itertools import groupby
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.ripe_bviews.read_bgpdump import BGPDumpSnapshotStats
from src.utils.graphs import plot_list_as_bar_plot, plot_list_as_line_plot, plot_stacked_line_plot
from src.ripe_bviews.timeline.bview_vars import get_annotations


def calculate_shortest_path_average_over_time(all_stats: list[BGPDumpSnapshotStats], 
                                              deduplicate_prepended_asns=True) -> list[float]:
    """Calculate the average shortest path length for arriving at each reachable for each day."""
    shortest_path_averages = []
    
    for stat in all_stats:
        # Dictionary to store the minimum length found so far for each reachable ASN
        # e.g., { "ASN123": 3, "ASN456": 2 }
        min_lengths_per_reachable = {}
        
        # 1. Single pass over the data to build the minimums
        # If 'mappings' is structured by member, we iterate through members and their mappings
        for member, mappings_list in stat.mappings.items():
            for mapping in mappings_list:
                reachable = mapping["reachable"]
                as_path = mapping["as_path"]
                
                # Calculate path length (handling prepending)
                as_path_length = len(as_path)
                if as_path_length > 1:
                    # Deduplicate consecutive prepended ASNs
                    if deduplicate_prepended_asns:
                        as_path_length = len([
                            asn for idx, asn in enumerate(as_path) 
                            if idx == 0 or asn != as_path[idx - 1]
                        ])
                
                # Keep the minimum length for this specific reachable
                if reachable not in min_lengths_per_reachable or as_path_length < min_lengths_per_reachable[reachable]:
                    min_lengths_per_reachable[reachable] = as_path_length
        
        # 2. Filter down to only the reachables that are actually in `stat.unique_reachables`
        # (Assuming unique_reachables might be a subset, otherwise you can just use min_lengths_per_reachable.values())
        shortest_path_lengths = [
            min_lengths_per_reachable[r] 
            for r in stat.unique_reachables 
            if r in min_lengths_per_reachable
        ]
        
        # 3. Calculate average for this day
        if shortest_path_lengths:
            average = sum(shortest_path_lengths) / len(shortest_path_lengths)
        else:
            average = 0
        shortest_path_averages.append(average)
    
    return shortest_path_averages

def _get_min_path_lengths(stat: BGPDumpSnapshotStats) -> dict[str, int]:
    """Helper to compute the shortest path length for all reachables in a single pass."""
    min_lengths = {}
    for member, mappings_list in stat.mappings.items():
        for mapping in mappings_list:
            reachable = mapping["reachable"]
            as_path = mapping["as_path"]
            
            # Compute path length with prepend removal
            as_path_length = len(as_path)
            if as_path_length > 1:
                as_path_length = sum(1 for _ in groupby(as_path)) 
            
            if reachable not in min_lengths or as_path_length < min_lengths[reachable]:
                min_lengths[reachable] = as_path_length
    return min_lengths


def calculate_average_path_length(stat: BGPDumpSnapshotStats, for_asn: str=None):

    sum = 0
    count = 0
    
    asns_to_consider = stat.mappings.keys()

    if for_asn: 
        if for_asn not in asns_to_consider:
            return -1 # AS doesnt exist in mappings...
        asns_to_consider = [for_asn]
        
    for member in asns_to_consider:
        paths = stat.mappings[member]

        for path in paths:
            count += 1
            sum += len(path["as_path"])

    return sum / count if count != 0 else -1

def calculate_routes_lost_that_made_shortest_path_worse(all_stats: list[BGPDumpSnapshotStats]):
    """
    Calculate routes lost that made the shortest path worse.
    Only considers lost routes for existing reachables that make the path longer.
    """
    if not all_stats:
        return []

    total_losses_that_made_shortest_path_worse_per_snapshot = []
    
    # Precompute shortest paths for the very first snapshot
    # Maps: reachable -> shortest_path_length
    prev_lengths = _get_min_path_lengths(all_stats[0])
    
    for i in range(1, len(all_stats)):
        losses_that_made_shortest_path_worse = 0
        
        # 1. Compute shortest paths for the current snapshot in O(K) time
        current_lengths = _get_min_path_lengths(all_stats[i])
        
        # 2. Compare the two snapshots using O(1) dictionary lookups
        # We only care about reachables that still exist in the current snapshot
        for reachable, current_shortest in current_lengths.items():
            if reachable in prev_lengths:
                prev_shortest = prev_lengths[reachable]
                
                # If the path became longer, a crucial route was lost
                if current_shortest > prev_shortest:
                    losses_that_made_shortest_path_worse += 1
                    
        total_losses_that_made_shortest_path_worse_per_snapshot.append(losses_that_made_shortest_path_worse)
        
        # Move forward: current snapshot becomes the previous snapshot for the next iteration
        prev_lengths = current_lengths
        
    return total_losses_that_made_shortest_path_worse_per_snapshot

def plot_shortest_path_average_over_time(all_stats, labels_summarized, title_start, title_end, subfolder, max_labels):
    """Plot the average shortest path length over time."""
    shortest_path_average_over_time = calculate_shortest_path_average_over_time(all_stats)
    plot_list_as_line_plot(
        shortest_path_average_over_time, 
        labels_summarized, 
        title=f'{title_start} Route Shortest Path Average Over Time {title_end}', 
        xlabel='Time', 
        ylabel='Average Shortest Path Length', 
        subfolder=subfolder,
        max_labels=max_labels, 
        annotations=get_annotations()
    )


def calculate_routes_added_that_improved_shortest_path(all_stats: list[BGPDumpSnapshotStats]):
    """
    Calculate routes added that improved the shortest path to reachables.
    Only considers new routes to already-existing reachables that shorten the path.
    """
    if not all_stats:
        return []

    routes_added_that_improved_shortest_path_per_snapshot = []
    
    # Precompute the shortest paths for the very first snapshot
    prev_lengths = _get_min_path_lengths(all_stats[0])
    
    for i in range(1, len(all_stats)):
        routes_added_that_improved_shortest_path = 0
        
        # 1. Compute shortest paths for the current snapshot in O(K) time
        current_lengths = _get_min_path_lengths(all_stats[i])
        
        # 2. Compare the two snapshots using O(1) dictionary lookups
        # We only look at reachables that existed in the previous snapshot
        for reachable, current_shortest in current_lengths.items():
            if reachable in prev_lengths:
                prev_shortest = prev_lengths[reachable]
                
                # If the path became shorter, it means an improving route was added
                if current_shortest < prev_shortest:
                    routes_added_that_improved_shortest_path += 1
                    
        routes_added_that_improved_shortest_path_per_snapshot.append(routes_added_that_improved_shortest_path)
        
        # Move forward: current snapshot becomes the previous snapshot for the next iteration
        prev_lengths = current_lengths
        
    return routes_added_that_improved_shortest_path_per_snapshot




def plot_routes_added_that_improved_shortest_path(all_stats, labels_summarized, name, ip_version, subfolder, max_labels):
    """Plot routes added that improved the shortest path."""
    routes_added_that_improved_shortest_path_per_snapshot = calculate_routes_added_that_improved_shortest_path(all_stats)
    plot_list_as_line_plot(
        routes_added_that_improved_shortest_path_per_snapshot,
        labels_summarized[1:],
        title=f'Routes Added That Improved Shortest Path - {name} - IP{ip_version}',
        xlabel='Time',
        ylabel='Number of Routes Added That Improved Shortest Path',
        subfolder=subfolder,
        max_labels=max_labels,
        annotations=get_annotations()
    )
    return routes_added_that_improved_shortest_path_per_snapshot


def plot_routes_lost_that_made_shortest_path_worse(all_stats, labels_summarized, name, ip_version, subfolder, max_labels):
    """Plot routes lost that made the shortest path worse."""
    total_losses_that_made_shortest_path_worse_per_snapshot = calculate_routes_lost_that_made_shortest_path_worse(all_stats)
    plot_list_as_line_plot(
        total_losses_that_made_shortest_path_worse_per_snapshot,
        labels_summarized[1:],
        title=f'Number of Routes Lost That Made Shortest Path Longer - {name} - IP{ip_version}',
        xlabel='Time',
        ylabel='Number of Routes Lost That Made Shortest Path Longer',
        subfolder=subfolder,
        max_labels=max_labels,
        annotations=get_annotations()
    )
    return total_losses_that_made_shortest_path_worse_per_snapshot


def plot_route_changes_and_shortest_path_delta_over_time(all_stats, labels_summarized, name, ip_version, subfolder, max_labels,
                                                         total_losses_that_made_shortest_path_worse_per_snapshot=None, routes_added_that_improved_shortest_path_per_snapshot=None
                                                         ):
    """Plot routes added that improved the shortest path and routes lost that made the shortest path worse in a single plot."""
    
    if routes_added_that_improved_shortest_path_per_snapshot is None:
        routes_added_that_improved_shortest_path_per_snapshot = calculate_routes_added_that_improved_shortest_path(all_stats)
    if total_losses_that_made_shortest_path_worse_per_snapshot is None:
        total_losses_that_made_shortest_path_worse_per_snapshot = calculate_routes_lost_that_made_shortest_path_worse(all_stats)
    
    total_changes = []

    for added, lost in zip(routes_added_that_improved_shortest_path_per_snapshot, total_losses_that_made_shortest_path_worse_per_snapshot):
        total_changes.append(added - lost)
    
    plot_list_as_line_plot(
        total_changes,
        labels_summarized[1:],
        title=f'Net Route Changes That Improved Shortest Path (Added - Lost) - {name} - IP{ip_version}',
        xlabel='Time',
        ylabel='Net Number of Route Changes That Improved Shortest Path',
        subfolder=subfolder,
        max_labels=max_labels, 
    )

    percentage_of_improvements_that_made_paths_better_in_comparison_to_total = 0

    total_improvements = sum(routes_added_that_improved_shortest_path_per_snapshot)
    total_worsenings = sum(total_losses_that_made_shortest_path_worse_per_snapshot)
    if total_improvements + total_worsenings > 0:
        percentage_of_improvements_that_made_paths_better_in_comparison_to_total = (total_improvements / (total_improvements + total_worsenings)) * 100
    print(f"Total routes added that improved shortest path: {total_improvements}")
    print(f"Total routes lost that made shortest path worse: {total_worsenings}")
    print(f"Percentage of improvements that made paths better in comparison to total: {percentage_of_improvements_that_made_paths_better_in_comparison_to_total:.2f}%")
    plot_stacked_line_plot(
        [routes_added_that_improved_shortest_path_per_snapshot, total_losses_that_made_shortest_path_worse_per_snapshot],
        ["Routes Added That Improved Shortest Path", "Routes Lost That Made Shortest Path Longer"],
        title=f'Route Changes That Improved or Worsened Shortest Path - {name} - IP{ip_version}',
        xlabel='Time',
        ylabel='Number of Route Changes',
        subfolder=subfolder,
        max_labels=max_labels,
        annotations=get_annotations(),
        x_labels=labels_summarized[1:]
    )

if __name__ == "__main__":
    print("This module is not meant to be run directly. Please run the timeline script instead.")