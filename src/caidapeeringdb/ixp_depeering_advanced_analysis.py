



from src.caidapeeringdb.ixp_overtime import get_ases_that_depeered_at_ixp_at_depeering_peak, get_ixp_with_most_depeering_loss_at_a_single_point_in_time, plot_ixps_connections_over_time


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
            print(f"  Most Impacted IXP: IXP {target_ixp_id} with {departure_analysis['most_impacted_ixp_loss']} connection(s) lost")

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

        if max_ixp_val_id is not None and max_ixp_val_id != max_ixp_ratio_id:
            # Optionally populate absolute value peak IXP as well if distinct
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
    
    If consider_absolute_value is True:
        - Step 2 calculates net departure per transition: (departed IXPs - joined IXPs).
        - Step 3 measures net loss for IXPs using (baseline_conns - future_conns).
    If False:
        - Step 2 calculates gross departure count: len(prev_ixps - curr_ixps).
        - Step 3 measures gross loss, clamping negative losses to 0 (gains ignored).
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
            # Net loss across IXPs for target_asn
            departure_score = len(left_ixps) - len(joined_ixps)
        else:
            # Gross loss (only counting departures)
            departure_score = len(left_ixps)

        if departure_score > max_departures_score:
            max_departures_score = departure_score
            best_index = idx
            left_ixps_at_best_index = left_ixps

    if max_departures_score <= 0 or best_index == -1:
        return {}

    # 3. Calculate connection loss for departed IXPs across consider_x_next snapshots
    # Departure baseline uses index best_index - 1 (the last state before departure occurred)
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
            # Clamp gains to 0 so we only track true connection drop
            ixp_losses[ixp_id] = max(0, net_loss)

    most_impacted_ixp = max(ixp_losses.items(), key=lambda item: item[1]) if ixp_losses else (None, 0)

    return {
        "departure_index": best_index,
        "max_departures_count": max_departures_score,
        "left_ixps": list(left_ixps_at_best_index),
        "most_impacted_ixp_id": most_impacted_ixp[0],
        "most_impacted_ixp_loss": most_impacted_ixp[1]
    }