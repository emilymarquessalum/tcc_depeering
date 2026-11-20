from pathlib import Path
import sys
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.caidapeeringdb.caidapeeringdb_load import get_all_data, get_data, get_unique_ixps_from_data_list 
from src.utils.graphs import plot_lists_as_plot_list_with_multiple_lines
from src.caidapeeringdb.build_structures import build_asn_ixp_data_structures
from src.caidapeeringdb.loaders import load_timeline_data



def plot_depeered_sessions_split_by_rs_timeline(
    all_data,
    all_files,
    data_structures,
    asn_to_analyze,
    start_date,
    end_date,
    depeerings_as_rs_depeers=True,
):
    """
    Plots aggregated Route Server and Non-Route Server connections (as well as total distinct ASNs)
    over time across all IXPs de-peered by a specific AS (not split by region).

    Args:
        all_data: List of PeeringDB snapshot dicts across the timeline.
        all_files: List of file paths corresponding to all_data.
        data_structures: Output from build_asn_ixp_data_structures().
        asn_to_analyze: Target ASN whose de-peered IXPs are analyzed.
        start_date: Baseline date string (e.g., "2024_01_01").
        end_date: Comparison end date string (e.g., "2026_09_01").
        depeerings_as_rs_depeers: Boolean controlling which IXPs to include:
            - True: IXPs where asn_to_analyze dropped Route Server peering.
            - False: IXPs where asn_to_analyze completely left the IXP infrastructure.
    """
    dates = [file.split("/")[-1].split(".")[0] for file in all_files]
    file_by_date = {date: file for date, file in zip(dates, all_files)}

    # --- STEP 1: Determine target IXPs based on depeerings_as_rs_depeers ---
    if depeerings_as_rs_depeers:
        depeered_ixp_ids = set(data_structures.get("depeered_ixp_ids", set()))
    else:
        start_snapshot = all_data[0] if start_date not in file_by_date else get_data(file_by_date[start_date])
        end_snapshot = all_data[-1] if end_date not in file_by_date else get_data(file_by_date[end_date])

        start_ixps = {
            conn.get("ix_id")
            for conn in start_snapshot.get("netixlan", {}).get("data", [])
            if (conn.get("asn") or conn.get("local_asn")) == asn_to_analyze and conn.get("ix_id")
        }
        end_ixps = {
            conn.get("ix_id")
            for conn in end_snapshot.get("netixlan", {}).get("data", [])
            if (conn.get("asn") or conn.get("local_asn")) == asn_to_analyze and conn.get("ix_id")
        }
        depeered_ixp_ids = start_ixps - end_ixps

    if not depeered_ixp_ids:
        print(f"No de-peered IXPs found for AS{asn_to_analyze} to track over the timeline.")
        return

    depeer_mode_label = "RS De-peered" if depeerings_as_rs_depeers else "Completely Left"
    print(f"Tracking RS and Non-RS sessions across {len(depeered_ixp_ids)} IXPs ({depeer_mode_label}) for AS{asn_to_analyze}.")

    # --- STEP 2: Gather aggregated RS vs Non-RS timeline metrics ---
    rs_total_timeline = []
    non_rs_total_timeline = []
    unique_total_timeline = []

    for data in all_data:
        global_rs_sessions = set()
        global_non_rs_sessions = set()
        global_all_sessions = set()

        for conn in data.get("netixlan", {}).get("data", []):
            ix_id = conn.get("ix_id")
            if ix_id not in depeered_ixp_ids:
                continue

            asn = conn.get("asn") or conn.get("local_asn")
            if not asn:
                continue

            session_key = (ix_id, asn)
            global_all_sessions.add(session_key)

            if conn.get("is_rs_peer", False):
                global_rs_sessions.add(session_key)
            else:
                global_non_rs_sessions.add(session_key)

        # Avoid double-counting an AS at the same IXP if it has both an RS port and a non-RS port
        global_non_rs_sessions.difference_update(global_rs_sessions)
        unique_asns_at_group = {asn for (_, asn) in global_all_sessions}

        rs_total_timeline.append(len(global_rs_sessions))
        non_rs_total_timeline.append(len(global_non_rs_sessions))
        unique_total_timeline.append(len(unique_asns_at_group))

    # --- STEP 3: Format payload for the plotting utility ---
    lines_payload = [
        {"data": rs_total_timeline, "label": "Route Server Connections", "color": "tab:green"},
        {"data": non_rs_total_timeline, "label": "Non-Route Server Connections", "color": "tab:orange"},
        {"data": unique_total_timeline, "label": "Distinct AS Networks", "color": "tab:blue", "linestyle": "--"},
    ]

    # --- STEP 4: Plot the data ---
    plot_lists_as_plot_list_with_multiple_lines(
        lines_data=lines_payload,
        x_labels=dates,
        title=f"RS vs Non-RS Connections Over Time on IXPs {depeer_mode_label} by AS{asn_to_analyze}",
        xlabel="Snapshot Dates",
        ylabel="Combined Member Connections Count",
        subfolder="peeringdb_connections",
        use_rotated_labels=True,
    )


if __name__ == "__main__":
    config_path = str(Path(__file__).parent.parent)
    all_files_before_depeering, all_files_after_depeering = load_timeline_data(config_path)
    all_files = all_files_before_depeering + all_files_after_depeering

    all_files = [file for file in all_files if "2024_05_01" not in file and "2025_02_01" not in file]

    start_date = "2024_01_01"
    end_date = "2026_09_01"

    all_data = get_all_data(all_files, use_cache=False)
    asn_to_analyze = 15169

    before_data = get_data(all_files[0])
    after_data = get_data(all_files[-1])
    print(f"Using date range from {all_files[0]} to {all_files[-1]} for analysis.")

    all_ixps = get_unique_ixps_from_data_list([after_data])

    data_structures = build_asn_ixp_data_structures(
        asn_to_analyze, before_data, after_data, all_ixps
    )

    plot_depeered_sessions_split_by_rs_timeline(
        all_data=all_data,
        all_files=all_files,
        data_structures=data_structures,
        asn_to_analyze=asn_to_analyze,
        start_date=start_date,
        end_date=end_date,
        depeerings_as_rs_depeers=True,  # True = left RS, False = left IXP completely
    )