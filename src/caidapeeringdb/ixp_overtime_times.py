import re
import numpy as np
from datetime import datetime
from src.caidapeeringdb.utils import PEERINGDB_SUBFOLDER_PREFIX
from src.caidapeeringdb.ixp_overtime import plot_ixp_connections_over_time_by_category

DEFAULT_TIME_RANGE_THRESHOLDS = [30, 90, 180, 365, 365*2, 365*3, 365*4]

def plot_ixp_connections_over_time_by_age_ranges(all_data, all_files, depeered_ixp_ids, asn_to_analyze, 
                                                  depeered_completely_lost_ixp_ids=None, depeered_with_nonpeered_ixp_ids=None,
                                                  time_range_thresholds=None):
    """
    Plots the number of connections over time for IXPs that were de-peered, 
    grouped by their age ranges (how long connections have been in the IXP).
    
    Args:
        all_data: List of PeeringDB data snapshots (dicts)
        all_files: List of filenames corresponding to all_data (to extract dates)
        depeered_ixp_ids: Set of IXP IDs that were de-peered
        asn_to_analyze: The ASN that de-peered
        depeered_completely_lost_ixp_ids: Set of de-peered IXPs with no connections after de-peering
        depeered_with_nonpeered_ixp_ids: Set of de-peered IXPs that still have non-peered connections
        time_range_thresholds: Thresholds for grouping connections by age (in days)
    """
    if time_range_thresholds is None:
        time_range_thresholds = DEFAULT_TIME_RANGE_THRESHOLDS
    
    if depeered_completely_lost_ixp_ids is None:
        depeered_completely_lost_ixp_ids = set()
    if depeered_with_nonpeered_ixp_ids is None:
        depeered_with_nonpeered_ixp_ids = set()
    
    # 1. Generate time range labels
    range_labels = []
    lower = 0
    for threshold in time_range_thresholds:
        range_labels.append(f"{lower}-{threshold}d")
        lower = threshold
    range_labels.append(f"{lower}+d")
    
    # 2. Extract dates from filenames
    dates = []
    snapshot_dates = []  # Store as datetime objects for age calculation
    for file in all_files:
        match = re.search(r"peeringdb_2_dump_(.*?)\.json", file)
        if match:
            date_str = match.group(1)
            dates.append(date_str)
            try:
                snapshot_dates.append(datetime.strptime(date_str, "%Y-%m-%d"))
            except:
                snapshot_dates.append(None)
        else:
            dates.append("unknown")
            snapshot_dates.append(None)
    
    # 3. Group de-peered IXPs by their age at the first snapshot
    completely_lost_by_age_range = {label: [] for label in range_labels}
    with_nonpeered_by_age_range = {label: [] for label in range_labels}
    all_relevant_ixp_ids = set()
    
    # Find the first valid snapshot date
    first_snapshot_date = None
    first_valid_data_idx = 0
    for i, dt in enumerate(snapshot_dates):
        if dt is not None:
            first_snapshot_date = dt
            first_valid_data_idx = i
            break
    
    if first_snapshot_date is None:
        print(f"[DEBUG age_ranges] Cannot proceed - no valid snapshot dates found")
        print(f"[DEBUG age_ranges] snapshot_dates: {snapshot_dates}")
        print(f"[DEBUG age_ranges] all_files: {all_files}")
        return  # Cannot proceed without valid date
    
    print(f"[DEBUG age_ranges] First valid snapshot date: {first_snapshot_date} (index {first_valid_data_idx}), completely_lost: {len(depeered_completely_lost_ixp_ids)}, with_nonpeered: {len(depeered_with_nonpeered_ixp_ids)}")
    
    # Determine age of each de-peered IXP at first snapshot
    ixp_ages = {}  # ixp_id -> age_in_days
    for conn in all_data[first_valid_data_idx].get("netixlan", {}).get("data", []):
        ixp_id = conn.get("ix_id")
        if ixp_id not in depeered_ixp_ids:
            continue
        
        created_str = conn.get("created", "")
        if not created_str:
            continue
        
        try:
            created_date = datetime.strptime(created_str[:10], "%Y-%m-%d")
            age_days = (first_snapshot_date - created_date).days
            
            if ixp_id not in ixp_ages or age_days < ixp_ages[ixp_id]:
                ixp_ages[ixp_id] = age_days
        except:
            pass
    
    # Categorize completely lost IXPs by age range
    for ixp_id, age_days in ixp_ages.items():
        if ixp_id not in depeered_completely_lost_ixp_ids:
            continue
            
        categorized = False
        for i, threshold in enumerate(time_range_thresholds):
            if age_days <= threshold:
                completely_lost_by_age_range[range_labels[i]].append(ixp_id)
                all_relevant_ixp_ids.add(str(ixp_id))
                categorized = True
                break
        if not categorized:
            completely_lost_by_age_range[range_labels[-1]].append(ixp_id)
            all_relevant_ixp_ids.add(str(ixp_id))
    
    # Categorize with-nonpeered IXPs by age range
    for ixp_id, age_days in ixp_ages.items():
        if ixp_id not in depeered_with_nonpeered_ixp_ids:
            continue
            
        categorized = False
        for i, threshold in enumerate(time_range_thresholds):
            if age_days <= threshold:
                with_nonpeered_by_age_range[range_labels[i]].append(ixp_id)
                all_relevant_ixp_ids.add(str(ixp_id))
                categorized = True
                break
        if not categorized:
            with_nonpeered_by_age_range[range_labels[-1]].append(ixp_id)
            all_relevant_ixp_ids.add(str(ixp_id))
    
    print(f"[DEBUG age_ranges] Total IXPs with age data: {len(ixp_ages)}, categorized: {len(all_relevant_ixp_ids)}")
    
    # 4. Collect connections over time for both groups
    timeline_data = {str(ixp_id): [] for ixp_id in all_relevant_ixp_ids}
    
    for idx, data in enumerate(all_data):
        ixp_counts = {str(ixp_id): 0 for ixp_id in all_relevant_ixp_ids}
        
        for conn in data.get("netixlan", {}).get("data", []):
            ixp_id = str(conn.get("ix_id"))
            if ixp_id in all_relevant_ixp_ids:
                ixp_counts[ixp_id] += 1
        
        for ixp_id, count in ixp_counts.items():
            timeline_data[ixp_id].append(count)
    
    # 5. Plot for each age range
    plots_generated = 0
    for label in range_labels:
        completely_lost_ixps = completely_lost_by_age_range[label]
        with_nonpeered_ixps = with_nonpeered_by_age_range[label]
        
        if not completely_lost_ixps and not with_nonpeered_ixps:
            continue
        
        # Calculate de-peering events: when each IXP goes from non-peered to completely lost
        depeering_event_timelines = {}
        for ixp_id in with_nonpeered_ixps:
            ixp_id_str = str(ixp_id)
            if ixp_id_str in timeline_data:
                event_timeline = []
                for i in range(len(dates)):
                    # Event occurs when transitioning from >0 to 0 connections
                    has_connections_now = timeline_data[ixp_id_str][i] > 0 if i < len(timeline_data[ixp_id_str]) else False
                    had_connections_before = timeline_data[ixp_id_str][i-1] > 0 if i > 0 and i-1 < len(timeline_data[ixp_id_str]) else True
                    event_timeline.append(had_connections_before and not has_connections_now)
                depeering_event_timelines[ixp_id_str] = event_timeline
        
        plots_generated += 1
        plot_ixp_connections_over_time_by_category(
            dates=dates,
            timeline_data=timeline_data,
            completely_lost_ixp_ids=completely_lost_ixps,
            depeered_nonpeered_ixp_ids=with_nonpeered_ixps,
            completely_lost_timeline_data=timeline_data,
            depeered_nonpeered_timeline_data=timeline_data,
            category_label=label,
            category_type="Age Range",
            asn_to_analyze=asn_to_analyze,
            plot_name_suffix=f"age_range_{label}",
            depeering_event_timelines=depeering_event_timelines
        )
    print(f"[DEBUG age_ranges] Generated {plots_generated} plots")
