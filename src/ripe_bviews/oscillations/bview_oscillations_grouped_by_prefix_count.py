import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

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
    
    # 3. Track PREFIX Counts Before Disappearance
    oscillating_prefix_counts = []
    oscillating_prefix_reached_counts = []
    did_not_come_back_prefix_counts = []
    did_not_come_back_prefix_reached_counts = []

    # Map permanent events for quick identity checks (asn -> last_seen_index)
    dncb_map = {asn: last_idx for asn, last_idx in metrics.all_did_not_come_back_events}

    # Process Oscillating ASes
    for asn, info in metrics.oscillation_info.items():
        for start_idx in info["start_idxs"]:
            prev_snapshot_idx = start_idx - 1
            if 0 <= prev_snapshot_idx < len(all_stats):
                stat = all_stats[prev_snapshot_idx]
                
                member_has, member_reaches, _ = stat.get_prefix_mappings()
                
                prefix_list = member_has.get(str(asn), set())
                oscillating_prefix_counts.append(len(prefix_list))

                reached_list = member_reaches.get(str(asn), set())
                oscillating_prefix_reached_counts.append(len(reached_list))

    # Process Permanently Disappeared ASes (Did Not Come Back)
    for asn, last_idx in dncb_map.items():
        if last_idx < len(all_stats):
            stat = all_stats[last_idx]
            
            member_has, member_reaches, _ = stat.get_prefix_mappings()
            
            prefix_list = member_has.get(str(asn), set())
            did_not_come_back_prefix_counts.append(len(prefix_list))

            reached_list = member_reaches.get(str(asn), set())
            did_not_come_back_prefix_reached_counts.append(len(reached_list))

    # 4. Group Prefix Counts into Footprint Categories
    # Bins for Prefixes Owned
    bins_owned = [0, 10, 50, float('inf')]
    bin_labels_owned = ["1-10 Prefixes", "11-50 Prefixes", "50+ Prefixes"]

    oscillating_owned_dist = [0] * (len(bins_owned) - 1)
    dncb_owned_dist = [0] * (len(bins_owned) - 1)

    for count in oscillating_prefix_counts:
        for i in range(len(bins_owned) - 1):
            if bins_owned[i] <= count < bins_owned[i+1]:
                oscillating_owned_dist[i] += 1
                break

    for count in did_not_come_back_prefix_counts:
        for i in range(len(bins_owned) - 1):
            if bins_owned[i] <= count < bins_owned[i+1]:
                dncb_owned_dist[i] += 1
                break

    # Bins for Prefixes Reached (Higher volume thresholds due to downstream/transit paths)
    bins_reached = [0, 100, 1000, float('inf')]
    bin_labels_reached = ["1-100 Reached", "101-1000 Reached", "1000+ Reached"]

    oscillating_reached_dist = [0] * (len(bins_reached) - 1)
    dncb_reached_dist = [0] * (len(bins_reached) - 1)

    for count in oscillating_prefix_reached_counts:
        for i in range(len(bins_reached) - 1):
            if bins_reached[i] <= count < bins_reached[i+1]:
                oscillating_reached_dist[i] += 1
                break

    for count in did_not_come_back_prefix_reached_counts:
        for i in range(len(bins_reached) - 1):
            if bins_reached[i] <= count < bins_reached[i+1]:
                dncb_reached_dist[i] += 1
                break

    # 5. Print out Analytical Findings
    print(f"--- Prefix Owned Concentration Analysis ({config.get('name', 'IXP')}) ---")
    for idx, label in enumerate(bin_labels_owned):
        tot_osc = oscillating_owned_dist[idx]
        tot_dncb = dncb_owned_dist[idx]
        total_events = tot_osc + tot_dncb
        ratio = (tot_osc / total_events * 100) if total_events > 0 else 0
        print(f"Owned Size [{label}]: Oscillated={tot_osc} | Dead={tot_dncb} -> Return Confidence: {ratio:.1f}%")

    print(f"\n--- Prefix Reached Concentration Analysis ({config.get('name', 'IXP')}) ---")
    for idx, label in enumerate(bin_labels_reached):
        tot_osc = oscillating_reached_dist[idx]
        tot_dncb = dncb_reached_dist[idx]
        total_events = tot_osc + tot_dncb
        ratio = (tot_osc / total_events * 100) if total_events > 0 else 0
        print(f"Reached Size [{label}]: Oscillated={tot_osc} | Dead={tot_dncb} -> Return Confidence: {ratio:.1f}%")

    # 6. Generate Stacked Bar Chart Visualizations
    # Graph 1: Prefixes Owned
    plot_stacked_bar_plot(
        data_lists=[oscillating_owned_dist, dncb_owned_dist],
        labels=["Oscillating (Returned)", "Permanently Left (Did Not Come Back)"],
        x_labels=bin_labels_owned,
        title="ASes Grouped by Prefix OWNED Volume Before Disappearance - Oscillating vs Permanently Left",
        xlabel="Number of Prefixes Owned by Member prior to departure",
        ylabel="Number of ASes",
        subfolder="oscillations",
        sort_by_size=False
    )

    # Graph 2: Prefixes Reached
    plot_stacked_bar_plot(
        data_lists=[oscillating_reached_dist, dncb_reached_dist],
        labels=["Oscillating (Returned)", "Permanently Left (Did Not Come Back)"],
        x_labels=bin_labels_reached,
        title="ASes Grouped by Prefix REACHED Volume Before Disappearance - Oscillating vs Permanently Left",
        xlabel="Number of Prefixes Reached by Member prior to departure",
        ylabel="Number of ASes",
        subfolder="oscillations",
        sort_by_size=False
    )

    # Calculate numerical correlations over sliced equal arrays if data exists
    min_len_owned = min(len(oscillating_prefix_counts), len(did_not_come_back_prefix_counts))
    if min_len_owned > 0:
        corr_owned = np.corrcoef(
            oscillating_prefix_counts[:min_len_owned], 
            did_not_come_back_prefix_counts[:min_len_owned]
        )[0, 1]
        print(f"\nCorrelation between prefix owned counts: {corr_owned:.4f}")

    min_len_reached = min(len(oscillating_prefix_reached_counts), len(did_not_come_back_prefix_reached_counts))
    if min_len_reached > 0:
        corr_reached = np.corrcoef(
            oscillating_prefix_reached_counts[:min_len_reached], 
            did_not_come_back_prefix_reached_counts[:min_len_reached]
        )[0, 1]
        print(f"Correlation between prefix reached counts: {corr_reached:.4f}")