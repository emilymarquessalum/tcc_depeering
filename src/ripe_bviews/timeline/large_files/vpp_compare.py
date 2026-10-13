from collections import defaultdict
import math
import os
from pathlib import Path
import sys
from typing import Dict, List, Optional, Set, Tuple, Union

from matplotlib import pyplot as plt

from src.ripe_bviews.timeline.bview_load import get_all_rrcs

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from definitions import ROOT_DIR
from src.google.vpps.google_vpps_list import get_google_vpp_asns
from src.ripe_bviews.timeline.large_files.bview_sqlite_parser import (
    get_all_dates_available_for_asn_data,
    get_hegemony_scores,
    get_interval_dates_for_asn_data,
)
from src.ripe_bviews.timeline.large_files.global_hegemony import (
    _get_clean_vpp_set,
    _parse_ip_versions,
    get_global_hegemony_scores,
)
from src.utils.graphs import DEFAULT_FIGSIZE, format_labels_if_they_are_dates, save_plot


# ==============================================================================
# Helper Data Parsing & Calculation Functions
# ==============================================================================

def _get_common_dates_and_scores(
    asn1: int,
    asn2: int,
    ip_ver: str,
    alpha: float,
    rrc_used: Optional[str] = None,
    rrc_list: Optional[List[str]] = None,
    month_interval: int = 6,
    start_date: Optional[str] = None,
    use_strict_viewpoint_filtering: bool = False,
) -> Tuple[Dict[str, Dict[str, float]], Dict[str, Dict[str, float]], List[str], str]:
    """Helper to fetch overlapping dates and hegemony score dictionaries for two ASes."""
    if rrc_list:
        dates1 = set()
        dates2 = set()
        for rrc in rrc_list:
            dates1.update(get_all_dates_available_for_asn_data(asn1, rrc, ip_ver, start_date=start_date))
            dates2.update(get_all_dates_available_for_asn_data(asn2, rrc, ip_ver, start_date=start_date))
        common_dates = sorted(list(dates1.intersection(dates2)))
    elif rrc_used:
        dates1 = get_interval_dates_for_asn_data(asn1, rrc_used, ip_ver, month_interval, start_date)
        dates2 = get_interval_dates_for_asn_data(asn2, rrc_used, ip_ver, month_interval, start_date)
        common_dates = sorted(list(set(dates1).intersection(set(dates2))))
    else:
        raise ValueError("Must provide either 'rrc_used' or 'rrc_list'.")

    if not common_dates:
        return {}, {}, [], ""

    if rrc_list:
        scores_1, _, valid_1 = get_global_hegemony_scores(
            asn1, ip_ver, common_dates, alpha, rrc_list, use_strict_viewpoint_filtering
        )
        scores_2, _, valid_2 = get_global_hegemony_scores(
            asn2, ip_ver, common_dates, alpha, rrc_list, use_strict_viewpoint_filtering
        )
        scope_desc = f"Global ({len(rrc_list)} RRCs)"
    else:
        scores_1, _, valid_1 = get_hegemony_scores(
            asn1, rrc_used, ip_ver, common_dates, alpha, use_strict_viewpoint_filtering
        )
        scores_2, _, valid_2 = get_hegemony_scores(
            asn2, rrc_used, ip_ver, common_dates, alpha, use_strict_viewpoint_filtering
        )
        scope_desc = f"RRC {rrc_used.upper()}"

    valid_dates = sorted(list(set(valid_1).intersection(set(valid_2))))
    return scores_1, scores_2, valid_dates, scope_desc


def _filter_scores(
    scores: Dict[str, float],
    specific_as_list: Optional[List[int]] = None,
) -> Dict[str, float]:
    """Filters score dictionary to clean ASN string keys and optional specific transit AS list."""
    cleaned = {str(k).upper().replace("AS", "").strip(): v for k, v in scores.items()}
    if specific_as_list:
        target_set = {str(a).strip() for a in specific_as_list}
        return {k: v for k, v in cleaned.items() if k in target_set}
    return cleaned


