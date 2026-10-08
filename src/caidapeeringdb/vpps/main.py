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
    Uses exact string matching on PeeringDB fallback to avoid over-matching.
    """
    vpp_asn_map = {}

    net_data = data.get("net", {}).get("data", [])
    pdb_name_to_asns = defaultdict(set)
    for net in net_data:
        asn = net.get("asn")
        name = net.get("name", "").strip().lower()
        if asn and name:
            pdb_name_to_asns[name].add(int(asn))

    for vpp in vpps_non_ixp:
        asns = extract_asns_from_vpp(vpp)

        # Fallback: exact match on ISP name against PeeringDB networks
        if not asns:
            isp_name = vpp.get("isp_name", "").split("\n")[0].strip().lower()
            if isp_name and isp_name in pdb_name_to_asns:
                asns.update(pdb_name_to_asns[isp_name])

        for asn in asns:
            vpp_asn_map[asn] = vpp

    print(f"Mapped {len(vpp_asn_map)} distinct ASNs from non-IXP VPPs.")
    return vpp_asn_map


def _get_connected_vpp_entities(snapshot, target_vpp_asns, vpp_asn_map):
    """
    Returns the set of unique VPP objects/identifiers (using id or isp_name)
    that have at least one IXP connection in a snapshot.
    """
    connected_vpps = set()
    for conn in snapshot.get("netixlan", {}).get("data", []):
        raw_asn = conn.get("asn") if conn.get("asn") is not None else conn.get("local_asn")
        if raw_asn is None:
            continue

        try:
            conn_asn = int(raw_asn)
        except (ValueError, TypeError):
            continue

        if conn_asn in target_vpp_asns:
            vpp_obj = vpp_asn_map[conn_asn]
            # Use a unique identifier for the VPP entity (e.g. primary ISP name line or id)
            vpp_id = vpp_obj.get("isp_name", "").split("\n")[0].strip()
            connected_vpps.add(vpp_id)

    return connected_vpps


def plot_vpps_with_ixp_connections_over_time(all_files, vpps_non_ixp):
    """
    Plots the percentage of unique VPP entities that have at least one IXP connection
    over time across all PeeringDB snapshot files.
    """
    latest_snapshot = get_data(all_files[-1])
    vpp_asn_map = build_vpp_asn_map(vpps_non_ixp, latest_snapshot)
    target_vpp_asns = set(vpp_asn_map.keys())

    dates = [file.split("/")[-1].split(".")[0] for file in all_files]
    all_snapshots = get_all_data(all_files)

    total_vpps_count = len(vpps_non_ixp)
    if total_vpps_count == 0:
        raise ValueError("No valid non-IXP VPPs found to evaluate.")

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
        title=f"Percentage of Unique VPPs with at Least One IXP Connection Over Time (Total VPPs: {total_vpps_count})",
        xlabel="Date",
        ylabel="Percentage of Connected VPPs (%)",
    )

    return dates, connected_vpps_pct_over_time


def plot_vpp_ixp_entries_and_exits_over_time(all_files, vpps_non_ixp):
    """
    Plots VPP entities entering and leaving IXP participation over time as a percentage.
    """
    if not all_files:
        raise ValueError("At least one PeeringDB snapshot is required.")

    latest_snapshot = get_data(all_files[-1])
    vpp_asn_map = build_vpp_asn_map(vpps_non_ixp, latest_snapshot)
    target_vpp_asns = set(vpp_asn_map.keys())
    
    dates = get_dates_from_files(all_files)
    snapshots = get_all_data(all_files)

    total_vpps_count = len(vpps_non_ixp)
    
    new_peerings_pct = [0.0]
    de_peerings_pct = [0.0]
    
    previous_connected_vpps = _get_connected_vpp_entities(snapshots[0], target_vpp_asns, vpp_asn_map)

    for snapshot in snapshots[1:]:
        connected_vpps = _get_connected_vpp_entities(snapshot, target_vpp_asns, vpp_asn_map)
        
        entered_count = len(connected_vpps - previous_connected_vpps)
        left_count = len(previous_connected_vpps - connected_vpps)
        
        new_peerings_pct.append(round((entered_count / total_vpps_count) * 100, 2))
        de_peerings_pct.append(round((left_count / total_vpps_count) * 100, 2))
        
        previous_connected_vpps = connected_vpps

    labels = [date.replace("_", "-") for date in dates]
    
    plot_list_as_line_plot(
        new_peerings_pct,
        y=labels,
        subfolder="vpps",
        title=f"New VPP IXP Peerings Over Time (Total VPPs: {total_vpps_count})",
        xlabel="Date",
        ylabel="% of VPPs entering an IXP",
        positive_color="green",
        negative_color="green",
    )
    plot_list_as_line_plot(
        de_peerings_pct,
        y=labels,
        subfolder="vpps",
        title=f"VPP IXP De-peerings Over Time (Total VPPs: {total_vpps_count})",
        xlabel="Date",
        ylabel="% of VPPs leaving all IXPs",
        positive_color="red",
        negative_color="red",
    )

    return dates, new_peerings_pct, de_peerings_pct

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


 

if __name__ == "__main__":
    all_files = get_all_files()
    latest_file = all_files[-1]
    print(f"Loading PeeringDB data snapshot: {latest_file}")
    data = get_data(latest_file)

    vpps_list = load_vpp_data()
    vpps_non_ixp = get_non_ixp_vpps(vpps_list, data)

    plot_vpps_with_ixp_connections_over_time(all_files, vpps_non_ixp)
    # vpp_participants, ixp_vpp_counts = analyze_vpp_ixp_participants(data, vpps_non_ixp)

    plot_vpp_ixp_entries_and_exits_over_time(all_files, vpps_non_ixp)