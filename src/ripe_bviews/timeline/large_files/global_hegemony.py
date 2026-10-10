from collections.abc import Set
from datetime import datetime
import math
import os
from pathlib import Path
import sqlite3
import sys
from typing import Dict, List, Optional, Tuple

from matplotlib import pyplot as plt
from matplotlib.dates import relativedelta

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from definitions import ROOT_DIR
from src.google.vpps.google_vpps_list import get_google_vpp_asns
from src.ripe_bviews.timeline.large_files.bview_sqlite_parser import (
    LargeBViewParser,
    calculate_as_hegemony_disk,
    get_active_viewpoints_for_date,
    get_all_dates_available_for_asn_data,
    get_top_five_asns_over_time,
)
from src.utils.graphs import DEFAULT_FIGSIZE, format_labels_if_they_are_dates, save_plot


def _get_clean_vpp_set() -> set[str]:
    """Retrieves and normalizes Google VPP ASNs into pure numeric string format."""
    raw_vpps = get_google_vpp_asns(include_alternatives=True)
    return {str(asn).upper().replace("AS", "").strip() for asn in raw_vpps}


def load_global_hegemony_for_date(
    asn: int,
    alpha: float,
    date: str,
    ip_version: str,
    rrc_list: list[str],
    allowed_viewpoints=None,
):
    """
    Parses and aggregates BGP data from ALL listed RRCs for a given date,
    then executes Hegemony math on the global dataset.
    """
    global_db_path = f"huge_bgp_cache_GLOBAL_{date}_{ip_version}_{asn}.db"

    # If the combined global DB doesn't exist, build it by importing tables from all RRCs
    if not os.path.exists(global_db_path):
        print(f"\n[GLOBAL] Initializing unified database for date {date} across {len(rrc_list)} RRCs...")

        # Initialize primary database schema
        parser = LargeBViewParser(db_path=global_db_path, ip_version=ip_version)
        parser.init_database()

        global_conn = sqlite3.connect(global_db_path)
        global_cursor = global_conn.cursor()

        for rrc in rrc_list:
            raw_path = f"{ROOT_DIR}/{rrc}/output_bview.{date}.0000.{ip_version}.origin_as.{asn}.txt"
            if not os.path.exists(raw_path):
                continue

            rrc_db_path = f"huge_bgp_cache_{rrc}_{date}_{ip_version}_{asn}.db"
            if not os.path.exists(rrc_db_path):
                rrc_parser = LargeBViewParser(db_path=rrc_db_path, ip_version=ip_version)
                rrc_parser.parse_to_disk(raw_path)

            # Attach individual RRC database and insert records into global DB
            global_cursor.execute("ATTACH DATABASE ? AS source_db;", (rrc_db_path,))
            global_cursor.execute("""
                INSERT INTO bgp_mappings 
                SELECT * FROM source_db.bgp_mappings;
            """)
            global_conn.commit()
            global_cursor.execute("DETACH DATABASE source_db;")

        global_conn.close()

    # Perform Hegemony calculation on the unified database
    return calculate_as_hegemony_disk(
        global_db_path,
        target_asn=asn,
        alpha=alpha,
        ip_version=ip_version,
        allowed_viewpoints=allowed_viewpoints,
    )


