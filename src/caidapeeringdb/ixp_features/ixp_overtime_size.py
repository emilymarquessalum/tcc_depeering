import re
import numpy as np
from src.caidapeeringdb.caidapeeringdb_load import get_dates_from_files
from src.caidapeeringdb.utils import PEERINGDB_SUBFOLDER_PREFIX
from src.caidapeeringdb.ixp_overtime import get_ases_that_depeered_at_ixp_at_depeering_peak, get_ixp_with_most_depeering_ratio_at_a_single_point_in_time, plot_ixp_connections_over_time_by_category, plot_ixps_connections_over_time

DEFAULT_SIZE_RANGE_THRESHOLDS = [50, 100, 150, 200]

def plot_ixp_connections_over_time_by_size_ranges(all_data, all_files, depeered_ixp_ids, depeered_ixp_sizes, asn_to_analyze, 
                                                size_range_thresholds=None,
                                                completely_lost_ixp_ids=None,
                                                ixp_names=None,
                                                depeered_with_nonpeered_ixp_ids=None):
    """
    Plots the number of connections over time for IXPs that were de-peered, 
    grouped by their size ranges, comparing completely lost vs still have non-peered connections.
    Additionally plots the single IXP with the highest de-peering ratio for each size group.
    """
    if size_range_thresholds is None:
        size_range_thresholds = DEFAULT_SIZE_RANGE_THRESHOLDS
    
    # Set defaults if not provided
    if completely_lost_ixp_ids is None:
        completely_lost_ixp_ids = set()
    if depeered_with_nonpeered_ixp_ids is None:
        depeered_with_nonpeered_ixp_ids = set()
    
    # 1. Group IXPs by size range and type
    range_labels = []
    lower = 0
    for threshold in size_range_thresholds:
        range_labels.append(f"{lower}-{threshold}")
        lower = threshold
    range_labels.append(f"{lower}+")
    
    completely_lost_by_range = {label: [] for label in range_labels}
    depeered_nonpeered_by_range = {label: [] for label in range_labels}
    all_relevant_ixp_ids = set()
    depeered_at_peak_ases_by_ixp = {}
    
    for ixp_id, size in depeered_ixp_sizes.items():
        if ixp_id not in depeered_ixp_ids:
            continue
            
        categorized = False
        for i, threshold in enumerate(size_range_thresholds):
            if size <= threshold:
                range_label = range_labels[i]
                if ixp_id in completely_lost_ixp_ids:
                    completely_lost_by_range[range_label].append(ixp_id)
                elif ixp_id in depeered_with_nonpeered_ixp_ids:
                    depeered_nonpeered_by_range[range_label].append(ixp_id)
                all_relevant_ixp_ids.add(str(ixp_id))
                categorized = True
                break
        if not categorized:
            range_label = range_labels[-1]
            if ixp_id in completely_lost_ixp_ids:
                completely_lost_by_range[range_label].append(ixp_id)
            elif ixp_id in depeered_with_nonpeered_ixp_ids:
                depeered_nonpeered_by_range[range_label].append(ixp_id)
            all_relevant_ixp_ids.add(str(ixp_id))
            
    dates = get_dates_from_files(all_files)
        
    # 2. Collect connections over time
    timeline_data = {str(ixp_id): [] for ixp_id in all_relevant_ixp_ids}
    completely_lost_timeline_data = {str(ixp_id): [] for ixp_id in all_relevant_ixp_ids}
    depeered_nonpeered_timeline_data = {str(ixp_id): [] for ixp_id in all_relevant_ixp_ids}
    
    for idx, data in enumerate(all_data):
        ixp_counts = {str(ixp_id): 0 for ixp_id in all_relevant_ixp_ids}
        completely_lost_counts = {str(ixp_id): 0 for ixp_id in all_relevant_ixp_ids}
        depeered_nonpeered_counts = {str(ixp_id): 0 for ixp_id in all_relevant_ixp_ids}
        
        for conn in data.get("netixlan", {}).get("data", []):
            ixp_id = str(conn.get("ix_id"))
            if ixp_id in all_relevant_ixp_ids:
                ixp_counts[ixp_id] += 1
                if ixp_id in [str(x) for x in completely_lost_ixp_ids]:
                    completely_lost_counts[ixp_id] += 1
                elif ixp_id in [str(x) for x in depeered_with_nonpeered_ixp_ids]:
                    depeered_nonpeered_counts[ixp_id] += 1
        
        for ixp_id, count in ixp_counts.items():
            timeline_data[ixp_id].append(count)
        for ixp_id, count in completely_lost_counts.items():
            completely_lost_timeline_data[ixp_id].append(count)
        for ixp_id, count in depeered_nonpeered_counts.items():
            depeered_nonpeered_timeline_data[ixp_id].append(count)
                
    # 3. Plot for each size range (Single, unified loop)
    for label in range_labels:
        completely_lost_ixps = completely_lost_by_range.get(label, [])
        depeered_nonpeered_ixps = depeered_nonpeered_by_range.get(label, [])
        combined_range_ixp_ids = list(set(completely_lost_ixps + depeered_nonpeered_ixps))
        
        # Skip if group is empty
        if not combined_range_ixp_ids:
            continue
        
        # --- A. Category aggregate plot ---
        depeering_event_timelines = {}
        for ixp_id in depeered_nonpeered_ixps:
            ixp_id_str = str(ixp_id)
            if ixp_id_str in depeered_nonpeered_timeline_data:
                event_timeline = []
                for i in range(len(dates)):
                    has_connections_now = (
                        depeered_nonpeered_timeline_data[ixp_id_str][i] > 0 
                        if i < len(depeered_nonpeered_timeline_data[ixp_id_str]) else False
                    )
                    had_connections_before = (
                        depeered_nonpeered_timeline_data[ixp_id_str][i-1] > 0 
                        if i > 0 and i-1 < len(depeered_nonpeered_timeline_data[ixp_id_str]) else True
                    )
                    event_timeline.append(had_connections_before and not has_connections_now)
                depeering_event_timelines[ixp_id_str] = event_timeline
        
        plot_ixp_connections_over_time_by_category(
            dates=dates,
            timeline_data=timeline_data,
            completely_lost_ixp_ids=completely_lost_ixps,
            depeered_nonpeered_ixp_ids=depeered_nonpeered_ixps,
            completely_lost_timeline_data=completely_lost_timeline_data,
            depeered_nonpeered_timeline_data=depeered_nonpeered_timeline_data,
            category_label=label,
            category_type="Size Range",
            asn_to_analyze=asn_to_analyze,
            plot_name_suffix=f"size_range_{label}",
            depeering_event_timelines=depeering_event_timelines
        )
 

        max_ixp_id_in_the_size_range, max_ratio, index_of_max_ratio = get_ixp_with_most_depeering_ratio_at_a_single_point_in_time(
            all_data=all_data, 
            ixp_ids=combined_range_ixp_ids,
            type_of_depeering="rs_to_non_rs"
        )

        depeered_at_peak_ases_by_ixp[max_ixp_id_in_the_size_range] = get_ases_that_depeered_at_ixp_at_depeering_peak(all_data, max_ixp_id_in_the_size_range, index_of_max_ratio)
        
        if max_ixp_id_in_the_size_range is not None:
            plot_ixps_connections_over_time(
                all_data=all_data,
                dates=dates,
                ixp_ids=[max_ixp_id_in_the_size_range],
                ixp_names=ixp_names,
                title_info=f"Size Group {label} (Highest De-Peering Ratio: {max_ratio:.2%})"
            )
        else:
            print(f"No IXP found with de-peering events in size range {label}...")

    return depeered_at_peak_ases_by_ixp