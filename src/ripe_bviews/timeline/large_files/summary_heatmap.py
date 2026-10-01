

import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

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
) -> Dict[str, Optional[float]]:
    """
    Evaluates continuous quantitative metrics for a single RRC and IP version.
    Returns dictionary with:
        - has_data: bool
        - heg_delta_pct: change in total top ASes hegemony (% points)
        - vpp_heg_delta_pct: change in VPP hegemony score (% points)
        - last_top_pct: total top ASes hegemony % in last snapshot
    """
    google_vpps_asns = set(str(a) for a in get_google_vpp_asns(include_alternatives=True))

    dates = get_interval_dates_for_asn_data(
        asn, rrc, ip_version, month_interval=6
    )

    empty_res = {"has_data": False, "heg_delta_pct": np.nan, "vpp_heg_delta_pct": np.nan, "last_top_pct": np.nan}

    if not dates or len(dates) < 2:
        return empty_res

    hegemony_scores_dict, _, valid_dates = get_hegemony_scores(
        asn, rrc, ip_version, dates, alpha, use_strict_viewpoint_filtering
    )

    if not valid_dates or len(valid_dates) < 2:
        return empty_res

    first_date = valid_dates[0]
    last_date = valid_dates[-1]

    first_scores = hegemony_scores_dict.get(first_date, {})
    last_scores = hegemony_scores_dict.get(last_date, {})

    first_total = sum(first_scores.values())
    last_total = sum(last_scores.values())

    if first_total <= 0.0 or last_total <= 0.0:
        return empty_res

    top_fives_over_time, unique_asns_list = get_top_five_asns_over_time(
        hegemony_scores_dict, valid_dates
    )

    if not unique_asns_list:
        return empty_res

    # Overall Hegemony calculations
    first_top_sum = sum(first_scores.get(target_asn, 0.0) for target_asn in unique_asns_list)
    last_top_sum = sum(last_scores.get(target_asn, 0.0) for target_asn in unique_asns_list)

    first_top_pct = (first_top_sum / first_total * 100.0)
    last_top_pct = (last_top_sum / last_total * 100.0)
    heg_delta_pct = last_top_pct - first_top_pct

    # VPP Hegemony calculations
    first_vpp_sum = sum(first_scores.get(t, 0.0) for t in unique_asns_list if str(t) in google_vpps_asns)
    last_vpp_sum = sum(last_scores.get(t, 0.0) for t in unique_asns_list if str(t) in google_vpps_asns)

    first_vpp_pct = (first_vpp_sum / first_total * 100.0)
    last_vpp_pct = (last_vpp_sum / last_total * 100.0)
    vpp_heg_delta_pct = last_vpp_pct - first_vpp_pct

    return {
        "has_data": True,
        "heg_delta_pct": heg_delta_pct,
        "vpp_heg_delta_pct": vpp_heg_delta_pct,
        "last_top_pct": last_top_pct
    }