def get_global_hegemony_scores(
    asn: int,
    ip_version: str,
    date_list: list[str],
    alpha: float,
    rrc_list: list[str],
    use_strict_viewpoint_filtering: bool = False,
    use_free_viewpoint_filtering: bool = False,
):
    """
    Computes global hegemony scores across all specified RRCs over time.
    """
    hegemony_scores_dict = {}
    viewpoint_counts_dict = {}
    valid_date_list = list(date_list)
    allowed_viewpoints_baseline = None

    if use_strict_viewpoint_filtering:
        print(f"[GLOBAL VIEWPOINTS] Finding strict viewpoint intersection across all {len(valid_date_list)} dates...")
        date_to_vps = {}
        for d in valid_date_list:
            d_vps = set()
            for rrc in rrc_list:
                raw_path = f"{ROOT_DIR}/{rrc}/output_bview.{d}.0000.{ip_version}.origin_as.{asn}.txt"
                if os.path.exists(raw_path):
                    d_vps.update(get_active_viewpoints_for_date(asn, rrc, d, ip_version))
            date_to_vps[d] = d_vps

        valid_date_list = [d for d in valid_date_list if len(date_to_vps[d]) > 3]
        if not valid_date_list:
            return {}, {}, []

        allowed_viewpoints_baseline = set.intersection(*[date_to_vps[d] for d in valid_date_list])

    for d in valid_date_list:
        scores, active_vps = load_global_hegemony_for_date(
            asn,
            alpha,
            d,
            ip_version,
            rrc_list,
            allowed_viewpoints=allowed_viewpoints_baseline,
        )
        hegemony_scores_dict[d] = scores
        viewpoint_counts_dict[d] = len(active_vps)

    return hegemony_scores_dict, viewpoint_counts_dict, valid_date_list


def analyze_global_hegemony_over_time(
    asn: int,
    alpha: float,
    ip_version: str,
    rrc_list: list[str],
    start_date=None,
    month_interval: int = 6,
    use_strict_viewpoint_filtering: bool = True,
    use_free_viewpoint_filtering: bool = False,
    show_as_percentage: bool = True,
    as_color_map=None,
    text_scale: float = 1.0,
):
    if as_color_map is None:
        as_color_map = {}

    all_available_dates = set()
    for rrc in rrc_list:
        dates = get_all_dates_available_for_asn_data(asn, rrc, ip_version, start_date=start_date)
        all_available_dates.update(dates)

    if not all_available_dates:
        print("[ERROR] No data available for the specified parameters.")
        return

    sorted_dates = sorted(list(all_available_dates))
    available_dts = [datetime.strptime(d, "%Y%m%d") for d in sorted_dates]
    interval_dates = [available_dts[0].strftime("%Y%m%d")]
    current_dt = available_dts[0]

    while True:
        ideal_target = current_dt + relativedelta(months=month_interval)
        future_dts = [d for d in available_dts if d > current_dt]
        if not future_dts:
            break
        closest_dt = min(future_dts, key=lambda d: abs((d - ideal_target).days))
        interval_dates.append(closest_dt.strftime("%Y%m%d"))
        current_dt = closest_dt
        if current_dt >= available_dts[-1]:
            break

    print(f"\n[GLOBAL HEGEMONY] Processing {len(interval_dates)} date snapshots across {len(rrc_list)} RRCs...")

    hegemony_scores_dict, viewpoint_counts_dict, valid_date_list = get_global_hegemony_scores(
        asn,
        ip_version,
        interval_dates,
        alpha,
        rrc_list,
        use_strict_viewpoint_filtering=use_strict_viewpoint_filtering,
        use_free_viewpoint_filtering=use_free_viewpoint_filtering,
    )

    if not valid_date_list:
        print("[WARNING] No valid global snapshots available.")
        return

    top_fives_over_time, unique_asns_list = get_top_five_asns_over_time(
        hegemony_scores_dict, valid_date_list
    )

    cmap = plt.get_cmap("tab20")
    for target_asn in unique_asns_list:
        if target_asn not in as_color_map:
            color_idx = len(as_color_map) % 20
            as_color_map[target_asn] = cmap(color_idx)

    total_hegemony_per_date = [
        sum(hegemony_scores_dict[d].values()) for d in valid_date_list
    ]

    # Apply global default text scaling across all Matplotlib defaults (catches implicit elements)
    plt.rcParams.update({
        "font.size": 10 * text_scale,
        "axes.titlesize": 14 * text_scale,
        "axes.labelsize": 12 * text_scale,
        "xtick.labelsize": 10 * text_scale,
        "ytick.labelsize": 10 * text_scale,
        "legend.fontsize": 10 * text_scale,
        "figure.titlesize": 16 * text_scale,
    })

    fig, ax1 = plt.subplots(figsize=DEFAULT_FIGSIZE)
    line_styles = ["-", "--", ":", "-."]
    markers = ["o", "s", "^", "v", "D", "X", "P"]

    for i, target_asn in enumerate(unique_asns_list):
        scores_for_asn = []
        for d_idx in range(len(valid_date_list)):
            val = top_fives_over_time[d_idx][i]
            if show_as_percentage:
                tot = total_hegemony_per_date[d_idx]
                val = (val / tot * 100.0) if tot > 0 else 0.0
            scores_for_asn.append(val)

        ax1.plot(
            valid_date_list,
            scores_for_asn,
            marker=markers[i % len(markers)],
            linestyle=line_styles[i % len(line_styles)],
            linewidth=2.5,
            color=as_color_map[target_asn],
            label=f"ASN {target_asn}",
        )

    ax1.set_xlabel("Date", fontsize=12 * text_scale)
    ax1.set_ylabel("Hegemony (%)" if show_as_percentage else "Hegemony Score", fontsize=12 * text_scale)
    ax1.set_title(
        f"GLOBAL Hegemony Over Time (All RRCs Combined)\n(Target ASN: {asn}, IP: {ip_version.upper()}, α={alpha})",
        fontsize=14 * text_scale,
    )
    ax1.tick_params(axis="both", labelsize=10 * text_scale)
    ax1.tick_params(axis="x", rotation=45)
    ax1.grid(True, linestyle="--", alpha=0.5)
    ax1.legend(
        bbox_to_anchor=(1.05, 1),
        loc="upper left",
        title="Top Transits",
        fontsize=10 * text_scale,
        title_fontsize=11 * text_scale,
    )

    plt.tight_layout()
    plt.show()
    save_plot(fig=fig, title=f"global_hegemony_over_time_{asn}_{ip_version}.png")


