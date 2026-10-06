import json
import sys
from collections import defaultdict
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.utils.graphs import plot_list_as_line_plot
 
from src.caidapeeringdb.caidapeeringdb_load import (
    get_all_data,
    get_all_files,
    get_all_ixps, 
    get_data,
    get_dates_from_files,
)
from src.google.vpps.vpp_ixps import (
    get_all_vpps_whose_name_matches_an_ixp_name,
    get_all_vpps_whose_name_matches_an_organization_that_owns_ixps,
)


def load_vpp_data():
    """Loads Google VPPs list from local JSON file."""
    with open(Path(__file__).parent / "google_vpps.json", "r", encoding="utf-8") as f:
        vpps_data = json.load(f)
        return vpps_data.get("gold", []) + vpps_data.get("silver", [])


def extract_asns_from_vpp(vpp):
    """
    Extracts all numeric ASNs from a VPP entry, whether stored as
    a single int/str, a list under 'asns'/'asn_list', or nested dicts.
    """
    found_asns = set()

    # Direct single keys
    for key in ("asn", "asn_number", "autsys"):
        val = vpp.get(key)
        if val is not None:
            if isinstance(val, list):
                for v in val:
                    try:
                        found_asns.add(int(str(v).strip().lower().replace("as", "")))
                    except (ValueError, TypeError):
                        pass
            else:
                try:
                    found_asns.add(int(str(val).strip().lower().replace("as", "")))
                except (ValueError, TypeError):
                    pass

    # List keys
    for key in ("asns", "asn_list", "autsys_list"):
        val = vpp.get(key, [])
        if isinstance(val, list):
            for v in val:
                try:
                    found_asns.add(int(str(v).strip().lower().replace("as", "")))
                except (ValueError, TypeError):
                    pass

    return found_asns


def get_non_ixp_vpps(vpps_list, data):
    """
    Filters VPPs to only include ASNs/organizations that ARE NOT IXPs 
    and DO NOT own IXPs.
    """
    # 1. Identify VPPs matching IXP names directly
    all_ixps = get_all_ixps(data)
    _, vpp_names_ixps, _ = get_all_vpps_whose_name_matches_an_ixp_name(vpps_list, all_ixps)

    # 2. Identify VPPs matching Organizations that own IXPs
    _, vpp_names_org_ixps, _ = get_all_vpps_whose_name_matches_an_organization_that_owns_ixps(vpps_list, data)

    # Combine names to exclude
    excluded_names = vpp_names_ixps.union(vpp_names_org_ixps)

    # Filter out VPPs whose ISP name matches excluded sets
    vpps_non_ixp = [
        vpp for vpp in vpps_list
        if vpp.get("isp_name", "").split("\n")[0].lower() not in excluded_names
    ]

    print(f"Total VPPs evaluated: {len(vpps_list)}")
    print(f"VPPs excluded (are IXPs or own IXPs): {len(vpps_list) - len(vpps_non_ixp)}")
    print(f"Valid VPPs remaining (NOT IXPs): {len(vpps_non_ixp)}")

    return vpps_non_ixp


def build_vpp_asn_map(vpps_non_ixp, data):
    """
    Builds a dictionary mapping ASN (int) -> VPP object.
    If a VPP entry does not explicitly list an ASN, attempts to match
    its isp_name against PeeringDB's 'net' records to extract its ASN.
    """
    vpp_asn_map = {}

    # Build name-to-ASN map from PeeringDB 'net' table as fallback
    net_data = data.get("net", {}).get("data", [])
    pdb_name_to_asns = defaultdict(set)
    for net in net_data:
        asn = net.get("asn")
        name = net.get("name", "").lower()
        if asn and name:
            pdb_name_to_asns[name].add(int(asn))

    for vpp in vpps_non_ixp:
        asns = extract_asns_from_vpp(vpp)

        # Fallback: match ISP name against PeeringDB networks if no ASNs in JSON
        if not asns:
            isp_name = vpp.get("isp_name", "").split("\n")[0].lower().strip()
            if isp_name:
                for pdb_name, pdb_asns in pdb_name_to_asns.items():
                    if isp_name in pdb_name or pdb_name in isp_name:
                        asns.update(pdb_asns)

        for asn in asns:
            vpp_asn_map[asn] = vpp

    print(f"Mapped {len(vpp_asn_map)} distinct ASNs from non-IXP VPPs.")
    return vpp_asn_map