# ==============================================================================
# Dedicated Mode Comparison Functions
# ==============================================================================

def compare_hegemony_general(
    asn1: int,
    asn2: int,
    alpha: float = 0.34,
    ip_version: Union[str, List[str]] = "v4",
    rrc_used: Optional[str] = None,
    rrc_list: Optional[List[str]] = None,
    specific_as_list: Optional[List[int]] = None,
    month_interval: int = 6,
    start_date: Optional[str] = None,
    use_strict_viewpoint_filtering: bool = False,
    text_scale: float = 1.0,
):
    """MODE 1: General Hegemony Comparison (Raw absolute score totals)."""
    ip_versions = _parse_ip_versions(ip_version)

    plt.rcParams.update({"font.size": 10 * text_scale, "axes.titlesize": 14 * text_scale})
    fig, ax = plt.subplots(figsize=DEFAULT_FIGSIZE)
    has_data = False

    for ip_ver in ip_versions:
        scores_1, scores_2, valid_dates, scope_desc = _get_common_dates_and_scores(
            asn1, asn2, ip_ver, alpha, rrc_used, rrc_list, month_interval, start_date, use_strict_viewpoint_filtering
        )
        if not valid_dates:
            continue

        val_1, val_2 = [], []
        for d in valid_dates:
            f1 = _filter_scores(scores_1.get(d, {}), specific_as_list)
            f2 = _filter_scores(scores_2.get(d, {}), specific_as_list)
            val_1.append(sum(f1.values()))
            val_2.append(sum(f2.values()))

        formatted_dates = format_labels_if_they_are_dates(valid_dates)
        linestyle = "-" if ip_ver == "v4" else "--"
        ip_label = f" ({ip_ver.upper()})" if len(ip_versions) > 1 else ""

        ax.plot(formatted_dates, val_1, marker="o" if ip_ver == "v4" else "^", linestyle=linestyle, linewidth=2.5, label=f"AS{asn1}{ip_label}")
        ax.plot(formatted_dates, val_2, marker="s" if ip_ver == "v4" else "D", linestyle=linestyle, linewidth=2.5, label=f"AS{asn2}{ip_label}")
        has_data = True

    if not has_data:
        print("[WARNING] General Mode: No comparative data plotted.")
        plt.close(fig)
        return

    filter_desc = f"\nFiltered Transits: {specific_as_list}" if specific_as_list else ""
    ax.set_ylabel("Hegemony Score", fontsize=12 * text_scale)
    ax.set_xlabel("Date", fontsize=12 * text_scale)
    ax.set_title(f"General Hegemony: AS{asn1} vs AS{asn2}\n[{scope_desc}] (α={alpha}){filter_desc}", fontsize=14 * text_scale)
    ax.tick_params(axis="x", rotation=45)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper right")
    plt.tight_layout()
    plt.show()

    rrc_tag = "global" if rrc_list else rrc_used
    save_plot(fig=fig, title=f"hegemony_compare_general_AS{asn1}_vs_AS{asn2}_{rrc_tag}.png")


