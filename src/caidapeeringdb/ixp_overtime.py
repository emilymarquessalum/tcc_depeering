import matplotlib.pyplot as plt
import numpy as np
import re
from src.caidapeeringdb.utils import PEERINGDB_SUBFOLDER_PREFIX
from src.caidapeeringdb.caidapeeringdb_load import get_asn_from_net
from src.utils.graphs import clean_title_name, plot_list_as_line_plot, save_plot

import matplotlib.pyplot as plt
import matplotlib.lines as mlines

def plot_ixps_connections_over_time(
    all_data, 
    dates, 
    ixp_ids, 
    ixp_names=None, 
    route_server_mode="all",
    title_info="IXPs",
    index_of_focused_asn_depeering=None  # <-- NEW PARAMETER
):
    # --- 1. Validation and Setup ---
    if ixp_ids is None or len(ixp_ids) == 0:
        raise ValueError("ixp_ids cannot be None or empty")
    if not isinstance(ixp_ids, (list, tuple, set)):
        ixp_ids = [ixp_ids]

    target_ixp_ids = [int(ixp_id) for ixp_id in ixp_ids]
    if not target_ixp_ids:
        raise ValueError("ixp_ids cannot be empty")

    ixp_name_map = {}
    if isinstance(ixp_names, dict):
        for key, value in ixp_names.items():
            ixp_name_map[int(key)] = value
    elif isinstance(ixp_names, (list, tuple)):
        for index, ixp_id in enumerate(target_ixp_ids):
            if index < len(ixp_names):
                ixp_name_map[ixp_id] = ixp_names[index]
    elif isinstance(ixp_names, str) and len(target_ixp_ids) == 1:
        ixp_name_map[target_ixp_ids[0]] = ixp_names

    snapshot_count = min(len(all_data), len(dates))
    dates = dates[:snapshot_count]
    all_data = all_data[:snapshot_count]

    target_ixp_id_set = set(target_ixp_ids)
    timeline_data = {ixp_id: [] for ixp_id in target_ixp_ids}

    # --- 2. Data Processing ---
    for snapshot_data in all_data:
        rs_asns_by_ixp = {ixp_id: set() for ixp_id in target_ixp_ids}
        non_rs_asns_by_ixp = {ixp_id: set() for ixp_id in target_ixp_ids}

        for conn in snapshot_data.get("netixlan", {}).get("data", []):
            ix_id = conn.get("ix_id")
            if ix_id is None:
                continue

            try:
                ix_id = int(ix_id)
            except (TypeError, ValueError):
                continue

            if ix_id not in target_ixp_id_set:
                continue

            asn = get_asn_from_net(conn)
            if not asn:
                continue

            if conn.get("is_rs_peer", False):
                rs_asns_by_ixp[ix_id].add(asn)
            else:
                non_rs_asns_by_ixp[ix_id].add(asn)

        for ixp_id in target_ixp_ids:
            rs_asns = rs_asns_by_ixp[ixp_id]
            non_rs_asns = non_rs_asns_by_ixp[ixp_id]
            non_rs_asns.difference_update(rs_asns)

            if route_server_mode == "only_routeserver":
                peer_count = len(rs_asns)
            elif route_server_mode == "only_non_routeserver":
                peer_count = len(non_rs_asns)
            else:
                peer_count = len(rs_asns) + len(non_rs_asns)

            timeline_data[ixp_id].append(peer_count)

    # Calculate Average and Median time series
    average_values = []
    median_values = []
    for index in range(len(dates)):
        values_at_index = [timeline_data[ixp_id][index] for ixp_id in target_ixp_ids if index < len(timeline_data[ixp_id])]
        if values_at_index:
            average_values.append(float(np.mean(values_at_index)))
            median_values.append(float(np.median(values_at_index)))
        else:
            average_values.append(0.0)
            median_values.append(0.0)

    # --- 3. Build Title and Labels ---
    if route_server_mode == "only_routeserver":
        mode_label = "RS Peers"
    elif route_server_mode == "only_non_routeserver":
        mode_label = "Non-RS Peers"
    else:
        mode_label = "Peers"

    ixp_labels = [ixp_name_map.get(ixp_id, f"IXP {ixp_id}") for ixp_id in target_ixp_ids]
    if len(ixp_labels) == 1:
        ixp_label = ixp_labels[0]
    elif len(ixp_labels) <= 3:
        ixp_label = ", ".join(ixp_labels)
    else:
        ixp_label = ", ".join(ixp_labels[:3]) + f" +{len(ixp_labels) - 3} more"

    title = f"Number of {mode_label} at {title_info} Over Time"
    if ixp_label:
        title += f" ({ixp_label})"

    # --- 4. Build Custom Lines & Annotations ---
    x_indices = np.arange(len(dates))
    extra_artists = []

    # Individual IXP lines
    for ixp_id in target_ixp_ids:
        display_name = ixp_name_map.get(ixp_id, f"IXP {ixp_id}")
        line = mlines.Line2D(
            x_indices, 
            timeline_data[ixp_id], 
            color="tab:blue", 
            alpha=0.2, 
            linewidth=1.2, 
            label=display_name
        )
        extra_artists.append(line)

    # Median line
    median_line = mlines.Line2D(
        x_indices, 
        median_values, 
        color="dimgray", 
        linewidth=2, 
        linestyle="--", 
        label="Median"
    )
    extra_artists.append(median_line)

    # --- De-peering Vertical Line Marker ---
    if index_of_focused_asn_depeering is not None and 0 <= index_of_focused_asn_depeering < len(dates):
        # Line2D with transform=plt.gca().get_xaxis_transform() spans the full vertical Y height
        depeering_line = plt.axvline(
            x=index_of_focused_asn_depeering, 
            color="red", 
            linestyle=":", 
            linewidth=2, 
            label="de-peering"
        )
        extra_artists.append(depeering_line)

    subfolder_path = PEERINGDB_SUBFOLDER_PREFIX + "ixp_overtime"

    # --- 5. Delegate Plotting ---
    plot_list_as_line_plot(
        data_list=average_values,
        y=dates,
        title=title,
        xlabel="Date",
        ylabel="Number of Peers",
        positive_color=None,
        negative_color=None,
        use_fill=False,
        subfolder=subfolder_path,
        max_labels=8 if len(dates) > 8 else None,
        use_rotated_labels=True,
        annotations=extra_artists
    )
    
    
