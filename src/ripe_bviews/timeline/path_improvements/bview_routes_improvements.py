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

def calculate_routes_added_that_improved_shortest_path_optimized(all_stats: list[BGPDumpSnapshotStats]):
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

def calculate_routes_lost_that_made_shortest_path_worse(all_stats: list[BGPDumpSnapshotStats]):
    """
    Calculate routes lost that made the shortest path worse.
    Only considers lost routes for existing members/reachables that make the path longer.
    """
    total_losses_that_made_shortest_path_worse_per_snapshot = []
    
    for i in range(1, len(all_stats)):
        lost_mappings_with_no_removed_members_or_reachables = []
        
        for mapping in all_stats[i-1].mappings.keys():
            # mapping was removed in index i, that means the member doesn't exist anymore
            # this doesn't count to our metric 
            if mapping not in all_stats[i].mappings:
                continue
            # member still exists, but might have lost reachables
            # we need to find reachables that were lost for this member, but that still exist now (because of other connections)
            else:
                # reachables that used to exist for this member, but don't anymore
                # ex: [1,2,3] -> [2,4] would give us {1,3} as lost reachables for this member
                lost_reachables_for_member = {r["reachable"] for r in all_stats[i-1].mappings[mapping]} - {r["reachable"] for r in all_stats[i].mappings[mapping]}
                if lost_reachables_for_member:
                    # reachables lost for this member that still exist in the new stat (because of other members)
                    # ex: lost {1,3} but (1 in i unique_reachables), then getting the "&" results in {1}
                    reachables_lost_that_still_exist = lost_reachables_for_member & all_stats[i].unique_reachables
                    if reachables_lost_that_still_exist:
                        lost_mappings_with_no_removed_members_or_reachables.append({mapping: reachables_lost_that_still_exist})
        
        unique_reachables_lost_that_still_exist = set()
        for mapping in lost_mappings_with_no_removed_members_or_reachables:
            reachables = list(mapping.values())[0]
            unique_reachables_lost_that_still_exist.update(reachables)
        
        reachable_shortest_paths_before = [all_stats[i-1].get_shortest_as_path_length_for_reachable(reachable) for reachable in unique_reachables_lost_that_still_exist]
        reachable_shortest_paths_after = [all_stats[i].get_shortest_as_path_length_for_reachable(reachable) for reachable in unique_reachables_lost_that_still_exist]
        losses_that_made_shortest_path_worse = 0
        for before, after in zip(reachable_shortest_paths_before, reachable_shortest_paths_after):
            if before is not None and after is not None and after[0] > before[0]: # if the shortest path length for this reachable got worse after the loss, that means this loss had an impact on the shortest path, even if it didn't remove the reachable from the graph
                losses_that_made_shortest_path_worse += 1
        
        total_losses_that_made_shortest_path_worse_per_snapshot.append(losses_that_made_shortest_path_worse)
    
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


if __name__ == "__main__":
    print("This module is not meant to be run directly. Please run the timeline script instead.")