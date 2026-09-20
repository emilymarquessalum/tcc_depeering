


import sys

from inquirer import Path

from src.caidapeeringdb.caidapeeringdb_load import get_all_data
from src.caidapeeringdb.ixp_features.ixp_overtime_size import plot_ixp_connections_over_time_by_size_ranges
#from src.caidapeeringdb.main import build_asn_ixp_data_structures, load_timeline_data
from src.caidapeeringdb.loaders import load_all_files, config


def check_external_ixp_depeering_for_peak_ases(
    depeered_at_peak_ases_by_ixp: dict[int | str, set[int]],
    all_data: list[dict],
    target_asn: int,
    connections_over_time_for_asns: dict[int, list[tuple[str, list[dict]]]] = None
):
    """
    Analyzes whether ASes that de-peered from highest-peak IXPs (connected to target_asn)
    were also connected to, and de-peered from, IXPs that target_asn was NEVER connected to.
    
    External de-peerings are only counted if they occur AT OR AFTER the first snapshot 
    where the AS de-peered from a target peak IXP.
    """
    # Helper function to build an AS's timeline across all snapshots in all_data
    def build_as_snapshot_ixps(asn: int) -> list[set[str]]:
        snapshot_ixps = []
        for snapshot in all_data:
            active_ixps = set()
            for net in snapshot.get("netixlan", {}).get("data", []):
                if net.get("asn") == asn:
                    ix_id = net.get("ix_id")
                    if ix_id is not None:
                        active_ixps.add(str(ix_id))
            snapshot_ixps.append(active_ixps)
        return snapshot_ixps

    # 1. Gather all unique IXPs target_asn has EVER been connected to
    target_asn_ixps = set()
    if connections_over_time_for_asns and target_asn in connections_over_time_for_asns:
        for _, conns in connections_over_time_for_asns[target_asn]:
            for conn in conns:
                ix_id = conn.get("ix_id")
                if ix_id is not None:
                    target_asn_ixps.add(str(ix_id))
    else:
        # Fallback to building directly from all_data
        target_timeline = build_as_snapshot_ixps(target_asn)
        target_asn_ixps = set().union(*target_timeline) if target_timeline else set()

    # Map peak IXPs to string format for consistent set matching
    peak_ixps_by_as = {}
    peak_ases = set()
    for ixp_id, asns in depeered_at_peak_ases_by_ixp.items():
        if asns:
            ixp_str = str(ixp_id)
            for a in asns:
                asn_int = int(a)
                if asn_int != target_asn:
                    peak_ases.add(asn_int)
                    peak_ixps_by_as.setdefault(asn_int, set()).add(ixp_str)

    unique_peak_ases_count = len(peak_ases)

    ases_connected_to_external_ixps = set()
    ases_depeered_from_external_ixps = set()
    ases_depeered_from_external_at_same_time = set()

    # 3. Analyze external IXP connections and de-peerings for each peak AS
    for asn in peak_ases:
        snapshot_ixps_list = build_as_snapshot_ixps(asn)
        all_as_ixps = set().union(*snapshot_ixps_list) if snapshot_ixps_list else set()

        # IXPs NOT in target_asn's footprint
        external_ixps = all_as_ixps - target_asn_ixps
        target_peak_ixps_for_this_as = peak_ixps_by_as.get(asn, set())

        if external_ixps:
            ases_connected_to_external_ixps.add(asn)

            # Find the first snapshot index where this AS de-peered from an internal target IXP
            first_internal_depeer_idx = None
            for idx in range(1, len(snapshot_ixps_list)):
                prev_ixps = snapshot_ixps_list[idx - 1]
                curr_ixps = snapshot_ixps_list[idx]
                departed_target_peaks = (prev_ixps - curr_ixps) & target_peak_ixps_for_this_as
                
                if departed_target_peaks:
                    first_internal_depeer_idx = idx
                    break

            # If the AS never actually dropped from the target IXP in the timeline, skip external timing check
            if first_internal_depeer_idx is None:
                continue

            depeered_from_external_after_or_at_internal = False
            depeered_at_same_time = False

            # Scan transitions from first_internal_depeer_idx onwards
            for idx in range(1, len(snapshot_ixps_list)):
                prev_ixps = snapshot_ixps_list[idx - 1]
                curr_ixps = snapshot_ixps_list[idx]
                departed_ixps = prev_ixps - curr_ixps

                departed_target_peaks = departed_ixps & target_peak_ixps_for_this_as
                departed_externals = departed_ixps & external_ixps

                # 1. Only evaluate external de-peerings occurring AT or AFTER the first internal de-peering index
                if idx >= first_internal_depeer_idx and departed_externals:
                    depeered_from_external_after_or_at_internal = True

                # 2. Exact same snapshot co-occurrence
                if departed_target_peaks and departed_externals:
                    depeered_at_same_time = True

            if depeered_from_external_after_or_at_internal:
                ases_depeered_from_external_ixps.add(asn)
            if depeered_at_same_time:
                ases_depeered_from_external_at_same_time.add(asn)

    # 4. Print results
    print("\n" + "=" * 60)
    print(f"External IXP De-Peering Analysis (Target ASN: {target_asn})")
    print("=" * 60)
    print(f"Number of unique ASes from highest-peak lists: {unique_peak_ases_count}")
    print(f"ASes connected to IXPs NOT in target_asn footprint: {len(ases_connected_to_external_ixps)}")
    print(f"ASes that de-peered from external IXPs (AT or AFTER internal de-peering): {len(ases_depeered_from_external_ixps)}")
    print(f"ASes that de-peered from external IXPs specifically AT THE SAME SNAPSHOT: {len(ases_depeered_from_external_at_same_time)}")
    print("=" * 60 + "\n")

    return {
        "unique_peak_ases_count": unique_peak_ases_count,
        "connected_to_external_count": len(ases_connected_to_external_ixps),
        "depeered_from_external_count": len(ases_depeered_from_external_ixps),
        "depeered_from_external_at_same_time_count": len(ases_depeered_from_external_at_same_time),
        "ases_connected_to_external": ases_connected_to_external_ixps,
        "ases_depeered_from_external": ases_depeered_from_external_ixps,
        "ases_depeered_from_external_at_same_time": ases_depeered_from_external_at_same_time,
    }


