"""Main orchestration for PeeringDB analysis."""
import datetime
import json
import sys
from pathlib import Path
from collections import defaultdict
import numpy as np


sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.caidapeeringdb.utils import COMPLETELY_LOST_LABEL, DEPEERED_IXPS_YLABEL, PEERINGDB_SUBFOLDER_PREFIX, PLOT_COLORS, STILL_CONNECTED_LABEL

from src.caidapeeringdb.ixp_times import get_ixp_connections_time_delta, plot_time_in_ixp_distribution
from src.caidapeeringdb.ixp_overtime_size import plot_ixp_connections_over_time_by_size_ranges
from src.caidapeeringdb.ixp_overtime_region import plot_ixp_connections_over_time_by_region
from src.caidapeeringdb.ixp_overtime_times import plot_ixp_connections_over_time_by_age_ranges
from src.utils.graphs import plot_stacked_bar_plot
from src.caidapeeringdb.ixp_size import analyze_depeering_by_size_ranges, get_largest_ixps_per_continent_of_an_asn, plot_ixp_size_ranges_by_percentage_of_total_loss_connections, plot_ixps_by_size_ranges
from src.caidapeeringdb.loaders import load_all_files, config
 
from src.caidapeeringdb.asns import plot_asns_analysis
from src.caidapeeringdb.caidapeeringdb_load import get_all_data, get_data, get_unique_ixps_from_data_list, get_connections_for_ixp, load_connections_over_time_for_asns
from src.caidapeeringdb.continent_logic import get_continent_for_ixp, get_data_structures_excluding_continent

group_focused = config.get("group_focused")

asns_to_search = [tuple(asn) for asn in config.get("asns_to_search", [])]
asns_to_search = [asn for asn in asns_to_search if group_focused in asn[2] or group_focused is None]


def load_earliest_data(config_path):

    with open(config_path + "/config_earliest_snapshots_timeline.json", 'r') as f:
        config_earliest_snapshots_timeline = json.load(f)
    
    all_files_earliest = load_all_files(config_earliest_snapshots_timeline)
    
    return all_files_earliest

def load_timeline_data(config_path):
    """Load before and after depeering timeline data.
    
    Args:
        config_path: Path to config directory
        
    Returns:
        tuple: (all_files_before_depeering, all_files_after_depeering)
    """
    with open(config_path + "/config_google_before_depeering_timeline.json", 'r') as f:
        config_google_before_depeering = json.load(f)
    with open(config_path + "/config_google_after_depeering_timeline.json", 'r') as f:
        config_google_after_depeering = json.load(f)
    
    all_files_before_depeering = load_all_files(config_google_before_depeering)
    all_files_after_depeering = load_all_files(config_google_after_depeering) 
    
    return all_files_before_depeering, all_files_after_depeering