def compare_hegemony_percentage(
    asn1: int,
    asn2: int,
    alpha: float = 0.34,
    ip_version: Union[str, List[str]] = "v4",
    rrc_used: Optional[str] = None,
    rrc_list: Optional[List[str]] = None,
    specific_as_list: Optional[List[int]] = None,
    top_percentage: Optional[float] = None,
    month_interval: int = 6,
    start_date: Optional[str] = None,
    use_strict_viewpoint_filtering: bool = False,
    text_scale: float = 1.0,
):
    """MODE 2: Percentage / Ratio Share Comparison (x% or Top X% Transits share)."""
    ip_versions = _parse_ip_versions(ip_version)

    plt.rcParams.update({"font.size": 10 * text_scale, "axes.titlesize": 14 * text_scale})
    fig, ax = plt.subplots(figsize=DEFAULT_FIGSIZE)
    has_data = False

    for ip_ver in ip_versions:
        scores_1, scores_2, valid_dates, scope_desc = _get_common_dates_and_scores(
            asn1, asn2, ip_ver, alpha, rrc_used, rrc_list, month_interval, start_date, use_strict_viewpoint_filtering
        )
        if not valid_dates:
            continue

        pct_1, pct_2 = [], []
        for d in valid_dates:
            f1 = _filter_scores(scores_1.get(d, {}), specific_as_list)
            f2 = _filter_scores(scores_2.get(d, {}), specific_as_list)

            tot_1 = sum(f1.values())
            tot_2 = sum(f2.values())

            if top_percentage is not None:
                sorted_1 = sorted(f1.items(), key=lambda x: x[1], reverse=True)
                sorted_2 = sorted(f2.items(), key=lambda x: x[1], reverse=True)
                k1 = max(1, math.ceil(len(sorted_1) * top_percentage / 100.0)) if sorted_1 else 0
                k2 = max(1, math.ceil(len(sorted_2) * top_percentage / 100.0)) if sorted_2 else 0
                sub_1 = sum(score for _, score in sorted_1[:k1])
                sub_2 = sum(score for _, score in sorted_2[:k2])
            else:
                sub_1 = tot_1
                sub_2 = tot_2

            pct_1.append((sub_1 / tot_1 * 100.0) if tot_1 > 0 else 0.0)
            pct_2.append((sub_2 / tot_2 * 100.0) if tot_2 > 0 else 0.0)

        formatted_dates = format_labels_if_they_are_dates(valid_dates)
        linestyle = "-" if ip_ver == "v4" else "--"
        ip_label = f" ({ip_ver.upper()})" if len(ip_versions) > 1 else ""

        ax.plot(formatted_dates, pct_1, marker="o" if ip_ver == "v4" else "^", linestyle=linestyle, linewidth=2.5, label=f"AS{asn1}{ip_label}")
        ax.plot(formatted_dates, pct_2, marker="s" if ip_ver == "v4" else "D", linestyle=linestyle, linewidth=2.5, label=f"AS{asn2}{ip_label}")
        has_data = True

    if not has_data:
        print("[WARNING] Percentage Mode: No comparative data plotted.")
        plt.close(fig)
        return

    filter_desc = f"\nFiltered Transits: {specific_as_list}" if specific_as_list else ""
    pct_title_suffix = f" (Top {top_percentage}%)" if top_percentage else ""
    ax.set_ylabel("Hegemony Share (%)", fontsize=12 * text_scale)
    ax.set_xlabel("Date", fontsize=12 * text_scale)
    ax.set_title(f"Hegemony Share (%) Comparison{pct_title_suffix}: AS{asn1} vs AS{asn2}\n[{scope_desc}] (α={alpha}){filter_desc}", fontsize=14 * text_scale)
    ax.tick_params(axis="x", rotation=45)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper right")
    plt.tight_layout()
    plt.show()

    rrc_tag = "global" if rrc_list else rrc_used
    save_plot(fig=fig, title=f"hegemony_compare_percentage_AS{asn1}_vs_AS{asn2}_{rrc_tag}.png")


