import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.caidapeeringdb.caidapeeringdb_load import get_all_files, get_data
from src.ripe_bviews.read_bgpdump import BGPDumpSnapshotStats
from src.ripe_bviews.timeline.bview_timeline import (
    build_vpp_asn_map,
    get_non_ixp_vpps,
    load_vpp_data,
)


def analyze_vpp_routes_and_prefixes(all_required_data):
    """
    Analyzes route and prefix announcements for non-IXP VPPs
    at the current (latest) snapshot of `all_stats`.
    """
    # 1. Extract the current/latest snapshot stats
    all_stats, labels_summarized, max_labels = all_required_data["timeline"]
    current_stat: BGPDumpSnapshotStats = all_stats[-1]

    # 2. Fetch PeeringDB snapshot and filter non-IXP VPPs
    all_files = get_all_files()
    latest_file = all_files[-1]
    pdb_data = get_data(latest_file)

    vpps_list = load_vpp_data()
    vpps_non_ixp = get_non_ixp_vpps(vpps_list, pdb_data)
    vpp_asn_map = build_vpp_asn_map(vpps_non_ixp, pdb_data)
    vpp_asns = set(vpp_asn_map.keys())

    # 3. Analyze Routes announced by VPPs
    vpp_routes_count = 0
    vpp_routes_by_asn = {}

    for member_asn, mappings in current_stat.mappings.items():
        try:
            asn_int = int(member_asn)
        except (ValueError, TypeError):
            continue

        if asn_int in vpp_asns:
            vpp_routes_by_asn[asn_int] = len(mappings)
            vpp_routes_count += len(mappings)

    # 4. Analyze Prefixes announced by VPPs
    # Extract prefix mappings if available on BGPDumpSnapshotStats
    if hasattr(current_stat, "get_prefix_mappings"):
        prefix_member_has, prefix_member_reaches, _ = current_stat.get_prefix_mappings()
    elif hasattr(current_stat, "prefix_mappings"):
        prefix_member_has = current_stat.prefix_mappings
    else:
        prefix_member_has = {}

    vpp_prefixes = set()
    vpp_prefixes_by_asn = {}

    for member_asn, prefix_list in prefix_member_has.items():
        try:
            asn_int = int(member_asn)
        except (ValueError, TypeError):
            continue

        if asn_int in vpp_asns:
            vpp_prefixes_by_asn[asn_int] = len(prefix_list)
            vpp_prefixes.update(prefix_list)

    # 5. Output Summary Results
    print(f"\n--- Current VPP Announcement Summary ({current_stat.date}) ---")
    print(f"Total VPP ASNs monitored: {len(vpp_asns)}")
    print(f"VPP ASNs actively announcing routes: {len(vpp_routes_by_asn)}")
    print(f"Total Routes announced by VPPs: {vpp_routes_count}")
    print(f"Total Unique Prefixes announced by VPPs: {len(vpp_prefixes)}")

    print("\n--- Breakdown by VPP ASN ---")
    active_vpp_asns = set(vpp_routes_by_asn.keys()).union(vpp_prefixes_by_asn.keys())
    for asn in active_vpp_asns:
        vpp_info = vpp_asn_map.get(asn, {})
        vpp_name = vpp_info.get("isp_name", "").split("\n")[0].strip() or f"AS{asn}"
        routes = vpp_routes_by_asn.get(asn, 0)
        prefixes = vpp_prefixes_by_asn.get(asn, 0)
        print(f"• {vpp_name} (AS{asn}): {routes} routes, {prefixes} prefixes")

    return {
        "snapshot_date": getattr(current_stat, "date", None),
        "total_vpp_asns": len(vpp_asns),
        "active_vpp_asns": len(active_vpp_asns),
        "total_vpp_routes": vpp_routes_count,
        "total_unique_vpp_prefixes": len(vpp_prefixes),
        "routes_by_asn": vpp_routes_by_asn,
        "prefixes_by_asn": vpp_prefixes_by_asn,
    }

