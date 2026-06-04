import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data_timeline_from_configs
from src.ripe_bviews.download_and_parse.load_configs import load_configs
from src.ripe_bviews.oscillations.bview_oscillation_logic import calculate_oscillation_metrics
from src.ripe_bviews.timeline.bview_vars import get_ip_version
from src.utils.graphs import plot_stacked_bar_plot

def get_dncb_asns_in_window(all_stats, start_idx, end_idx, use_reachables=False):
    attr_name = "unique_reachables" if use_reachables else "unique_members"
    starting_asns = getattr(all_stats[start_idx], attr_name).copy()
    
    for idx in range(start_idx + 1, end_idx + 1):
        active_asns = getattr(all_stats[idx], attr_name)
        starting_asns -= active_asns
        
    return starting_asns

if __name__ == "__main__":
    # 1. Load Configurations and Timeline Data
    config = load_configs("AMS-IX.json")
    ip_version = get_ip_version(config) 
    all_stats, labels = load_bview_data_timeline_from_configs(config, ip_version=ip_version)     
    
    # 2. Extract Global Ground Truth Metrics
    metrics = calculate_oscillation_metrics(all_stats) 
    metrics.load_oscillating_lists()
    
    # Global set of ASes that genuinely never return across the whole dataset
    # metrics.all_did_not_come_backs is a set[int] populated by load_oscillating_lists()
    global_true_dncb = metrics.all_did_not_come_backs

    # 3. Window Configuration
    safe_snapshots = 4  # Window size (n) to evaluate
    use_reachables = False
    num_snapshots = len(all_stats)
    
    window_labels = []
    true_dncb_counts = []
    mismatch_counts = []  # False positives (window said dead, but they return globally)
    
    print(f"--- Running DNCB Window Mismatch Analysis (n = {safe_snapshots}) ---")
    
    # 4. Slide through the timeline n-by-n and cross-examine with Global Truth
    for start_idx in range(0, num_snapshots - 1, safe_snapshots):
        end_idx = min(start_idx + safe_snapshots, num_snapshots - 1)
        
        if start_idx == end_idx:
            break
            
        # ASes flagged as "dead" inside this local window
        window_dncb_asns = get_dncb_asns_in_window(all_stats, start_idx, end_idx, use_reachables=use_reachables)
        
        # Breakdown into Matches vs. Mismatches
        true_positive_window = set()
        mismatch_window = set()
        
        for asn in window_dncb_asns:
            # Note: Cast asn to int if your global_true_dncb contains integers
            if int(asn) in global_true_dncb:
                true_positive_window.add(asn)
            else:
                mismatch_window.add(asn)
                
        window_range_str = f"S{start_idx}→S{end_idx}"
        window_labels.append(window_range_str)
        true_dncb_counts.append(len(true_positive_window))
        mismatch_counts.append(len(mismatch_window))
        
        total_window_dead = len(window_dncb_asns)
        accuracy = (len(true_positive_window) / total_window_dead * 100) if total_window_dead > 0 else 100
        print(f"Window [{window_range_str}]: Local Dead={total_window_dead} | "
              f"True Dead={len(true_positive_window)} | Mismatches={len(mismatch_window)} -> Window Accuracy: {accuracy:.1f}%")

    # 5. Generate Comparison Stacked Bar Chart
    plot_stacked_bar_plot(
        data_lists=[true_dncb_counts, mismatch_counts],
        labels=["True Local De-peerings (Never Returned)", "Window Mismatches (Returned Globally Later)"],
        x_labels=window_labels,
        title=f"{config.get('name', 'IXP')} - Window Mismatch with 'Truth' (n={safe_snapshots})",
        xlabel="Snapshot Windows",
        ylabel="Number of ASes",
        subfolder="oscillations",
        sort_by_size=False
    )