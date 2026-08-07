
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
# Generate a result that essencially suggests how much confidence we can have 
# that an AS is not going to returrn after X time of it not announcing routes.
# We could calculate this by grouping ASes by time to come back, and get a metric like
# "90% of ASes that come back do so within X snapshots". So, if we want to cover 
# 90% of ASes that come back, we can consider ASes only as de-peered after X snapshots and 
# leave the rest as "possibly unavailable". 
# We can calculate it both ways. How many snapshots are needed for X% confidence,
# but also how much confidence we have after X snapshots.







from src.ripe_bviews.download_and_parse.load_configs import load_configs
from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data_timeline_from_configs
from src.ripe_bviews.oscillations.bview_oscillation_logic import calculate_oscillation_metrics
from src.ripe_bviews.oscillations.bview_timeline_oscillation_metrics import calculate_comeback_time_metrics
from src.ripe_bviews.timeline.bview_vars import get_ip_version


if __name__ == "__main__":
    config = load_configs("ixbr.json")
    config = load_configs("AMS-IX.json")
 
    ip_version = get_ip_version(config) 

    all_stats, labels = load_bview_data_timeline_from_configs(config, ip_version=ip_version)     
 

    metrics = calculate_oscillation_metrics(all_stats) 
    all_comeback_times, all_comeback_times_with_one_contribution_per_asn_in_a_time, average_time_ases_take_to_come_back = calculate_comeback_time_metrics(metrics)

    
    comeback_times_count = {}
    for time in all_comeback_times:
        if time not in comeback_times_count:
            comeback_times_count[time] = 0
        comeback_times_count[time] += 1
    
    target_confidence = 0.9
    
    # Sort comeback times and calculate cumulative metrics
    sorted_times = sorted(comeback_times_count.keys())
    total_comebacks = sum(comeback_times_count.values())
    
    cumulative_count = 0
    snapshots_for_target_confidence = None
    
    print(f"Total ASes that came back: {total_comebacks}\n")
    print("Snapshots -> Count | Cumulative Count | Confidence")
    print("-" * 55)
    
    for snapshot_count in sorted_times:
        cumulative_count += comeback_times_count[snapshot_count]
        confidence = cumulative_count / total_comebacks
        
        print(f"{snapshot_count:>9} -> {comeback_times_count[snapshot_count]:>5} | {cumulative_count:>16} | {confidence:.2%}")
        
        # Find snapshots needed for target confidence
        if snapshots_for_target_confidence is None and confidence >= target_confidence:
            snapshots_for_target_confidence = snapshot_count
    
    print("\n" + "=" * 55)
    print(f"\nResults:")
    print(f"  • To have {target_confidence:.0%} confidence an AS won't return: {snapshots_for_target_confidence} snapshots")
    print(f"  • Average time ASes take to come back: {average_time_ases_take_to_come_back:.2f} snapshots")
    
    