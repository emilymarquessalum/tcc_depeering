import re
import numpy as np
from src.caidapeeringdb.utils import PEERINGDB_SUBFOLDER_PREFIX
from src.caidapeeringdb.ixp_overtime import plot_ixp_connections_over_time_by_category

DEFAULT_SIZE_RANGE_THRESHOLDS = [50, 100, 150, 200]

def plot_ixp_connections_over_time_by_size_ranges(all_data, all_files, depeered_ixp_ids, depeered_ixp_sizes, asn_to_analyze, 
                                                size_range_thresholds=None,
                                                completely_lost_ixp_ids=None,
                                                depeered_with_nonpeered_ixp_ids=None):
    """
    Plots the number of connections over time for IXPs that were de-peered, 
    grouped by their size ranges, comparing completely lost vs still have non-peered connections.
    
    Args:
        all_data: List of PeeringDB data snapshots (dicts)
        all_files: List of filenames corresponding to all_data (to extract dates)
        depeered_ixp_ids: Set of IXP IDs that were de-peered
        depeered_ixp_sizes: Dict mapping ixp_id to its size (peered connections) before de-peering
        asn_to_analyze: The ASN that de-peered
        size_range_thresholds: Thresholds for grouping IXPs by size
        completely_lost_ixp_ids: Set of IXP IDs that were completely lost
        depeered_with_nonpeered_ixp_ids: Set of IXP IDs that still have non-peered connections
    """
    if size_range_thresholds is None:
        size_range_thresholds = DEFAULT_SIZE_RANGE_THRESHOLDS
    
    # Set defaults if not provided
    if completely_lost_ixp_ids is None:
        completely_lost_ixp_ids = set()
    if depeered_with_nonpeered_ixp_ids is None:
        depeered_with_nonpeered_ixp_ids = set()
    
    # 1. Group IXPs by size range and type (completely lost vs still has non-peered)
    range_labels = []
    lower = 0
    for threshold in size_range_thresholds:
        range_labels.append(f"{lower}-{threshold}")
        lower = threshold
    range_labels.append(f"{lower}+")
    
    # Track both completely lost and depeered with non-peered separately by range
    completely_lost_by_range = {label: [] for label in range_labels}
    depeered_nonpeered_by_range = {label: [] for label in range_labels}
    all_relevant_ixp_ids = set()
    
    # We only care about IXPs that are in depeered_ixp_ids
    for ixp_id, size in depeered_ixp_sizes.items():
        if ixp_id not in depeered_ixp_ids:
            continue
            
        categorized = False
        for i, threshold in enumerate(size_range_thresholds):
            if size <= threshold:
                range_label = range_labels[i]
                # Categorize as completely lost or still has non-peered
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
            
    # 2. Extract dates from filenames
    dates = []
    for file in all_files:
        match = re.search(r"peeringdb_2_dump_(.*?)\.json", file)
        dates.append(match.group(1) if match else "unknown")
        
    # 3. Collect connections over time (efficient pass)
    # Track both completely lost and depeered with non-peered separately
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
                # Categorize by type
                if ixp_id in completely_lost_timeline_data:
                    # Check if this IXP is in completely_lost list
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
                
    # 4. Plot for each range
    for label in range_labels:
        completely_lost_ixps = completely_lost_by_range.get(label, [])
        depeered_nonpeered_ixps = depeered_nonpeered_by_range.get(label, [])
        
        # Skip if both groups are empty
        if not completely_lost_ixps and not depeered_nonpeered_ixps:
            continue
        
        # Calculate de-peering events: when each IXP goes from non-peered to completely lost
        depeering_event_timelines = {}
        for ixp_id in depeered_nonpeered_ixps:
            ixp_id_str = str(ixp_id)
            if ixp_id_str in depeered_nonpeered_timeline_data:
                event_timeline = []
                for i in range(len(dates)):
                    # Event occurs when transitioning from >0 to 0 connections
                    has_connections_now = depeered_nonpeered_timeline_data[ixp_id_str][i] > 0 if i < len(depeered_nonpeered_timeline_data[ixp_id_str]) else False
                    had_connections_before = depeered_nonpeered_timeline_data[ixp_id_str][i-1] > 0 if i > 0 and i-1 < len(depeered_nonpeered_timeline_data[ixp_id_str]) else True
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
