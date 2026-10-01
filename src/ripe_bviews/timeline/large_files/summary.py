import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from definitions import ROOT_DIR
from src.google.vpps.google_vpps_list import get_google_vpp_asns
from src.utils.graphs import DEFAULT_FIGSIZE, save_plot

from bview_sqlite_parser import (
    get_hegemony_scores,
    get_interval_dates_for_asn_data,
    get_top_five_asns_over_time,
)
from global_hegemony import get_global_hegemony_scores


def evaluate_rrc_metrics(
    asn: int,
    rrc: str,
    ip_version: str,
    alpha: float = 0.34,
    use_strict_viewpoint_filtering: bool = True,
    increase_threshold_pct: float = 5.0,
) -> Tuple[bool, bool, bool, float]:
    """
    Evaluates metrics for a single RRC and IP version.
    Returns:
        (has_data, top_ases_increased, vpp_wins, last_snapshot_top_ases_pct)
    """
    google_vpps_asns = set(str(a) for a in get_google_vpp_asns(include_alternatives=True))

    dates = get_interval_dates_for_asn_data(
        asn, rrc, ip_version, month_interval=6
    )

    if not dates or len(dates) < 2:
        return False, False, False, 0.0

    hegemony_scores_dict, _, valid_dates = get_hegemony_scores(
        asn, rrc, ip_version, dates, alpha, use_strict_viewpoint_filtering
    )

    if not valid_dates or len(valid_dates) < 2:
        return False, False, False, 0.0

    # Ensure actual non-zero hegemony scores exist
    first_date = valid_dates[0]
    last_date = valid_dates[-1]

    first_scores = hegemony_scores_dict.get(first_date, {})
    last_scores = hegemony_scores_dict.get(last_date, {})

    first_total = sum(first_scores.values())
    last_total = sum(last_scores.values())

    # STRICT CHECK: If either snapshot has 0 score, this IP version has NO valid data
    if first_total <= 0.0 or last_total <= 0.0:
        return False, False, False, 0.0

    top_fives_over_time, unique_asns_list = get_top_five_asns_over_time(
        hegemony_scores_dict, valid_dates
    )

    if not unique_asns_list:
        return False, False, False, 0.0

    first_top_sum = sum(first_scores.get(target_asn, 0.0) for target_asn in unique_asns_list)
    last_top_sum = sum(last_scores.get(target_asn, 0.0) for target_asn in unique_asns_list)

    first_top_pct = (first_top_sum / first_total * 100.0)
    last_top_pct = (last_top_sum / last_total * 100.0)

    top_ases_increased = (last_top_pct - first_top_pct) >= increase_threshold_pct

    vpp_hegemony = 0.0
    non_vpp_hegemony = 0.0

    for target_asn in unique_asns_list:
        score = last_scores.get(target_asn, 0.0)
        if str(target_asn) in google_vpps_asns:
            vpp_hegemony += score
        else:
            non_vpp_hegemony += score

    vpp_wins = vpp_hegemony > non_vpp_hegemony

    return True, top_ases_increased, vpp_wins, last_top_pct


def evaluate_global_metrics(
    asn: int,
    rrc_list: List[str],
    ip_version: str,
    alpha: float = 0.34,
    use_strict_viewpoint_filtering: bool = True,
    increase_threshold_pct: float = 5.0,
) -> Tuple[bool, bool, bool, float]:
    """
    Evaluates metrics globally across ALL combined RRCs.
    Returns:
        (has_data, top_ases_increased, vpp_wins, last_snapshot_top_ases_pct)
    """
    google_vpps_asns = set(str(a) for a in get_google_vpp_asns(include_alternatives=True))

    all_available_dates = set()
    for rrc in rrc_list:
        dates = get_interval_dates_for_asn_data(asn, rrc, ip_version)
        all_available_dates.update(dates)

    if not all_available_dates:
        return False, False, False, 0.0

    sorted_dates = sorted(list(all_available_dates))

    hegemony_scores_dict, _, valid_dates = get_global_hegemony_scores(
        asn, ip_version, sorted_dates, alpha, rrc_list,
        use_strict_viewpoint_filtering=use_strict_viewpoint_filtering
    )

    if not valid_dates or len(valid_dates) < 2:
        return False, False, False, 0.0

    first_date = valid_dates[0]
    last_date = valid_dates[-1]

    first_scores = hegemony_scores_dict.get(first_date, {})
    last_scores = hegemony_scores_dict.get(last_date, {})

    first_total = sum(first_scores.values())
    last_total = sum(last_scores.values())

    if first_total <= 0.0 or last_total <= 0.0:
        return False, False, False, 0.0

    top_fives_over_time, unique_asns_list = get_top_five_asns_over_time(
        hegemony_scores_dict, valid_dates
    )

    if not unique_asns_list:
        return False, False, False, 0.0

    first_top_sum = sum(first_scores.get(target_asn, 0.0) for target_asn in unique_asns_list)
    last_top_sum = sum(last_scores.get(target_asn, 0.0) for target_asn in unique_asns_list)

    first_top_pct = (first_top_sum / first_total * 100.0)
    last_top_pct = (last_top_sum / last_total * 100.0)

    top_ases_increased = (last_top_pct - first_top_pct) >= increase_threshold_pct

    vpp_hegemony = 0.0
    non_vpp_hegemony = 0.0

    for target_asn in unique_asns_list:
        score = last_scores.get(target_asn, 0.0)
        if str(target_asn) in google_vpps_asns:
            vpp_hegemony += score
        else:
            non_vpp_hegemony += score

    vpp_wins = vpp_hegemony > non_vpp_hegemony

    return True, top_ases_increased, vpp_wins, last_top_pct