def build_asn_ixp_data_structures(asn_to_analyze, before_data, after_data, all_ixps):
    # 1. Create a lookup map for IXPs immediately
    # This turns O(N) searches into O(1) lookups
    ixp_lookup = {ixp["id"]: ixp for ixp in all_ixps}
    
    # 2. Process 'before' data efficiently
    before_peered_ixp_ids = {
        conn.get("ix_id") for conn in before_data.get("netixlan", {}).get("data", [])
        if (conn.get("asn") == asn_to_analyze or conn.get("local_asn") == asn_to_analyze)
        and conn.get("is_rs_peer", False)
    }
    
    # 3. Process 'after' data in a SINGLE pass
    all_asn_connections = []
    current_peered_ixp_ids = set()
    not_peered_ixp_ids = set()
    asn_ixp_connections_by_continent = defaultdict(lambda: defaultdict(int))

    after_raw_data = after_data.get("netixlan", {}).get("data", [])
    for conn in after_raw_data:
        asn = conn.get("asn")
        local_asn = conn.get("local_asn")
        
        if asn == asn_to_analyze or local_asn == asn_to_analyze:
            all_asn_connections.append(conn)
            ixp_id = conn.get("ix_id")
            
            # Categorize by peering status
            if conn.get("is_rs_peer", False):
                current_peered_ixp_ids.add(ixp_id)
            else:
                not_peered_ixp_ids.add(ixp_id)
            
            # Update continent counts using our lookup map
            ixp_info = ixp_lookup.get(ixp_id)
            continent = get_continent_for_ixp(ixp_id, ixp_info)
            asn_ixp_connections_by_continent[continent][ixp_id] += 1

    # 4. Build the continent_to_ixps_map efficiently
    continent_to_ixps_map = defaultdict(list)
    for ixp_id, ixp_info in ixp_lookup.items():
        continent = get_continent_for_ixp(ixp_id, ixp_info)
        continent_to_ixps_map[continent].append(ixp_id)

    # 5. Set logic (remains efficient as is)
    current_all_ixp_ids = {conn.get("ix_id") for conn in all_asn_connections}
    depeered_ixp_ids = before_peered_ixp_ids - current_peered_ixp_ids
    completely_lost_ixp_ids = before_peered_ixp_ids - current_all_ixp_ids
    depeered_with_nonpeered_ixp_ids = depeered_ixp_ids & not_peered_ixp_ids
    
    return {
        "before_peered_ixp_ids": before_peered_ixp_ids,
        "current_peered_ixp_ids": current_peered_ixp_ids,
        "not_peered_ixp_ids": not_peered_ixp_ids,
        "depeered_ixp_ids": depeered_ixp_ids,
        "completely_lost_ixp_ids": completely_lost_ixp_ids,
        "depeered_with_nonpeered_ixp_ids": depeered_with_nonpeered_ixp_ids,
        "asn_ixp_connections_by_continent": dict(asn_ixp_connections_by_continent),
        "continent_to_ixps_map": dict(continent_to_ixps_map),
        "all_asn_connections": all_asn_connections,
    }


def print_depeering_summary(asn_to_analyze, data_structures):
    """Print summary statistics of de-peering for an ASN.
    
    Args:
        asn_to_analyze: ASN number
        data_structures: Dict from build_asn_ixp_data_structures()
    """
    before_peered = data_structures["before_peered_ixp_ids"]
    current_peered = data_structures["current_peered_ixp_ids"]
    depeered = data_structures["depeered_ixp_ids"]
    depeered_with_nonpeered = data_structures["depeered_with_nonpeered_ixp_ids"]
    completely_lost = data_structures["completely_lost_ixp_ids"]
    
    print(f"\nASN {asn_to_analyze} De-Peering Analysis:")
    print(f"IXPs peered BEFORE de-peering (Jan-Apr 2024): {len(before_peered)}")
    print(f"IXPs peered AFTER de-peering (May 2026): {len(current_peered)}")
    print(f"IXPs de-peered (lost peering): {len(depeered)}")
    print(f"  - Still connected via non-peered: {len(depeered_with_nonpeered)}")
    print(f"  - Completely lost (no connections): {len(completely_lost)}")



def find_depeering_index_for_ixp(ixp_id, all_data, with_asn,
                                 losing_rs_counts_as_lost_peering=True):
   
    peering_status_timeline = []
    
    for i, data in enumerate(all_data):
        conns = get_connections_for_ixp(ixp_id, data, key="netixlan", connections_should_be="all")
        
        if losing_rs_counts_as_lost_peering:
            # Count loss of any connection as de-peering
            asn_has_connection = any(
                (conn.get("asn") == with_asn or conn.get("local_asn") == with_asn)
                for conn in conns
            )
            connection_status = asn_has_connection
        else:
            # Only count loss of route server peering as de-peering
            asn_peered = any(
                (conn.get("asn") == with_asn or conn.get("local_asn") == with_asn) and conn.get("is_rs_peer", False)
                for conn in conns
            )
            connection_status = asn_peered
        
        peering_status_timeline.append((i, connection_status))
    
    # Find the transition point where peering was lost
    for j in range(1, len(peering_status_timeline)):
        if peering_status_timeline[j-1][1] and not peering_status_timeline[j][1]:  # Was peered, now not
            return j - 1  # Return index right before de-peering
    
    return None



