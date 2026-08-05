

from pathlib import Path
import re
import sys
import matplotlib.pyplot as plt
from collections import defaultdict, Counter


sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.caidapeeringdb.caidapeeringdb_load import get_all_data, get_data, get_unique_ixps_from_data_list
from src.caidapeeringdb.main import build_asn_ixp_data_structures, load_timeline_data
from src.utils.graphs import plot_lists_as_plot_list_with_multiple_lines


def plot_top_depeering_as_ixps_combined_timeline(
    all_data, all_files, start_date, end_date, ignore_n_percent_biggest_ixps=None, top_asn_n=1
):
    """
    Finds the AS with the most de-peerings, identifies the IXPs it left,
    and plots the aggregated member metrics across all those IXPs combined over time.
    Allows filtering out the largest N% of IXPs by member count to avoid skewing data.
    """
     
    # --- STEP 1: Find the AS with the most Route Server losses ---
    file_date_pattern = re.compile(r"peeringdb_2_dump_(.*?)\.json")
    file_by_date = {}
    dates = []
    
    for file in all_files:
        match = file_date_pattern.search(file)
        if match:
            dt = match.group(1)
             
            file_by_date[dt] = file
            dates.append(dt)
            
    dates.sort()
    
    start_snapshot = all_data[0] if start_date not in file_by_date else get_data(file_by_date[start_date])
    end_snapshot = all_data[-1] if end_date not in file_by_date else get_data(file_by_date[end_date])
    
    def _get_rs_asns_per_ixp(snapshot_data):
        conns = snapshot_data.get("netixlan", {}).get("data", [])
        ixp_to_asns = defaultdict(set)
        for conn in conns:
            if conn.get("is_rs_peer", False):
                ix_id = conn.get("ix_id")
                asn = conn.get("asn") or conn.get("local_asn")
                if ix_id and asn:
                    ixp_to_asns[ix_id].add(asn)
        return ixp_to_asns

    start_ixp_asns = _get_rs_asns_per_ixp(start_snapshot)
    end_ixp_asns = _get_rs_asns_per_ixp(end_snapshot)
    
    asn_losses = Counter()
    for ix_id, baseline_asns in start_ixp_asns.items():
        current_asns = end_ixp_asns.get(ix_id, set())
        dropped_asns = baseline_asns - current_asns
        for asn in dropped_asns:
            asn_losses[asn] += 1
            
    if not asn_losses:
        print("No de-peering events found between the given dates.")
        return
         
    top_asn, loss_count = asn_losses.most_common(top_asn_n)[top_asn_n - 1]
    print(f"Targeting top de-peering network: AS{top_asn} (Lost {loss_count} Route Server sessions)")

    # --- STEP 2: Isolate the exact IXPs that AS{top_asn} dropped ---
    depeered_ixp_ids = set()
    for ix_id, baseline_asns in start_ixp_asns.items():
        if top_asn in baseline_asns and top_asn not in end_ixp_asns.get(ix_id, set()):
            depeered_ixp_ids.add(ix_id)

    # --- NEW: Filter out the largest IXPs if requested ---
    if ignore_n_percent_biggest_ixps is not None:
        # Calculate global size of ALL IXPs in the baseline snapshot to find the threshold
        ixp_member_counts = Counter()
        for conn in start_snapshot.get("netixlan", {}).get("data", []):
            ix_id = conn.get("ix_id")
            if ix_id:
                ixp_member_counts[ix_id] += 1
        
        if ixp_member_counts:
            # Sort IXPs by size (largest first)
            sorted_ixps = [ix_id for ix_id, _ in ixp_member_counts.most_common()]
            
            # Determine how many IXPs make up the top N%
            cutoff_index = int(len(sorted_ixps) * (ignore_n_percent_biggest_ixps / 100.0))
            ixps_to_ignore = set(sorted_ixps[:cutoff_index])
            
            # Filter our target list
            before_count = len(depeered_ixp_ids)
            depeered_ixp_ids = depeered_ixp_ids - ixps_to_ignore
            print(f"Filtered out {before_count - len(depeered_ixp_ids)} IXPs belonging to the top {ignore_n_percent_biggest_ixps}% largest global IXPs.")
            print(f"Remaining IXPs to analyze after filtering: {len(depeered_ixp_ids)}, from the original {before_count}.")
    print(f"Aggregating data metrics across {len(depeered_ixp_ids)} affected IXPs: {list(depeered_ixp_ids)}")
    
    if not depeered_ixp_ids:
        print("No IXPs left to plot after filtering.")
        return

    # --- STEP 3: Gather aggregated member statistics over the entire timeline ---
    rs_total_timeline = []
    non_rs_total_timeline = []
    unique_total_timeline = []

    for data in all_data:
        global_rs_sessions = set()
        global_non_rs_sessions = set()
        
        for conn in data.get("netixlan", {}).get("data", []):
            ix_id = conn.get("ix_id")
            if ix_id not in depeered_ixp_ids:
                continue
                
            asn = conn.get("asn") or conn.get("local_asn")
            if not asn:
                continue
                
            session_key = (ix_id, asn)
            if conn.get("is_rs_peer", False):
                global_rs_sessions.add(session_key)
            else:
                global_non_rs_sessions.add(session_key)
                
        global_non_rs_sessions.difference_update(global_rs_sessions)
        unique_asns_at_group = {asn for (_, asn) in (global_rs_sessions | global_non_rs_sessions)}
        
        rs_total_timeline.append(len(global_rs_sessions))
        non_rs_total_timeline.append(len(global_non_rs_sessions))
        unique_total_timeline.append(len(unique_asns_at_group))

    lines_payload = [
        {"data": rs_total_timeline, "label": "Total Route Server Peers", "color": "tab:green"},
        {"data": non_rs_total_timeline, "label": "Total Non-Route Server Peers", "color": "tab:orange"},
        {"data": unique_total_timeline, "label": "Total Distinct AS Networks", "color": "tab:blue", "linestyle": "--"}
    ]

    filter_str = f"- Filtered to Exclude Top {ignore_n_percent_biggest_ixps}% Largest IXPs" if ignore_n_percent_biggest_ixps is not None and ignore_n_percent_biggest_ixps > 0 else ""
    plot_lists_as_plot_list_with_multiple_lines(
        lines_data=lines_payload,
        x_labels=dates,
        title=f"Aggregated Member Info for IXPs Lost by AS{top_asn} Over Time {filter_str}",
        xlabel="Timeline Snapshot Dates",
        ylabel="Combined Absolute Member Sessions Count",
        subfolder="peeringdb_connections/grouped",
        use_rotated_labels=True
    )