def generate_summary_plot(
    asn: int = 15169,
    alpha: float = 0.34,
    rrc_list: List[str] = None,
    use_strict_viewpoint_filtering: bool = True,
):
    if rrc_list is None:
        rrc_list = [
            "rrc00", "rrc01", "rrc03", "rrc04", "rrc05", "rrc06", "rrc07", "rrc08",
            "rrc09", "rrc10", "rrc11", "rrc12", "rrc13", "rrc14", "rrc15", "rrc16",
            "rrc17", "rrc18", "rrc19", "rrc20", "rrc21", "rrc22"
        ]

    condition_labels = [
        "Has v4+v6 Data",
        "v4: Top ASes +5%",
        "v4: VPP Wins",
        "v6: Top ASes +5%",
        "v6: VPP Wins",
        "IPv6 > IPv4"
    ]

    num_conditions = len(condition_labels)
    results_matrix: List[List[bool]] = []
    display_rows = ["GLOBAL"] + [rrc.upper() for rrc in rrc_list]

    print(f"[SUMMARY] Processing GLOBAL metrics across {len(rrc_list)} RRCs...")
    try:
        g_v4_has, g_v4_inc, g_v4_vpp_win, g_v4_pct = evaluate_global_metrics(
            asn, rrc_list, "v4", alpha=alpha,
            use_strict_viewpoint_filtering=use_strict_viewpoint_filtering
        )
        g_v6_has, g_v6_inc, g_v6_vpp_win, g_v6_pct = evaluate_global_metrics(
            asn, rrc_list, "v6", alpha=alpha,
            use_strict_viewpoint_filtering=use_strict_viewpoint_filtering
        )
        
        has_both = g_v4_has and g_v6_has
        g_v6_gt_v4 = (g_v6_pct > g_v4_pct) if has_both else False

        results_matrix.append([has_both, g_v4_inc, g_v4_vpp_win, g_v6_inc, g_v6_vpp_win, g_v6_gt_v4])
    except Exception as e:
        print(f"[WARNING] Could not process GLOBAL: {e}")
        results_matrix.append([False, False, False, False, False, False])

    print(f"[SUMMARY] Processing individual metrics for {len(rrc_list)} RRCs...")
    for rrc in rrc_list:
        try:
            v4_has, v4_inc, v4_vpp_win, v4_pct = evaluate_rrc_metrics(
                asn, rrc, "v4", alpha=alpha,
                use_strict_viewpoint_filtering=use_strict_viewpoint_filtering
            )
            v6_has, v6_inc, v6_vpp_win, v6_pct = evaluate_rrc_metrics(
                asn, rrc, "v6", alpha=alpha,
                use_strict_viewpoint_filtering=use_strict_viewpoint_filtering
            )

            has_both = v4_has and v6_has
            v6_gt_v4 = (v6_pct > v4_pct) if has_both else False

            results_matrix.append([has_both, v4_inc, v4_vpp_win, v6_inc, v6_vpp_win, v6_gt_v4])
        except Exception as e:
            print(f"[WARNING] Could not process {rrc}: {e}")
            results_matrix.append([False, False, False, False, False, False])

    num_rows = len(display_rows)

    # Plot Matrix Grid
    fig, ax = plt.subplots(figsize=(11, 8))

    box_w = 0.6
    box_h = 0.6
    x_offset = (1.0 - box_w) / 2.0
    y_offset = (1.0 - box_h) / 2.0

    for row_idx, rrc_results in enumerate(results_matrix):
        for col_idx, is_true in enumerate(rrc_results):
            color = "#2ecc71" if is_true else "#e74c3c"
            
            edge_c = "black"
            line_w = 2.0 if row_idx == 0 else 0.8
            
            rect = plt.Rectangle(
                (col_idx + x_offset, row_idx + y_offset), box_w, box_h,
                facecolor=color, edgecolor=edge_c, linewidth=line_w
            )
            ax.add_patch(rect)

    ax.set_xlim(0, num_conditions)
    ax.set_ylim(0, num_rows)

    ax.set_xticks([i + 0.5 for i in range(num_conditions)])
    ax.set_xticklabels(condition_labels, rotation=0, ha="center", fontsize=9.5, fontweight="bold")

    ax.set_yticks([i + 0.5 for i in range(num_rows)])
    ax.set_yticklabels(display_rows, fontsize=10, fontweight="bold")

    # Draw horizontal separator line below GLOBAL row
    ax.axhline(y=1.0, color="black", linewidth=1.5, linestyle="--")

    ax.invert_yaxis()
    ax.grid(False)

    green_patch = mpatches.Patch(color="#2ecc71", label="True")
    red_patch = mpatches.Patch(color="#e74c3c", label="False")
    ax.legend(handles=[green_patch, red_patch], bbox_to_anchor=(1.02, 1), loc="upper left")

    plt.title(f"Hegemony Summary Matrix (ASN {asn}, α={alpha})", fontsize=13, pad=15)
    plt.tight_layout()
    plt.show()

    save_plot(fig=fig, title=f"rrc_hegemony_summary_matrix_{asn}.png")


if __name__ == "__main__":
    generate_summary_plot(asn=15169, alpha=0.34)


    