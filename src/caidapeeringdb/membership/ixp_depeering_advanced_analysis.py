import sys
from pathlib import Path

# Ensure the project root is on sys.path (matching ixp_members_by_top_losses.py)
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.caidapeeringdb.build_structures import build_asn_ixp_data_structures
from src.caidapeeringdb.loaders import load_timeline_data

from src.caidapeeringdb.caidapeeringdb_load import (
    get_all_data,
    get_data,
    get_unique_ixps_from_data_list,
    load_connections_over_time_for_asns,
) 
from src.caidapeeringdb.membership.ixp_overtime import (
    get_ases_that_depeered_at_ixp_at_depeering_peak,
    get_ixp_with_most_depeering_loss_at_a_single_point_in_time,
    plot_ixps_connections_over_time,
)


def look_at_max_loss(
    all_data,
    combined_range_ixp_ids,
    ixp_names,
    label,
    depeered_at_peak_ases_by_ixp,
    dates,
    connections_over_time_for_asns,
    target_asn,
    use_target_asn_peak_event: bool = False,
    consider_x_next: int = 3
):
    """
    Populates depeered_at_peak_ases_by_ixp and plots connection trends.

    Modes:
      - use_target_asn_peak_event=False (Default):
        Finds the IXP with the overall highest de-peering loss/ratio at ANY point in time.

      - use_target_asn_peak_event=True:
        Finds the snapshot where target_asn left the most IXPs (peak event), then finds the 
        most impacted IXP specifically during that de-peering event window.
    """
    if use_target_asn_peak_event:
        # MODE 2: Target ASN Peak De-peering Event Analysis
        departure_analysis = find_max_departure_and_impacted_ixp(
            all_data=all_data,
            connections_over_time_for_asns=connections_over_time_for_asns,
            target_asn=target_asn,
            combined_range_ixp_ids=combined_range_ixp_ids,
            consider_x_next=consider_x_next
        )

        if departure_analysis and departure_analysis.get('most_impacted_ixp_id'):
            target_ixp_id = departure_analysis['most_impacted_ixp_id']
            peak_index = departure_analysis['departure_index']

            # Capture ASes that de-peered at this specific IXP during the target ASN's peak event snapshot
            depeered_at_peak_ases_by_ixp[target_ixp_id] = get_ases_that_depeered_at_ixp_at_depeering_peak(
                all_data, target_ixp_id, peak_index
            )

            print(f"\n[ASN {target_asn} Peak Event Mode - Group {label}]")
            print(f"  Max IXP Departures Index: {peak_index} ({dates[peak_index]})")
            print(f"  IXPs Left by Target ASN: {departure_analysis['max_departures_count']}")
            print(f"  Most Impacted IXP: IXP {target_ixp_id} ({ixp_names.get(int(target_ixp_id), ixp_names.get(target_ixp_id, 'Unknown'))}) "
                  f"with {departure_analysis['most_impacted_ixp_loss']} connection(s) lost")

            plot_ixps_connections_over_time(
                all_data=all_data,
                dates=dates,
                ixp_ids=[target_ixp_id],
                ixp_names=ixp_names,
                title_info=f"Target ASN Peak Event - Size Group {label} (IXP {target_ixp_id})",
                index_of_focused_asn_depeering=peak_index
            )
        else:
            print(f"No target ASN peak de-peering event found for size group {label}.")

    else:
        # MODE 1: Standard Global Max Loss Mode
        # 1. Ratio-based check
        max_ixp_ratio_id, max_ratio, index_of_max_ratio = get_ixp_with_most_depeering_loss_at_a_single_point_in_time(
            all_data=all_data,
            ixp_ids=combined_range_ixp_ids,
            type_of_depeering="rs_to_non_rs"
        )

        if max_ixp_ratio_id is not None:
            print(f"\n[Global Max Ratio Loss - {label}]")
            print(f"  IXP: {max_ixp_ratio_id} ({ixp_names.get(max_ixp_ratio_id, 'Unknown')})")
            print(f"  Max Ratio Loss: {max_ratio:.2%} at {dates[index_of_max_ratio]} (index {index_of_max_ratio})")

            depeered_at_peak_ases_by_ixp[max_ixp_ratio_id] = get_ases_that_depeered_at_ixp_at_depeering_peak(
                all_data, max_ixp_ratio_id, index_of_max_ratio
            )

            plot_ixps_connections_over_time(
                all_data=all_data,
                dates=dates,
                ixp_ids=[max_ixp_ratio_id],
                ixp_names=ixp_names,
                title_info=f"Size Group {label} (Highest De-Peering Ratio: {max_ratio:.2%})",
                index_of_focused_asn_depeering=index_of_max_ratio
            )
        else:
            print(f"No IXP found with de-peering events in size range {label}...")

        # 2. Absolute Value check
        max_ixp_val_id, max_val, index_of_max_val = get_ixp_with_most_depeering_loss_at_a_single_point_in_time(
            all_data=all_data,
            ixp_ids=combined_range_ixp_ids,
            type_of_depeering="rs_to_non_rs",
            as_ratio=False
        )

        if max_ixp_val_id is not None:
            print(f"\n[Global Max Absolute Loss - {label}]")
            print(f"  IXP: {max_ixp_val_id} ({ixp_names.get(max_ixp_val_id, 'Unknown')})")
            print(f"  Max Connections Lost: {max_val} at {dates[index_of_max_val]} (index {index_of_max_val})")

        if max_ixp_val_id is not None and max_ixp_val_id != max_ixp_ratio_id:
            depeered_at_peak_ases_by_ixp[max_ixp_val_id] = get_ases_that_depeered_at_ixp_at_depeering_peak(
                all_data, max_ixp_val_id, index_of_max_val
            )

            plot_ixps_connections_over_time(
                all_data=all_data,
                dates=dates,
                ixp_ids=[max_ixp_val_id],
                ixp_names=ixp_names,
                title_info=f"Size Group {label} (Highest De-Peering Value: {max_val})",
                index_of_focused_asn_depeering=index_of_max_val
            )


