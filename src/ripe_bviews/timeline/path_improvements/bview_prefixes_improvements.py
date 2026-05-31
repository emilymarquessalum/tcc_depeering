import sys
from pathlib import Path
import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from src.ripe_bviews.read_bgpdump import BGPDumpSnapshotStats
from src.utils.graphs import plot_list_as_bar_plot, plot_list_as_line_plot, plot_stacked_line_plot
from src.ripe_bviews.timeline.bview_vars import get_annotations
from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data_timeline_from_configs
from src.ripe_bviews.download_and_parse.load_configs import load_configs, print_config
from src.ripe_bviews.timeline.bview_vars import get_ip_version, get_subfolder, get_title_end, get_title_start
from src.utils.graphs import create_window_with_all_rendered_graphs_this_session

import ipaddress


def calculate_total_addresses(prefix_list):
    """Calculate total IP addresses in a list of prefixes."""
    total_addresses = 0
    
    for prefix in prefix_list:
        try:
            network = ipaddress.ip_network(prefix, strict=False)
            total_addresses += network.num_addresses
        except ValueError as e:
            print(f"Skipping invalid prefix '{prefix}': {e}")
            
    return total_addresses


def calculate_unique_addresses(prefix_list):
    """Calculate unique IP addresses after collapsing overlapping prefixes."""
    # Convert strings to network objects and deduplicate
    networks = [ipaddress.ip_network(p, strict=False) for p in set(prefix_list)]
    
    # Collapse overlapping prefixes
    unique_networks = list(ipaddress.collapse_addresses(networks))
    
    # Sum the unique addresses
    total_unique = sum(net.num_addresses for net in unique_networks)
    
    return total_unique, unique_networks


def calculate_shortest_path_average_over_time_for_prefixes(all_stats: list[BGPDumpSnapshotStats]):
    """Calculate the average shortest path length for reaching each prefix for each snapshot."""
    shortest_path_averages = []
    for stat in all_stats:
        shortest_path_lengths = []
        
        # Get all unique prefixes in this snapshot
        all_prefixes = set()
        for member_as, prefix_list in stat.prefix_mappings.items():
            all_prefixes.update(prefix_list)
        
        # For each prefix, find the shortest path to reach it
        for prefix in all_prefixes:
            # Find the shortest path among all members that announce this prefix
            shortest_length = float('inf')
            for member_as, prefix_list in stat.prefix_mappings.items():
                if prefix in prefix_list:
                    # Get shortest path for this member to reach reachables via this prefix
                    # We use the prefix as a proxy and look at the member's routes
                    for mapping in stat.mappings.get(member_as, []):
                        # Count the path length for routes containing this prefix
                        as_path_length = len(mapping["as_path"])
                        if as_path_length < shortest_length:
                            shortest_length = as_path_length
            
            if shortest_length != float('inf'):
                shortest_path_lengths.append(shortest_length)
        
        # Calculate average for this snapshot
        if shortest_path_lengths:
            average = sum(shortest_path_lengths) / len(shortest_path_lengths)
        else:
            average = 0
        shortest_path_averages.append(average)
    
    return shortest_path_averages


def calculate_routes_that_improved_access_to_prefixes(all_stats: list[BGPDumpSnapshotStats]):
    """
    Calculate routes that improved access to prefixes with shorter path lengths.
    Only considers prefixes that already existed but got new routes with shorter paths.
    """
    routes_that_improved_access_per_snapshot = []
    
    for i in range(1, len(all_stats)):
        routes_that_improved_access = 0
        
        # Get all prefixes in current and previous snapshot
        prefixes_current = set()
        for prefix_list in all_stats[i].prefix_mappings.values():
            prefixes_current.update(prefix_list)
        
        prefixes_previous = set()
        for prefix_list in all_stats[i-1].prefix_mappings.values():
            prefixes_previous.update(prefix_list)
        
        # Look at prefixes that existed before
        for prefix in prefixes_previous & prefixes_current:
            # Find shortest path in both snapshots
            shortest_path_before = float('inf')
            shortest_path_after = float('inf')
            
            # Before
            for member_as, prefix_list in all_stats[i-1].prefix_mappings.items():
                if prefix in prefix_list:
                    for mapping in all_stats[i-1].mappings.get(member_as, []):
                        as_path_length = len(mapping["as_path"])
                        if as_path_length < shortest_path_before:
                            shortest_path_before = as_path_length
            
            # After
            for member_as, prefix_list in all_stats[i].prefix_mappings.items():
                if prefix in prefix_list:
                    for mapping in all_stats[i].mappings.get(member_as, []):
                        as_path_length = len(mapping["as_path"])
                        if as_path_length < shortest_path_after:
                            shortest_path_after = as_path_length
            
            # Check if path improved
            if (shortest_path_before != float('inf') and shortest_path_after != float('inf') and 
                shortest_path_after < shortest_path_before):
                routes_that_improved_access += 1
        
        routes_that_improved_access_per_snapshot.append(routes_that_improved_access)
    
    return routes_that_improved_access_per_snapshot