def analyze_global_vpp_hegemony_over_time(
    asn: int,
    alpha: float,
    ip_version: str,
    rrc_list: list[str],
    start_date=None,
    month_interval: int = 6,
    use_strict_viewpoint_filtering: bool = True,
    use_free_viewpoint_filtering: bool = False,
    show_as_percentage: bool = True,
    text_scale: float = 1.0,
):
    """
    Computes global VPP vs Non-VPP hegemony over time across ALL transit ASes in the routing table.
    """
    clean_vpp_set = _get_clean_vpp_set()

    all_available_dates = set()
    for rrc in rrc_list:
        dates = get_all_dates_available_for_asn_data(asn, rrc, ip_version, start_date=start_date)
        all_available_dates.update(dates)

    if not all_available_dates:
        print("[ERROR] No global data available for the specified parameters.")
        return

    sorted_dates = sorted(list(all_available_dates))
    available_dts = [datetime.strptime(d, "%Y%m%d") for d in sorted_dates]
    interval_dates = [available_dts[0].strftime("%Y%m%d")]
    current_dt = available_dts[0]

    while True:
        ideal_target = current_dt + relativedelta(months=month_interval)
        future_dts = [d for d in available_dts if d > current_dt]
        if not future_dts:
            break
        closest_dt = min(future_dts, key=lambda d: abs((d - ideal_target).days))
        interval_dates.append(closest_dt.strftime("%Y%m%d"))
        current_dt = closest_dt
        if current_dt >= available_dts[-1]:
            break

    hegemony_scores_dict, _, valid_date_list = get_global_hegemony_scores(
        asn,
        ip_version,
        interval_dates,
        alpha,
        rrc_list,
        use_strict_viewpoint_filtering=use_strict_viewpoint_filtering,
        use_free_viewpoint_filtering=use_free_viewpoint_filtering,
    )

    if not valid_date_list:
        print("[WARNING] No valid global snapshots available.")
        return

    hegemony_over_time_vpp_or_not_vpp: list[tuple[float, float]] = []

    # Iterate over ALL ASes present in each date snapshot
    for date in valid_date_list:
        date_scores = hegemony_scores_dict.get(date, {})
        tot = sum(date_scores.values())

        if tot <= 0.0:
            hegemony_over_time_vpp_or_not_vpp.append((0.0, 0.0))
            continue

        hegemony_vpp = 0.0
        hegemony_not_vpp = 0.0

        for raw_transit_asn, score in date_scores.items():
            clean_transit_asn = str(raw_transit_asn).upper().replace("AS", "").strip()

            if clean_transit_asn in clean_vpp_set:
                hegemony_vpp += score
            else:
                hegemony_not_vpp += score

        if show_as_percentage:
            hegemony_vpp = (hegemony_vpp / tot) * 100.0
            hegemony_not_vpp = (hegemony_not_vpp / tot) * 100.0

        hegemony_over_time_vpp_or_not_vpp.append((hegemony_vpp, hegemony_not_vpp))

    # Apply global default text scaling across all Matplotlib defaults (catches implicit elements)
    plt.rcParams.update({
        "font.size": 10 * text_scale,
        "axes.titlesize": 14 * text_scale,
        "axes.labelsize": 12 * text_scale,
        "xtick.labelsize": 10 * text_scale,
        "ytick.labelsize": 10 * text_scale,
        "legend.fontsize": 10 * text_scale,
        "figure.titlesize": 16 * text_scale,
    })

    fig, ax = plt.subplots(figsize=DEFAULT_FIGSIZE)

    ax.plot(
        valid_date_list,
        [h[0] for h in hegemony_over_time_vpp_or_not_vpp],
        marker="o",
        linewidth=2.5,
        color="tab:blue",
        label="Global VPP Hegemony (All ASes)",
    )

    ax.plot(
        valid_date_list,
        [h[1] for h in hegemony_over_time_vpp_or_not_vpp],
        marker="s",
        linewidth=2.5,
        color="tab:orange",
        linestyle="--",
        label="Global Non-VPP Hegemony (All ASes)",
    )

    ax.set_xlabel("Date", fontsize=12 * text_scale)
    y_label = "Hegemony Percentage (%)" if show_as_percentage else "Hegemony"
    ax.set_ylabel(y_label, fontsize=12 * text_scale)
    ax.set_title(
        f"{asn_}’s {ip_version.title()} Global Hegemony - VPP vs Non-VPP (Top 5)"
        f"GLOBAL VPP vs. Non-VPP Hegemony"
        f"(Target ASN: {asn}, IP: {ip_version.upper()}, α={alpha})",
        fontsize=14 * text_scale,
    )
    ax.tick_params(axis="both", labelsize=10 * text_scale)
    ax.tick_params(axis="x", rotation=45)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(
        bbox_to_anchor=(1.02, 1),
        loc="upper left",
        title="Is-VPP",
        fontsize=10 * text_scale,
        title_fontsize=11 * text_scale,
    )

    plt.tight_layout()
    plt.show()

    save_plot(fig=fig, title=f"global_vpp_hegemony_over_time_{asn}_{ip_version}.png")


