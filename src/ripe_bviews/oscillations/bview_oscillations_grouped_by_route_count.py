

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
# The idea here is to group ASes by the number of routes they gave before 
# stop announcing routes. 
# We will do one for oscillating ASes, another for ASes that did not come back, and then
# we can also do a stack plot with both of them (if we think it can tell us something).
# I am expecting ASes that oscillate for a short period of time to have a low number of routes,
# meanwhile the group of ASes that do not come back shouldn't really have a pattern.
# Its harder for an AS that gives a lot of routes to oscillate, but either small or big ASes 
# can leave and not come back.
# then we can do a different visualization: how many ASes that give only a few routes
#  are oscillating VS did-not-come-back. If there is a correlation here, we can say small ASes
# are more likely to come back from an oscillation. We can then do the same analysis for big ASes.
# The results can basically indicate that I can have a higher confidence of de-peering if the AS 
# is large, and smaller confidence of de-peering if the AS is small.


from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data_timeline_from_configs
from src.ripe_bviews.download_and_parse.load_configs import load_configs
from src.ripe_bviews.oscillations.bview_oscillation_logic import calculate_oscillation_metrics
from src.ripe_bviews.timeline.bview_timeline_oscillation_metrics import calculate_comeback_time_metrics
from src.ripe_bviews.timeline.bview_vars import get_ip_version


import numpy as np
from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data_timeline_from_configs
from src.ripe_bviews.download_and_parse.load_configs import load_configs
from src.ripe_bviews.oscillations.bview_oscillation_logic import calculate_oscillation_metrics
from src.ripe_bviews.timeline.bview_timeline_oscillation_metrics import calculate_comeback_time_metrics
from src.ripe_bviews.timeline.bview_vars import get_ip_version
from src.utils.graphs import plot_stacked_bar_plot

if __name__ == "__main__":
    # 1. Load Configurations and Data Timeline
    config = load_configs("AMS-IX.json")
    ip_version = get_ip_version(config) 
    all_stats, labels = load_bview_data_timeline_from_configs(config, ip_version=ip_version)     
 
    # 2. Extract Oscillation and Permanently Disappeared Metrics
    metrics = calculate_oscillation_metrics(all_stats) 
    metrics.load_oscillating_lists()
    
    # 3. Track Route Counts Before Disappearance
    # Structures to hold route counts right before an AS leaves
    oscillating_route_counts = []
    did_not_come_back_route_counts = []

    # Map permanent events for quick identity checks
    # metrics.all_did_not_come_back_events contains tuples: (asn, last_seen_index)
    dncb_map = {asn: last_idx for asn, last_idx in metrics.all_did_not_come_back_events}

    # Process Oscillating ASes
    # oscillation_info format: asn -> {"start_idxs": [...], "presence_historic": [...], ...}
    for asn, info in metrics.oscillation_info.items():
        for start_idx in info["start_idxs"]:
            # The snapshot immediately preceding the disappearance idx (start_idx)
            prev_snapshot_idx = start_idx - 1
            if 0 <= prev_snapshot_idx < len(all_stats):
                stat = all_stats[prev_snapshot_idx]
                # Measure "size" by routes allowed through this member AS
                routes_count = len(stat.mappings.get(str(asn), []))
                oscillating_route_counts.append(routes_count)

    # Process Permanently Disappeared ASes (Did Not Come Back)
    for asn, last_idx in dncb_map.items():
        if last_idx < len(all_stats):
            stat = all_stats[last_idx]
            routes_count = len(stat.mappings.get(str(asn), []))
            did_not_come_back_route_counts.append(routes_count)

    # 4. Group Counts into Size-Based Categorical Buckets
    # Defining buckets representing the operational footprint size of the ASes
    bins = [0, 20, 100, 300, float('inf')]
    bin_labels = ["1-20 Routes",  "21-100 Routes", "101-300 Routes", "300+ Routes"]

    oscillating_distribution = [0] * (len(bins) - 1)
    dncb_distribution = [0] * (len(bins) - 1)

    for count in oscillating_route_counts:
        for i in range(len(bins) - 1):
            if bins[i] <= count < bins[i+1]:
                oscillating_distribution[i] += 1
                break

    for count in did_not_come_back_route_counts:
        for i in range(len(bins) - 1):
            if bins[i] <= count < bins[i+1]:
                dncb_distribution[i] += 1
                break

    # 5. Print out Analytical Findings
    print(f"--- Analysis Breakdown ({config.get('name', 'IXP')}) ---")
    for idx, label in enumerate(bin_labels):
        tot_osc = oscillating_distribution[idx]
        tot_dncb = dncb_distribution[idx]
        total_events = tot_osc + tot_dncb
        ratio = (tot_osc / total_events * 100) if total_events > 0 else 0
        print(f"Size [{label}]: Oscillated={tot_osc} | Dead={tot_dncb} -> Return Confidence: {ratio:.1f}%")

    # 6. Generate Stacked Bar Chart Visualization
    plot_stacked_bar_plot(
        data_lists=[oscillating_distribution, dncb_distribution],
        labels=["Oscillating (Returned)", "Permanently Left (Did Not Come Back)"],
        x_labels=bin_labels,
        title="ASes Grouped by Route Count Before Stopping Announcements -  Oscillating vs Permanently Left",
        xlabel="Number of Routes before stopping announcements",
        ylabel="Number of ASes",
        subfolder="oscillations",
        sort_by_size=False
    )

    # Calculate correlation using only overlapping data length
    if oscillating_route_counts and did_not_come_back_route_counts:
        min_len = min(len(oscillating_route_counts), len(did_not_come_back_route_counts))
        numerical_correlation = np.corrcoef(oscillating_route_counts[:min_len], did_not_come_back_route_counts[:min_len])[0, 1]
        print(f"Correlation between route counts of oscillating ASes and permanently disappeared ASes: {numerical_correlation:.4f}")
    else:
        print("Not enough data to calculate correlation")