from collections import Counter
import heapq
from pathlib import Path
import sys
 
import matplotlib.pyplot as plt
import re



sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.utils.graphs import plot_list_as_line_plot

from src.caidapeeringdb.caidapeeringdb_load import get_all_data, get_asn_from_net, get_data, get_file_from_date
from src.caidapeeringdb.main import load_timeline_data

def plot_ixp_connections_over_time(all_data, all_files, ixp_id,
                                   ixp_name=None,
                                    route_server_mode="all"):
 
    file_date_pattern = re.compile(r"peeringdb_2_dump_(.*?)\.json")
    dates = []
    for file in all_files:
        match = file_date_pattern.search(file)
        dates.append(match.group(1) if match else "unknown")
        
    # Lists to store metrics across snapshots
    rs_peer_counts = []
    non_rs_peer_counts = []
    total_unique_asns = []
    
    target_ixp_id = int(ixp_id)

    # Process each snapshot dataset sequentially
    for data in all_data:
        
        rs_asns = set()
        non_rs_asns = set()


        for conn in data.get("netixlan", {}).get("data", []):
            
            if int(conn.get("ix_id") or 0) != target_ixp_id:
                continue

            asn = get_asn_from_net(conn)
            if not asn:
                continue

            if conn.get("is_rs_peer", False):
                rs_asns.add(asn)
            else:
                non_rs_asns.add(asn)

        # Handle overlapping states dynamically using set logic:
        # If an ASN is present in rs_asns, it gets scrubbed from non_rs_asns 
        # because Route Server status takes absolute priority.
        non_rs_asns.difference_update(rs_asns)

        # O(1) set length checks replace our previous loop iterations/conditional logic
        rs_count = len(rs_asns)
        non_rs_count = len(non_rs_asns)
        
        rs_peer_counts.append(rs_count)
        non_rs_peer_counts.append(non_rs_count)
        total_unique_asns.append(rs_count + non_rs_count)

   
    if route_server_mode == "only_routeserver":
        peer_count = rs_peer_counts
    elif route_server_mode == "only_non_routeserver":
        peer_count = non_rs_peer_counts
    else:
        peer_count = [rs + non_rs for rs, non_rs in zip(rs_peer_counts, non_rs_peer_counts)]

    ixp_label = ixp_name if ixp_name else f"IXP {ixp_id}"
    plot_list_as_line_plot(
        peer_count,
        dates,
        title=f"Number of {'RS Peers' if route_server_mode == 'only_routeserver' else ("Non-RS Peers" if route_server_mode == "only_non_routeserver" else 'Peers')} at {ixp_label} Over Time",
        xlabel="Date",
        ylabel="Number of Peers",
        max_labels=8
    )



def top_n_ixps_with_most_depeerings(start_date, end_date, n=10):
  
    # 1. Resolve raw filenames using your utility map and load data snapshots
    start_file = get_file_from_date(start_date)
    end_file = get_file_from_date(end_date)
    
    start_data = get_data(start_file)
    end_data = get_data(end_file)

    # Helper function to capture active route server peering connections
    def _count_peered_members_per_ixp(snapshot_data):
        conns = snapshot_data.get("netixlan", {}).get("data", [])
        if not conns:
            return Counter()
            
        # We uniquely identify a peering session by matching the IXP with the connecting AS
        # A single AS might have multiple connections at one IXP, so we track unique (ix_id, asn) pairs
        unique_sessions = set()
        for conn in conns:
            if conn.get("is_rs_peer", False):
                ix_id = conn.get("ix_id")
                asn = conn.get("asn") or conn.get("local_asn")
                if ix_id and asn:
                    unique_sessions.add((ix_id, asn))
                    
        # Count how many unique peer AS networks reside at each IXP ID
        return Counter(ix_id for ix_id, _ in unique_sessions)

    # 2. Extract peering metrics across both data states
    before_counts = _count_peered_members_per_ixp(start_data)
    after_counts = _count_peered_members_per_ixp(end_data)

    # 3. Use Counter subtraction to isolate losses per IXP
    # (Before Count - After Count) evaluates to positive numbers for true structural losses
    ixp_losses = before_counts - after_counts

    # 4. Stream extraction utilizing Heaps for minimal execution overhead
    top_depeered_ixps = heapq.nlargest(n, ixp_losses.items(), key=lambda x: x[1])

    return top_depeered_ixps

if __name__ == "__main__":
    
    config_path = str(Path(__file__).parent)
    
    all_files_before_depeering, all_files_after_depeering = load_timeline_data(config_path)
    all_files = all_files_before_depeering + all_files_after_depeering
    

    all_data = get_all_data(all_files_before_depeering) + get_all_data(all_files_after_depeering)

     
    print(top_n_ixps_with_most_depeerings("2023_01_01", "2025_01_01", n=5))   
    #plot_ixp_connections_over_time(all_data, all_files, ixp_id=26, ixp_name="AMS-IX", route_server_mode="only_routeserver")
    #plot_ixp_connections_over_time(all_data, all_files, ixp_id=26, ixp_name="AMS-IX", route_server_mode="only_routeserver")
    
    #plot_ixp_connections_over_time(all_data, all_files, ixp_id=592, ixp_name="NAPAfrica", route_server_mode="only_routeserver")
    #plot_ixp_connections_over_time(all_data, all_files, ixp_id=592, ixp_name="NAPAfrica", route_server_mode="only_non_routeserver")
    
    
    plot_ixp_connections_over_time(all_data, all_files, ixp_id=171, ixp_name="IX.br São Paulo", route_server_mode="only_routeserver")
    plot_ixp_connections_over_time(all_data, all_files, ixp_id=171, ixp_name="IX.br São Paulo", route_server_mode="only_non_routeserver")
    plot_ixp_connections_over_time(all_data, all_files, ixp_id=171, ixp_name="IX.br São Paulo", route_server_mode="all")
    