def plot_depeered_rs_sessions_by_region_timeline(
    all_data, all_files, data_structures, asn_to_analyze, start_date, end_date
):
    """
    Plots only the Route Server connections over time for the aggregated IXPs 
    that were de-peered by a specific AS, split into separate lines per region/continent.
    Ignores regions containing fewer than 3 de-peered IXPs.
    """
    # --- STEP 1: Parse and sort the dates ---
    file_date_pattern = re.compile(r"peeringdb_2_dump_(.*?)\.json")
    dates = []
    for file in all_files:
        match = file_date_pattern.search(file)
        if match:
            dates.append(match.group(1))
    dates.sort()

    # --- STEP 2: Identify target IXPs and map them to their continents ---
    depeered_ixp_ids = data_structures.get("depeered_ixp_ids", set())
    continent_to_ixps = data_structures.get("continent_to_ixps_map", {})

    if not depeered_ixp_ids:
        print(f"No de-peered IXPs found for AS{asn_to_analyze} to track over the timeline.")
        return

    # Count how many de-peered IXPs fall into each region first
    region_ixp_counts = Counter()
    ixp_to_continent_raw = {}
    for continent, ix_list in continent_to_ixps.items():
        for ix_id in ix_list:
            if ix_id in depeered_ixp_ids:
                ixp_to_continent_raw[ix_id] = continent
                region_ixp_counts[continent] += 1

    # --- NEW FILTER: Filter out regions with fewer than 3 IXPs ---
    ixp_to_continent = {}
    ignored_regions = []
    
    for ix_id, continent in ixp_to_continent_raw.items():
        if region_ixp_counts[continent] >= 3:
            ixp_to_continent[ix_id] = continent
        else:
            if continent not in ignored_regions:
                ignored_regions.append(continent)

    if ignored_regions:
        print(f"Ignored regions due to < 3 member IXPs: {ignored_regions}")

    active_regions = set(ixp_to_continent.values())
    if not active_regions:
        print("No regions left to plot after applying the minimum threshold of 3 IXPs.")
        return

    print(f"Tracking Route Server sessions across {len(ixp_to_continent)} IXPs in active regions: {list(active_regions)}")

    # --- STEP 3: Gather RS timeline data per continent ---
    region_timelines = defaultdict(list)

    for data in all_data:
        current_snapshot_counts = Counter()
        
        for conn in data.get("netixlan", {}).get("data", []):
            ix_id = conn.get("ix_id")
            
            # This implicitly filters out both non-target IXPs AND ignored regions
            if ix_id in ixp_to_continent and conn.get("is_rs_peer", False):
                asn = conn.get("asn") or conn.get("local_asn")
                if asn:
                    continent = ixp_to_continent[ix_id]
                    current_snapshot_counts[continent] += 1

        # Append the counts for this snapshot to the timelines
        for region in active_regions:
            region_timelines[region].append(current_snapshot_counts[region])

    # --- STEP 4: Format payload for the plotting utility ---
    lines_payload = []
    
    # Updated color mapping to reflect full names found in your logs
    color_map = {
        "North America": "tab:blue", 
        "Europe": "tab:orange", 
        "Asia Pacific": "tab:green", 
        "South America": "tab:red", 
        "Africa": "tab:purple", 
        "Australia": "tab:brown",
        "Middle East": "tab:pink"
    }

    for region, timeline_data in region_timelines.items():
        lines_payload.append({
            "data": timeline_data,
            "label": f"RS Peers in {region}",
            "color": color_map.get(region, None)
        })

    lines_payload.sort(key=lambda x: x["label"])

    # --- STEP 5: Plot the data ---
    plot_lists_as_plot_list_with_multiple_lines(
        lines_data=lines_payload,
        x_labels=dates,
        title=f"Route Server Connections Over Time on IXPs De-peered by AS{asn_to_analyze}",
        xlabel="Snapshot Dates",
        ylabel="Route Server Connections Count",
        subfolder="peeringdb_connections",
        use_rotated_labels=True
    )

