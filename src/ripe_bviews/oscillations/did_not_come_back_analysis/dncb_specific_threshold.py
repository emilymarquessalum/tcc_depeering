import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data_timeline_from_configs
from src.ripe_bviews.download_and_parse.load_configs import load_configs
from src.ripe_bviews.oscillations.bview_oscillation_logic import calculate_oscillation_metrics
from src.ripe_bviews.timeline.bview_vars import get_ip_version
from src.utils.graphs import plot_list_as_bar_plot, plot_stacked_bar_plot

if __name__ == "__main__":
    
    config = load_configs("ixbr.json")
    ip_version = get_ip_version(config) 
    all_stats, labels = load_bview_data_timeline_from_configs(config, ip_version=ip_version)     
     
    metrics = calculate_oscillation_metrics(all_stats) 
    metrics.load_oscillating_lists()

    
    global_true_dncb = metrics.all_did_not_come_backs
    attr_name = "unique_reachables" if False else "unique_members" 
    num_snapshots = len(all_stats)

    # 3. Define the values of 'n' (consecutive absent snapshots threshold) to test
    n_thresholds = [1, 2, 3, 4, 5, 6, 7, 8]
    
    x_axis_labels = [f"n={n}" for n in n_thresholds]
    true_dncb_totals = [] # was correctly identified as permanent (absent for >= n snapshots and never returned)
    mismatch_totals = []  # False alarms (absent for >= n snapshots, but returned eventually) 
    false_negative_totals = [] # was incorrectly identified as non-permanent (absent for < n snapshots, but never returned)


    absent_for_mapping = {} # number_of_snapshots: [list of ASes]

    print(f"--- Running DNCB Sensitivity Threshold Analysis ---")

    for n in n_thresholds: 
        flagged_true_depeerings = set()
        flagged_false_positives = set()
         
        seen_events = set()
        
        for i in range(num_snapshots - n):
            current_asns = getattr(all_stats[i], attr_name)
            next_asns = getattr(all_stats[i+1], attr_name)
            dropped_asns = current_asns - next_asns
            
            for asn in dropped_asns:
                asn_int = int(asn)
                event_key = (asn_int, i)
                if event_key in seen_events:
                    continue
                seen_events.add(event_key)
                
                is_absent_for_n = True
                for check_idx in range(i + 1, i + 1 + n):
                    if asn in getattr(all_stats[check_idx], attr_name):
                        is_absent_for_n = False
                        break
                
                if is_absent_for_n:
                    if asn_int in global_true_dncb:
                        flagged_true_depeerings.add(asn_int)
                    else:
                        flagged_false_positives.add(asn_int)

        tp_count = len(flagged_true_depeerings)
        fp_count = len(flagged_false_positives)
        fn_count = total_true_depeerings_count - tp_count
        
        true_dncb_totals.append(tp_count)
        mismatch_totals.append(fp_count)
        false_negative_totals.append(fn_count)
        
        total_flagged = tp_count + fp_count
        precision = (tp_count / total_flagged * 100) if total_flagged > 0 else 100.0
        recall = (tp_count / total_true_depeerings_count * 100) if total_true_depeerings_count > 0 else 100.0
        
        print(f"Threshold [n={n}]: Flagged={total_flagged} | TP={tp_count} | FP={fp_count} | FN={fn_count} -> Precision: {precision:.1f}% | Recall: {recall:.1f}%")

    # 4. Generate the Comparison Chart Across Threshold Values
    plot_stacked_bar_plot(
        data_lists=[true_dncb_totals, mismatch_totals],
        labels=["True De-peerings (Never Returned)", "False Positives (Returned Later)"],
        x_labels=x_axis_labels,
        title=f"{config.get('name', 'IXP')} - Predictive Accuracy of using X as time-to-come-back threshold",
        xlabel="Threshold (Number of consecutive snapshots an AS must be missing)",
        ylabel="Identified Disappearance Events",
        subfolder="oscillations",
        sort_by_size=False
    ) 


    # I am making this but just realized I am implementing by hand the concept of a CDF, ops.
    match_percentage_over_time = []

    # all depeerings that happened, indepdendently of time taken
    total_depeerings_that_happened = sum([len(list_of_ases) for list_of_ases in absent_for_mapping.values()])
   

    
    print("\n--- Computing Temporary Outage Duration ECDF ---")
    
    temporary_outage_durations = []
    seen_drop_events = set()

    for i in range(num_snapshots - 1):
        current_asns = getattr(all_stats[i], attr_name)
        next_asns = getattr(all_stats[i+1], attr_name)
        dropped_asns = current_asns - next_asns
        
        for asn in dropped_asns:
            asn_int = int(asn)
            
            # Exclude true permanent de-peerings (they never return, so duration is undefined)
            if asn_int in global_true_dncb:
                continue

            event_key = (asn_int, i)
            if event_key in seen_drop_events:
                continue
            seen_drop_events.add(event_key)

            # Measure exact duration (in snapshots/days) until the AS reappears
            duration = 1
            returned = False
            for check_idx in range(i + 2, num_snapshots):
                if asn in getattr(all_stats[check_idx], attr_name):
                    returned = True
                    break
                duration += 1
            
            if returned:
                temporary_outage_durations.append(duration)

    # Plot proper ECDF of outage recovery durations
    plot_cdf(
        data=temporary_outage_durations,
        title=f"{config.get('name', 'IXP')} - ECDF of Temporary Outage Durations Before Recovery",
        xlabel="Outage Duration (Snapshots/Days)",
        ylabel="Cumulative Percentage of Recovered Drops",
        subfolder="oscillations",
        color="navy",
        notes=f"Total temporary drop events analyzed: {len(temporary_outage_durations)}"
    )