# if all_data and with_asn exists, it will try to get the IXP size 
# right before de-peering. Otherwise, it will use the data snapshot "before_data"
def get_depeered_ixp_sizes(depeered_ixp_ids, before_data, all_data=None,
                           with_asn=None):
     
    depeered_ixp_sizes = {}
    
    number_of_times_exact_point_was_found = 0
    number_of_times_exact_point_was_not_found = 0
    
    # If we have all_data and with_asn, find the exact point of de-peering for each IXP
    if all_data and with_asn:

        number_of_depeers_over_time = [0] * len(all_data)  # for debugging purposes


        # Build a mapping of IXP ID to the data snapshot right before de-peering
        ixp_to_depeering_data = {}
        
        for ixp_id in depeered_ixp_ids:
            depeering_index = find_depeering_index_for_ixp(ixp_id, all_data, with_asn)
            
            #number_of_depeers_over_time[depeering_index] += 1 if depeering_index is not None else 0
            if depeering_index is not None:
                ixp_to_depeering_data[ixp_id] = all_data[depeering_index]
                number_of_times_exact_point_was_found += 1
            else:
                # Fallback to before_data if we can't find exact point
                ixp_to_depeering_data[ixp_id] = before_data
                number_of_times_exact_point_was_not_found += 1
        
        # Get sizes from the appropriate data snapshot for each IXP
        for ixp_id in depeered_ixp_ids:
            data_snapshot = ixp_to_depeering_data.get(ixp_id, before_data)
            ixp_conns = get_connections_for_ixp(ixp_id, data_snapshot, key="netixlan", connections_should_be="peered")
            depeered_ixp_sizes[ixp_id] = len(ixp_conns)
    else:
        # Use before_data as before
        for ixp_id in depeered_ixp_ids:
            ixp_conns = get_connections_for_ixp(ixp_id, before_data, key="netixlan", connections_should_be="peered")
            depeered_ixp_sizes[ixp_id] = len(ixp_conns)
    
    print(f"Exact de-peering point found for {number_of_times_exact_point_was_found} IXPs, not found for {number_of_times_exact_point_was_not_found} IXPs (used before_data as fallback)")
    print(f"Number of de-peering events over time (by data snapshot index): {number_of_depeers_over_time}")
    return depeered_ixp_sizes



