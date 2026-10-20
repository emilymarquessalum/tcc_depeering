import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
import re
from matplotlib import pyplot as plt

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.caidapeeringdb.ixp_features.continent_logic import organize_connections_by_continent
from src.utils.graphs import DEFAULT_FIGSIZE, plot_list_as_line_plot

from src.caidapeeringdb.caidapeeringdb_load import (
    get_all_data,
    get_all_files,
    get_all_ixps, 
    get_data,
    get_dates_from_files,
)
from src.google.vpps.google_vpps_list import get_google_vpp_asns


def build_vpp_asn_map(data=None): 
    raw_asns = get_google_vpp_asns(include_alternatives=False)
    target_asns = set()
    for asn in raw_asns:
        try:
            target_asns.add(int(str(asn).upper().replace("AS", "").strip()))
        except (ValueError, TypeError):
            continue

    vpp_asn_map = defaultdict(list)

    if data:
        net_data = data.get("net", {}).get("data", [])
        net_lookup = {
            int(net["asn"]): net.get("name", "Unknown VPP") 
            for net in net_data if net.get("asn")
        }
        
        for asn in target_asns:
            vpp_name = net_lookup.get(asn, f"VPP AS{asn}")
            vpp_asn_map[asn].append({"isp_name": vpp_name, "asn": asn})
    else:
        for asn in target_asns:
            vpp_asn_map[asn].append({"isp_name": f"VPP AS{asn}", "asn": asn})

    print(f"Mapped {len(vpp_asn_map)} distinct target VPP ASNs from google_vpps_list.")
    return dict(vpp_asn_map)


def get_connected_vpp_asns(snapshot, target_vpp_asns):
    """
    Returns the set of target VPP ASNs (as integers) that have
    at least one IXP connection in the provided PeeringDB snapshot.
    """
    connected_asns = set()
    for conn in snapshot.get("netixlan", {}).get("data", []):
        raw_asn = conn.get("asn") if conn.get("asn") is not None else conn.get("local_asn")
        if raw_asn is None:
            continue

        try:
            conn_asn = int(raw_asn)
        except (ValueError, TypeError):
            continue

        if conn_asn in target_vpp_asns:
            connected_asns.add(conn_asn)

    return connected_asns


def _get_connected_vpp_entities(snapshot, target_vpp_asns, vpp_asn_map):
    """
    Returns the set of unique VPP identifiers (using isp_name)
    that have at least one IXP connection in a snapshot.
    """
    connected_vpps = set()
    connected_asns = get_connected_vpp_asns(snapshot, target_vpp_asns)

    for conn_asn in connected_asns:
        vpp_objs = vpp_asn_map.get(conn_asn, [])
        if isinstance(vpp_objs, list):
            for vpp_obj in vpp_objs:
                vpp_id = vpp_obj.get("isp_name", "").split("\n")[0].strip()
                if vpp_id:
                    connected_vpps.add(vpp_id)
        else:
            vpp_id = vpp_objs.get("isp_name", "").split("\n")[0].strip()
            if vpp_id:
                connected_vpps.add(vpp_id)

    return connected_vpps


def get_vpp_ixp_connection_status_map(all_files, all_snapshots, vpp_asn_map):
    target_vpp_asns = set(vpp_asn_map.keys())
    status_map = {}

    for file_path, snapshot in zip(all_files, all_snapshots):
        f_name = Path(file_path).name
        
        # Match year (20xx), month, day with optional underscores or dashes
        match = re.search(r"(20\d{2})[-_]?(\d{2})[-_]?(\d{2})", f_name)
        if not match:
            continue
        
        # Reconstruct YYYYMMDD cleanly
        clean_date = "".join(match.groups())

        connected = get_connected_vpp_asns(snapshot, target_vpp_asns)
        unconnected = target_vpp_asns - connected

        status_map[clean_date] = {
            "connected_asns": connected,
            "unconnected_asns": unconnected,
        }

    return status_map