def plot_ixp_statistics_connections_over_time(all_data, dates, ixp_ids, ixp_names=None, 
                                                route_server_mode="all", title_info="IXPs"):
    """
    Plots aggregate statistics (average, median, max, and total trend) for IXP connections over time.
    Individual IXP timelines are plotted lightly in the background without legend entries.
    """
    if ixp_ids is None or len(ixp_ids) == 0:
        raise ValueError("ixp_ids cannot be None or empty")
    if not isinstance(ixp_ids, (list, tuple, set)):
        ixp_ids = [ixp_ids]

    target_ixp_ids = [int(ixp_id) for ixp_id in ixp_ids]
    if not target_ixp_ids:
        raise ValueError("ixp_ids cannot be empty")

    # Map IXP names for clean title labeling
    ixp_name_map = {}
    if isinstance(ixp_names, dict):
        for key, value in ixp_names.items():
            ixp_name_map[int(key)] = value
    elif isinstance(ixp_names, (list, tuple)):
        for index, ixp_id in enumerate(target_ixp_ids):
            if index < len(ixp_names):
                ixp_name_map[ixp_id] = ixp_names[index]
    elif isinstance(ixp_names, str) and len(target_ixp_ids) == 1:
        ixp_name_map[target_ixp_ids[0]] = ixp_names

    snapshot_count = min(len(all_data), len(dates))
    dates = dates[:snapshot_count]
    all_data = all_data[:snapshot_count]

    target_ixp_id_set = set(target_ixp_ids)
    timeline_data = {ixp_id: [] for ixp_id in target_ixp_ids}

    # Extract peer connection counts per snapshot
    for snapshot_data in all_data:
        rs_asns_by_ixp = {ixp_id: set() for ixp_id in target_ixp_ids}
        non_rs_asns_by_ixp = {ixp_id: set() for ixp_id in target_ixp_ids}

        for conn in snapshot_data.get("netixlan", {}).get("data", []):
            ix_id = conn.get("ix_id")
            if ix_id is None:
                continue

            try:
                ix_id = int(ix_id)
            except (TypeError, ValueError):
                continue

            if ix_id not in target_ixp_id_set:
                continue

            asn = get_asn_from_net(conn)
            if not asn:
                continue

            if conn.get("is_rs_peer", False):
                rs_asns_by_ixp[ix_id].add(asn)
            else:
                non_rs_asns_by_ixp[ix_id].add(asn)

        for ixp_id in target_ixp_ids:
            rs_asns = rs_asns_by_ixp[ixp_id]
            non_rs_asns = non_rs_asns_by_ixp[ixp_id]
            non_rs_asns.difference_update(rs_asns)

            if route_server_mode == "only_routeserver":
                peer_count = len(rs_asns)
            elif route_server_mode == "only_non_routeserver":
                peer_count = len(non_rs_asns)
            else:
                peer_count = len(rs_asns) + len(non_rs_asns)

            timeline_data[ixp_id].append(peer_count)

    fig, ax1 = plt.subplots(figsize=(12, 6))

    # Plot individual IXP lines softly in the background on primary axis
    for ixp_id in target_ixp_ids:
        ax1.plot(
            range(len(dates)),
            timeline_data[ixp_id],
            color="steelblue",
            alpha=0.15,
            linewidth=1.0,
            zorder=1
        )

    # Calculate statistical metrics across all target IXPs per snapshot
    average_values = []
    median_values = []
    max_values = []
    total_values = []

    for index in range(len(dates)):
        values_at_index = [
            timeline_data[ixp_id][index] 
            for ixp_id in target_ixp_ids 
            if index < len(timeline_data[ixp_id])
        ]
        if values_at_index:
            average_values.append(float(np.mean(values_at_index)))
            median_values.append(float(np.median(values_at_index)))
            max_values.append(float(np.max(values_at_index)))
            total_values.append(float(np.sum(values_at_index)))
        else:
            average_values.append(0.0)
            median_values.append(0.0)
            max_values.append(0.0)
            total_values.append(0.0)

    # Plot Max, Average, and Median lines on the Primary Y-Axis
    line_max = ax1.plot(
        range(len(dates)), 
        max_values, 
        color="darkorange", 
        linewidth=2.0, 
        linestyle=":", 
        label="Max (Highest IXP)",
        zorder=3
    )
    line_avg = ax1.plot(
        range(len(dates)), 
        average_values, 
        color="crimson", 
        linewidth=2.5, 
        label=f"Average ({len(target_ixp_ids)} IXPs)",
        zorder=4
    )
    line_med = ax1.plot(
        range(len(dates)), 
        median_values, 
        color="black", 
        linewidth=2.0, 
        linestyle="--", 
        label=f"Median ({len(target_ixp_ids)} IXPs)",
        zorder=5
    )

    # Plot Overall Total/Growth Trend on Secondary Y-Axis to preserve visual scale
    ax2 = ax1.twinx()
    line_tot = ax2.plot(
        range(len(dates)), 
        total_values, 
        color="forestgreen", 
        linewidth=2.5, 
        linestyle="-.", 
        label="Overall Total (Growth)",
        zorder=2
    )

    # Label mode configuration
    if route_server_mode == "only_routeserver":
        mode_label = "RS Peers"
    elif route_server_mode == "only_non_routeserver":
        mode_label = "Non-RS Peers"
    else:
        mode_label = "Peers"

    # Axis Labels
    ax1.set_xlabel("Date")
    ax1.set_ylabel(f"Number of {mode_label} (per IXP)")
    ax2.set_ylabel(f"Total Cumulative {mode_label} (All IXPs)", color="forestgreen")
    ax2.tick_params(axis='y', labelcolor="forestgreen")

    # Combine handles and labels from both axes for a unified legend
    lines = line_max + line_avg + line_med + line_tot
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc="upper left")

    # Dynamic Title creation
    ixp_labels = [ixp_name_map.get(ixp_id, f"IXP {ixp_id}") for ixp_id in target_ixp_ids]
    if len(ixp_labels) == 1:
        ixp_label = ixp_labels[0]
    elif len(ixp_labels) <= 3:
        ixp_label = ", ".join(ixp_labels)
    else:
        ixp_label = f"{len(target_ixp_ids)} IXPs"

    title = f"Statistical Summary of {mode_label} at {title_info} Over Time ({ixp_label})"

    # Date formatting on X axis
    if len(dates) > 8:
        step = max(1, len(dates) // 8)
        tick_positions = list(range(0, len(dates), step))
        tick_labels = [dates[i] for i in tick_positions]
        ax1.set_xticks(tick_positions)
        ax1.set_xticklabels(tick_labels, rotation=45)
    else:
        ax1.set_xticks(range(len(dates)))
        ax1.set_xticklabels(dates, rotation=45)

    plt.title(title)
    ax1.grid(True, linestyle=":", alpha=0.6)

    # Save and cleanup
    save_plot(
        plt,
        clean_title_name(title),
        subfolder=PEERINGDB_SUBFOLDER_PREFIX + "ixp_stats_overtime"
    )
    plt.close()
 

def get_ixp_with_most_depeering_ratio_at_a_single_point_in_time(all_data, ixp_ids, type_of_depeering="completely_lost"):
    """
    Returns the IXP ID with the highest de-peering ratio at any single snapshot in time.
    De-peering ratio is defined as (completely lost connections) / (total connections).
    """
    if ixp_ids is None or len(ixp_ids) == 0: 
        raise ValueError("ixp_ids cannot be None or empty")
    if not isinstance(ixp_ids, (list, tuple, set)):
        ixp_ids = [ixp_ids]

    target_ixp_ids = [int(ixp_id) for ixp_id in ixp_ids]
    if not target_ixp_ids:
        raise ValueError("ixp_ids cannot be empty")

    max_depeering_ratio = -1
    ixp_with_max_ratio = None
    index_of_max_ratio = -1

    for i in range(1, len(all_data)):
        snapshot_data = all_data[i]
        previous_snapshot_data = all_data[i - 1]

        for ixp_id in target_ixp_ids:

            if type_of_depeering == "completely_lost":
                # Calculate de-peering ratio for completely lost connections
                current_connections = sum(
                    1 for conn in snapshot_data.get("netixlan", {}).get("data", [])
                    if conn.get("ix_id") == ixp_id
                )
                previous_connections = sum( 
                1 for conn in previous_snapshot_data.get("netixlan", {}).get("data", [])
                if conn.get("ix_id") == ixp_id
                )
            elif type_of_depeering == "rs_to_non_rs":
                # passed from rs to not-rs (was rs in the past, isnt anymore). For both cases we get all the rs ones, 
                # this way we then filter to find the ones that existed as RS but dont exist as RS in the future
                current_connections = sum( 
                    1 for conn in snapshot_data.get("netixlan", {}).get("data", [])
                    if conn.get("ix_id") == ixp_id and conn.get("is_rs_peer", False)
                ) 
                previous_connections = sum(
                    1 for conn in previous_snapshot_data.get("netixlan", {}).get("data", [])
                    if conn.get("ix_id") == ixp_id and conn.get("is_rs_peer", False)
                ) 
            else:
                raise ValueError("Invalid type_of_depeering. Must be 'completely_lost' or 'rs_to_non_rs'.")

            if previous_connections > 0:
                depeering_ratio = (previous_connections - current_connections) / previous_connections
                if depeering_ratio > max_depeering_ratio:
                    index_of_max_ratio = i
                    max_depeering_ratio = depeering_ratio
                    ixp_with_max_ratio = ixp_id

    return ixp_with_max_ratio, max_depeering_ratio, index_of_max_ratio


def get_ases_that_depeered_at_ixp_at_depeering_peak(all_data, ixp_id, index_of_max_depeering):
    """
    Returns the list of ASNs that de-peered at a specific IXP during the snapshot with the highest de-peering ratio.
    """
    if index_of_max_depeering <= 0 or index_of_max_depeering >= len(all_data):
        raise ValueError("index_of_max_depeering must be within the range of available snapshots.")

    current_snapshot = all_data[index_of_max_depeering]
    previous_snapshot = all_data[index_of_max_depeering - 1]

    current_asns = {
        get_asn_from_net(conn) for conn in current_snapshot.get("netixlan", {}).get("data", [])
        if conn.get("ix_id") == ixp_id
    }
    previous_asns = {
        get_asn_from_net(conn) for conn in previous_snapshot.get("netixlan", {}).get("data", [])
        if conn.get("ix_id") == ixp_id
    }

    depeered_asns = previous_asns - current_asns
    return list(depeered_asns)


def plot_ixp_connections_over_time_by_category(dates, timeline_data, completely_lost_ixp_ids, 
                                                depeered_nonpeered_ixp_ids,
                                                completely_lost_timeline_data, depeered_nonpeered_timeline_data,
                                                category_label, category_type, asn_to_analyze,
                                                plot_name_suffix, depeering_event_timelines=None):
    """
    Reusable function to plot IXP connections over time for a given category,
    comparing completely lost vs still have non-peered connections.
    
    Args:
        dates: List of date strings (e.g., ["2024-01-01", "2024-02-01"])
        timeline_data: Dict mapping ixp_id (str) to list of all connection counts over time
        completely_lost_ixp_ids: List/set of completely lost IXP IDs for this category
        depeered_nonpeered_ixp_ids: List/set of depeered IXP IDs with non-peered connections for this category
        completely_lost_timeline_data: Dict mapping ixp_id (str) to list of counts for completely lost IXPs
        depeered_nonpeered_timeline_data: Dict mapping ixp_id (str) to list of counts for IXPs with non-peered
        category_label: Label for this category (e.g., "Europe", "50-100", "0-30d")
        category_type: Type of categorization (e.g., "Region", "Size Range", "Age Range")
        asn_to_analyze: The ASN that de-peered
        plot_name_suffix: Suffix for the plot filename (e.g., "region_Europe", "range_50-100")
        depeering_event_timelines: Dict mapping ixp_id (str) to list of booleans indicating de-peering events over time
    """
    
    # Count IXPs in each category
    completely_lost_count = len(completely_lost_ixp_ids)
    depeered_nonpeered_count = len(depeered_nonpeered_ixp_ids)
    
    plt.figure(figsize=(12, 6))
    
    # Plot individual lines for completely lost IXPs
    completely_lost_ids_str = [str(ixp_id) for ixp_id in completely_lost_ixp_ids]
    for ixp_id in completely_lost_ids_str:
        if ixp_id in timeline_data:
            plt.plot(range(len(dates)), timeline_data[ixp_id], alpha=0.3, color='#ff9999')
    
    # Plot the average for completely lost IXPs
    if completely_lost_ids_str:
        avg_completely_lost = [sum(timeline_data[ixp_id][i] for ixp_id in completely_lost_ids_str if ixp_id in timeline_data) / len(completely_lost_ids_str) 
                               for i in range(len(dates))]
        plt.plot(range(len(dates)), avg_completely_lost, color='red', linewidth=3, label='Average (Completely Lost)')
        
        # Plot the median for completely lost IXPs
        median_completely_lost = [np.median([timeline_data[ixp_id][i] for ixp_id in completely_lost_ids_str if ixp_id in timeline_data]) 
                                  for i in range(len(dates))]
        plt.plot(range(len(dates)), median_completely_lost, color='darkred', linewidth=2, linestyle='--', 
                 label='Median (Completely Lost)')
    
    # Plot individual lines for depeered with non-peered IXPs
    depeered_nonpeered_ids_str = [str(ixp_id) for ixp_id in depeered_nonpeered_ixp_ids]
    for ixp_id in depeered_nonpeered_ids_str:
        if ixp_id in timeline_data:
            plt.plot(range(len(dates)), timeline_data[ixp_id], alpha=0.3, color='#99ccff')
    
    # Plot the average for depeered with non-peered IXPs
    if depeered_nonpeered_ids_str:
        avg_depeered_nonpeered = [sum(timeline_data[ixp_id][i] for ixp_id in depeered_nonpeered_ids_str if ixp_id in timeline_data) / len(depeered_nonpeered_ids_str) 
                                  for i in range(len(dates))]
        plt.plot(range(len(dates)), avg_depeered_nonpeered, color='blue', linewidth=3, label='Average (Still Has Non-Peered)')
        
        # Plot the median for depeered with non-peered IXPs
        median_depeered_nonpeered = [np.median([timeline_data[ixp_id][i] for ixp_id in depeered_nonpeered_ids_str if ixp_id in timeline_data]) 
                                     for i in range(len(dates))]
        plt.plot(range(len(dates)), median_depeered_nonpeered, color='darkblue', linewidth=2, linestyle='--', 
                 label='Median (Still Has Non-Peered)')
    
    # Plot de-peering events (when IXPs transition to completely lost)
    if depeering_event_timelines:
        depeering_event_counts = [0] * len(dates)
        
        for ixp_id, event_timeline in depeering_event_timelines.items():
            if len(event_timeline) == len(dates):
                for i, has_event in enumerate(event_timeline):
                    if has_event:
                        depeering_event_counts[i] += 1
        
        # Plot the de-peering event line if there are any events
        if any(depeering_event_counts):
            plt.plot(range(len(dates)), depeering_event_counts, color='gold', linewidth=3, 
                     label='De-Peering Events', marker='o', markersize=6)
    
    # Formatting with counts in title
    title = (f"IXP Connections Over Time - {category_type} {category_label}\n"
             f"(Completely Lost: {completely_lost_count} IXPs | Still Has Non-Peered: {depeered_nonpeered_count} IXPs | "
             f"ASN {asn_to_analyze})")
    
    plt.xticks(range(len(dates)), dates, rotation=45)
    plt.title(title)
    plt.xlabel("Date")
    plt.ylabel("Number of Connections (Total)")
    plt.legend()
    plt.grid(True)
    
    save_plot(plt, f"ixp_overtime_connections_{plot_name_suffix}_{asn_to_analyze}", 
              subfolder=PEERINGDB_SUBFOLDER_PREFIX + str(asn_to_analyze))
    plt.close()



if __name__ == "__main__":
    pass