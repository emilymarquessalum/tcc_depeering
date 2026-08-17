"""Main orchestration for PeeringDB analysis."""
import datetime
import json
import sys
from pathlib import Path
from collections import defaultdict
import numpy as np



sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.caidapeeringdb.grouped_asns import get_ixps_by_continent_count
from src.caidapeeringdb.ixp_overtime import plot_ixps_connections_over_time
from src.utils.user_input import choose_option, confirm_action, finish_actions, start_actions

from src.caidapeeringdb.ixp_features.ixp_over_time_never_connected import plot_ixp_connections_over_time_for_ixps_that_never_connected_to_ases
#from src.google.vpps.vpp_ixps import get_all_vpps_whose_name_matches_an_ixp_name, get_vpps_list



from src.caidapeeringdb.ixp_region import analyze_depeering_by_continent
from src.caidapeeringdb.utils import COMPLETELY_LOST_LABEL, DEPEERED_IXPS_YLABEL, PEERINGDB_SUBFOLDER_PREFIX, PLOT_COLORS, STILL_CONNECTED_LABEL

from src.caidapeeringdb.ixp_times import get_ixp_connections_time_delta, plot_time_in_ixp_distribution
from src.caidapeeringdb.ixp_features.ixp_overtime_size import plot_ixp_connections_over_time_by_size_ranges
from src.caidapeeringdb.ixp_features.ixp_overtime_region import plot_ixp_connections_over_time_by_region
from src.caidapeeringdb.ixp_features.ixp_overtime_times import plot_ixp_connections_over_time_by_age_ranges
from src.utils.graphs import plot_stacked_bar_plot
from src.caidapeeringdb.ixp_size import analyze_depeering_by_size_ranges, get_largest_ixps_per_continent_of_an_asn, plot_ixp_size_ranges_by_percentage_of_total_loss_connections, plot_ixps_by_size_ranges
from src.caidapeeringdb.loaders import load_all_files, config
 
from src.caidapeeringdb.asns import plot_asns_analysis
from src.caidapeeringdb.caidapeeringdb_load import get_all_data, get_all_files, get_all_ixps, get_connections_for_ixp_over_time, get_data, get_unique_ixps_from_data_list, get_connections_for_ixp, load_connections_over_time_for_asns
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


 
def get_all_content_providers_asns(asns_to_search):
    """Get all ASNs that are content providers based on the config."""
    content_provider_asns = []
    for asn_tuple in asns_to_search:
        asn, name, categories = asn_tuple
        if "ICP" in categories:
            content_provider_asns.append(asn_tuple)
    return content_provider_asns


def get_depeerings_from_connections_over_time(connections_over_time):

    depeerings = []
    for i in range(1, len(connections_over_time)):
        prev_connections = connections_over_time[i-1][1]
        curr_connections = connections_over_time[i][1]
        
        # Check if any previously peered connection is now lost
        lost_connections = [conn for conn in prev_connections if conn not in curr_connections]
        
        if lost_connections:
            depeerings.append((i, lost_connections))

    return depeerings