def plot_vpps_with_percentage_ixp_connections_over_time(all_files, all_snapshots, vpp_asn_map):
    """
    Plots the percentage of unique VPP entities that have at least one IXP connection
    over time across all PeeringDB snapshot files.
    """
    latest_snapshot = get_data(all_files[-1])
    target_vpp_asns = set(vpp_asn_map.keys())

    dates = [file.split("/")[-1].split(".")[0] for file in all_files]

    total_vpps_count = len(target_vpp_asns)
    if total_vpps_count == 0:
        raise ValueError("No valid VPP ASNs found to evaluate.")

    connected_vpps_pct_over_time = []

    for snapshot in all_snapshots:
        connected_vpps = _get_connected_vpp_entities(snapshot, target_vpp_asns, vpp_asn_map)
        pct_connected = (len(connected_vpps) / total_vpps_count) * 100
        connected_vpps_pct_over_time.append(round(pct_connected, 2))

    dates = [date.split("dump_")[1] for date in dates]

    plot_list_as_line_plot(
        connected_vpps_pct_over_time,
        y=dates,
        subfolder="vpps",
        title="Percentage of Unique VPPs with at Least One IXP Connection Over Time",
        xlabel="Date",
        ylabel="Percentage of Connected VPPs (%)",
        max_labels=12
    )

    return dates, connected_vpps_pct_over_time


def plot_vpps_total_ixp_connections_over_time(
    all_files, all_snapshots, vpp_asn_map, consider_only_one_connection_per_ixp=True
):  
    target_vpp_asns = set(vpp_asn_map.keys())

    dates = [file.split("/")[-1].split(".")[0] for file in all_files] 

    total_vpps_count = len(target_vpp_asns)
    if total_vpps_count == 0:
        raise ValueError("No valid VPP ASNs found to evaluate.")

    total_ixp_connections_over_time = []

    for snapshot in all_snapshots:
        if consider_only_one_connection_per_ixp:
            seen_ixp_connections = set()
            for conn in snapshot.get("netixlan", {}).get("data", []):
                raw_asn = conn.get("asn") if conn.get("asn") is not None else conn.get("local_asn")
                if raw_asn is None:
                    continue
                try:
                    conn_asn = int(raw_asn)
                except (ValueError, TypeError):
                    continue

                if conn_asn in target_vpp_asns:
                    ixp_id = conn.get("ix_id")
                    if ixp_id is not None:
                        seen_ixp_connections.add((conn_asn, ixp_id))

            total_connections = len(seen_ixp_connections)
        else:
            total_connections = 0
            for conn in snapshot.get("netixlan", {}).get("data", []):
                raw_asn = conn.get("asn") if conn.get("asn") is not None else conn.get("local_asn")
                if raw_asn is None:
                    continue
                try:
                    conn_asn = int(raw_asn)
                except (ValueError, TypeError):
                    continue

                if conn_asn in target_vpp_asns:
                    total_connections += 1

        total_ixp_connections_over_time.append(total_connections)

    dates = [date.split("dump_")[1] for date in dates]

    plot_list_as_line_plot(
        total_ixp_connections_over_time,
        y=dates,
        subfolder="vpps",
        title="Total IXP Connections Across VPPs Over Time",
        xlabel="Date",
        ylabel="Total Number of IXP Connections",
        max_labels=7,
        fontsize=18
    )

    return dates, total_ixp_connections_over_time


def plot_vpp_ixp_entries_and_exits_over_time(all_files, snapshots, vpp_asn_map):
    """
    Plots the absolute number of VPP entities entering and leaving IXP participation over time,
    and prints which ASes/VPP entities entered or left at each date.
    """
    if not all_files:
        raise ValueError("At least one PeeringDB snapshot is required.")
 
    target_vpp_asns = set(vpp_asn_map.keys())
    
    dates = get_dates_from_files(all_files) 
    
    new_peerings_count = [0]
    de_peerings_count = [0]
    
    previous_connected_vpps = _get_connected_vpp_entities(snapshots[0], target_vpp_asns, vpp_asn_map)

    for i, snapshot in enumerate(snapshots[1:], start=1):
        connected_vpps = _get_connected_vpp_entities(snapshot, target_vpp_asns, vpp_asn_map)
        
        entered_vpps = connected_vpps - previous_connected_vpps
        left_vpps = previous_connected_vpps - connected_vpps
        
        entered_count = len(entered_vpps)
        left_count = len(left_vpps)

        date_str = dates[i].replace("_", "-")
        if entered_vpps:
            print(f"[{date_str}] Entered IXP participation ({entered_count}): {', '.join(sorted(entered_vpps))}")
        if left_vpps:
            print(f"[{date_str}] Left IXP participation ({left_count}): {', '.join(sorted(left_vpps))}")
        
        new_peerings_count.append(entered_count)
        de_peerings_count.append(left_count)
        
        previous_connected_vpps = connected_vpps

    labels = [date.replace("_", "-") for date in dates]
    
    plot_list_as_line_plot(
        new_peerings_count,
        y=labels,
        subfolder="vpps",
        title="New VPP IXP Peerings Over Time",
        xlabel="Date",
        ylabel="Number of VPPs entering an IXP",
        positive_color="green",
        negative_color="green",
        fontsize=18,
        max_labels=12
    )
    plot_list_as_line_plot(
        de_peerings_count,
        y=labels,
        subfolder="vpps",
        title="VPP IXP De-peerings Over Time",
        xlabel="Date",
        ylabel="Number of VPPs leaving all IXPs",
        positive_color="red",
        negative_color="red",
        max_labels=12
    )

    return dates, new_peerings_count, de_peerings_count
 
