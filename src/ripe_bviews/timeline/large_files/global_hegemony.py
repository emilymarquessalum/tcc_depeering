from collections.abc import Set
from datetime import datetime
import math
import os
from pathlib import Path
import re
import sqlite3
import sys
from typing import Dict, List, Optional, Tuple, Union

from matplotlib import pyplot as plt
from matplotlib.dates import relativedelta
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from src.caidapeeringdb.vpps.main import build_vpp_asn_map, get_vpp_ixp_connection_status_map

from definitions import ROOT_DIR
from src.caidapeeringdb.caidapeeringdb_load import get_all_data, get_all_files, get_data
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


def _parse_ip_versions(
    ip_version: Union[str, List[str], Tuple[str, ...]],
    show_both_ip_versions: bool = False,
) -> List[str]:
    """Parses and normalizes input IP version specifications into a list of version strings ('v4', 'v6')."""
    if show_both_ip_versions or ip_version == "both":
        return ["v4", "v6"]
    if isinstance(ip_version, (list, tuple, set)):
        res = []
        for v in ip_version:
            clean_v = str(v).lower().replace("ip", "").strip()
            if clean_v in ["v4", "v6"]:
                res.append(clean_v)
            elif clean_v in ["both", "v4_v6", "v4v6"]:
                return ["v4", "v6"]
        return res if res else ["v4"]
    clean_v = str(ip_version).lower().replace("ip", "").strip()
    if clean_v in ["both", "v4_v6", "v4v6"]:
        return ["v4", "v6"]
    if clean_v in ["v4", "v6"]:
        return [clean_v]
    return ["v4"]


def _get_closest_peeringdb_date(bgp_date_str: str, pdb_dates_normalized: List[str]) -> str:
    """Finds the closest PeeringDB snapshot date for a given BGP date string (YYYYMMDD)."""
    bgp_dt = datetime.strptime(str(bgp_date_str)[:8], "%Y%m%d")
    return min(
        pdb_dates_normalized,
        key=lambda d: abs((datetime.strptime(str(d)[:8], "%Y%m%d") - bgp_dt).days)
    )


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

    if not os.path.exists(global_db_path):
        print(f"\n[GLOBAL] Initializing unified database for date {date} across {len(rrc_list)} RRCs...")

        parser = LargeBViewParser(db_path=global_db_path, ip_version=ip_version)
        parser.init_database()

        global_conn = sqlite3.connect(global_db_path)
        global_cursor = global_conn.cursor()

        for rrc in rrc_list:
            raw_path = f"{ROOT_DIR}/{rrc}/output_bview.{date}.0000.{ip_version}.origin_as.{asn}.txt"
            if not os.path.exists(raw_path):
                raw_path = f"{ROOT_DIR}/{rrc}/output_bview.{date}.0000.origin_as.{asn}.txt"
                if not os.path.exists(raw_path):
                    continue

            rrc_db_path = f"huge_bgp_cache_{rrc}_{date}_{ip_version}_{asn}.db"
            if not os.path.exists(rrc_db_path):
                rrc_parser = LargeBViewParser(db_path=rrc_db_path, ip_version=ip_version)
                rrc_parser.parse_to_disk(raw_path)

            global_cursor.execute("ATTACH DATABASE ? AS source_db;", (rrc_db_path,))
            global_cursor.execute("""
                INSERT INTO bgp_mappings 
                SELECT * FROM source_db.bgp_mappings;
            """)
            global_conn.commit()
            global_cursor.execute("DETACH DATABASE source_db;")

        global_conn.close()

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