def analyze_global_vpp_hegemony_over_time_top_ases(
    asn: int,
    alpha: float,
    ip_version: str,
    rrc_list: list[str],
    start_date=None,
    month_interval: int = 6,
    use_strict_viewpoint_filtering: bool = True,
    use_free_viewpoint_filtering: bool = False,
    show_as_percentage: bool = True,
    text_scale: float = 1.0,
    percentage: Optional[float] = None,
):
    """
    Computes global VPP vs Non-VPP hegemony over time strictly among 
    the top ASes at each snapshot. Defaults to Top 5, or uses a percentage cutoff if provided.
    """
    clean_vpp_set = _get_clean_vpp_set()

    all_available_dates = set()
    for rrc in rrc_list:
        dates = get_all_dates_available_for_asn_data(asn, rrc, ip_version, start_date=start_date)
        all_available_dates.update(dates)

    if not all_available_dates:
        print("[ERROR] No global data available for the specified parameters.")
        return

    sorted_dates = sorted(list(all_available_dates))
    available_dts = [datetime.strptime(d, "%Y%m%d") for d in sorted_dates]
    interval_dates = [available_dts[0].strftime("%Y%m%d")]
    current_dt = available_dts[0]

    while True:
        ideal_target = current_dt + relativedelta(months=month_interval)
        future_dts = [d for d in available_dts if d > current_dt]
        if not future_dts:
            break
        closest_dt = min(future_dts, key=lambda d: abs((d - ideal_target).days))
        interval_dates.append(closest_dt.strftime("%Y%m%d"))
        current_dt = closest_dt
        if current_dt >= available_dts[-1]:
            break

    cutoff_desc = f"Top {percentage}%" if percentage is not None else "Top 5"
    print(f"\n[GLOBAL VPP] Computing global VPP hegemony ({cutoff_desc}) for {len(interval_dates)} date snapshots across {len(rrc_list)} RRCs...")

    hegemony_scores_dict, _, valid_date_list = get_global_hegemony_scores(
        asn,
        ip_version,
        interval_dates,
        alpha,
        rrc_list,
        use_strict_viewpoint_filtering=use_strict_viewpoint_filtering,
        use_free_viewpoint_filtering=use_free_viewpoint_filtering,
    )

    if not valid_date_list:
        print("[WARNING] No valid global snapshots available.")
        return

    hegemony_over_time_vpp_or_not_vpp: list[tuple[float, float]] = []
    top_counts: list[int] = []

    for date in valid_date_list:
        date_scores = hegemony_scores_dict.get(date, {})
        tot = sum(date_scores.values())

        if tot <= 0.0:
            hegemony_over_time_vpp_or_not_vpp.append((0.0, 0.0))
            continue

        cleaned_date_scores = {
            str(raw_asn).upper().replace("AS", "").strip(): score
            for raw_asn, score in date_scores.items()
        }

        # Select Top cutoff for THIS snapshot
        sorted_items = sorted(cleaned_date_scores.items(), key=lambda x: x[1], reverse=True)
        total_asns = len(sorted_items)

        if percentage is not None:
            top_count = max(1, math.ceil(total_asns * percentage / 100.0))
        else:
            top_count = 5

        top_counts.append(top_count)
        top_items = sorted_items[:top_count]

        hegemony_vpp = 0.0
        hegemony_not_vpp = 0.0

        for clean_transit_asn, score in top_items:
            if clean_transit_asn in clean_vpp_set:
                hegemony_vpp += score
            else:
                hegemony_not_vpp += score

        if show_as_percentage:
            hegemony_vpp = (hegemony_vpp / tot) * 100.0
            hegemony_not_vpp = (hegemony_not_vpp / tot) * 100.0

        hegemony_over_time_vpp_or_not_vpp.append((hegemony_vpp, hegemony_not_vpp))

    # Determine dynamic legend label and title suffix based on percentage or default Top 5
    if percentage is not None:
        avg_top_asns = sum(top_counts) / len(top_counts) if top_counts else 0
        group_label = f"Top {percentage}% (~{avg_top_asns:.1f} ASNs)"
        title_cutoff = f"Top {percentage}%"
        file_suffix = f"top{int(percentage)}pct"
    else:
        group_label = "Top 5 Only"
        title_cutoff = "Top 5"
        file_suffix = "top5"

    # Apply global default text scaling across all Matplotlib defaults (catches implicit elements)
    plt.rcParams.update({
        "font.size": 10 * text_scale,
        "axes.titlesize": 14 * text_scale,
        "axes.labelsize": 12 * text_scale,
        "xtick.labelsize": 10 * text_scale,
        "ytick.labelsize": 10 * text_scale,
        "legend.fontsize": 10 * text_scale,
        "figure.titlesize": 16 * text_scale,
    })

    fig, ax = plt.subplots(figsize=DEFAULT_FIGSIZE)
    
    if valid_date_list is not None:
        valid_date_list = format_labels_if_they_are_dates(valid_date_list)

    ax.plot(
        valid_date_list,
        [h[0] for h in hegemony_over_time_vpp_or_not_vpp],
        marker="o",
        linewidth=2.5,
        color="tab:blue",
        label=f"Global VPP Hegemony ({group_label})",
    )
    
    ax.plot(
        valid_date_list,
        [h[1] for h in hegemony_over_time_vpp_or_not_vpp],
        marker="s",
        linewidth=2.5,
        color="tab:orange",
        linestyle="--",
        label=f"Global Non-VPP Hegemony ({group_label})",
    )

    ax.set_xlabel("Date", fontsize=12 * text_scale)
    y_label = "Hegemony Percentage (%)" if show_as_percentage else "Hegemony"
    ax.set_ylabel(y_label, fontsize=12 * text_scale)
    ax.set_title(
        f"GLOBAL VPP vs. Non-VPP Hegemony [{title_cutoff}] ({len(rrc_list)} RRCs)\n"
        f"(AS{asn}, IP{ip_version.lower()}, α={alpha})",
        fontsize=14 * text_scale,
    )
    ax.set_title(
            f"Google’s Global Hegemony - VPP vs Non-VPP ({title_cutoff})",
            fontsize=14 * text_scale,
    )
    ax.tick_params(axis="both", labelsize=10 * text_scale)
    ax.tick_params(axis="x")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(
        bbox_to_anchor=(1, 0),
        loc="lower right",
        title="Is-VPP",
        fontsize=10 * text_scale,
        title_fontsize=11 * text_scale,
    )

    plt.tight_layout()
    plt.show()

    save_plot(fig=fig, title=f"global_vpp_hegemony_over_time_{asn}_{ip_version}_{file_suffix}.png")