if __name__ == "__main__":
    sys.exit(0)
    config_path = str(Path(__file__).parent)
    all_files_before_depeering, all_files_after_depeering = load_timeline_data(config_path)
    all_files = all_files_before_depeering + all_files_after_depeering
    
    all_data = get_all_data(all_files_before_depeering) + get_all_data(all_files_after_depeering)

        
    group_focused = config.get("group_focused")

    asns_to_search = [tuple(asn) for asn in config.get("asns_to_search", [])]
    asns_to_search = [asn for asn in asns_to_search if group_focused in asn[2] or group_focused is None]
    asns_to_search_for_analysis = [asns_to_search[0]] # Get the ASN to analyze
    asn_to_analyze = asns_to_search_for_analysis[0][0]  # Get the ASN number from tuple

    data_structures = build_asn_ixp_data_structures(asn_to_analyze, before_data, after_data, all_ixps)
    depeered_at_peak_ases_by_size_range = plot_ixp_connections_over_time_by_size_ranges(all_data, all_files, depeered_ixp_ids, depeered_ixp_sizes, asn_to_analyze, 
                                                                 completely_lost_ixp_ids=completely_lost_ixp_ids,
                                                                 ixp_names={ixp["id"]: ixp["name"] for ixp in all_ixps}, 
                                                                 connections_over_time_for_asns=connections_over_time_for_asns,
                                                                 depeered_with_nonpeered_ixp_ids=depeered_with_nonpeered_ixp_ids)
        
    check_external_ixp_depeering_for_peak_ases(
                depeered_at_peak_ases_by_ixp=depeered_at_peak_ases_by_size_range,
                all_data=all_data,
                connections_over_time_for_asns=connections_over_time_for_asns,
                target_asn=15169 # e.g. Google
    )