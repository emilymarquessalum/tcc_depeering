



import numpy as np

from src.caidapeeringdb.caidapeeringdb_load import get_connections_for_ixp
from src.caidapeeringdb.utils import COMPLETELY_LOST_LABEL, DEPEERED_IXPS_YLABEL, PEERINGDB_SUBFOLDER_PREFIX, PLOT_COLORS, STILL_CONNECTED_LABEL

from src.utils.graphs import plot_list_as_bar_plot, plot_stacked_bar_plot
    
def plot_ixp_connections_by_continent(continent_to_connections_map, asn_to_search, dates_y, colors, subfolder):

    connections_key = list(continent_to_connections_map.keys())
    connections_values = list(continent_to_connections_map.values())
    
    total_ixp_connections = sum(connections_values)
    plot_list_as_bar_plot(
            connections_key,
            y=[v / total_ixp_connections for v in connections_values],
            subfolder=subfolder,
            is_percentage=True,
            title=f"Distribution of IXP Connections in Route Server by Region for ASN {asn_to_search[0]} ({asn_to_search[1]}) at {dates_y[0]}",
            xlabel="Region",
            ylabel="Number of IXP Connections in Route Server",
            colors=colors
    )


def plot_ixp_connections_ratio_from_total_ixps_in_that_region(ixps_peered_region_distribution_count_by_total_ixps_in_that_region, asn_to_search, dates_y, colors, subfolder):

    plot_list_as_bar_plot(
            list(ixps_peered_region_distribution_count_by_total_ixps_in_that_region.keys()),
            y=list(ixps_peered_region_distribution_count_by_total_ixps_in_that_region.values()),
            subfolder=subfolder,
            is_percentage=True,
            sort_by_size=True,
            title=f"IXP Connections in Route Server by Region, in terms of total IXPs in that Region, for ASN {asn_to_search[0]} ({asn_to_search[1]}) at {dates_y[0]}",
            xlabel="Region",
            ylabel="Number of IXP Connections / Total IXPs in that Region",
            colors=colors
    )


def get_largest_ixps_from_ixp_list(ixps, data, top_n=3):

    connections_by_ixp = {}

    for ixp in ixps:
        ixp_connections = get_connections_for_ixp(ixp_id=ixp["id"], data=data)
        connections_by_ixp[ixp["id"]] = len(ixp_connections)

    # Sort IXPs by the number of connections and return the top N
    sorted_ixps = sorted(connections_by_ixp.items(), key=lambda x: x[1], reverse=True)

    sorted_ixp_info = []
    for ixp_id, connections in sorted_ixps[:top_n]:
        ixp_info = next((ixp for ixp in ixps if ixp["id"] == ixp_id), None)
        if ixp_info:
            sorted_ixp_info.append({
                "id": ixp_id,
                "name": ixp_info.get("name", "Unknown"),
                "connections": connections,
                **{k: v for k, v in ixp_info.items() if k not in ["id", "name"]}
            })

    return sorted_ixp_info


def get_largest_ixps_per_continent_of_an_asn(asn_ixp_connections_by_continent, continent_to_ixps_map, top_n=1):

    largest_ixps_per_continent = {}
    for continent, connections in asn_ixp_connections_by_continent.items():
        ixps_in_continent = continent_to_ixps_map.get(continent, [])
        if not ixps_in_continent:
            continue
        # Only consider IXPs that the ASN is actually connected to (those in the connections dict)
        connected_ixps_in_continent = [ixp for ixp in ixps_in_continent if ixp in connections]
        if not connected_ixps_in_continent:
            continue
        largest_ixps = sorted(connected_ixps_in_continent, key=lambda ixp, conn=connections: conn.get(ixp, 0), reverse=True)[:top_n]
        largest_ixps_per_continent[continent] = [(ixp, connections.get(ixp, 0)) for ixp in largest_ixps]

    return largest_ixps_per_continent