def evaluate_global_metrics(
    asn: int,
    rrc_list: List[str],
    ip_version: str,
    alpha: float = 0.34,
    use_strict_viewpoint_filtering: bool = True,
) -> Dict[str, Optional[float]]:
    """
    Evaluates continuous quantitative metrics globally across ALL combined RRCs.
    """
    google_vpps_asns = set(str(a) for a in get_google_vpp_asns(include_alternatives=True))
    empty_res = {"has_data": False, "heg_delta_pct": np.nan, "vpp_heg_delta_pct": np.nan, "last_top_pct": np.nan}

    all_available_dates = set()
    for rrc in rrc_list:
        dates = get_interval_dates_for_asn_data(asn, rrc, ip_version)
        all_available_dates.update(dates)

    if not all_available_dates:
        return empty_res

    sorted_dates = sorted(list(all_available_dates))

    hegemony_scores_dict, _, valid_dates = get_global_hegemony_scores(
        asn, ip_version, sorted_dates, alpha, rrc_list,
        use_strict_viewpoint_filtering=use_strict_viewpoint_filtering
    )

    if not valid_dates or len(valid_dates) < 2:
        return empty_res

    first_date = valid_dates[0]
    last_date = valid_dates[-1]

    first_scores = hegemony_scores_dict.get(first_date, {})
    last_scores = hegemony_scores_dict.get(last_date, {})

    first_total = sum(first_scores.values())
    last_total = sum(last_scores.values())

    if first_total <= 0.0 or last_total <= 0.0:
        return empty_res

    top_fives_over_time, unique_asns_list = get_top_five_asns_over_time(
        hegemony_scores_dict, valid_dates
    )

    if not unique_asns_list:
        return empty_res

    # Overall Hegemony calculations
    first_top_sum = sum(first_scores.get(target_asn, 0.0) for target_asn in unique_asns_list)
    last_top_sum = sum(last_scores.get(target_asn, 0.0) for target_asn in unique_asns_list)

    first_top_pct = (first_top_sum / first_total * 100.0)
    last_top_pct = (last_top_sum / last_total * 100.0)
    heg_delta_pct = last_top_pct - first_top_pct

    # VPP Hegemony calculations
    first_vpp_sum = sum(first_scores.get(t, 0.0) for t in unique_asns_list if str(t) in google_vpps_asns)
    last_vpp_sum = sum(last_scores.get(t, 0.0) for t in unique_asns_list if str(t) in google_vpps_asns)

    first_vpp_pct = (first_vpp_sum / first_total * 100.0)
    last_vpp_pct = (last_vpp_sum / last_total * 100.0)
    vpp_heg_delta_pct = last_vpp_pct - first_vpp_pct

    return {
        "has_data": True,
        "heg_delta_pct": heg_delta_pct,
        "vpp_heg_delta_pct": vpp_heg_delta_pct,
        "last_top_pct": last_top_pct
    }


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

    column_labels = [
        "v4 Heg Δ (%)",
        "v4 VPP Heg Δ (%)",
        "v6 Heg Δ (%)",
        "v6 VPP Heg Δ (%)",
        "v6 vs v4 Heg Δ (%)"
    ]

    display_rows = ["GLOBAL"] + [rrc.upper() for rrc in rrc_list]
    matrix_rows = []

    # 1. Process GLOBAL
    print(f"[SUMMARY] Processing GLOBAL metrics across {len(rrc_list)} RRCs...")
    try:
        g_v4 = evaluate_global_metrics(asn, rrc_list, "v4", alpha, use_strict_viewpoint_filtering)
        g_v6 = evaluate_global_metrics(asn, rrc_list, "v6", alpha, use_strict_viewpoint_filtering)

        v6_minus_v4 = (
            (g_v6["last_top_pct"] - g_v4["last_top_pct"])
            if (g_v4["has_data"] and g_v6["has_data"])
            else np.nan
        )

        matrix_rows.append([
            g_v4["heg_delta_pct"],
            g_v4["vpp_heg_delta_pct"],
            g_v6["heg_delta_pct"],
            g_v6["vpp_heg_delta_pct"],
            v6_minus_v4
        ])
    except Exception as e:
        print(f"[WARNING] Could not process GLOBAL: {e}")
        matrix_rows.append([np.nan] * 5)

    # 2. Process Individual RRCs
    print(f"[SUMMARY] Processing individual metrics for {len(rrc_list)} RRCs...")
    for rrc in rrc_list:
        try:
            v4_res = evaluate_rrc_metrics(asn, rrc, "v4", alpha, use_strict_viewpoint_filtering)
            v6_res = evaluate_rrc_metrics(asn, rrc, "v6", alpha, use_strict_viewpoint_filtering)

            v6_minus_v4 = (
                (v6_res["last_top_pct"] - v4_res["last_top_pct"])
                if (v4_res["has_data"] and v6_res["has_data"])
                else np.nan
            )

            matrix_rows.append([
                v4_res["heg_delta_pct"],
                v4_res["vpp_heg_delta_pct"],
                v6_res["heg_delta_pct"],
                v6_res["vpp_heg_delta_pct"],
                v6_minus_v4
            ])
        except Exception as e:
            print(f"[WARNING] Could not process {rrc}: {e}")
            matrix_rows.append([np.nan] * 5)

    # Convert to DataFrame
    df = pd.DataFrame(matrix_rows, index=display_rows, columns=column_labels)

    # Create Heatmap
    fig, ax = plt.subplots(figsize=(12, 10))
    ax.set_facecolor("#e0e0e0")  # Gray background for missing (NaN) values

    # Format values for annotation string with explicit +/- sign
    annot_matrix = np.empty(df.shape, dtype=object)
    for i in range(df.shape[0]):
        for j in range(df.shape[1]):
            val = df.iloc[i, j]
            annot_matrix[i, j] = f"{val:+.1f}%" if not np.isnan(val) else "N/A"

    sns.heatmap(
        df,
        annot=annot_matrix,
        fmt="",
        cmap="RdYlGn",
        center=0.0,
        linewidths=0.8,
        linecolor="white",
        cbar_kws={"label": "Percentage Point Delta (%)"},
        ax=ax
    )

    # Separate GLOBAL row visually
    ax.axhline(y=1.0, color="black", linewidth=2.5)

    plt.title(f"Hegemony Growth & Delta Summary Heatmap (ASN {asn}, α={alpha})", fontsize=14, pad=15, fontweight="bold")
    plt.xticks(rotation=15, ha="right", fontsize=10, fontweight="bold")
    plt.yticks(fontsize=10, fontweight="bold")
    plt.tight_layout()
    plt.show()

    save_plot(fig=fig, title=f"rrc_hegemony_summary_heatmap_{asn}.png")


if __name__ == "__main__":
    generate_summary_plot(asn=15169, alpha=0.34)
    