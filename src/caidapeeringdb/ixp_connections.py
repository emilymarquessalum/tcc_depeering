 
import heapq
import sys
from pathlib import Path
from collections import Counter, defaultdict
import numpy as np



sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from collections import defaultdict
from src.utils.graphs import plot_list_as_bar_plot
from src.caidapeeringdb.caidapeeringdb_load import get_all_files, get_all_files, get_asn_from_net, get_data


from src.caidapeeringdb.main import load_earliest_data, load_timeline_data

def _count_connections_by_asn(data, connection_type="peered"):
    conns = data.get("netixlan", {}).get("data", [])
    if not conns:
        return Counter()
        
    if connection_type == "peered":
        valid_conn = lambda c: c.get("is_rs_peer", False)
    elif connection_type == "non-peered":
        valid_conn = lambda c: not c.get("is_rs_peer", False)
    else: 
        valid_conn = lambda c: True

    # Use a set to deduplicate (asn, ix_id) pairs upfront
    unique_ixp_presences = set()
    
    for conn in conns:
        asn = get_asn_from_net(conn)
        # Get the unique identifier for the IXP (e.g., 'ix_id')
        ix_id = conn.get("ix_id") 
        
        if asn is not None and ix_id is not None and valid_conn(conn):
            unique_ixp_presences.add((asn, ix_id))
            
    # Now count how many unique IXPs each ASN has
    return Counter(asn for asn, _ in unique_ixp_presences)

def get_top_n_ixp_changes(before_data, after_data, n=10, connection_type="peered"):
    """
    Returns a tuple of (top_losses, top_gains) while parsing the raw data 
    only once for maximum performance.
    """
    # 1. Parse the data once 
    before_counts = _count_connections_by_asn(before_data, connection_type)
    after_counts = _count_connections_by_asn(after_data, connection_type)
    
    # 2. Do the math using Counter subtraction
    losses = before_counts - after_counts
    gains = after_counts - before_counts
    
    # 3. Extract the top N using Heaps
    top_losses = heapq.nlargest(n, losses.items(), key=lambda x: x[1])
    top_gains = heapq.nlargest(n, gains.items(), key=lambda x: x[1])
    
    return top_losses, top_gains


asn_to_name_mapping = {
    "396986": "ByteDance Inc.",
    "15169": "Google",
    "15133": "EdgeCast",
    "33438": "Datum Cloud",
    "20940": "Akamai",  
    "13335": "Cloudflare",
    "139341": "Huawei",
    "210633": ""
}

def _get_asn_display_name(asn):
    """Get display name for ASN, using mapping if available."""
    asn_str = str(asn)
    if asn_str in asn_to_name_mapping:
        return f"{asn_to_name_mapping[asn_str]} (AS{asn})"
    else:
        return f"AS{asn}"

def plot_top_3(before_data, after_data, all_files_before, all_files_after, display_dates_as_year_only=True):
    
    top_n = 3
    # Get top 3 losses and gains
    top_3_losses, top_3_gains = get_top_n_ixp_changes(before_data, after_data, n=top_n, connection_type="peered")
    
    # Extract dates from filenames
    before_date_str = all_files_before[0].split('peeringdb_2_dump_')[1].split('.json')[0]
    after_date_str = all_files_after[-1].split('peeringdb_2_dump_')[1].split('.json')[0]
    
    if display_dates_as_year_only:
        before_date_str = before_date_str.split('_')[0]
        after_date_str = after_date_str.split('_')[0]
    
    # Format losses for plotting
    losses_display_names = [_get_asn_display_name(asn) for asn, _ in top_3_losses]
    losses_values = [loss for _, loss in top_3_losses]
    
    plot_list_as_bar_plot(
        [asn_to_name_mapping[str(asn[0])] if str(asn[0]) in asn_to_name_mapping else asn for asn in top_3_losses],
        extra_labels=[f"AS{asn[0]}" for asn in top_3_losses],
        y=losses_values,
        subfolder="peeringdb_connections/top3",
        title=f"Top {top_n} ASes in terms of De-Peerings from Route Servers, between {before_date_str} and {after_date_str}",
        xlabel="ASN",
        ylabel="Number of De-Peerings",
        use_rotated_labels=False
    )

    # Format gains for plotting
    gains_display_names = [_get_asn_display_name(asn) for asn, _ in top_3_gains]
    gains_values = [gain for _, gain in top_3_gains]
    
    plot_list_as_bar_plot(
        gains_display_names,
        y=gains_values,
        subfolder="peeringdb_connections/top3",
        title=f"Top {top_n} ASes in terms of new Route Server Peerings, between {before_date_str} and {after_date_str}",
        xlabel="ASN",
        ylabel="New Peerings",
        use_rotated_labels=False
    ) 


