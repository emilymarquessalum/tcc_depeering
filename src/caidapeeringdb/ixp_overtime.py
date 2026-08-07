import matplotlib.pyplot as plt
import numpy as np
from src.caidapeeringdb.utils import PEERINGDB_SUBFOLDER_PREFIX
from src.utils.graphs import save_plot


def plot_ixp_connections_over_time_by_category(dates, timeline_data, completely_lost_ixp_ids, 
                                                depeered_nonpeered_ixp_ids,
                                                completely_lost_timeline_data, depeered_nonpeered_timeline_data,
                                                category_label, category_type, asn_to_analyze,
                                                plot_name_suffix, depeering_event_timelines=None):
    """
    Reusable function to plot IXP connections over time for a given category,
    comparing completely lost vs still have non-peered connections.
    
    Args:
        dates: List of date strings (e.g., ["2024-01-01", "2024-02-01"])
        timeline_data: Dict mapping ixp_id (str) to list of all connection counts over time
        completely_lost_ixp_ids: List/set of completely lost IXP IDs for this category
        depeered_nonpeered_ixp_ids: List/set of depeered IXP IDs with non-peered connections for this category
        completely_lost_timeline_data: Dict mapping ixp_id (str) to list of counts for completely lost IXPs
        depeered_nonpeered_timeline_data: Dict mapping ixp_id (str) to list of counts for IXPs with non-peered
        category_label: Label for this category (e.g., "Europe", "50-100", "0-30d")
        category_type: Type of categorization (e.g., "Region", "Size Range", "Age Range")
        asn_to_analyze: The ASN that de-peered
        plot_name_suffix: Suffix for the plot filename (e.g., "region_Europe", "range_50-100")
        depeering_event_timelines: Dict mapping ixp_id (str) to list of booleans indicating de-peering events over time
    """
    
    # Count IXPs in each category
    completely_lost_count = len(completely_lost_ixp_ids)
    depeered_nonpeered_count = len(depeered_nonpeered_ixp_ids)
    
    plt.figure(figsize=(12, 6))
    
    # Plot individual lines for completely lost IXPs
    completely_lost_ids_str = [str(ixp_id) for ixp_id in completely_lost_ixp_ids]
    for ixp_id in completely_lost_ids_str:
        if ixp_id in timeline_data:
            plt.plot(range(len(dates)), timeline_data[ixp_id], alpha=0.3, color='#ff9999')
    
    # Plot the average for completely lost IXPs
    if completely_lost_ids_str:
        avg_completely_lost = [sum(timeline_data[ixp_id][i] for ixp_id in completely_lost_ids_str if ixp_id in timeline_data) / len(completely_lost_ids_str) 
                               for i in range(len(dates))]
        plt.plot(range(len(dates)), avg_completely_lost, color='red', linewidth=3, label='Average (Completely Lost)')
        
        # Plot the median for completely lost IXPs
        median_completely_lost = [np.median([timeline_data[ixp_id][i] for ixp_id in completely_lost_ids_str if ixp_id in timeline_data]) 
                                  for i in range(len(dates))]
        plt.plot(range(len(dates)), median_completely_lost, color='darkred', linewidth=2, linestyle='--', 
                 label='Median (Completely Lost)')
    
    # Plot individual lines for depeered with non-peered IXPs
    depeered_nonpeered_ids_str = [str(ixp_id) for ixp_id in depeered_nonpeered_ixp_ids]
    for ixp_id in depeered_nonpeered_ids_str:
        if ixp_id in timeline_data:
            plt.plot(range(len(dates)), timeline_data[ixp_id], alpha=0.3, color='#99ccff')
    
    # Plot the average for depeered with non-peered IXPs
    if depeered_nonpeered_ids_str:
        avg_depeered_nonpeered = [sum(timeline_data[ixp_id][i] for ixp_id in depeered_nonpeered_ids_str if ixp_id in timeline_data) / len(depeered_nonpeered_ids_str) 
                                  for i in range(len(dates))]
        plt.plot(range(len(dates)), avg_depeered_nonpeered, color='blue', linewidth=3, label='Average (Still Has Non-Peered)')
        
        # Plot the median for depeered with non-peered IXPs
        median_depeered_nonpeered = [np.median([timeline_data[ixp_id][i] for ixp_id in depeered_nonpeered_ids_str if ixp_id in timeline_data]) 
                                     for i in range(len(dates))]
        plt.plot(range(len(dates)), median_depeered_nonpeered, color='darkblue', linewidth=2, linestyle='--', 
                 label='Median (Still Has Non-Peered)')
    
    # Plot de-peering events (when IXPs transition to completely lost)
    if depeering_event_timelines:
        depeering_event_counts = [0] * len(dates)
        
        for ixp_id, event_timeline in depeering_event_timelines.items():
            if len(event_timeline) == len(dates):
                for i, has_event in enumerate(event_timeline):
                    if has_event:
                        depeering_event_counts[i] += 1
        
        # Plot the de-peering event line if there are any events
        if any(depeering_event_counts):
            plt.plot(range(len(dates)), depeering_event_counts, color='gold', linewidth=3, 
                     label='De-Peering Events', marker='o', markersize=6)
    
    # Formatting with counts in title
    title = (f"IXP Connections Over Time - {category_type} {category_label}\n"
             f"(Completely Lost: {completely_lost_count} IXPs | Still Has Non-Peered: {depeered_nonpeered_count} IXPs | "
             f"ASN {asn_to_analyze})")
    
    plt.xticks(range(len(dates)), dates, rotation=45)
    plt.title(title)
    plt.xlabel("Date")
    plt.ylabel("Number of Connections (Total)")
    plt.legend()
    plt.grid(True)
    
    save_plot(plt, f"ixp_overtime_connections_{plot_name_suffix}_{asn_to_analyze}", 
              subfolder=PEERINGDB_SUBFOLDER_PREFIX + str(asn_to_analyze))
    plt.close()



if __name__ == "__main__":
    pass