def find_ixps_that_were_individually_depeered_from_content_providers(all_files, asns_to_search):

    print(asns_to_search)
    content_providers = get_all_content_providers_asns(asns_to_search)

    connections_over_time_for_asns = load_connections_over_time_for_asns(all_files=all_files, asns_to_search=content_providers, connections_should_be="peered")

    individual_depeerings_by_asn = {}
    individual_depeerings_by_year = {}
    for content_provider in content_providers:

        connections_over_time = connections_over_time_for_asns.get(content_provider[0], [])

        depeerings_over_time = get_depeerings_from_connections_over_time(connections_over_time)

        if depeerings_over_time:
            all_individual_depeerings = []

            for depeering in depeerings_over_time:

                date_from_depeering = all_files[depeering[0]].split("/")[-1].split(".")[0]  # Extract date from filename
                if len(depeering[1]) == 1:  # Only consider single IXP depeerings
                    connection = depeering[1][0]
                    all_individual_depeerings.append((date_from_depeering, connection['name'], connection['ix_id']))  # Store date and lost connection
                    individual_depeerings_by_year[date_from_depeering] = all_individual_depeerings
                    individual_depeerings_by_asn[content_provider[0]] = all_individual_depeerings

        print("For content provider ASN", content_provider[0], "(", content_provider[1], "):", len(all_individual_depeerings), "individual depeerings found.")
        print("Details of individual depeerings (data snapshot index, lost connection):", all_individual_depeerings)

    ixps_that_were_depeered_per_year = defaultdict(set)
    for date, lost_connections in individual_depeerings_by_year.items():
        for lost_connection in lost_connections:
            ixps_that_were_depeered_per_year[date].add(lost_connection[2])  

    for year in sorted(ixps_that_were_depeered_per_year.keys()):
        plot_ixps_connections_over_time(
        all_data=get_all_data(all_files),
        dates=[file.split("/")[-1].split(".")[0] for file in all_files],
        ixp_ids=ixps_that_were_depeered_per_year[year],
        title_info="IXPs individually depeered from ICPs in " + year,
        )

def identify_dead_ixps(all_files, all_ixps) -> set[int]: 
    dead_ixps = set()

    all_data = get_all_data(all_files[-3:])  
    
    for ixp in all_ixps:
        ixp_id = ixp.get("id")
        connections_over_time = get_connections_for_ixp_over_time(
            ixp_id,
            all_data=all_data,
            connections_should_be="all"
        )
           
        if all(len(conns) == 0 for conns in connections_over_time):
            dead_ixps.add(ixp_id)

    return dead_ixps

