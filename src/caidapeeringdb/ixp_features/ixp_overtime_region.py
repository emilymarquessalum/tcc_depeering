import re
from src.caidapeeringdb.caidapeeringdb_load import get_dates_from_files
from src.caidapeeringdb.utils import PEERINGDB_SUBFOLDER_PREFIX
from src.caidapeeringdb.continent_logic import get_continent_for_ixp
from src.caidapeeringdb.ixp_overtime import (
    get_ases_that_depeered_at_ixp_at_depeering_peak,
    plot_ixp_connections_over_time_by_category,
    get_ixp_with_most_depeering_ratio_at_a_single_point_in_time,
    plot_ixps_connections_over_time,
)


def plot_ixp_connections_over_time_by_region(
    all_data,
    all_files,
    depeered_ixp_ids,
    asn_to_analyze,
    all_ixps,
    index_the_asn_analyzed_mass_depeered=None,
    depeered_completely_lost_ixp_ids=None,
    depeered_with_nonpeered_ixp_ids=None,
    ixp_names=None,
):
    """
    Plots the number of connections over time for IXPs that were de-peered, 
    grouped by region/continent, comparing completely lost vs still have non-peered connections.
    Additionally identifies and plots the single IXP with the highest de-peering ratio for each region.
    """
    if depeered_completely_lost_ixp_ids is None:
        depeered_completely_lost_ixp_ids = set()
    if depeered_with_nonpeered_ixp_ids is None: 
        depeered_with_nonpeered_ixp_ids = set()

    # 1. Create a lookup map for IXPs
    ixp_lookup = {ixp["id"]: ixp for ixp in all_ixps}

    # 2. Group de-peered IXPs by continent/region (separate groups)
    completely_lost_by_region = {}
    with_nonpeered_by_region = {}
    all_relevant_ixp_ids = set()

    depeered_at_peak_ases_by_ixp = {}

    for ixp_id in depeered_completely_lost_ixp_ids:
        ixp_info = ixp_lookup.get(ixp_id)
        continent = get_continent_for_ixp(ixp_id, ixp_info)

        if continent not in completely_lost_by_region:
            completely_lost_by_region[continent] = []
        completely_lost_by_region[continent].append(ixp_id)
        all_relevant_ixp_ids.add(str(ixp_id))

    for ixp_id in depeered_with_nonpeered_ixp_ids:
        ixp_info = ixp_lookup.get(ixp_id)
        continent = get_continent_for_ixp(ixp_id, ixp_info)

        if continent not in with_nonpeered_by_region:
            with_nonpeered_by_region[continent] = []
        with_nonpeered_by_region[continent].append(ixp_id)
        all_relevant_ixp_ids.add(str(ixp_id))

    dates = get_dates_from_files(all_files)

    # 3. Collect connections over time for both groups
    timeline_data = {str(ixp_id): [] for ixp_id in all_relevant_ixp_ids}

    for idx, data in enumerate(all_data):
        ixp_counts = {str(ixp_id): 0 for ixp_id in all_relevant_ixp_ids}

        for conn in data.get("netixlan", {}).get("data", []):
            ixp_id = str(conn.get("ix_id"))
            if ixp_id in all_relevant_ixp_ids:
                ixp_counts[ixp_id] += 1

        for ixp_id, count in ixp_counts.items():
            timeline_data[ixp_id].append(count)

    # 4. Plot for each region
    all_regions = set(completely_lost_by_region.keys()) | set(
        with_nonpeered_by_region.keys()
    )
    for region in sorted(all_regions):
        completely_lost_ixps = completely_lost_by_region.get(region, [])
        with_nonpeered_ixps = with_nonpeered_by_region.get(region, [])
        combined_region_ixp_ids = list(
            set(completely_lost_ixps + with_nonpeered_ixps)
        )

        if not combined_region_ixp_ids:
            continue

        # --- A. Regional Category Plot ---
        depeering_event_timelines = {}
        for ixp_id in with_nonpeered_ixps:
            ixp_id_str = str(ixp_id)
            if ixp_id_str in timeline_data:
                event_timeline = []
                for i in range(len(dates)):
                    has_connections_now = (
                        timeline_data[ixp_id_str][i] > 0
                        if i < len(timeline_data[ixp_id_str])
                        else False
                    )
                    had_connections_before = (
                        timeline_data[ixp_id_str][i - 1] > 0
                        if i > 0 and i - 1 < len(timeline_data[ixp_id_str])
                        else True
                    )
                    event_timeline.append(
                        had_connections_before and not has_connections_now
                    )
                depeering_event_timelines[ixp_id_str] = event_timeline

        plot_ixp_connections_over_time_by_category(
            dates=dates,
            timeline_data=timeline_data,
            completely_lost_ixp_ids=completely_lost_ixps,
            depeered_nonpeered_ixp_ids=with_nonpeered_ixps,
            completely_lost_timeline_data=timeline_data,
            depeered_nonpeered_timeline_data=timeline_data,
            category_label=region,
            category_type="Region",
            asn_to_analyze=asn_to_analyze,
            plot_name_suffix=f"region_{region}",
            depeering_event_timelines=depeering_event_timelines,
        )

        # --- B. Find & Plot the IXP with Highest De-peering Ratio in this Region ---
        max_ixp_id_in_the_region, max_ratio, index_of_max_ratio = get_ixp_with_most_depeering_ratio_at_a_single_point_in_time(
            all_data=all_data, 
            ixp_ids=combined_region_ixp_ids,
            type_of_depeering="rs_to_non_rs"
        )

        depeered_at_peak_ases_by_ixp[max_ixp_id_in_the_region] = get_ases_that_depeered_at_ixp_at_depeering_peak(all_data, max_ixp_id_in_the_region, index_of_max_ratio)

        if max_ixp_id_in_the_region is not None:
            plot_ixps_connections_over_time(
                all_data=all_data,
                dates=dates,
                ixp_ids=[max_ixp_id_in_the_region],
                ixp_names=ixp_names,
                title_info=f"Region {region} (Highest De-Peering Ratio: {max_ratio:.2%})",
                index_of_focused_asn_depeering=index_the_asn_analyzed_mass_depeered,
            )
        else:
            print(f"No IXP found with de-peering events in region {region}...")
 

    return depeered_at_peak_ases_by_ixp