def find_max_departure_and_impacted_ixp(
    all_data: list[dict],
    connections_over_time_for_asns: dict[int, list[tuple[str, list[dict]]]],
    target_asn: int,
    combined_range_ixp_ids: list[int | str],
    consider_x_next: int = 1,
    consider_absolute_value: bool = True
) -> dict:
    """
    Finds the index where target_asn left the most IXPs within combined_range_ixp_ids,
    and identifies which IXP from that set lost the most total connections 
    across 'consider_x_next' snapshots.
    """
    if target_asn not in connections_over_time_for_asns:
        return {}

    timeline = connections_over_time_for_asns[target_asn]
    num_snapshots = len(timeline)
    target_ixp_set = {str(ixp) for ixp in combined_range_ixp_ids}

    # 1. Map IXPs connected per snapshot index for target_asn (filtered to combined_range_ixp_ids)
    snapshot_ixp_sets = []
    for _, conns in timeline:
        ixp_ids = {
            str(conn.get("ix_id"))
            for conn in conns
            if str(conn.get("ix_id")) in target_ixp_set
        }
        snapshot_ixp_sets.append(ixp_ids)

    # 2. Find index where target_asn experienced the maximum loss of IXPs
    max_departures_score = -float('inf') if consider_absolute_value else 0
    best_index = -1
    left_ixps_at_best_index = set()

    for idx in range(1, num_snapshots):
        prev_ixps = snapshot_ixp_sets[idx - 1]
        curr_ixps = snapshot_ixp_sets[idx]

        left_ixps = prev_ixps - curr_ixps
        joined_ixps = curr_ixps - prev_ixps

        if consider_absolute_value:
            departure_score = len(left_ixps) - len(joined_ixps)
        else:
            departure_score = len(left_ixps)

        if departure_score > max_departures_score:
            max_departures_score = departure_score
            best_index = idx
            left_ixps_at_best_index = left_ixps

    if max_departures_score <= 0 or best_index == -1:
        return {}

    # 3. Calculate connection loss for departed IXPs across consider_x_next snapshots
    start_snapshot_idx = best_index - 1
    end_snapshot_idx = min(start_snapshot_idx + consider_x_next, len(all_data) - 1)

    ixp_losses = {}
    for ixp_id in left_ixps_at_best_index:
        baseline_conns = sum(
            1 for net in all_data[start_snapshot_idx].get("netixlan", {}).get("data", [])
            if str(net.get("ix_id")) == ixp_id
        )
        future_conns = sum(
            1 for net in all_data[end_snapshot_idx].get("netixlan", {}).get("data", [])
            if str(net.get("ix_id")) == ixp_id
        )

        net_loss = baseline_conns - future_conns

        if consider_absolute_value:
            ixp_losses[ixp_id] = net_loss
        else:
            ixp_losses[ixp_id] = max(0, net_loss)

    most_impacted_ixp = max(ixp_losses.items(), key=lambda item: item[1]) if ixp_losses else (None, 0)

    return {
        "departure_index": best_index,
        "max_departures_count": max_departures_score,
        "left_ixps": list(left_ixps_at_best_index),
        "most_impacted_ixp_id": most_impacted_ixp[0],
        "most_impacted_ixp_loss": most_impacted_ixp[1]
    }