def analyze_global_vpp_ixp_connected_hegemony_over_time(
    asn: int,
    alpha: float,
    ip_version: Union[str, List[str]] = "v4",
    rrc_list: list[str] = None,
    start_date=None,
    month_interval: int = 6,
    use_strict_viewpoint_filtering: bool = False,
    use_free_viewpoint_filtering: bool = True,
    text_scale: float = 1.0,
):
    """
    Calculates and plots the percentage of Total VPP Hegemony coming from VPPs
    that have at least one IXP connection over time.

    If unconnected VPPs account for X% of total VPP hegemony on a date,
    this plot displays (100 - X)%, representing the hegemony share of IXP-connected VPPs.
    """
    # 1. Load PeeringDB snapshots and build VPP status map from main.py
    all_files = get_all_files()
    all_snapshots = get_all_data(all_files)
    latest_snapshot = get_data(all_files[-1])
    vpp_asn_map = build_vpp_asn_map(latest_snapshot)

    status_map = get_vpp_ixp_connection_status_map(all_files, all_snapshots, vpp_asn_map)
    pdb_dates_normalized = list(status_map.keys())

    ip_versions = _parse_ip_versions(ip_version)

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
    has_data = False

    for ip_ver in ip_versions:
        all_available_dates = set()
        for rrc in rrc_list:
            dates = get_all_dates_available_for_asn_data(asn, rrc, ip_ver, start_date=start_date)
            all_available_dates.update(dates)

        if not all_available_dates:
            print(f"[ERROR] No global data available for ASN {asn} ({ip_ver.upper()}).")
            continue

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

        print(f"\n[GLOBAL VPP IXP HEGEMONY] Computing IXP-connected VPP hegemony share ({ip_ver.upper()}) across {len(interval_dates)} dates...")

        hegemony_scores_dict, _, valid_date_list = get_global_hegemony_scores(
            asn,
            ip_ver,
            interval_dates,
            alpha,
            rrc_list,
            use_strict_viewpoint_filtering=use_strict_viewpoint_filtering,
            use_free_viewpoint_filtering=use_free_viewpoint_filtering,
        )

        if not valid_date_list:
            print(f"[WARNING] No valid global snapshots available for {ip_ver.upper()}.")
            continue

        connected_vpp_hegemony_pcts = []

        for date in valid_date_list:
            date_scores = hegemony_scores_dict.get(date, {})

            cleaned_date_scores = {}
            for raw_asn, score in date_scores.items():
                try:
                    clean_asn = int(str(raw_asn).upper().replace("AS", "").strip())
                    cleaned_date_scores[clean_asn] = score
                except (ValueError, TypeError):
                    continue

            # Match BGP date to closest PeeringDB snapshot date
            closest_pdb_date = _get_closest_peeringdb_date(date, pdb_dates_normalized)
            conn_asns = status_map[closest_pdb_date]["connected_asns"]
            unconn_asns = status_map[closest_pdb_date]["unconnected_asns"]
            all_vpp_asns = conn_asns | unconn_asns

            total_vpp_hegemony = sum(
                score for asn_id, score in cleaned_date_scores.items() if asn_id in all_vpp_asns
            )

            if total_vpp_hegemony <= 0.0:
                connected_vpp_hegemony_pcts.append(0.0)
                continue

            unconnected_vpp_hegemony = sum(
                score for asn_id, score in cleaned_date_scores.items() if asn_id in unconn_asns
            )

            # If unconnected VPPs account for X%, display value is (100 - X)%
            pct_unconnected = (unconnected_vpp_hegemony / total_vpp_hegemony) * 100.0
            pct_connected = 100.0 - pct_unconnected

            connected_vpp_hegemony_pcts.append(round(pct_connected, 2))

        formatted_dates = format_labels_if_they_are_dates(valid_date_list)
        linestyle = "-" if ip_ver == "v4" else "--"
        marker = "o" if ip_ver == "v4" else "^"
        label_suffix = f" ({ip_ver.upper()})" if len(ip_versions) > 1 else ""

        ax.plot(
            formatted_dates,
            connected_vpp_hegemony_pcts,
            marker=marker,
            linewidth=2.5,
            color="tab:green",
            linestyle=linestyle,
            label=f"IXP-Connected VPP Hegemony Share{label_suffix}",
        )
        has_data = True

    if not has_data:
        print("[WARNING] No data plotted.")
        plt.close(fig)
        return

    ax.set_xlabel("Date", fontsize=12 * text_scale)
    ax.set_ylabel("% of Total VPP Hegemony", fontsize=12 * text_scale)
    ax.set_title(
        "Percentage of Total VPP Hegemony From IXP-Connected VPPs Over Time",
        fontsize=14 * text_scale,
    )
    ax.tick_params(axis="both", labelsize=10 * text_scale)
    ax.tick_params(axis="x", rotation=45)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="best", fontsize=10 * text_scale)
    ax.set_ylim(bottom=0, top=105)

    plt.tight_layout()
    plt.show()

    save_suffix = "both" if len(ip_versions) > 1 else ip_versions[0]
    save_plot(fig=fig, title=f"global_vpp_ixp_connected_hegemony_share_{asn}_{save_suffix}.png")