def analyze_depeering_by_percentiles(data_structures, depeered_ixp_sizes, asn_to_analyze, 
                                      percentile_thresholds=None):
     
    if percentile_thresholds is None:
        percentile_thresholds = [20, 50]
    
    not_peered_ixp_ids = data_structures["not_peered_ixp_ids"]
    completely_lost_ixp_ids = data_structures["completely_lost_ixp_ids"]
    
    sizes_list = list(depeered_ixp_sizes.values())
    percentile_values = {p: np.percentile(sizes_list, p) for p in percentile_thresholds}
    
    range_labels = []
    lower = 0
    for i, p in enumerate(percentile_thresholds):
        range_labels.append(f"{lower}-{p}%")
        lower = p
    range_labels.append(f"{lower}-100%")
    
    size_categories = {label: [] for label in range_labels}
    
    for ixp_id, size in depeered_ixp_sizes.items():
        for i, p in enumerate(percentile_thresholds):
            if size <= percentile_values[p]:
                size_categories[range_labels[i]].append(ixp_id)
                break
        else:
            # If size is larger than the highest percentile
            size_categories[range_labels[-1]].append(ixp_id)
    

    size_labels = list(size_categories.keys())
    still_connected_by_size = []
    lost_by_size = []
    
    for category in size_labels:
        ixps_in_category = set(size_categories[category])
        still_connected = len(ixps_in_category & not_peered_ixp_ids)
        completely_lost = len(ixps_in_category & completely_lost_ixp_ids)
        still_connected_by_size.append(still_connected)
        lost_by_size.append(completely_lost)
    
    plot_stacked_bar_plot(
        [still_connected_by_size, lost_by_size],
        [STILL_CONNECTED_LABEL, COMPLETELY_LOST_LABEL],
        x_labels=size_labels,
        title=f"De-Peered IXPs by Size Percentile for ASN {asn_to_analyze}",
        xlabel="IXP Size Percentile (by peered connections before de-peering)",
        ylabel=DEPEERED_IXPS_YLABEL,
        subfolder=PEERINGDB_SUBFOLDER_PREFIX + str(asn_to_analyze),
        colors=PLOT_COLORS
    )



DEFAULT_SIZE_RANGE_THRESHOLDS = [50, 100, 150, 200]


def plot_ixps_by_size_ranges(data, ixp_ids, title_suffix=""):
    ixp_sizes = {ixp_id: len(get_connections_for_ixp(ixp_id=ixp_id, data=data)) for ixp_id in ixp_ids}
    
    size_range_thresholds = DEFAULT_SIZE_RANGE_THRESHOLDS

    range_labels_exact = []
    lower = 0
    for threshold in size_range_thresholds:
        range_labels_exact.append(f"{lower}-{threshold}")
        lower = threshold
    range_labels_exact.append(f"{lower}+")

    size_ranges = {label: [] for label in range_labels_exact}
    
    for ixp_id, size in ixp_sizes.items():
        for lower, upper in zip([0] + DEFAULT_SIZE_RANGE_THRESHOLDS, DEFAULT_SIZE_RANGE_THRESHOLDS + [float('inf')]):
            if lower < size <= upper:
                range_label = f"{lower}-{upper}" if upper != float('inf') else f"{lower}+"
                size_ranges[range_label].append(ixp_id)
                break
    
    plot_list_as_bar_plot(
        list(size_ranges.keys()),
        y=[len(ids) for ids in size_ranges.values()],
        title=f"Distribution of De-Peered IXPs by Size Range {title_suffix}",
        xlabel="IXP Size Range (by number of peered connections before de-peering)",
        ylabel="Number of De-Peered IXPs",
        subfolder=PEERINGDB_SUBFOLDER_PREFIX  ,
        colors=PLOT_COLORS
    )