def plot_top_3_per_year(all_files):
     
    import re
    from collections import defaultdict
    

    top_n = 4
    # Parse filenames to extract dates and map them to files
    file_date_map = {}  # date_str (YYYY_MM_DD) -> filename
    years_available = set()
    
    for filename in all_files:
        match = re.search(r"peeringdb_2_dump_((\d{4})_(\d{2})_(\d{2}))\.json", filename)
        if match:
            date_str = match.group(1)  # YYYY_MM_DD
            year = match.group(2)       # YYYY
            file_date_map[date_str] = filename
            years_available.add(year)
        else:
            print(f"Warning: Filename {filename} does not match expected pattern and will be skipped.")
    
    # For each year, check if we have the required snapshots and process
    for year in sorted(years_available):
        year_start_date = f"{year}_01_01"
        year_end_date = f"{year}_12_01"
        subtitute_end_date = f"{year}_11_01"
        
        # Check if both required files exist
        if year_start_date not in file_date_map or (year_end_date not in file_date_map and subtitute_end_date not in file_date_map):
            print(f"Skipping year {year} because required snapshots are missing.")
            continue
        
        # Load data for this year
        start_file = file_date_map[year_start_date]
        end_file = file_date_map[year_end_date] if year_end_date in file_date_map else file_date_map[subtitute_end_date]
        
        start_data = get_data(start_file)
        end_data = get_data(end_file)
        
        # Get top 3 losses and gains
        top_n_losses, top_n_gains = get_top_n_ixp_changes(start_data, end_data, n=top_n, connection_type="peered")
        
        # Format losses for plotting
        losses_display_names = [_get_asn_display_name(asn) for asn, _ in top_n_losses]
        losses_values = [loss for _, loss in top_n_losses]
        
        plot_list_as_bar_plot(
            losses_display_names,
            y=losses_values,
            subfolder="peeringdb_connections/top3_per_year",
            title=f"Top {top_n} ASes with Most De-Peerings from Route Servers in {year}",
            xlabel="ASN",
            ylabel="Number of Lost Route Server Connections"
        )

        # Format gains for plotting
        gains_display_names = [_get_asn_display_name(asn) for asn, _ in top_3_gains]
        gains_values = [gain for _, gain in top_3_gains]
        
        plot_list_as_bar_plot(
            gains_display_names,
            y=gains_values,
            subfolder="peeringdb_connections/top3_per_year",
            title=f"Top 3 ASes with Most Gains in Route Server Connections in {year}",
            xlabel="ASN",
            ylabel="Number of Gained Route Server Connections"
        )

if __name__ == "__main__":

    config_path = str(Path(__file__).parent)
    all_files_earliest = load_earliest_data(config_path)
    all_files_earliest, all_files_after = load_timeline_data(config_path)

    all_files_earliest[0] = "peeringdb_2_dump_2024_01_01.json"
    start_data = get_data(all_files_earliest[0])
    #start_data = get_data("peeringdb_2_dump_2024_01_01.json") 
    print(all_files_after[-1])
    end_data = get_data(all_files_after[-1])

    if False:
        top_n_losses, top_n_gains = get_top_n_ixp_changes(start_data, end_data, n=10, connection_type="peered")
        print("From {} to {}:".format(all_files_earliest[0].split('peeringdb_2_dump_')[1].split('.json')[0], all_files_after[-1].split('peeringdb_2_dump_')[1].split('.json')[0]))
        print("Top 10 ASes with Most Losses in Route Server Connections:")
        for asn, loss in top_n_losses:
            print(f"ASN {asn} lost {loss} connections")
        print("\nTop 10 ASes with Most Gains in Route Server Connections:")
        for asn, gain in top_n_gains:
            print(f"ASN {asn} gained {gain} connections")
        
    
    plot_top_3(start_data, end_data, all_files_earliest, all_files_after)
    
    # Plot top 3 per year
    all_files = get_all_files()
    #plot_top_3_per_year(all_files)