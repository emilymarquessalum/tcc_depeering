

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


def evaluate_rrc_metrics(
    asn: int,
    rrc: str,
    ip_version: str,
    alpha: float = 0.34,
    use_strict_viewpoint_filtering: bool = True,
    increase_threshold_pct: float = 5.0,
) -> Tuple[bool, bool, float]:
    """
    Evaluates condition 1 and condition 2 for a specific RRC and IP version:
    1. Has Top ASes hegemony increased by >= threshold % between first and last dates?
    2. Does VPP hegemony surpass Non-VPP hegemony at the final date snapshot?
    
    Returns:
        (top_ases_increased, vpp_wins, last_snapshot_top_ases_pct)
    """
    google_vpps_asns = set(str(a) for a in get_google_vpp_asns(include_alternatives=True))

    # 1. Fetch available interval dates
    dates = get_interval_dates_for_asn_data(
        asn, rrc, ip_version, month_interval=6
    )

    if not dates or len(dates) < 2:
        return False, False, 0.0

    # 2. Get scores across available snapshots
    hegemony_scores_dict, _, valid_dates = get_hegemony_scores(
        asn, rrc, ip_version, dates, alpha, use_strict_viewpoint_filtering
    )

    if not valid_dates or len(valid_dates) < 2:
        return False, False, 0.0

    # Get the unique top ASNs (determined consistently using the reusable parser function)
    top_fives_over_time, unique_asns_list = get_top_five_asns_over_time(
        hegemony_scores_dict, valid_dates
    )

    if not unique_asns_list:
        return False, False, 0.0

    # 3. Calculate percentage shares per date for Top ASNs
    first_date = valid_dates[0]
    last_date = valid_dates[-1]

    first_scores = hegemony_scores_dict.get(first_date, {})
    last_scores = hegemony_scores_dict.get(last_date, {})

    first_total = sum(first_scores.values())
    last_total = sum(last_scores.values())

    first_top_sum = sum(first_scores.get(target_asn, 0.0) for target_asn in unique_asns_list)
    last_top_sum = sum(last_scores.get(target_asn, 0.0) for target_asn in unique_asns_list)

    first_top_pct = (first_top_sum / first_total * 100.0) if first_total > 0 else 0.0
    last_top_pct = (last_top_sum / last_total * 100.0) if last_total > 0 else 0.0

    # Condition 1: Has hegemony for Top ASes increased >= threshold_pct?
    top_ases_increased = (last_top_pct - first_top_pct) >= increase_threshold_pct

    # 4. Condition 2: Check if VPP hegemony > Non-VPP hegemony on the latest snapshot date
    vpp_hegemony = 0.0
    non_vpp_hegemony = 0.0

    for target_asn in unique_asns_list:
        score = last_scores.get(target_asn, 0.0)
        if str(target_asn) in google_vpps_asns:
            vpp_hegemony += score
        else:
            non_vpp_hegemony += score

    vpp_wins = vpp_hegemony > non_vpp_hegemony

    return top_ases_increased, vpp_wins, last_top_pct


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
        "v4: Top ASes Hegemony Increased (>=5%)",
        "v4: VPP Hegemony Wins",
        "v6: Top ASes Hegemony Increased (>=5%)",
        "v6: VPP Hegemony Wins",
        "v4 Top ASes Hegemony % > v6 Top ASes Hegemony %"
    ]

    num_rrcs = len(rrc_list)
    num_conditions = len(condition_labels)

    # Matrix to store boolean outcomes (True -> Green, False -> Red)
    results_matrix = []

    print(f"[SUMMARY] Processing metrics across {num_rrcs} RRCs for ASN {asn}...")

    for rrc in rrc_list:
        try:
            v4_inc, v4_vpp_win, v4_pct = evaluate_rrc_metrics(
                asn, rrc, "v4", alpha=alpha,
                use_strict_viewpoint_filtering=use_strict_viewpoint_filtering
            )
            v6_inc, v6_vpp_win, v6_pct = evaluate_rrc_metrics(
                asn, rrc, "v6", alpha=alpha,
                use_strict_viewpoint_filtering=use_strict_viewpoint_filtering
            )
            v4_gt_v6 = v4_pct > v6_pct

            results_matrix.append([v4_inc, v4_vpp_win, v6_inc, v6_vpp_win, v4_gt_v6])
            print(f"  [{rrc.upper()}] Done -> v4 Inc: {v4_inc}, v4 VPP Win: {v4_vpp_win}, v6 Inc: {v6_inc}, v6 VPP Win: {v6_vpp_win}, v4>v6: {v4_gt_v6}")
        except Exception as e:
            print(f"[WARNING] Could not process {rrc}: {e}")
            results_matrix.append([False, False, False, False, False])

    # Plot Matrix Grid
    fig, ax = plt.subplots(figsize=(14, 8))

    for row_idx, rrc_results in enumerate(results_matrix):
        for col_idx, is_true in enumerate(rrc_results):
            color = "#2ecc71" if is_true else "#e74c3c"
            rect = plt.Rectangle(
                (col_idx, row_idx), 0.85, 0.8,
                facecolor=color, edgecolor="black", linewidth=1.2
            )
            ax.add_patch(rect)
            ax.text(
                col_idx + 0.425, row_idx + 0.4,
                "YES" if is_true else "NO",
                ha="center", va="center",
                color="white", fontweight="bold", fontsize=9
            )

    ax.set_xlim(0, num_conditions)
    ax.set_ylim(0, num_rrcs)

    ax.set_xticks([i + 0.425 for i in range(num_conditions)])
    ax.set_xticklabels(condition_labels, rotation=30, ha="right", fontsize=10, fontweight="bold")

    ax.set_yticks([i + 0.4 for i in range(num_rrcs)])
    ax.set_yticklabels([rrc.upper() for rrc in rrc_list], fontsize=10, fontweight="bold")

    ax.invert_yaxis()  # rrc00 at the top
    ax.grid(False)

    green_patch = mpatches.Patch(color="#2ecc71", label="Condition Met (True)")
    red_patch = mpatches.Patch(color="#e74c3c", label="Condition Not Met (False)")
    ax.legend(handles=[green_patch, red_patch], bbox_to_anchor=(1.02, 1), loc="upper left")

    plt.title(f"Hegemony & VPP Metrics Summary Per RRC Collector (ASN {asn}, α={alpha})", fontsize=14, pad=20)
    plt.tight_layout()
    plt.show()

    save_plot(fig=fig, title=f"rrc_hegemony_summary_matrix_{asn}.png")


if __name__ == "__main__":
    generate_summary_plot(asn=15169, alpha=0.34)