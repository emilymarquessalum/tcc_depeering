from collections import defaultdict
from datetime import datetime
import os
from pathlib import Path
import sqlite3
import sys
from typing import Dict, List, Optional, Set, Tuple, Union

from dateutil.relativedelta import relativedelta
from matplotlib import pyplot as plt

from src.ripe_bviews.timeline.large_files.global_hegemony import _parse_ip_versions

# Preserving project root path insertion
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from definitions import ROOT_DIR
from src.google.vpps.google_vpps_list import get_google_vpp_asns
from src.ripe_bviews.timeline.bview_hegemony import get_sorted_asns_from_scores
from src.utils.graphs import DEFAULT_FIGSIZE, save_plot

# Import database parsing and core score computations
from bview_sqlite_parser import (
    get_hegemony_scores,
    get_interval_dates_for_asn_data,
)


def _get_clean_vpp_set() -> Set[str]:
    """Retrieves and normalizes Google VPP ASNs into pure numeric string format."""
    raw_vpps = get_google_vpp_asns(include_alternatives=True)
    return {str(asn).upper().replace("AS", "").strip() for asn in raw_vpps}


def compare_vpp_and_non_vpp_hegemony_over_time(
    asn: int,
    alpha: float,
    rrc_used: str,
    ip_version: Union[str, List[str]] = "v4",
    date_list: Optional[List[str]] = None,
    use_strict_viewpoint_filtering: bool = False,
    use_best_next_days: int = 0,
    show_as_percentage: bool = False,
    only_top_5: bool = False,
    text_scale: float = 1.0,
    show_both_ip_versions: bool = False,
    start_date=None,
    month_interval: int = 6,
): 
    clean_vpp_set = _get_clean_vpp_set()
    ip_versions = _parse_ip_versions(ip_version, show_both_ip_versions)

    # Apply global default text scaling across all Matplotlib defaults
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
    scope_str = "Top 5 ASes Only" if only_top_5 else "All ASes"
    has_data = False

    for ip_ver in ip_versions:
        if date_list is None:
            current_date_list = get_interval_dates_for_asn_data(
                asn, rrc_used, ip_ver, month_interval=month_interval, start_date=start_date
            )
        else:
            current_date_list = date_list

        hegemony_scores_dict, viewpoint_counts_dict, valid_date_list = get_hegemony_scores(
            asn,
            rrc_used,
            ip_ver,
            current_date_list,
            alpha,
            use_strict_viewpoint_filtering,
            use_best_next_days=use_best_next_days,
        )

        if not valid_date_list:
            print(f"[WARNING] No valid snapshots available to process for RRC {rrc_used} ({ip_ver.upper()}).")
            continue

        hegemony_over_time_vpp_or_not_vpp: List[Tuple[float, float]] = []

        for date in valid_date_list:
            date_scores = hegemony_scores_dict.get(date, {})
            total_hegemony = sum(date_scores.values())

            if total_hegemony <= 0.0:
                hegemony_over_time_vpp_or_not_vpp.append((0.0, 0.0))
                continue

            cleaned_date_scores = {
                str(raw_asn).upper().replace("AS", "").strip(): score
                for raw_asn, score in date_scores.items()
            }

            if only_top_5:
                sorted_items = sorted(cleaned_date_scores.items(), key=lambda x: x[1], reverse=True)
                target_items = sorted_items[:5]
            else:
                target_items = cleaned_date_scores.items()

            hegemony_vpp = 0.0
            hegemony_not_vpp = 0.0

            for clean_transit_asn, score in target_items:
                if clean_transit_asn in clean_vpp_set:
                    hegemony_vpp += score
                else:
                    hegemony_not_vpp += score

            if show_as_percentage:
                hegemony_vpp = (hegemony_vpp / total_hegemony) * 100.0
                hegemony_not_vpp = (hegemony_not_vpp / total_hegemony) * 100.0

            hegemony_over_time_vpp_or_not_vpp.append((hegemony_vpp, hegemony_not_vpp))

        linestyle = "-" if ip_ver == "v4" else "--"
        label_suffix = f" ({ip_ver.upper()})" if len(ip_versions) > 1 else ""

        ax.plot(
            valid_date_list,
            [h[0] for h in hegemony_over_time_vpp_or_not_vpp],
            marker="o" if ip_ver == "v4" else "^",
            linewidth=2.5,
            color="tab:blue",
            linestyle=linestyle,
            label=f"VPP Hegemony ({scope_str}){label_suffix}",
        )

        ax.plot(
            valid_date_list,
            [h[1] for h in hegemony_over_time_vpp_or_not_vpp],
            marker="s" if ip_ver == "v4" else "D",
            linewidth=2.5,
            color="tab:orange",
            linestyle=linestyle,
            label=f"Non-VPP Hegemony ({scope_str}){label_suffix}",
        )
        has_data = True

    if not has_data:
        print("[WARNING] No data plotted.")
        plt.close(fig)
        return

    y_label = "Hegemony Percentage (%)" if show_as_percentage else "Hegemony Score"
    ax.set_ylabel(y_label, fontsize=12 * text_scale)
    ax.set_xlabel("Date", fontsize=12 * text_scale)

    ip_desc = "IPv4 & IPv6" if len(ip_versions) > 1 else ip_versions[0].upper()
    ax.set_title(
        f"VPP vs. Non-VPP Hegemony Share Over Time [{scope_str}]\n"
        f"(Target ASN: {asn}, RRC: {rrc_used.upper()}, IP: {ip_desc}, α={alpha})",
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

    file_tag = "top5" if only_top_5 else "all"
    save_suffix = "both" if len(ip_versions) > 1 else ip_versions[0]
    save_plot(
        fig=fig,
        title=f"hegemony_over_time_by_vpp_feature_{asn}_{rrc_used}_{save_suffix}_{file_tag}.png",
    )

if __name__ == "__main__":
    asn = 15169
    text_scale = 1.0  # Increase to scale font size of EVERYTHING (e.g., 1.5 = 150% size)
    start_date = None

    rrcs = [
        "rrc03", "rrc04", "rrc05", "rrc06", "rrc07", "rrc08", "rrc09", "rrc10",
        "rrc11", "rrc12", "rrc13", "rrc14", "rrc15", "rrc16", "rrc17", "rrc18",
        "rrc19", "rrc20", "rrc21", "rrc22",
    ]

    asn_input = input(f"Enter ASN to analyze (default {asn}): ")
    if asn_input:
        asn = int(asn_input)

    configs = [
        {"rrc_used": rrc, "ip_version": "both", "asn": asn, "start_date": None, "use_best_next_days": 0}
        for rrc in rrcs
    ]

    alpha = 0.34
    use_strict_viewpoint_filtering = True
    show_as_percentage = True
    only_top_5 = True  # Toggle between True (Top 5 only) and False (All ASes)

    for config in configs:
        rrc_used = config["rrc_used"]
        ip_version = config["ip_version"]
        target_asn = config["asn"]
        start_date = config["start_date"]
        use_best_next_days = config["use_best_next_days"]

        print(f"\n[INFO] Running VPP Analysis for ASN {target_asn} on RRC {rrc_used} ({ip_version.upper()}) [Top 5 Only: {only_top_5}]...")

        try:
            dates = get_interval_dates_for_asn_data(
                target_asn, rrc_used, ip_version, month_interval=6, start_date=start_date
            )

            compare_vpp_and_non_vpp_hegemony_over_time(
                target_asn,
                alpha,
                rrc_used,
                ip_version,
                dates,
                use_strict_viewpoint_filtering=use_strict_viewpoint_filtering,
                use_best_next_days=use_best_next_days,
                show_as_percentage=show_as_percentage,
                only_top_5=only_top_5,
                text_scale=text_scale,
            )
        except Exception as e:
            print(f"[ERROR] An error occurred during VPP analysis for RRC {rrc_used}: {e}")
            continue