if __name__ == "__main__": 
    config_path = str(Path(__file__).parent.parent)
    if not (Path(config_path) / "config_google_before_depeering_timeline.json").exists():
        config_path = str(Path(__file__).parent)

    # 1. Load timeline files (matching ixp_members_by_top_losses.py)
    all_files_before_depeering, all_files_after_depeering = load_timeline_data(config_path)
    all_files = all_files_before_depeering + all_files_after_depeering
    all_files = [f for f in all_files if "2024_05_01" not in f and "2025_02_01" not in f]

    dates = [file.split("/")[-1].split(".")[0] for file in all_files]
    all_data = get_all_data(all_files, use_cache=False)

    # 2. Identify all IXPs Google (AS15169) de-peered from
    google_asn = 15169
    before_data = get_data(all_files_before_depeering[-1])
    after_data = get_data(all_files_after_depeering[-1])

    all_ixps = get_unique_ixps_from_data_list([before_data, after_data])
    ixp_names = {ixp["id"]: ixp.get("name", f"IXP {ixp['id']}") for ixp in all_ixps}

    data_structures = build_asn_ixp_data_structures(
        google_asn, before_data, after_data, all_ixps
    )
    google_depeered_ixp_ids = list(data_structures["depeered_ixp_ids"])
    print(f"Google (AS{google_asn}) de-peered from {len(google_depeered_ixp_ids)} IXPs.")

    # 3. Load Google's peering timeline for Mode 2 analysis
    connections_over_time_for_asns = load_connections_over_time_for_asns(
        all_files=all_files,
        asns_to_search=[(google_asn, "Google", ["ICP"])],
        connections_should_be="peered"
    )

    depeered_at_peak_ases_by_ixp = {}

    # 4A. Mode 1: Overall highest loss (both ratio and absolute) across all Google de-peered IXPs
    look_at_max_loss(
        all_data=all_data,
        combined_range_ixp_ids=google_depeered_ixp_ids,
        ixp_names=ixp_names,
        label="All Google De-peered IXPs",
        depeered_at_peak_ases_by_ixp=depeered_at_peak_ases_by_ixp,
        dates=dates,
        connections_over_time_for_asns=connections_over_time_for_asns,
        target_asn=google_asn,
        use_target_asn_peak_event=False
    )

    # 4B. Mode 2: Highest loss specifically during Google's peak de-peering event window
    look_at_max_loss(
        all_data=all_data,
        combined_range_ixp_ids=google_depeered_ixp_ids,
        ixp_names=ixp_names,
        label="All Google De-peered IXPs",
        depeered_at_peak_ases_by_ixp=depeered_at_peak_ases_by_ixp,
        dates=dates,
        connections_over_time_for_asns=connections_over_time_for_asns,
        target_asn=google_asn,
        use_target_asn_peak_event=True,
        consider_x_next=3
    )