import itertools

def plot_ixp_entries_and_exits_over_time(all_files, snapshots, vpp_asn_map):
    """
    Plots the absolute and cumulative (accumulated) number of IXP entries 
    and exits (VPP-IXP connection pairings) over time.
    """
    if not all_files:
        raise ValueError("At least one PeeringDB snapshot is required.")
 
    target_vpp_asns = set(vpp_asn_map.keys())
    dates = get_dates_from_files(all_files) 

    def _get_vpp_ixp_pairs(snapshot):
        pairs = set()
        for conn in snapshot.get("netixlan", {}).get("data", []):
            raw_asn = conn.get("asn") if conn.get("asn") is not None else conn.get("local_asn")
            if raw_asn is None:
                continue
            try:
                conn_asn = int(raw_asn)
            except (ValueError, TypeError):
                continue

            if conn_asn in target_vpp_asns:
                ixp_id = conn.get("ix_id")
                if ixp_id is not None:
                    pairs.add((conn_asn, ixp_id))
        return pairs

    new_peerings_count = [0]
    de_peerings_count = [0]
    
    previous_pairs = _get_vpp_ixp_pairs(snapshots[0])

    for snapshot in snapshots[1:]:
        current_pairs = _get_vpp_ixp_pairs(snapshot)
        
        entered_count = len(current_pairs - previous_pairs)
        left_count = len(previous_pairs - current_pairs)
        
        new_peerings_count.append(entered_count)
        de_peerings_count.append(left_count)
        
        previous_pairs = current_pairs

    accumulated_new_peerings = list(itertools.accumulate(new_peerings_count))
    accumulated_de_peerings = list(itertools.accumulate(de_peerings_count))

    labels = [date.replace("_", "-") for date in dates]
    
    plot_list_as_line_plot(
        new_peerings_count,
        y=labels,
        subfolder="vpps",
        title="New IXP Connections Over Time",
        xlabel="Date",
        ylabel="Number of New Connections Added",
        positive_color="green",
        negative_color="green",
        fontsize=18,
        max_labels=12
    )
    plot_list_as_line_plot(
        de_peerings_count,
        y=labels,
        subfolder="vpps",
        title="IXP De-peerings Over Time",
        xlabel="Date",
        ylabel="Number of Connections Removed",
        positive_color="red",
        negative_color="red",
        max_labels=12
    )

    plot_list_as_line_plot(
        accumulated_new_peerings,
        y=labels,
        subfolder="vpps",
        title="Accumulated New IXP Connections Over Time",
        xlabel="Date",
        ylabel="Cumulative New Connections Added",
        positive_color="green",
        negative_color="green",
        fontsize=18,
        max_labels=12
    )
    plot_list_as_line_plot(
        accumulated_de_peerings,
        y=labels,
        subfolder="vpps",
        title="Accumulated IXP De-peerings Over Time",
        xlabel="Date",
        ylabel="Cumulative Connections Removed",
        positive_color="red",
        negative_color="red",
        max_labels=12
    )

    return dates, new_peerings_count, de_peerings_count, accumulated_new_peerings, accumulated_de_peerings


