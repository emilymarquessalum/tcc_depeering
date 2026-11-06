"""Plot the highest-hegemony transit ASes over time across all RRCs combined (Global view)."""

import os
import sqlite3
from collections import defaultdict
from pathlib import Path
import sys
from typing import Dict, List, Optional, Sequence, Set, Tuple, Union

from matplotlib import pyplot as plt

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from src.ripe_bviews.timeline.bview_load import get_all_rrcs
from src.ripe_bviews.timeline.large_files.bview_sqlite_parser import (
    _apply_alpha_trimming,
    _resolve_rrc_dir,
    get_auto_interval_dates,
    get_sorted_asns_from_scores,
    get_top_five_asns_over_time,
    get_active_viewpoints_for_date,
    LargeBViewParser,
)
from src.utils.graphs import DEFAULT_FIGSIZE, save_plot


def _parse_ip_versions(ip_version: Union[str, Sequence[str]]) -> List[str]:
    """Normalize an IP-version argument to one or both supported values."""
    values = [ip_version] if isinstance(ip_version, str) else list(ip_version)
    versions: List[str] = []
    for value in values:
        normalized = str(value).lower().replace("ip", "").strip()
        if normalized in {"both", "v4_v6", "v4v6"}:
            return ["v4", "v6"]
        if normalized in {"v4", "v6"} and normalized not in versions:
            versions.append(normalized)
    return versions or ["v4"]


def calculate_global_hegemony_for_date(
    asn: int,
    rrc_list: List[str],
    date: str,
    ip_version: str = "v4",
    alpha: float = 0.34,
    allowed_viewpoints_map: Optional[Dict[str, Set[str]]] = None,
    only_penultimate_as: bool = True,
    v4_threshold: int = 1,
    v6_threshold: int = 1,
) -> Tuple[Dict[int, float], int]:
    """
    Computes Hegemony across ALL RRC databases for a specific date,
    treating viewpoints from all collectors as part of a global monitor pool.
    """
    global_vp_active_weights = {}
    global_transit_vp_weights = defaultdict(lambda: defaultdict(float))
    all_transit_asns = set()

    for rrc in rrc_list:
        db_path = f"huge_bgp_cache_{rrc}_{date}_{ip_version}_{asn}.db"
        rrc_dir = _resolve_rrc_dir(rrc)
        raw_path = os.path.join(rrc_dir, f"output_bview.{date}.0000.{ip_version}.origin_as.{asn}.txt")
        if not os.path.exists(raw_path):
            raw_path = os.path.join(rrc_dir, f"output_bview.{date}.0000.origin_as.{asn}.txt")

        if not os.path.exists(db_path):
            if not os.path.exists(raw_path):
                continue
            parser = LargeBViewParser(db_path=db_path, ip_version=ip_version)
            parser.parse_to_disk(raw_path)

        if not os.path.exists(db_path):
            continue

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Step 1: Baseline weights for this RRC
        cursor.execute("""
            SELECT viewpoint_peer, COUNT(DISTINCT prefix) 
            FROM bgp_mappings 
            GROUP BY viewpoint_peer
        """)
        vp_table_sizes = {vp: size for vp, size in cursor.fetchall()}

        cursor.execute("SELECT viewpoint_peer, prefix_weight FROM bgp_mappings WHERE reachable_as = ?", (asn,))
        vp_total_weights = defaultdict(float)
        for vp, weight in cursor.fetchall():
            vp_total_weights[vp] += weight

        rrc_allowed_vps = allowed_viewpoints_map.get(rrc) if allowed_viewpoints_map else None
        chosen_threshold = v4_threshold if ip_version == "v4" else v6_threshold

        active_vps_for_rrc = set()
        for vp, total_w in vp_total_weights.items():
            if rrc_allowed_vps is not None and vp not in rrc_allowed_vps:
                continue
            if vp_table_sizes.get(vp, 0) < chosen_threshold:
                continue

            # Qualify viewpoint by RRC to avoid naming collisions across collectors
            global_vp_key = f"{rrc}_{vp}"
            global_vp_active_weights[global_vp_key] = total_w
            active_vps_for_rrc.add(vp)

        if not active_vps_for_rrc:
            conn.close()
            continue

        # Step 2: Transit intersections for active viewpoints
        cursor.execute("SELECT viewpoint_peer, as_path, prefix_weight FROM bgp_mappings WHERE reachable_as = ?", (asn,))
        while True:
            rows = cursor.fetchmany(size=50_000)
            if not rows:
                break
            for vp, path_str, weight in rows:
                if vp not in active_vps_for_rrc:
                    continue
                try:
                    as_path = [int(x) for x in path_str.split(",") if x]
                except ValueError:
                    continue

                global_vp_key = f"{rrc}_{vp}"

                if only_penultimate_as:
                    unique_transits = set()
                    for idx, asn_node in enumerate(as_path):
                        if asn_node == asn and idx > 0:
                            penultimate_as = as_path[idx - 1]
                            if penultimate_as != asn:
                                unique_transits.add(penultimate_as)
                else:
                    unique_transits = set(as_path)
                    if asn in unique_transits:
                        unique_transits.remove(asn)

                for transit_node in unique_transits:
                    global_transit_vp_weights[transit_node][global_vp_key] += weight
                    all_transit_asns.add(transit_node)

        conn.close()

    total_monitors = len(global_vp_active_weights)
    if total_monitors == 0:
        return {}, 0

    # Step 3: Alpha-Trimming over all global viewpoints
    hegemony_scores = {}
    active_peers_list = list(global_vp_active_weights.keys())

    for transit_asn in all_transit_asns:
        scores = []
        for vp_key in active_peers_list:
            vp_weight = global_transit_vp_weights[transit_asn].get(vp_key, 0.0)
            denom = global_vp_active_weights[vp_key]
            fraction = vp_weight / denom if denom > 0 else 0.0
            scores.append(fraction)
        hegemony_scores[transit_asn] = _apply_alpha_trimming(scores, alpha)

    return hegemony_scores, total_monitors