def analyze_vpp_ixp_participants(data, vpps_non_ixp):
    """
    Extracts IXP participation data (netixlan) for non-IXP VPP ASNs.
    """
    vpp_asn_map = build_vpp_asn_map(vpps_non_ixp, data)

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

            participant_info = {
                "connection_id": conn.get("id"),
                "asn": conn_asn,
                "vpp_name": vpp_asn_map[conn_asn].get("isp_name", "").split("\n")[0],
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


def plot_vpps_with_ixp_connections_over_time(all_files, vpps_non_ixp):
    """
    Plots the count of unique VPPs that have at least one IXP connection (netixlan entry)
    over time across all PeeringDB snapshot files.
    """
    # 1. Map all valid VPP ASNs to a set for fast lookup
    vpp_asn_map = build_vpp_asn_map(vpps_non_ixp, get_data(all_files[-1]))
    target_vpp_asns = set(vpp_asn_map.keys())

    # 2. Extract snapshot dates and load all dataset snapshots
    dates = [file.split("/")[-1].split(".")[0] for file in all_files]
    all_snapshots = get_all_data(all_files)

    connected_vpps_over_time = []

    # 3. Process each snapshot over time
    for snapshot in all_snapshots:
        netixlan_data = snapshot.get("netixlan", {}).get("data", [])
        connected_vpps_in_snapshot = set()

        for conn in netixlan_data:
            raw_asn = conn.get("asn") if conn.get("asn") is not None else conn.get("local_asn")
            if raw_asn is None:
                continue

            try:
                conn_asn = int(raw_asn)
            except (ValueError, TypeError):
                continue

            if conn_asn in target_vpp_asns:
                # Store the distinct VPP entity (using ASN or VPP ISP name)
                connected_vpps_in_snapshot.add(conn_asn)

        connected_vpps_over_time.append(len(connected_vpps_in_snapshot))

    # 4. Total number of VPPs evaluated (non-IXPs)
    total_vpps_count = len(vpps_non_ixp)

    dates = [date.split("dump_")[1] for date in dates]

    print(dates)

    # 5. Render line plot
    plot_list_as_line_plot(
        connected_vpps_over_time,
        y=dates,
        subfolder="vpps",
        title=f"Unique VPPs with at Least One IXP Connection Over Time (Total VPPs: {total_vpps_count})",
        xlabel="Date",
        ylabel="Number of Unique Connected VPPs",
    )

    return dates, connected_vpps_over_time


def _get_connected_vpp_asns(snapshot, target_vpp_asns):
    """Returns VPP ASNs with at least one IXP connection in a snapshot."""
    connected_vpp_asns = set()
    for conn in snapshot.get("netixlan", {}).get("data", []):
        raw_asn = conn.get("asn") if conn.get("asn") is not None else conn.get("local_asn")
        if raw_asn is None:
            continue

        try:
            conn_asn = int(raw_asn)
        except (ValueError, TypeError):
            continue

        if conn_asn in target_vpp_asns:
            connected_vpp_asns.add(conn_asn)

    return connected_vpp_asns


def plot_vpp_ixp_entries_and_exits_over_time(all_files, vpps_non_ixp):
    """
    Plots VPPs entering and leaving IXP participation between snapshots.

    A VPP enters when its ASN is absent from the previous snapshot's
    netixlan records and present in the current snapshot. It leaves when the
    reverse transition occurs. Each VPP is counted once per snapshot,
    regardless of how many IXPs it uses.
    """
    if not all_files:
        raise ValueError("At least one PeeringDB snapshot is required.")

    vpp_asn_map = build_vpp_asn_map(vpps_non_ixp, get_data(all_files[-1]))
    target_vpp_asns = set(vpp_asn_map)
    dates = get_dates_from_files(all_files)
    snapshots = get_all_data(all_files)

    new_peerings = [0]
    de_peerings = [0]
    previous_connected_vpps = _get_connected_vpp_asns(snapshots[0], target_vpp_asns)

    for snapshot in snapshots[1:]:
        connected_vpps = _get_connected_vpp_asns(snapshot, target_vpp_asns)
        new_peerings.append(len(connected_vpps - previous_connected_vpps))
        de_peerings.append(len(previous_connected_vpps - connected_vpps))
        previous_connected_vpps = connected_vpps

    total_vpps_count = len(vpps_non_ixp)
    labels = [date.replace("_", "-") for date in dates]
    plot_list_as_line_plot(
        new_peerings,
        y=labels,
        subfolder="vpps",
        title=f"New VPP IXP Peerings Over Time (Total VPPs: {total_vpps_count})",
        xlabel="Date",
        ylabel="VPPs entering an IXP",
        positive_color="green",
        negative_color="green",
    )
    plot_list_as_line_plot(
        de_peerings,
        y=labels,
        subfolder="vpps",
        title=f"VPP IXP De-peerings Over Time (Total VPPs: {total_vpps_count})",
        xlabel="Date",
        ylabel="VPPs leaving all IXPs",
        positive_color="red",
        negative_color="red",
    )

    return dates, new_peerings, de_peerings


if __name__ == "__main__":
    all_files = get_all_files()
    latest_file = all_files[-1]
    print(f"Loading PeeringDB data snapshot: {latest_file}")
    data = get_data(latest_file)

    vpps_list = load_vpp_data()
    vpps_non_ixp = get_non_ixp_vpps(vpps_list, data)
    # vpp_participants, ixp_vpp_counts = analyze_vpp_ixp_participants(data, vpps_non_ixp)

    plot_vpp_ixp_entries_and_exits_over_time(all_files, vpps_non_ixp)