def analyze_vpp_ixp_participants(data):
    """
    Extracts IXP participation data (netixlan) for VPP ASNs.
    """
    vpp_asn_map = build_vpp_asn_map(data)

    netixlan_data = data.get("netixlan", {}).get("data", [])
    ixp_lookup = {ixp["id"]: ixp for ixp in get_all_ixps(data)}

    vpp_participants = defaultdict(list)
    ixp_vpp_counts = defaultdict(int)
    rs_peered_count = 0

    for conn in netixlan_data:
        raw_asn = conn.get("asn") if conn.get("asn") is not None else conn.get("local_asn")
        if raw_asn is None:
            continue

        try:
            conn_asn = int(raw_asn)
        except (ValueError, TypeError):
            continue

        if conn_asn in vpp_asn_map:
            ixp_id = conn.get("ix_id")
            ixp_info = ixp_lookup.get(ixp_id, {})

            vpp_objs = vpp_asn_map[conn_asn]
            vpp_name = vpp_objs[0].get("isp_name", "").split("\n")[0] if vpp_objs else f"AS{conn_asn}"

            participant_info = {
                "connection_id": conn.get("id"),
                "asn": conn_asn,
                "vpp_name": vpp_name,
                "ixp_id": ixp_id,
                "ixp_name": ixp_info.get("name", "Unknown IXP"),
                "is_rs_peer": conn.get("is_rs_peer", False),
                "speed": conn.get("speed", 0),
            }

            vpp_participants[conn_asn].append(participant_info)
            ixp_vpp_counts[ixp_id] += 1
            if conn.get("is_rs_peer"):
                rs_peered_count += 1

    print("\n--- IXP Participation Summary ---")
    print(f"Total VPP connections found across IXPs: {sum(len(conns) for conns in vpp_participants.values())}")
    print(f"Total VPP ASNs present in at least one IXP: {len(vpp_participants)}")
    print(f"Total unique IXPs with VPP participants: {len(ixp_vpp_counts)}")
    print(f"Connections peered via Route Server: {rs_peered_count}")

    return vpp_participants, ixp_vpp_counts


def plot_vpp_average_ixp_speed_over_time(all_files, all_snapshots, convert_to_gbps=True, use_median=False):
    """
    Plots the average/median speed of VPP IXP connections over time across PeeringDB snapshots.
    """
    if not all_files:
        raise ValueError("At least one PeeringDB snapshot is required.")

    latest_snapshot = get_data(all_files[-1])
    vpp_asn_map = build_vpp_asn_map(latest_snapshot)
    target_vpp_asns = set(vpp_asn_map.keys())

    dates = get_dates_from_files(all_files) 

    speeds_over_time = []

    for snapshot in all_snapshots:
        speeds = []
        netixlan_entries = snapshot.get("netixlan", {}).get("data", [])

        for conn in netixlan_entries:
            raw_asn = conn.get("asn") if conn.get("asn") is not None else conn.get("local_asn")
            if raw_asn is None:
                continue

            try:
                conn_asn = int(raw_asn)
            except (ValueError, TypeError):
                continue

            if conn_asn in target_vpp_asns:
                speed = conn.get("speed")
                if speed is not None:
                    try:
                        speed_val = int(speed)
                        if speed_val > 0:
                            speeds.append(speed_val)
                    except (ValueError, TypeError):
                        pass

        if speeds:
            val = statistics.median(speeds) if use_median else (sum(speeds) / len(speeds))
            if convert_to_gbps:
                val = val / 1000.0
        else:
            val = 0.0

        speeds_over_time.append(round(val, 2))

    labels = [date.replace("_", "-") for date in dates]
    unit = "Gbps" if convert_to_gbps else "Mbps"
    stat_type = "Median" if use_median else "Average"

    plot_list_as_line_plot(
        speeds_over_time,
        y=labels,
        subfolder="vpps",
        title=f"{stat_type} VPP Connection Speed at IXPs Over Time ({unit})",
        xlabel="Date",
        ylabel=f"{stat_type} Speed ({unit})",
        max_labels=7,
        fontsize=18
    )

    return dates, speeds_over_time