if __name__ == "__main__":

    config_path = str(Path(__file__).parent)
    
    # Load timeline data
    all_files_before_depeering, all_files_after_depeering = load_timeline_data(config_path)
    all_files = all_files_before_depeering + all_files_after_depeering

    all_files_in_depeering_event_but_focused_ones = all_files_before_depeering + all_files_after_depeering#[0:3]

    # Get data snapshots
    before_data = get_data(all_files_before_depeering[-1])
    after_data = get_data(all_files_after_depeering[-1])
    
    asns_to_search_for_analysis = [asns_to_search[0]] # Get the ASN to analyze
    asn_to_analyze = asns_to_search_for_analysis[0][0]  # Get the ASN number from tuple


    print(f"Analyzing ASN {asn_to_analyze} ({asns_to_search_for_analysis[0][1]})")
    #all_ixps = get_unique_ixps_from_data_list([after_data])
    

    # Get IXP distribution by continent
    #ixp_by_continent_count, ixp_by_continent_count_percentage, _ = get_ixps_by_continent_count(all_files_after_depeering)

    # Plot IXP distribution
    #plot_ixps_distribution_by_continent(ixp_by_continent_count_percentage)
 
    plot_asns_analysis(all_files_in_depeering_event_but_focused_ones, asns_to_search_for_analysis, None)
     
    sys.exit(0)
    #plot_asns_analysis(all_files_after_depeering, asns_to_search_for_analysis, ixp_by_continent_count)
    
    
   
    # Build data structures for analysis
    data_structures = build_asn_ixp_data_structures(asn_to_analyze, before_data, after_data, all_ixps)
    
    # Print summary statistics
    #print_depeering_summary(asn_to_analyze, data_structures)
    
    # Analyze and plot by continent
    #analyze_depeering_by_continent(data_structures, asn_to_analyze, all_ixps)
    
    depeered_ixp_ids: set[str] = data_structures["depeered_ixp_ids"]
    depeered_completely_lost_ixp_ids: set[str] = data_structures["completely_lost_ixp_ids"]
    if False:
        #conns = before_data.get("netixlan", {}).get("data", [])
        
        from_field = "created"  
        conn_lists = [conn_tuple[1] for conn_tuple in load_connections_over_time_for_asns(
            [all_files_before_depeering[-1]],
            asns_to_search_for_analysis,
                connections_should_be="peered"
        )[asn_to_analyze]]

        conns = [conn for sublist in conn_lists for conn in sublist]

        print("conns found:", len(conns)) 

        time_deltas_for_connections = get_ixp_connections_time_delta(conns,
                                                                     current_date=datetime.datetime(2024, 4, 1),
                                                                from_field=from_field)

        plot_time_in_ixp_distribution(asn_to_analyze, time_deltas_for_connections, from_field=from_field)

        depeered_ixps_completely_lost_by_time_in_ixp = {ixp_id: time_deltas_for_connections.get(str(ixp_id), None)
                                      for ixp_id in depeered_completely_lost_ixp_ids}
        
        plot_time_in_ixp_distribution(asn_to_analyze, depeered_ixps_completely_lost_by_time_in_ixp, from_field=from_field,
                                      title_suffix="(Only IXPs that were completely lost later)")

        sys.exit(0) 


    def ixp_sizes_analysis():
        all_data = get_all_data(all_files_before_depeering) + get_all_data(all_files_after_depeering)
        
        depeered_ixp_sizes = get_depeered_ixp_sizes(depeered_ixp_ids, after_data,
                                                    all_data=all_data, with_asn=asn_to_analyze)
        # Analyze and plot by size percentiles
        #analyze_depeering_by_percentiles(data_structures, depeered_ixp_sizes, asn_to_analyze)
        

        
        

        all_files = all_files_before_depeering + all_files_after_depeering
        completely_lost_ixp_ids = data_structures["completely_lost_ixp_ids"]
        depeered_with_nonpeered_ixp_ids = data_structures["depeered_with_nonpeered_ixp_ids"]
        
        # Plot IXP connections over time with de-peering events
        plot_ixp_connections_over_time_by_size_ranges(all_data, all_files, depeered_ixp_ids, depeered_ixp_sizes, asn_to_analyze, 
                                                     completely_lost_ixp_ids=completely_lost_ixp_ids,
                                                     depeered_with_nonpeered_ixp_ids=depeered_with_nonpeered_ixp_ids)
        
        plot_ixp_connections_over_time_by_region(all_data, all_files, depeered_ixp_ids, asn_to_analyze, all_ixps,
                                            depeered_completely_lost_ixp_ids=completely_lost_ixp_ids,
                                            depeered_with_nonpeered_ixp_ids=depeered_with_nonpeered_ixp_ids)
        
        plot_ixp_connections_over_time_by_age_ranges(all_data, all_files, depeered_ixp_ids, asn_to_analyze,
                                                     depeered_completely_lost_ixp_ids=completely_lost_ixp_ids,
                                                     depeered_with_nonpeered_ixp_ids=depeered_with_nonpeered_ixp_ids)  
     
    ixp_sizes_analysis() 
