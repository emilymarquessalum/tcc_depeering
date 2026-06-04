import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data_timeline_from_configs
from src.ripe_bviews.download_and_parse.load_configs import load_configs
from src.ripe_bviews.oscillations.bview_oscillation_logic import calculate_oscillation_metrics
from src.ripe_bviews.timeline.bview_vars import get_ip_version
from src.utils.graphs import plot_stacked_bar_plot

if __name__ == "__main__":
    # 1. Load Configurations and Timeline Data
    config = load_configs("AMS-IX.json")
    ip_version = get_ip_version(config) 
    all_stats, labels = load_bview_data_timeline_from_configs(config, ip_version=ip_version)     
    
    # 2. Extract Global Ground Truth Metrics
    metrics = calculate_oscillation_metrics(all_stats) 
    metrics.load_oscillating_lists()
    
    # Global ground truth sets
    global_true_dncb = metrics.all_did_not_come_backs
    attr_name = "unique_reachables" if False else "unique_members" # Toggle for reachables if needed
    num_snapshots = len(all_stats)

    # 3. Define the values of 'n' (consecutive absent snapshots threshold) to test
    n_thresholds = [1, 2, 3, 4, 5, 6, 7, 8]
    
    x_axis_labels = [f"n={n}" for n in n_thresholds]
    true_dncb_totals = []
    mismatch_totals = []  # False alarms (absent for >= n snapshots, but returned eventually)

    print(f"--- Running DNCB Sensitivity Threshold Analysis ---")

    for n in n_thresholds:
        flagged_as_permanent = set()
        true_positive_count = 0
        mismatch_count = 0
        
        # Look for disappearance events across the timeline
        for i in range(num_snapshots - n):
            current_asns = getattr(all_stats[i], attr_name)
            
            # Check which ASes are missing in the immediate next snapshot
            next_asns = getattr(all_stats[i+1], attr_name)
            dropped_asns = current_asns - next_asns
            
            for asn in dropped_asns:
                # To be flagged under threshold n, it must remain absent for all n snapshots
                is_absent_for_n = True
                for check_idx in range(i + 1, i + 1 + n):
                    if asn in getattr(all_stats[check_idx], attr_name):
                        is_absent_for_n = False
                        break
                
                if is_absent_for_n:
                    # Deduplicate based on ASN and event origin index to avoid double counting 
                    # an AS that stays down for a long time across sliding evaluation steps
                    event_key = (int(asn), i)
                    
                    if int(asn) in global_true_dncb:
                        true_positive_count += 1
                    else:
                        mismatch_count += 1

        true_dncb_totals.append(true_positive_count)
        mismatch_totals.append(mismatch_count)
        
        total_flagged = true_positive_count + mismatch_count
        precision = (true_positive_count / total_flagged * 100) if total_flagged > 0 else 100
        print(f"Threshold [n={n}]: Observed Drops={total_flagged} | True De-peerings={true_positive_count} | Mismatches={mismatch_count} -> Predictive Precision: {precision:.1f}%")

    # 4. Generate the Comparison Chart Across Threshold Values
    plot_stacked_bar_plot(
        data_lists=[true_dncb_totals, mismatch_totals],
        labels=["True De-peerings (Never Returned)", "False Positives (Returned Later)"],
        x_labels=x_axis_labels,
        title=f"{config.get('name', 'IXP')} - Predictive Accuracy vs Observation Hold-Time Threshold (n)",
        xlabel="Threshold (Number of consecutive snapshots an AS must be missing)",
        ylabel="Identified Disappearance Events",
        subfolder="oscillations",
        sort_by_size=False
    )