def plot_google_vs_vpp_total_port_speed_over_time(
    all_files,
    all_snapshots,
    google_asns={15169},
    convert_to_tbps=True,
    output_dir="plots/vpps",
):
    """
    Plots Google's total port speed vs. VPP total port speed across all IXPs over time.
    """
    if not all_files:
        raise ValueError("At least one PeeringDB snapshot is required.")

    latest_snapshot = get_data(all_files[-1])
    vpp_asn_map = build_vpp_asn_map(latest_snapshot)
    target_vpp_asns = set(vpp_asn_map.keys())

    dates = get_dates_from_files(all_files) 

    divisor = 1000000.0 if convert_to_tbps else 1000.0
    unit = "Tbps" if convert_to_tbps else "Gbps"

    google_totals = []
    vpp_totals = []

    for snapshot in all_snapshots:
        google_speed_mbps = 0
        vpp_speed_mbps = 0

        netixlan_entries = snapshot.get("netixlan", {}).get("data", [])

        for conn in netixlan_entries:
            raw_asn = (
                conn.get("asn")
                if conn.get("asn") is not None
                else conn.get("local_asn")
            )
            if raw_asn is None:
                continue

            try:
                conn_asn = int(raw_asn)
            except (ValueError, TypeError):
                continue

            speed = conn.get("speed")
            if speed is None:
                continue

            try:
                speed_val = int(speed)
                if speed_val <= 0:
                    continue
            except (ValueError, TypeError):
                continue

            if conn_asn in google_asns:
                google_speed_mbps += speed_val
            if conn_asn in target_vpp_asns:
                vpp_speed_mbps += speed_val

        google_totals.append(round(google_speed_mbps / divisor, 2))
        vpp_totals.append(round(vpp_speed_mbps / divisor, 2))

    labels = [date.replace("_", "-") for date in dates]

    plt.figure(figsize=DEFAULT_FIGSIZE)
 
    plt.plot(
        labels,
        google_totals,
        marker="o",
        linewidth=2,
        color="#4285F4",
        label=f"Google (ASNs: {', '.join(map(str, google_asns))})",
    )
    plt.plot(
        labels,
        vpp_totals,
        marker="s",
        linewidth=2,
        color="#EA4335",
        label=f"All VPPs (Total Count: {len(target_vpp_asns)})",
    )

    plt.title(
        f"Total IXP Port Speed: Google vs. VPPs Over Time ({unit})",
        fontsize=14,
        pad=15,
    )
    plt.xlabel("Date", fontsize=12)
    plt.ylabel(f"Total Port Speed ({unit})", fontsize=12)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend(fontsize=11)

    max_labels = 12
    if len(labels) > max_labels:
        step = len(labels) // max_labels
        plt.xticks(
            ticks=range(0, len(labels), step),
            labels=[labels[i] for i in range(0, len(labels), step)],
            rotation=45,
        )
    else:
        plt.xticks(rotation=45)

    plt.tight_layout()

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path / "google_vs_vpp_total_port_speed.png", dpi=300)
    plt.show()

    return dates, google_totals, vpp_totals



def plot_vpp_ixp_geographical_distribution_over_time(all_files, all_snapshots, vpp_asn_map):
    """
    Plots the geographical distribution (by continent) of IXPs that VPPs 
    are connected to over time across all PeeringDB snapshot files.
    """
    if not all_files or not all_snapshots:
        raise ValueError("At least one snapshot is required.")

    target_vpp_asns = set(vpp_asn_map.keys())

    # Get all unique IXPs from the latest snapshot for metadata lookups
    all_ixps = get_all_ixps(all_snapshots[-1])

    connections_over_time = []

    for file_path, snapshot in zip(all_files, all_snapshots):
        raw_date = Path(file_path).stem
        clean_date = re.sub(r"\D", "", raw_date)

        vpp_ixp_connections = []
        for conn in snapshot.get("netixlan", {}).get("data", []):
            raw_asn = conn.get("asn") if conn.get("asn") is not None else conn.get("local_asn")
            if raw_asn is None:
                continue

            try:
                conn_asn = int(raw_asn)
            except (ValueError, TypeError):
                continue

            if conn_asn in target_vpp_asns:
                vpp_ixp_connections.append(conn)

        connections_over_time.append((clean_date, vpp_ixp_connections))

    # Organize connections by continent using logic from continent_logic
    continent_data_series, dates_for_plot, sorted_continents = organize_connections_by_continent(
        connections_over_time, all_ixps
    )

    # Plot stacked bar chart or individual continent line plots
    plt.figure(figsize=DEFAULT_FIGSIZE)
    labels = [date.replace("_", "-") for date in dates_for_plot]

    for continent in sorted_continents:
        plt.plot(
            labels,
            continent_data_series[continent],
            marker="o",
            linewidth=2,
            label=continent
        )

    plt.title("Geographical Distribution of IXP Connections for VPPs Over Time", fontsize=14, pad=15)
    plt.xlabel("Date", fontsize=12)
    plt.ylabel("Number of IXP Connections", fontsize=12)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend(fontsize=11, title="Continent")

    max_labels = 12
    if len(labels) > max_labels:
        step = len(labels) // max_labels
        plt.xticks(
            ticks=range(0, len(labels), step),
            labels=[labels[i] for i in range(0, len(labels), step)],
            rotation=45,
        )
    else:
        plt.xticks(rotation=45)

    plt.tight_layout()

    out_path = Path("plots/vpps")
    out_path.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path / "vpp_ixp_geographical_distribution.png", dpi=300)
    plt.show()

    return dates_for_plot, continent_data_series


