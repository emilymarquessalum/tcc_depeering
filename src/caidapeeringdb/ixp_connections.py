 
import sys
from pathlib import Path
from collections import defaultdict
import numpy as np



sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from collections import defaultdict
from src.utils.graphs import plot_list_as_bar_plot
from src.caidapeeringdb.caidapeeringdb_load import get_all_files, get_all_files, get_asn_from_net, get_data


from src.caidapeeringdb.main import load_earliest_data, load_timeline_data
def _count_connections_by_asn(data, connection_type="peered"):
    """Count connections per ASN from data snapshot.
    
    Args:
        data: PeeringDB data snapshot
        connection_type: "peered", "non-peered", or "all"
    
    Returns:
        dict: ASN -> count of connections
    """
    asn_counts = defaultdict(int)
    
    for conn in data.get("netixlan", {}).get("data", []):
        asn = get_asn_from_net(conn)
        if asn is None:
            continue
        
        # Filter by connection type
        is_peered = conn.get("is_rs_peer", False)
        if connection_type == "peered" and not is_peered:
            continue
        elif connection_type == "non-peered" and is_peered:
            continue
        # For "all", include everything
        
        asn_counts[asn] += 1
    
    return asn_counts


def get_top_n_asns_by_lost_ixp_connections(before_data, after_data, n=10, connection_type="peered"):
    """Get top n ASes that lost the most IXP connections from before to after.
    
    Args:
        before_data: PeeringDB data snapshot from period A
        after_data: PeeringDB data snapshot from period B
        n: Number of top ASes to return (default 10)
        connection_type: "peered", "non-peered", or "all" (default "peered")
    
    Returns:
        list: List of tuples (ASN, lost_count) sorted by losses descending
    """
    before_counts = _count_connections_by_asn(before_data, connection_type)
    after_counts = _count_connections_by_asn(after_data, connection_type)
    
    # Calculate losses
    losses = []
    for asn, before_count in before_counts.items():
        after_count = after_counts.get(asn, 0)
        lost = before_count - after_count
        if lost > 0:  # Only include actual losses
            losses.append((asn, lost))
    
    # Sort by losses descending and return top n
    losses.sort(key=lambda x: x[1], reverse=True)
    return losses[:n]


def get_top_n_asns_by_gained_ixp_connections(before_data, after_data, n=10, connection_type="peered"):
    """Get top n ASes that gained the most IXP connections from before to after.
    
    Args:
        before_data: PeeringDB data snapshot from period A
        after_data: PeeringDB data snapshot from period B
        n: Number of top ASes to return (default 10)
        connection_type: "peered", "non-peered", or "all" (default "peered")
    
    Returns:
        list: List of tuples (ASN, gained_count) sorted by gains descending
    """
    before_counts = _count_connections_by_asn(before_data, connection_type)
    after_counts = _count_connections_by_asn(after_data, connection_type)
    
    # Calculate gains
    gains = []
    for asn, after_count in after_counts.items():
        before_count = before_counts.get(asn, 0)
        gained = after_count - before_count
        if gained > 0:  # Only include actual gains
            gains.append((asn, gained))
    
    # Sort by gains descending and return top n
    gains.sort(key=lambda x: x[1], reverse=True)
    return gains[:n]

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
        return f"{asn_to_name_mapping[asn_str]} ({asn})"
    else:
        return f"ASN {asn}"

def plot_top_3(before_data, after_data, all_files_before, all_files_after, display_dates_as_year_only=True):
    """Plot top 3 ASNs with biggest losses and gains.
    
    Args:
        before_data: PeeringDB data snapshot from period A
        after_data: PeeringDB data snapshot from period B
        all_files_before: List of PeeringDB files from period A
        all_files_after: List of PeeringDB files from period B
        display_dates_as_year_only: If True, show only year in title (default True)
    """
    # Get top 3 losses and gains
    top_3_losses = get_top_n_asns_by_lost_ixp_connections(before_data, after_data, n=3, connection_type="peered")
    top_3_gains = get_top_n_asns_by_gained_ixp_connections(before_data, after_data, n=3, connection_type="peered")
    
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
        losses_display_names,
        y=losses_values,
        subfolder="peeringdb_connections/top3",
        title=f"Top 3 ASes with Most De-Peerings from Route Servers, between {before_date_str} and {after_date_str}",
        xlabel="ASN",
        ylabel="Number of De-Peerings"
    )

    # Format gains for plotting
    gains_display_names = [_get_asn_display_name(asn) for asn, _ in top_3_gains]
    gains_values = [gain for _, gain in top_3_gains]
    
    plot_list_as_bar_plot(
        gains_display_names,
        y=gains_values,
        subfolder="peeringdb_connections/top3",
        title=f"Top 3 ASes with Most new Peerings From Route Servers, between {before_date_str} and {after_date_str}",
        xlabel="ASN",
        ylabel="Number of new Peerings"
    ) 


def plot_top_3_per_year(all_files):
    """Plot top 3 ASNs with biggest losses and gains for each year.
    
    For each year, finds the beginning snapshot (YYYY_01_01) and end snapshot (YYYY_12_01).
    If either doesn't exist, skips that year. Creates two plots per year (losses and gains).
    
    Args:
        all_files: List of all available PeeringDB dump filenames
    """
    import re
    from collections import defaultdict
    
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
        top_3_losses = get_top_n_asns_by_lost_ixp_connections(start_data, end_data, n=3, connection_type="peered")
        top_3_gains = get_top_n_asns_by_gained_ixp_connections(start_data, end_data, n=3, connection_type="peered")
        
        # Format losses for plotting
        losses_display_names = [_get_asn_display_name(asn) for asn, _ in top_3_losses]
        losses_values = [loss for _, loss in top_3_losses]
        
        plot_list_as_bar_plot(
            losses_display_names,
            y=losses_values,
            subfolder="peeringdb_connections/top3_per_year",
            title=f"Top 3 ASes with Most De-Peerings from Route Servers in {year}",
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

    start_data = get_data(all_files_earliest[0])
    end_data = get_data(all_files_after[-1])

    if False:
        top_n_losses = get_top_n_asns_by_lost_ixp_connections(start_data, end_data, n=10, connection_type="peered")
        top_n_gains = get_top_n_asns_by_gained_ixp_connections(start_data, end_data, n=10, connection_type="peered")
        print("From {} to {}:".format(all_files_earliest[0].split('peeringdb_2_dump_')[1].split('.json')[0], all_files_after[-1].split('peeringdb_2_dump_')[1].split('.json')[0]))
        print("Top 10 ASes with Most Losses in Route Server Connections:")
        for asn, loss in top_n_losses:
            print(f"ASN {asn} lost {loss} connections")
        print("\nTop 10 ASes with Most Gains in Route Server Connections:")
        for asn, gain in top_n_gains:
            print(f"ASN {asn} gained {gain} connections")
        
    # Uncomment to generate plots
    plot_top_3(start_data, end_data, all_files_earliest, all_files_after)
    
    # Plot top 3 per year
    all_files = get_all_files()
    plot_top_3_per_year(all_files)