def get_global_hegemony_scores(
    asn: int,
    rrc_list: List[str],
    date_list: List[str],
    ip_version: str,
    alpha: float = 0.34,
    use_strict_viewpoint_filtering: bool = True,
) -> Tuple[Dict[str, Dict[int, float]], Dict[str, int], List[str]]:
    """Calculates global hegemony scores across all dates."""
    rrc_allowed_vps: Dict[str, Set[str]] = {}

    if use_strict_viewpoint_filtering:
        for rrc in rrc_list:
            date_vps = []
            for date in date_list:
                vps = get_active_viewpoints_for_date(asn, rrc, date, ip_version)
                if len(vps) > 3:
                    date_vps.append(vps)
            if date_vps:
                rrc_allowed_vps[rrc] = set.intersection(*date_vps)

    global_hegemony_dict = {}
    global_monitors_dict = {}
    valid_dates = []

    for date in date_list:
        scores, monitor_count = calculate_global_hegemony_for_date(
            asn=asn,
            rrc_list=rrc_list,
            date=date,
            ip_version=ip_version,
            alpha=alpha,
            allowed_viewpoints_map=rrc_allowed_vps if use_strict_viewpoint_filtering else None,
        )
        if monitor_count > 0:
            global_hegemony_dict[date] = scores
            global_monitors_dict[date] = monitor_count
            valid_dates.append(date)

    return global_hegemony_dict, global_monitors_dict, valid_dates