def analyze_global_hegemony_over_time(
    asn: int,
    alpha: float,
    ip_version: Union[str, List[str]] = "v4",
    rrc_list: list[str] = None,
    start_date=None,
    month_interval: int = 6,
    use_strict_viewpoint_filtering: bool = False,
    use_free_viewpoint_filtering: bool = True,
    show_as_percentage: bool = True,
    as_color_map=None,
    top_n: int = 5,
    text_scale: float = 1.0,
):
    if as_color_map is None:
        as_color_map = {}

    ip_versions = _parse_ip_versions(ip_version)

    for ip_ver in ip_versions:
        all_available_dates = set()
        for rrc in rrc_list:
            dates = get_all_dates_available_for_asn_data(asn, rrc, ip_ver, start_date=start_date)
            all_available_dates.update(dates)

        if not all_available_dates:
            print(f"[ERROR] No data available for ASN {asn} ({ip_ver.upper()}).")
            continue

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

        print(f"\n[GLOBAL HEGEMONY] Processing {len(interval_dates)} dates for {ip_ver.upper()} across {len(rrc_list)} RRCs...")

        hegemony_scores_dict, _, valid_date_list = get_global_hegemony_scores(
            asn,
            ip_ver,
            interval_dates,
            alpha,
            rrc_list,
            use_strict_viewpoint_filtering=use_strict_viewpoint_filtering,
            use_free_viewpoint_filtering=use_free_viewpoint_filtering,
        )

        if not valid_date_list:
            print(f"[WARNING] No valid global snapshots available for {ip_ver.upper()}.")
            continue

        top_fives_over_time, unique_asns_list = get_top_five_asns_over_time(
            hegemony_scores_dict, valid_date_list,
            top_n=top_n
        )

        cmap = plt.get_cmap("tab20")
        for target_asn in unique_asns_list:
            if target_asn not in as_color_map:
                color_idx = len(as_color_map) % 20
                as_color_map[target_asn] = cmap(color_idx)

        total_hegemony_per_date = [
            sum(hegemony_scores_dict[d].values()) for d in valid_date_list
        ]

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
            f"GLOBAL Hegemony Over Time (All RRCs Combined)\n(Target ASN: {asn}, IP: {ip_ver.upper()}, α={alpha})",
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
        save_plot(fig=fig, title=f"global_hegemony_over_time_{asn}_{ip_ver}.png")


