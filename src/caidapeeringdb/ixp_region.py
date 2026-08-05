




from src.caidapeeringdb.continent_logic import get_continent_for_ixp
from src.caidapeeringdb.grouped_asns import get_ixps_by_continent_count
from src.caidapeeringdb.utils import COMPLETELY_LOST_LABEL, DEPEERED_IXPS_YLABEL, PEERINGDB_SUBFOLDER_PREFIX, PLOT_COLORS, STILL_CONNECTED_LABEL
from src.utils.graphs import plot_list_as_bar_plot, plot_stacked_bar_plot



def plot_ixps_by_region(all_files, ixp_ids, title_suffix=""):
    _, _, ixps_by_continent = get_ixps_by_continent_count(all_files)

    # 1. Convert to a set for O(1) lookups
    ixp_ids_set = set(ixp_ids)

    # 2. Filter and count in a single step, avoiding intermediate list creation
    ixp_by_continent_count = {
        continent: sum(1 for ixp in ixps if ixp["id"] in ixp_ids_set)
        for continent, ixps in ixps_by_continent.items()
    }

    plot_list_as_bar_plot(
        list(ixp_by_continent_count.keys()),
        y=list(ixp_by_continent_count.values()),
        subfolder=PEERINGDB_SUBFOLDER_PREFIX + "vpps_ixps",
        title=f"Number of IXPs by Region for VPPs {title_suffix}",
        xlabel="Region",
        ylabel="Number of IXPs",    
        sort_by_size=True
    )

def analyze_depeering_by_continent(data_structures, asn_to_analyze, all_ixps):
    asn_ixp_connections_by_continent = data_structures["asn_ixp_connections_by_continent"]
    not_peered_ixp_ids = data_structures["not_peered_ixp_ids"]
    completely_lost_ixp_ids = data_structures["completely_lost_ixp_ids"]
    
    # 1. Pre-map IXP IDs to Continents for O(1) lookup
    # This avoids the expensive nested any() call
    ixp_to_continent = {
        ixp["id"]: get_continent_for_ixp(ixp["id"], ixp) 
        for ixp in all_ixps
    }
    
    continents = sorted(asn_ixp_connections_by_continent.keys())
    
    # Initialize counts
    not_peered_counts_all = []
    lost_counts_all = []
    
    # 2. Convert to sets for faster membership testing
    not_peered_set = set(not_peered_ixp_ids)
    lost_set = set(completely_lost_ixp_ids)

    for continent in continents:
        # Count 'not peered' in the specific continent structure
        ixp_ids_in_continent = asn_ixp_connections_by_continent[continent].keys()
        not_peered_in_continent = sum(1 for ixp_id in ixp_ids_in_continent if ixp_id in not_peered_set)
        
        # 3. Use the pre-calculated map to count lost IXPs
        lost_in_continent = sum(1 for ixp_id in lost_set if ixp_to_continent.get(ixp_id) == continent)
        
        not_peered_counts_all.append(not_peered_in_continent)
        lost_counts_all.append(lost_in_continent)

    plot_stacked_bar_plot(
        [not_peered_counts_all, lost_counts_all],
        [STILL_CONNECTED_LABEL, COMPLETELY_LOST_LABEL],
        x_labels=continents,
        title=f"De-Peered IXPs per Continent for ASN {asn_to_analyze}",
        xlabel="Continent",
        ylabel=DEPEERED_IXPS_YLABEL,
        subfolder=PEERINGDB_SUBFOLDER_PREFIX + str(asn_to_analyze),
        colors=PLOT_COLORS,
        sort_by_size=True
    )