def bview_analyze_depeering_by_continent(all_required_data):

    before_data = all_required_data["before_data_peeringdb"]
    after_data = all_required_data["after_data_peeringdb"]
    all_ixps = get_unique_ixps_from_data_list([before_data, after_data])


    asn_to_analyze = choose_option([asn[0] for asn in asns_to_search], "ASN to analyze", can_give_custom_text=True)
    
    data_structures = build_asn_ixp_data_structures(asn_to_analyze, before_data, after_data, all_ixps)

    analyze_depeering_by_continent(data_structures, asn_to_analyze, all_required_data["all_ixps"])


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



    #find_ixps_that_were_individually_depeered_from_content_providers(all_files, asns_to_search)
    #sys.exit(0)  

    print(f"Analyzing ASN {asn_to_analyze} ({asns_to_search_for_analysis[0][1]})") 
    all_ixps = get_unique_ixps_from_data_list([before_data, after_data])
    print(f"Total unique IXPs in both snapshots: {len(all_ixps)}")

    #print(f"Dead IXPs (no connections for >3 snapshots): {len(dead_ixps)}")
    #sys.exit(0)  


    # Get IXP distribution by continent
    ixp_by_continent_count, ixp_by_continent_count_percentage, _ = get_ixps_by_continent_count(all_files_after_depeering)

    # Plot IXP distribution
    #plot_ixps_distribution_by_continent(ixp_by_continent_count_percentage)
 
    start_actions()
    confirm_action("Plot asns analysis", lambda: plot_asns_analysis(all_files_in_depeering_event_but_focused_ones, asns_to_search_for_analysis, None))
     
    plot_asns_analysis(all_files_after_depeering, asns_to_search_for_analysis, ixp_by_continent_count)
    
    
   
    # Build data structures for analysis
    data_structures = build_asn_ixp_data_structures(asn_to_analyze, before_data, after_data, all_ixps)
    
    # Print summary statistics
    #print_depeering_summary(asn_to_analyze, data_structures)
    
    # Analyze and plot by continent

    confirm_action("Plot depeering by continent", 
                   lambda: analyze_depeering_by_continent(data_structures, asn_to_analyze, all_ixps))
        
  
    
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

    depeered_ixp_ids: set[str] = data_structures["depeered_ixp_ids"]
    depeered_completely_lost_ixp_ids: set[str] = data_structures["completely_lost_ixp_ids"]

    def ixps_features_analysis():
        all_data = get_all_data(all_files_before_depeering) + get_all_data(all_files_after_depeering)
        
        depeered_ixp_sizes = get_depeered_ixp_sizes(depeered_ixp_ids, after_data,
                                                    all_data=all_data, with_asn=asn_to_analyze)
        # Analyze and plot by size percentiles
        #analyze_depeering_by_percentiles(data_structures, depeered_ixp_sizes, asn_to_analyze)
        

        
        
        
        #depeered_ixp_ids
        #completely_lost_ixp_ids
        

                
        all_files = get_all_files()

        print(all_files[-1])
        data = get_data(all_files[-1])

        #vpps_list = get_vpps_list()
        #vpps, vpp_names_that_are_ixps, vpp_ixp_ids = get_all_vpps_whose_name_matches_an_ixp_name(vpps_list, get_all_ixps(data))
         


        all_files = all_files_before_depeering + all_files_after_depeering
        completely_lost_ixp_ids = data_structures["completely_lost_ixp_ids"]
        depeered_with_nonpeered_ixp_ids = data_structures["depeered_with_nonpeered_ixp_ids"]


        index_the_asn_analyzed_mass_depeered = None
        

        depeered_at_peak_ases_by_size_range = plot_ixp_connections_over_time_by_size_ranges(all_data, all_files, depeered_ixp_ids, depeered_ixp_sizes, asn_to_analyze, 
                                                             completely_lost_ixp_ids=completely_lost_ixp_ids,
                                                             ixp_names={ixp["id"]: ixp["name"] for ixp in all_ixps},
                                                             depeered_with_nonpeered_ixp_ids=depeered_with_nonpeered_ixp_ids)
         
            

        depeered_at_peak_ases_by_region = plot_ixp_connections_over_time_by_region(all_data, all_files, depeered_ixp_ids, asn_to_analyze, all_ixps,
                                            depeered_completely_lost_ixp_ids=completely_lost_ixp_ids,
                                            index_the_asn_analyzed_mass_depeered=index_the_asn_analyzed_mass_depeered,
                                            depeered_with_nonpeered_ixp_ids=depeered_with_nonpeered_ixp_ids)

        
        print("From the de-peered ASes in peaks of de-peering by region and size range, how much % of ASes show up in more than one IXP?")
        percentage_of_ases_in_multiple_ixps_by_size_range = {}

        all_depeered_ases_lists = list(depeered_at_peak_ases_by_size_range.values()) + list(depeered_at_peak_ases_by_region.values())
        all_depeered_ases = [asn for sublist in all_depeered_ases_lists for asn in sublist]
        unique_depeered_ases = set(all_depeered_ases)
        ases_in_multiple_ixps = [asn for asn in unique_depeered_ases if all_depeered_ases.count(asn) > 1]
        percentage_of_ases_in_multiple_ixps = (len(ases_in_multiple_ixps) / len(unique_depeered_ases)) * 100 if unique_depeered_ases else 0
        print(f"Percentage of ASes in multiple IXPs: {percentage_of_ases_in_multiple_ixps:.2f}% ({len(ases_in_multiple_ixps)} out of {len(unique_depeered_ases)} unique de-peered ASes)")

        confirm_action("Plot connections over time by time-in-IXP ranges", lambda: 
            plot_ixp_connections_over_time_by_age_ranges(all_data, all_files, depeered_ixp_ids, asn_to_analyze,
                                                     depeered_completely_lost_ixp_ids=completely_lost_ixp_ids,
                                                     depeered_with_nonpeered_ixp_ids=depeered_with_nonpeered_ixp_ids)  
        )


        dead_ixps = identify_dead_ixps(all_files, all_ixps)
        all_ixps_valid = [ixp for ixp in all_ixps if ixp.get("id") not in dead_ixps]
        confirm_action("Plot connections over time for IXP's that never connected to specific ASNs", lambda: 
            plot_ixp_connections_over_time_for_ixps_that_never_connected_to_ases(all_data, all_files, asn_to_analyze, all_ixps_valid)
        )

        finish_actions() 

    ixps_features_analysis() 