def analyze_global_vpp_hegemony_over_time_top_ases(
    asn: int,
    alpha: float,
    ip_version: Union[str, List[str]] = "v4",
    rrc_list: list[str] = None,
    start_date=None,
    month_interval: int = 6,
    use_strict_viewpoint_filtering: bool = False,
    use_free_viewpoint_filtering: bool = True,
    show_as_percentage: bool = True,
    text_scale: float = 1.0,
    percentage: Optional[float] = None,
): 
    clean_vpp_set = _get_clean_vpp_set()
    ip_versions = _parse_ip_versions(ip_version)

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
    has_data = False

    for ip_ver in ip_versions:
        all_available_dates = set()
        for rrc in rrc_list:
            dates = get_all_dates_available_for_asn_data(asn, rrc, ip_ver, start_date=start_date)
            all_available_dates.update(dates)

        if not all_available_dates:
            print(f"[ERROR] No global data available for ASN {asn} ({ip_ver.upper()}).")
            continue

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
        print(f"\n[GLOBAL VPP] Computing global VPP hegemony ({cutoff_desc}) ({ip_ver.upper()}) for {len(interval_dates)} dates across {len(rrc_list)} RRCs...")

        hegemony_scores_dict, _, valid_date_list = get_global_hegemony_scores(
            asn,
            ip_ver,
            interval_dates,
            alpha,
            rrc_list,
            use_strict_viewpoint_filtering=use_strict_viewpoint_filtering,
            use_free_viewpoint_filtering=use_free_viewpoint_filtering,
        )

        if not valid_date_list:
            print(f"[WARNING] No valid global snapshots available for {ip_ver.upper()}.")
            continue

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

            sorted_items = sorted(cleaned_date_scores.items(), key=lambda x: x[1], reverse=True)
            total_asns = len(sorted_items)

            if percentage is not None:
                top_count = max(1, math.ceil(total_asns * percentage / 100.0))
            else:
                top_count = 5

            top_counts.append(top_count)
            top_items = sorted_items[:top_count]

            hegemony_vpp = sum(score for clean_transit_asn, score in top_items if clean_transit_asn in clean_vpp_set)
            hegemony_not_vpp = sum(score for clean_transit_asn, score in top_items if clean_transit_asn not in clean_vpp_set)

            if show_as_percentage:
                hegemony_vpp = (hegemony_vpp / tot) * 100.0
                hegemony_not_vpp = (hegemony_not_vpp / tot) * 100.0

            hegemony_over_time_vpp_or_not_vpp.append((hegemony_vpp, hegemony_not_vpp))

        formatted_dates = format_labels_if_they_are_dates(valid_date_list)
        linestyle = "-" if ip_ver == "v4" else "--"
        label_suffix = f"IP{ip_ver.lower()}" if len(ip_versions) > 1 else ""

        ax.plot(
            formatted_dates,
            [h[0] for h in hegemony_over_time_vpp_or_not_vpp],
            marker="o" if ip_ver == "v4" else "^",
            linewidth=2.5,
            color="tab:blue",
            linestyle=linestyle,
            label=f"VPP Hegemony {label_suffix}",
        )
        
        ax.plot(
            formatted_dates,
            [h[1] for h in hegemony_over_time_vpp_or_not_vpp],
            marker="s" if ip_ver == "v4" else "D",
            linewidth=2.5,
            color="tab:orange",
            linestyle=linestyle,
            label=f"Non-VPP Hegemony {label_suffix}",
        )
        has_data = True

    if not has_data:
        print("[WARNING] No data plotted.")
        plt.close(fig)
        return

    cutoff_desc = f"Top {percentage}%" if percentage is not None else "Top 5"
    ax.set_xlabel("Date", fontsize=12 * text_scale)
    ax.set_ylabel("Hegemony Percentage (%)" if show_as_percentage else "Hegemony", fontsize=12 * text_scale)
    ax.set_title(
        f"Google's Global Hegemony - VPP vs Non-VPP ({cutoff_desc})",
        fontsize=16 * text_scale,
    )
    ax.tick_params(axis="both", labelsize=10 * text_scale)
    ax.tick_params(axis="x", rotation=45)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(
        loc="upper right",
        title="Is-VPP",
        fontsize=10 * text_scale,
        title_fontsize=11 * text_scale,
    ) 

    ax.set_ylim(bottom=0, top=20 if show_as_percentage else None)

    plt.tight_layout()
    plt.show()

    save_suffix = "both" if len(ip_versions) > 1 else ip_versions[0]
    file_suffix = f"top{int(percentage)}pct" if percentage is not None else "top5"
    save_plot(fig=fig, title=f"global_vpp_hegemony_over_time_{asn}_{save_suffix}_{file_suffix}.png")