def plot_top_global_asns_over_time(
    asn: int,
    rrc_list: Optional[List[str]] = None,
    alpha: float = 0.34,
    top_n: int = 5,
    ip_version: Union[str, Sequence[str]] = "v4",
    date_list: Optional[List[str]] = None,
    use_strict_viewpoint_filtering: bool = True,
    show_as_percentage: bool = False,
    month_interval: int = 6,
    start_date: Optional[str] = None,
    text_scale: float = 1.0,
    highlight_max_per_date: bool = False,
    show: bool = False,
) -> List[plt.Figure]:
    """Save plots of top N global transit providers across all RRCs combined."""
    if rrc_list is None:
        rrc_list = [item["rrc"] for item in get_all_rrcs()]

    figures: List[plt.Figure] = []
    for ip_ver in _parse_ip_versions(ip_version):
        dates = date_list
        if dates is None:
            dates = get_auto_interval_dates(
                asn=asn,
                rrc_list=rrc_list,
                ip_version=ip_ver,
                is_global=True,
                month_interval=month_interval,
                start_date=start_date,
            )

        if not dates:
            print(f"[WARNING] No snapshots available globally for ASN {asn} ({ip_ver.upper()}).")
            continue

        scores, monitor_counts, valid_dates = get_global_hegemony_scores(
            asn=asn,
            rrc_list=rrc_list,
            date_list=dates,
            ip_version=ip_ver,
            alpha=alpha,
            use_strict_viewpoint_filtering=use_strict_viewpoint_filtering,
        )

        if not valid_dates:
            print(f"[WARNING] No valid global snapshots found for ASN {asn} ({ip_ver.upper()}).")
            continue

        top_scores, top_asns = get_top_five_asns_over_time(
            scores,
            valid_dates,
            top_n=top_n,
        )

        if not top_asns:
            print(f"[WARNING] No transit ASes available globally for ASN {asn} ({ip_ver.upper()}).")
            continue

        totals = [sum(scores[date].values()) for date in valid_dates]
        fig, ax = plt.subplots(figsize=DEFAULT_FIGSIZE)
        cmap = plt.get_cmap("tab20")
        plotted_values: List[List[float]] = []

        for index, target_asn in enumerate(top_asns):
            values = [top_scores[date_index][index] for date_index in range(len(valid_dates))]
            if show_as_percentage:
                values = [
                    value / total * 100.0 if total > 0 else 0.0
                    for value, total in zip(values, totals)
                ]
            plotted_values.append(values)
            ax.plot(
                valid_dates,
                values,
                marker="o",
                linewidth=2.0,
                color=cmap(index % 20),
                label=f"AS{target_asn}",
            )

        if highlight_max_per_date:
            highest_values = [
                max(values_at_date) if values_at_date else 0.0
                for values_at_date in zip(*plotted_values)
            ]
            ax.plot(
                valid_dates,
                highest_values,
                color="blue",
                linewidth=4.5,
                zorder=5,
                label="Highest Score",
            )

        ax.set_xlabel("Date", fontsize=12 * text_scale)
        ax.set_ylabel(
            "Global Hegemony (%)" if show_as_percentage else "Global Hegemony Score",
            fontsize=12 * text_scale,
        )
        ax.set_title(
            f"Top {top_n} Global Transit ASes Over Time\n"
            f"(Target ASN: {asn}, Pool: ALL RRCs, IP: {ip_ver.upper()}, α={alpha})",
            fontsize=14 * text_scale,
        )
        ax.tick_params(axis="both", labelsize=10 * text_scale)
        ax.tick_params(axis="x", rotation=45)
        ax.grid(True, linestyle="--", alpha=0.5)
        ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", title="Global Transit AS")

        fig.tight_layout()
        save_plot(
            fig=fig,
            title=f"top{top_n}_global_asns_over_time_{asn}_{ip_ver}.png",
        )
        if show:
            plt.show()
        else:
            plt.close(fig)
        figures.append(fig)

    return figures


def over_time_global(
    asn: int,
    rrc_list: Optional[List[str]] = None,
    alpha: float = 0.34,
    **kwargs,
) -> List[plt.Figure]:
    """Plots global top ASes by aggregating data across all (or specified) RRCs."""
    return plot_top_global_asns_over_time(asn, rrc_list=rrc_list, alpha=alpha, **kwargs)


if __name__ == "__main__":
    target_asn = int(input("Enter target ASN (default 15169): ") or "15169")
    top_n = int(input("Enter number of top global ASes (default 5): ") or "5")
    over_time_global(
        target_asn,
        top_n=top_n,
        ip_version="both",
        show_as_percentage=True,
        highlight_max_per_date=True,
    )