if __name__ == "__main__":
    config_path = str(Path(__file__).parent)
    all_files_before_depeering, all_files_after_depeering = load_timeline_data(config_path)
    all_files = all_files_before_depeering + all_files_after_depeering
    

    all_files = [file for file in all_files if "2024_05_01" not in file and "2025_02_01" not in file]

    start_date = "2024_01_01"
    end_date = "2026_05_01"
    all_files = [file for file in all_files if start_date <= file.split('peeringdb_2_dump_')[1].split('.json')[0] <= end_date]
    all_data = get_all_data(all_files)
    

    asn_to_analyze = 396986 

    before_data = get_data(all_files[0])   
    after_data = get_data(all_files[-1])
    print(f"Using date range from {all_files[0]} to {all_files[-1]} for analysis.")

    all_ixps = get_unique_ixps_from_data_list([after_data])
     
    data_structures = build_asn_ixp_data_structures(asn_to_analyze, before_data, after_data, 
                                                    all_ixps)
    plot_depeered_rs_sessions_by_region_timeline(all_data, all_files, data_structures=data_structures, asn_to_analyze=asn_to_analyze, start_date=start_date, end_date=end_date)

    sys.exit(0)
    plot_top_depeering_as_ixps_combined_timeline(all_data, all_files, start_date=start_date, end_date=end_date,
                                                 ignore_n_percent_biggest_ixps=0,
                                                 top_asn_n=3) 