import matplotlib.pyplot as plt
import numpy as np
import re
from src.caidapeeringdb.utils import PEERINGDB_SUBFOLDER_PREFIX
from src.caidapeeringdb.caidapeeringdb_load import get_asn_from_net
from src.utils.graphs import clean_title_name, save_plot




def plot_ixps_connections_over_time(all_data, dates, ixp_ids, ixp_names=None, route_server_mode="all"):
   
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

    plt.figure(figsize=(12, 6))

    for ixp_id in target_ixp_ids:
        display_name = ixp_name_map.get(ixp_id, f"IXP {ixp_id}")
        plt.plot(
            range(len(dates)),
            timeline_data[ixp_id],
            alpha=0.2,
            linewidth=1.2,
            label=display_name,
        )

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

    plt.plot(range(len(dates)), average_values, color="black", linewidth=3, label="Average")
    plt.plot(range(len(dates)), median_values, color="dimgray", linewidth=2, linestyle="--", label="Median")

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

    if len(dates) > 8:
        step = max(1, len(dates) // 8)
        tick_positions = list(range(0, len(dates), step))
        tick_labels = [dates[i] for i in tick_positions]
        plt.xticks(tick_positions, tick_labels, rotation=45)
    else:
        plt.xticks(range(len(dates)), dates, rotation=45)

    plt.title(title)
    plt.xlabel("Date")
    plt.ylabel("Number of Peers")
    plt.legend()
    plt.grid(True)

    id_suffix = "_".join(str(ixp_id) for ixp_id in target_ixp_ids)
    save_plot(
        plt,
        clean_title_name(title),
        subfolder=PEERINGDB_SUBFOLDER_PREFIX + "ixp_overtime/"
    )
    plt.close()

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