def plot_global_hegemony_cdf(
    asn: int,
    alpha: float,
    date: str,
    ip_version: Union[str, List[str]] = "both",
    rrc_list: Optional[List[str]] = None,
    text_scale: float = 1.25,
):
    if rrc_list is None:
        rrc_list = ["rrc03"]

    ip_versions = _parse_ip_versions(ip_version)

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
    has_data = False

    for ip_ver in ip_versions:
        scores, active_vps = load_global_hegemony_for_date(
            asn=asn,
            alpha=alpha,
            date=date,
            ip_version=ip_ver,
            rrc_list=rrc_list,
        )

        if not scores:
            print(f"[WARNING] No scores found for {ip_ver.upper()} on {date}.")
            continue

        valid_scores = [val for val in scores.values() if val > 0]
        if not valid_scores:
            print(f"[WARNING] All scores were zero for {ip_ver.upper()} on {date}.")
            continue

        sorted_scores = sorted(valid_scores, reverse=True)
        total_hegemony = sum(sorted_scores)

        cum_scores = np.cumsum(sorted_scores)
        cum_share = (cum_scores / total_hegemony) * 100.0

        num_ases = len(sorted_scores)
        pct_ases = [(i + 1) / num_ases * 100.0 for i in range(num_ases)]

        x_cdf = [0.0] + pct_ases
        y_cdf = [0.0] + list(cum_share)

        linestyle = "-" if ip_ver == "v4" else "--"
        color = "tab:blue" if ip_ver == "v4" else "tab:orange"
        label = f"IPv4 (N={num_ases} ASes)" if ip_ver == "v4" else f"IPv6 (N={num_ases} ASes)"

        ax.plot(
            x_cdf,
            y_cdf,
            linewidth=2.5,
            linestyle=linestyle,
            color=color,
            label=label,
        )
        has_data = True

    if not has_data:
        print("[WARNING] No data available to plot CDF.")
        plt.close(fig)
        return

    ax.plot([0, 100], [0, 100], color="grey", linestyle=":", linewidth=1.5, label="Uniform Distribution")

    ax.set_xlabel("% of ASes (Ranked Highest to Lowest)", fontsize=12 * text_scale)
    ax.set_ylabel("Cumulative Share of Hegemony (%)", fontsize=12 * text_scale)
    ax.set_title(
        f"Cumulative Hegemony Distribution (CDF)\n(Target ASN: {asn}, Date: {date}, α={alpha})",
        fontsize=14 * text_scale,
    )

    ax.set_xlim(0, 100)
    ax.set_ylim(0, 105)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="lower right", fontsize=10 * text_scale)

    plt.tight_layout()
    plt.show()

    save_plot(fig=fig, title=f"global_hegemony_cdf_{asn}_{date}.png")


def plot_global_vpp_vs_non_vpp_cdf(
    asn: int,
    alpha: float,
    date: str,
    ip_version: Union[str, List[str]] = "both",
    rrc_list: Optional[List[str]] = None,
    text_scale: float = 1.25,
):
    if rrc_list is None:
        rrc_list = ["rrc03"]

    clean_vpp_set = _get_clean_vpp_set()
    ip_versions = _parse_ip_versions(ip_version)

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
    has_data = False

    for ip_ver in ip_versions:
        scores, _ = load_global_hegemony_for_date(
            asn=asn,
            alpha=alpha,
            date=date,
            ip_version=ip_ver,
            rrc_list=rrc_list,
        )

        if not scores:
            print(f"[WARNING] No global scores found for {ip_ver.upper()} on {date}.")
            continue

        vpp_scores = []
        non_vpp_scores = []

        for raw_asn, score in scores.items():
            if score <= 0:
                continue
            clean_asn = str(raw_asn).upper().replace("AS", "").strip()
            if clean_asn in clean_vpp_set:
                vpp_scores.append(score)
            else:
                non_vpp_scores.append(score)

        linestyle = "-" if ip_ver == "v4" else "--"
        ip_label = f" ({ip_ver.upper()})" if len(ip_versions) > 1 else ""

        if vpp_scores:
            sorted_vpp = sorted(vpp_scores, reverse=True)
            tot_vpp = sum(sorted_vpp)
            cum_vpp = (np.cumsum(sorted_vpp) / tot_vpp) * 100.0
            x_vpp = [0.0] + [(i + 1) / len(sorted_vpp) * 100.0 for i in range(len(sorted_vpp))]
            y_vpp = [0.0] + list(cum_vpp)

            ax.plot(
                x_vpp,
                y_vpp,
                linewidth=2.5,
                linestyle=linestyle,
                color="tab:blue",
                label=f"VPP ASes (N={len(sorted_vpp)}){ip_label}",
            )
            has_data = True

        if non_vpp_scores:
            sorted_non = sorted(non_vpp_scores, reverse=True)
            tot_non = sum(sorted_non)
            cum_non = (np.cumsum(sorted_non) / tot_non) * 100.0
            x_non = [0.0] + [(i + 1) / len(sorted_non) * 100.0 for i in range(len(sorted_non))]
            y_non = [0.0] + list(cum_non)

            ax.plot(
                x_non,
                y_non,
                linewidth=2.5,
                linestyle=linestyle,
                color="tab:orange",
                label=f"Non-VPP ASes (N={len(sorted_non)}){ip_label}",
            )
            has_data = True

    if not has_data:
        print("[WARNING] No valid VPP/Non-VPP score data to plot.")
        plt.close(fig)
        return

    ax.plot([0, 100], [0, 100], color="grey", linestyle=":", linewidth=1.5, label="Uniform Distribution")

    ax.set_xlabel("% of ASes within Group (Ranked Highest to Lowest)", fontsize=12 * text_scale)
    ax.set_ylabel("Group Cumulative Share of Hegemony (%)", fontsize=12 * text_scale)
    ax.set_title(
        f"Global Hegemony Distribution: VPP vs. Non-VPP (CDF)\n(Target ASN: {asn}, Date: {date}, α={alpha})",
        fontsize=14 * text_scale,
    )

    ax.set_xlim(0, 100)
    ax.set_ylim(0, 105)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="lower right", fontsize=10 * text_scale)

    plt.tight_layout()
    plt.show()

    save_plot(fig=fig, title=f"global_vpp_vs_non_vpp_hegemony_cdf_{asn}_{date}.png")