def analyze_depeering_by_size_ranges(data_structures, depeered_ixp_sizes, asn_to_analyze,
                                     size_range_thresholds=None,
                                     title_suffix=""):
    """Analyze and plot de-peering by IXP size ranges.
    
    Args:
        data_structures: Dict from build_asn_ixp_data_structures()
        depeered_ixp_sizes: Dict from get_depeered_ixp_sizes()
        asn_to_analyze: ASN number
        size_range_thresholds: List of threshold values (e.g., [50, 100, 150, 200])
    """
    if size_range_thresholds is None:
        size_range_thresholds = DEFAULT_SIZE_RANGE_THRESHOLDS
    
    not_peered_ixp_ids = data_structures["not_peered_ixp_ids"]
    completely_lost_ixp_ids = data_structures["completely_lost_ixp_ids"]
    
    range_labels_exact = []
    lower = 0
    for threshold in size_range_thresholds:
        range_labels_exact.append(f"{lower}-{threshold}")
        lower = threshold
    range_labels_exact.append(f"{lower}+")
    
    size_ranges = {label: [] for label in range_labels_exact}
    
    for ixp_id, size in depeered_ixp_sizes.items():
        categorized = False
        for i, threshold in enumerate(size_range_thresholds):
            if size <= threshold:
                size_ranges[range_labels_exact[i]].append(ixp_id)
                categorized = True
                break
        if not categorized:
            # If size is larger than the highest threshold
            size_ranges[range_labels_exact[-1]].append(ixp_id)
    
    still_connected_by_range = []
    lost_by_range = []
    
    for label in range_labels_exact:
        ixps_in_range = set(size_ranges[label])
        still_connected = len(ixps_in_range & not_peered_ixp_ids)
        completely_lost = len(ixps_in_range & completely_lost_ixp_ids)
        still_connected_by_range.append(still_connected)
        lost_by_range.append(completely_lost)
    
    plot_stacked_bar_plot(
        [still_connected_by_range, lost_by_range],
        [STILL_CONNECTED_LABEL, COMPLETELY_LOST_LABEL],
        x_labels=range_labels_exact,
        title=f"De-Peered IXPs by Size Range for ASN {asn_to_analyze} {title_suffix}",
        xlabel="IXP Size Range (by number of peered connections before de-peering)",
        ylabel=DEPEERED_IXPS_YLABEL,
        subfolder=PEERINGDB_SUBFOLDER_PREFIX + str(asn_to_analyze),
        colors=PLOT_COLORS
    )


def plot_ixp_size_ranges_by_percentage_of_total_loss_connections(data_structures, depeered_ixp_sizes, asn_to_analyze,
                                                                   size_range_thresholds=None,
                                                                   title_suffix=""):
    """Plot de-peering by IXP size ranges as percentages within each range.
    
    Each size range bar totals 100%, showing the proportion of IXPs that lost
    all connections vs those that still have non-peered connections.
    
    Args:
        data_structures: Dict from build_asn_ixp_data_structures()
        depeered_ixp_sizes: Dict from get_depeered_ixp_sizes()
        asn_to_analyze: ASN number
        size_range_thresholds: List of threshold values (e.g., [50, 100, 150, 200])
        title_suffix: Optional suffix for the plot title
    """
    if size_range_thresholds is None:
        size_range_thresholds = DEFAULT_SIZE_RANGE_THRESHOLDS
    
    not_peered_ixp_ids = data_structures["not_peered_ixp_ids"]
    completely_lost_ixp_ids = data_structures["completely_lost_ixp_ids"]
    
    range_labels_exact = []
    lower = 0
    for threshold in size_range_thresholds:
        range_labels_exact.append(f"{lower}-{threshold}")
        lower = threshold
    range_labels_exact.append(f"{lower}+")
    
    size_ranges = {label: [] for label in range_labels_exact}
    
    for ixp_id, size in depeered_ixp_sizes.items():
        categorized = False
        for i, threshold in enumerate(size_range_thresholds):
            if size <= threshold:
                size_ranges[range_labels_exact[i]].append(ixp_id)
                categorized = True
                break
        if not categorized:
            # If size is larger than the highest threshold
            size_ranges[range_labels_exact[-1]].append(ixp_id)
    
    still_connected_percentages = []
    lost_percentages = []
    
    for label in range_labels_exact:
        ixps_in_range = set(size_ranges[label])
        total_in_range = len(ixps_in_range)
        
        if total_in_range == 0:
            still_connected_percentages.append(0)
            lost_percentages.append(0)
        else:
            still_connected = len(ixps_in_range & not_peered_ixp_ids)
            completely_lost = len(ixps_in_range & completely_lost_ixp_ids)
            
            still_connected_percentages.append((still_connected / total_in_range) )
            lost_percentages.append((completely_lost / total_in_range) )
    
    plot_stacked_bar_plot(
        [still_connected_percentages, lost_percentages],
        [STILL_CONNECTED_LABEL, COMPLETELY_LOST_LABEL],
        x_labels=range_labels_exact,
        title=f"De-Peered IXPs by Size Range (% per range) for ASN {asn_to_analyze} {title_suffix}",
        xlabel="IXP Size Range (by number of peered connections before de-peering)",
        ylabel="Percentage of IXPs in Range (%)",
        max_labels=100,
        is_percentage=True,
        subfolder=PEERINGDB_SUBFOLDER_PREFIX + str(asn_to_analyze),
        colors=PLOT_COLORS
    )