def calculate_routes_that_degraded_access_to_prefixes(all_stats: list[BGPDumpSnapshotStats]):
    """
    Calculate routes that degraded access to prefixes with longer path lengths.
    Only considers prefixes that still exist but whose shortest path got longer.
    """
    routes_that_degraded_access_per_snapshot = []
    
    for i in range(1, len(all_stats)):
        routes_that_degraded_access = 0
        
        # Get all prefixes in current and previous snapshot
        prefixes_current = set()
        for prefix_list in all_stats[i].prefix_mappings.values():
            prefixes_current.update(prefix_list)
        
        prefixes_previous = set()
        for prefix_list in all_stats[i-1].prefix_mappings.values():
            prefixes_previous.update(prefix_list)
        
        # Look at prefixes that still exist
        for prefix in prefixes_previous & prefixes_current:
            # Find shortest path in both snapshots
            shortest_path_before = float('inf')
            shortest_path_after = float('inf')
            
            # Before
            for member_as, prefix_list in all_stats[i-1].prefix_mappings.items():
                if prefix in prefix_list:
                    for mapping in all_stats[i-1].mappings.get(member_as, []):
                        as_path_length = len(mapping["as_path"])
                        if as_path_length < shortest_path_before:
                            shortest_path_before = as_path_length
            
            # After
            for member_as, prefix_list in all_stats[i].prefix_mappings.items():
                if prefix in prefix_list:
                    for mapping in all_stats[i].mappings.get(member_as, []):
                        as_path_length = len(mapping["as_path"])
                        if as_path_length < shortest_path_after:
                            shortest_path_after = as_path_length
            
            # Check if path got worse
            if (shortest_path_before != float('inf') and shortest_path_after != float('inf') and 
                shortest_path_after > shortest_path_before):
                routes_that_degraded_access += 1
        
        routes_that_degraded_access_per_snapshot.append(routes_that_degraded_access)
    
    return routes_that_degraded_access_per_snapshot


def plot_shortest_path_average_over_time_for_prefixes(all_stats, labels_summarized, title_start, title_end, subfolder, max_labels):
    """Plot the average shortest path length for prefixes over time."""
    shortest_path_average_over_time = calculate_shortest_path_average_over_time_for_prefixes(all_stats)
    plot_list_as_line_plot(
        shortest_path_average_over_time, 
        labels_summarized, 
        title=f'{title_start} Prefix Shortest Path Average Over Time {title_end}', 
        xlabel='Time', 
        ylabel='Average Shortest Path Length', 
        subfolder=subfolder,
        max_labels=max_labels, 
        annotations=get_annotations()
    )


def plot_routes_that_improved_access_to_prefixes(all_stats, labels_summarized, name, ip_version, subfolder, max_labels):
    """Plot routes that improved access to prefixes with shorter path lengths."""
    routes_that_improved_access_per_snapshot = calculate_routes_that_improved_access_to_prefixes(all_stats)
    plot_list_as_line_plot(
        routes_that_improved_access_per_snapshot,
        labels_summarized[1:],
        title=f'Routes That Improved Access to Prefixes - {name} - IP{ip_version}',
        xlabel='Time',
        ylabel='Number of Routes with Improved Access',
        subfolder=subfolder,
        max_labels=max_labels,
        annotations=get_annotations()
    )
    return routes_that_improved_access_per_snapshot