if __name__ == "__main__":
    asn = 15169
    alpha = 0.34
    ip_version = "both"
    text_scale = 1.25
    start_date = None

    all_rrcs = ["rrc03"]

    user_input = input("Enter percentage of top ASNs to consider (leave blank to default to Top 5): ").strip()
    percentage = float(user_input) if user_input else None

    user_input = input("Enter the number of top ASNs to consider (leave blank to default to 5): ").strip()

    # 1. Run Global Individual Transit Hegemony Over Time
    print(f"\n[1/3] Running Global Hegemony Over Time (Per Transit) for ASN {asn} ({ip_version.upper()})...")
    analyze_global_hegemony_over_time(
        asn=asn,
        alpha=alpha,
        ip_version=ip_version,
        rrc_list=all_rrcs,
        start_date=start_date,
        month_interval=6,
        use_strict_viewpoint_filtering=False,
        use_free_viewpoint_filtering=True,
        show_as_percentage=True,
        text_scale=text_scale,
        top_n=int(user_input) if user_input else 5
    )
 
    # 2. Run Global VPP vs Non-VPP Hegemony Over Time
    print(f"\n[2/3] Running Global VPP vs Non-VPP Hegemony ({'Top ' + str(percentage) + '%' if percentage else 'Top 5'}) for ASN {asn} ({ip_version.upper()})...")
    analyze_global_vpp_hegemony_over_time_top_ases(
        asn=asn,
        alpha=alpha,
        ip_version=ip_version,
        rrc_list=all_rrcs,
        start_date=start_date,
        month_interval=6,
        use_strict_viewpoint_filtering=False,
        use_free_viewpoint_filtering=True,
        show_as_percentage=True,
        text_scale=text_scale,
        percentage=percentage,
    )

    # 3. Run IXP-Connected VPP Hegemony Share Over Time
    print(f"\n[3/3] Running IXP-Connected VPP Hegemony Share Over Time for ASN {asn} ({ip_version.upper()})...")
    analyze_global_vpp_ixp_connected_hegemony_over_time(
        asn=asn,
        alpha=alpha,
        ip_version=ip_version,
        rrc_list=all_rrcs,
        start_date=start_date,
        month_interval=6,
        use_strict_viewpoint_filtering=False,
        use_free_viewpoint_filtering=True,
        text_scale=text_scale,
    )

    plot_global_hegemony_cdf(
        asn=asn,
        alpha=alpha,
        date="20260901",
        ip_version=ip_version,
        rrc_list=all_rrcs,
        text_scale=text_scale,
    )

    plot_global_vpp_vs_non_vpp_cdf(
        asn=asn,
        alpha=alpha,
        date="20260901",
        ip_version=ip_version,
        rrc_list=all_rrcs,
        text_scale=text_scale,
    )