if __name__ == "__main__":
    asn = 15169
    alpha = 0.34
    ip_version = "v6"
    text_scale = 1.0  # Increase to scale font size of EVERYTHING globally (e.g., 1.5 = 150% size)

    start_date = None

    all_rrcs = [
        "rrc00", "rrc01", "rrc03", "rrc04", "rrc05", "rrc06", "rrc07", "rrc08",
        "rrc09", "rrc10", "rrc11", "rrc12", "rrc13", "rrc14", "rrc15", "rrc16",
        "rrc17", "rrc18", "rrc19", "rrc20", "rrc21", "rrc22"
    ]

    # Optional: Prompt user for percentage or default to Top 5 (None)
    user_input = input("Enter percentage of top ASNs to consider (leave blank to default to Top 5): ").strip()
    percentage = float(user_input) if user_input else None

    # 1. Run Global Individual Transit Hegemony Over Time
    print(f"\n[1/3] Running Global Hegemony Over Time (Per Transit) for ASN {asn} ({ip_version.upper()})...")
    analyze_global_hegemony_over_time(
        asn=asn,
        alpha=alpha,
        ip_version=ip_version,
        rrc_list=all_rrcs,
        start_date=start_date,
        month_interval=6,
        use_strict_viewpoint_filtering=True,
        show_as_percentage=True,
        text_scale=text_scale,
    )

    # 2. Run Global VPP vs Non-VPP Hegemony Over Time (ALL ASes)
    print(f"\n[2/3] Running Global VPP vs Non-VPP Hegemony (All ASes) for ASN {asn} ({ip_version.upper()})...")
    analyze_global_vpp_hegemony_over_time(
        asn=asn,
        alpha=alpha,
        ip_version=ip_version,
        rrc_list=all_rrcs,
        start_date=start_date,
        month_interval=6,
        use_strict_viewpoint_filtering=True,
        show_as_percentage=True,
        text_scale=text_scale,
    )

    # 3. Run Global VPP vs Non-VPP Hegemony Over Time (Top ASes or Top 5)
    print(f"\n[3/3] Running Global VPP vs Non-VPP Hegemony (Top ASes) for ASN {asn} ({ip_version.upper()})...")
    analyze_global_vpp_hegemony_over_time_top_ases(
        asn=asn,
        alpha=alpha,
        ip_version=ip_version,
        rrc_list=all_rrcs,
        start_date=start_date,
        month_interval=6,
        use_strict_viewpoint_filtering=True,
        show_as_percentage=True,
        text_scale=text_scale,
        percentage=percentage,
    )