def plot_routes_that_degraded_access_to_prefixes(all_stats, labels_summarized, name, ip_version, subfolder, max_labels):
    """Plot routes that degraded access to prefixes with longer path lengths."""
    routes_that_degraded_access_per_snapshot = calculate_routes_that_degraded_access_to_prefixes(all_stats)
    plot_list_as_line_plot(
        routes_that_degraded_access_per_snapshot,
        labels_summarized[1:],
        title=f'Routes That Degraded Access to Prefixes - {name} - IP{ip_version}',
        xlabel='Time',
        ylabel='Number of Routes with Degraded Access',
        subfolder=subfolder,
        max_labels=max_labels,
        annotations=get_annotations()
    )
    return routes_that_degraded_access_per_snapshot


def plot_prefix_path_improvements_analysis(all_stats, labels_summarized, name, ip_version, subfolder, max_labels):
    """Plot comprehensive prefix path improvement analysis."""
    prefixes_improved = calculate_routes_that_improved_access_to_prefixes(all_stats)
    prefixes_degraded = calculate_routes_that_degraded_access_to_prefixes(all_stats)
    
    net_prefix_path_improvement = [improved - degraded for improved, degraded in zip(prefixes_improved, prefixes_degraded)]
    accumulated_net_improvement = []
    accumulated = 0
    for net in net_prefix_path_improvement:
        accumulated += net
        accumulated_net_improvement.append(accumulated)
    
    plot_stacked_line_plot(
        [prefixes_improved, prefixes_degraded],
        ['Paths Improved', 'Paths Degraded'],
        x_labels=labels_summarized[1:],
        title=f'Prefix Path Changes - {name} - IP{ip_version}',
        xlabel='Time',
        ylabel='Number of Prefixes',
        subfolder=subfolder,
        max_labels=max_labels
    )
    
    plot_list_as_line_plot(
        net_prefix_path_improvement,
        labels_summarized[1:],
        title=f'Net Prefix Path Improvement - {name} - IP{ip_version}',
        xlabel='Time',
        ylabel='Net Number of Prefixes (Improved - Degraded)',
        subfolder=subfolder,
        max_labels=max_labels,
        annotations=get_annotations()
    )
    
    plot_list_as_line_plot(
        accumulated_net_improvement,
        labels_summarized[1:],
        title=f'Accumulated Prefix Path Improvement - {name} - IP{ip_version}',
        xlabel='Time',
        ylabel='Accumulated Net Prefix Path Improvement',
        subfolder=subfolder,
        max_labels=max_labels,
        annotations=get_annotations()
    )


if __name__ == "__main__":
    from src.ripe_bviews.bview_labels import get_max_labels, summarized_date_labels
    
    config = load_configs("ixbr.json")
    #config = load_configs("AMS-IX.json")
    ip_version = get_ip_version(config)
    print_config(config, ip_version)

    name = config.get("name", "Unknown")
    
    all_stats, labels = load_bview_data_timeline_from_configs(config, ip_version=ip_version,
                                                              skip_if_missing=3)    

    labels_summarized = summarized_date_labels(labels)
    title_start = get_title_start(config)
    title_end = get_title_end(config)
    subfolder = get_subfolder(config, ip_version)
    max_labels = get_max_labels(labels)
    
    # Plot prefix-based path improvements
    plot_shortest_path_average_over_time_for_prefixes(all_stats, labels_summarized, title_start, title_end, subfolder, max_labels)
    plot_routes_that_improved_access_to_prefixes(all_stats, labels_summarized, name, ip_version, subfolder, max_labels)
    plot_routes_that_degraded_access_to_prefixes(all_stats, labels_summarized, name, ip_version, subfolder, max_labels)
    plot_prefix_path_improvements_analysis(all_stats, labels_summarized, name, ip_version, subfolder, max_labels)
    
    create_window_with_all_rendered_graphs_this_session()