def compare_hegemony_vpp_only(
    asn1: int,
    asn2: int,
    alpha: float = 0.34,
    ip_version: Union[str, List[str]] = "v4",
    rrc_used: Optional[str] = None,
    rrc_list: Optional[List[str]] = None,
    month_interval: int = 6,
    start_date: Optional[str] = None, 
    use_strict_viewpoint_filtering: bool = False,
    text_scale: float = 1.0,
):
    """MODE 3: VPP-Only Hegemony Comparison (Restricted strictly to Google VPP transits)."""
    ip_versions = _parse_ip_versions(ip_version)
    vpp_set = _get_clean_vpp_set()

    plt.rcParams.update({"font.size": 10 * text_scale, "axes.titlesize": 14 * text_scale})
    fig, ax = plt.subplots(figsize=DEFAULT_FIGSIZE)
    has_data = False

    for ip_ver in ip_versions:
        scores_1, scores_2, valid_dates, scope_desc = _get_common_dates_and_scores(
            asn1, asn2, ip_ver, alpha, rrc_used, rrc_list, month_interval, start_date, use_strict_viewpoint_filtering
        )
        if not valid_dates:
            continue

        val_1, val_2 = [], []
        for d in valid_dates:
            f1 = _filter_scores(scores_1.get(d, {}))
            f2 = _filter_scores(scores_2.get(d, {}))

            vpp_score_1 = sum(v for k, v in f1.items() if k in vpp_set)
            vpp_score_2 = sum(v for k, v in f2.items() if k in vpp_set)

            val_1.append(vpp_score_1)
            val_2.append(vpp_score_2)

        formatted_dates = format_labels_if_they_are_dates(valid_dates)
        linestyle = "-" if ip_ver == "v4" else "--"
        ip_label = f" ({ip_ver.upper()})" if len(ip_versions) > 1 else ""

        ax.plot(formatted_dates, val_1, marker="o" if ip_ver == "v4" else "^", linestyle=linestyle, linewidth=2.5, label=f"AS{asn1}{ip_label}")
        ax.plot(formatted_dates, val_2, marker="s" if ip_ver == "v4" else "D", linestyle=linestyle, linewidth=2.5, label=f"AS{asn2}{ip_label}")
        has_data = True

    if not has_data:
        print("[WARNING] VPP-Only Mode: No comparative data plotted.")
        plt.close(fig)
        return

    ax.set_ylabel("VPP Hegemony Score", fontsize=12 * text_scale)
    ax.set_xlabel("Date", fontsize=12 * text_scale)
    ax.set_title(f"VPP-Only Hegemony: AS{asn1} vs AS{asn2}\n[{scope_desc}] (α={alpha})", fontsize=14 * text_scale)
    ax.tick_params(axis="x", rotation=45)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper right")
    plt.tight_layout()
    plt.show()

    rrc_tag = "global" if rrc_list else rrc_used
    save_plot(fig=fig, title=f"hegemony_compare_vpp_only_AS{asn1}_vs_AS{asn2}_{rrc_tag}.png")


# ==============================================================================
# Execution Driver
# ==============================================================================

if __name__ == "__main__":
    asn1 = 15169
    asn2 = 396986
    alpha = 0.34
    ip_version = "both"
    rrc_used = "rrc03"
    rrc_list = [rrc["rrc"] for rrc in get_all_rrcs()]

    print("=================================================================")
    print(f"Running Hegemony Comparison Pipelines for AS{asn1} vs AS{asn2}")
    print("=================================================================")

    # 1. Run General Hegemony Comparison
    print("\n[1/3] Executing MODE 1: General Hegemony Comparison...")
    compare_hegemony_general(
        asn1=asn1,
        asn2=asn2,
        alpha=alpha,
        ip_version=ip_version,
        rrc_used=rrc_used,
        rrc_list=rrc_list,
    )

    # 2. Run Percentage / Ratio Comparison (Top 20%)
    print("\n[2/3] Executing MODE 2: Percentage Hegemony Share Comparison (Top 20%)...")
    compare_hegemony_percentage(
        asn1=asn1,
        asn2=asn2,
        alpha=alpha,
        ip_version=ip_version,
        rrc_used=rrc_used,
        rrc_list=rrc_list,
        top_percentage=20.0,
    )

    # 3. Run VPP-Only Hegemony Comparison
    print("\n[3/3] Executing MODE 3: VPP-Only Hegemony Comparison...")
    compare_hegemony_vpp_only(
        asn1=asn1,
        asn2=asn2,
        alpha=alpha,
        ip_version=ip_version,
        rrc_used=rrc_used,
        rrc_list=rrc_list,
    )

    print("\n[SUCCESS] All comparison modes executed successfully.")