def plot_vpp_percentage_of_google_rs_ixps_over_time(
    all_files,
    all_snapshots,
    vpp_asn_map,
    google_asns={15169},
    cutoff_year=2024,
    output_dir="plots/vpps"
): 
    if not all_files or not all_snapshots:
        raise ValueError("At least one PeeringDB snapshot is required.")

    target_vpp_asns = set(vpp_asn_map.keys())

    # Step 1: Extract unique IXP IDs where Google had a Route Server connection before `cutoff_year`
    google_rs_ixps_pre_2024 = set()

    for file_path, snapshot in zip(all_files, all_snapshots):
        f_name = file_path.split("/")[-1]
        
        # Extract year from filename (e.g., peeringdb_2_dump_2023_01_01.json)
        match = re.search(r"(20\d{2})", f_name)
        if not match:
            continue
        
        year = int(match.group(1))
        if year < cutoff_year:
            for conn in snapshot.get("netixlan", {}).get("data", []):
                raw_asn = conn.get("asn") if conn.get("asn") is not None else conn.get("local_asn")
                if raw_asn is None:
                    continue
                try:
                    conn_asn = int(raw_asn)
                except (ValueError, TypeError):
                    continue

                if conn_asn in google_asns and bool(conn.get("is_rs_peer")):
                    ix_id = conn.get("ix_id")
                    if ix_id is not None:
                        google_rs_ixps_pre_2024.add(ix_id)

    total_google_ixps = len(google_rs_ixps_pre_2024)
    if total_google_ixps == 0:
        raise ValueError(f"No IXPs found with Google Route Server connections prior to {cutoff_year}.")

    print(f"Found {total_google_ixps} distinct IXPs with Google Route Server connections before {cutoff_year}.")

    # Step 2: Track VPP connections to these specific Google IXPs over time
    dates = get_dates_from_files(all_files)
    labels = [date.replace("_", "-") for date in dates]
    pct_over_time = []

    for snapshot in all_snapshots:
        vpp_connected_ixps = set()
        
        for conn in snapshot.get("netixlan", {}).get("data", []):
            raw_asn = conn.get("asn") if conn.get("asn") is not None else conn.get("local_asn")
            if raw_asn is None:
                continue
            try:
                conn_asn = int(raw_asn)
            except (ValueError, TypeError):
                continue

            if conn_asn in target_vpp_asns:
                ix_id = conn.get("ix_id")
                if ix_id is not None:
                    vpp_connected_ixps.add(ix_id)

        # Overlap between Google pre-2024 RS IXPs and IXPs currently connected to by any VPP
        matched_ixps = google_rs_ixps_pre_2024.intersection(vpp_connected_ixps)
        pct = (len(matched_ixps) / total_google_ixps) * 100.0
        pct_over_time.append(round(pct, 2))

    # Step 3: Plot the line graph
    plot_list_as_line_plot(
        pct_over_time,
        y=labels,
        subfolder="vpps",
        title=f"% of Google Pre-{cutoff_year} RS IXPs Connected to by VPPs Over Time",
        xlabel="Date",
        ylabel="% of Google RS IXPs Connected to by VPPs",
        max_labels=12,
        fontsize=18
    )

    return labels, pct_over_time, google_rs_ixps_pre_2024


if __name__ == "__main__":
    all_files = get_all_files()
    latest_file = all_files[-1] 

    all_snapshots = get_all_data(all_files)
    
    latest_snapshot = get_data(all_files[-1]) 
    print(f"Latest PeeringDB snapshot: {latest_file} with {len(latest_snapshot.get('netixlan', {}).get('data', []))} netixlan entries.")
    vpp_asn_map = build_vpp_asn_map(latest_snapshot)

    plot_vpps_with_percentage_ixp_connections_over_time(all_files, all_snapshots, vpp_asn_map)
    plot_vpps_total_ixp_connections_over_time(all_files, all_snapshots, vpp_asn_map)

    plot_vpp_ixp_entries_and_exits_over_time(all_files, all_snapshots, vpp_asn_map)
    plot_ixp_entries_and_exits_over_time(all_files, all_snapshots, vpp_asn_map)

    plot_vpp_average_ixp_speed_over_time(all_files, all_snapshots, use_median=True)

    plot_vpp_ixp_geographical_distribution_over_time(all_files, all_snapshots, vpp_asn_map)

    dates, percentages, google_ixps = plot_vpp_percentage_of_google_rs_ixps_over_time(
        all_files, all_snapshots, vpp_asn_map
    )