from collections import defaultdict
import math
import os
from pathlib import Path
import sys
from typing import Dict, List, Optional, Set, Tuple, Union

from matplotlib import pyplot as plt


sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from definitions import ROOT_DIR
from src.ripe_bviews.timeline.bview_load import get_all_rrcs
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

from collections import defaultdict
import math
import os
from pathlib import Path
import sys
from typing import Dict, List, Optional, Set, Tuple, Union

from matplotlib import pyplot as plt

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


def compute_cosine_similarity_pct(
    scores_1: Dict[str, float],
    scores_2: Dict[str, float],
) -> float:
    """
    Computes Cosine Similarity between two ASN hegemony distribution vectors as a percentage (0% - 100%).
    
    Formula: (A · B) / (||A|| * ||B||) * 100
    """
    all_asns = set(scores_1.keys()).union(set(scores_2.keys()))
    if not all_asns:
        return 0.0

    dot_product = sum(scores_1.get(asn, 0.0) * scores_2.get(asn, 0.0) for asn in all_asns)
    magnitude_1 = math.sqrt(sum(v ** 2 for v in scores_1.values()))
    magnitude_2 = math.sqrt(sum(v ** 2 for v in scores_2.values()))

    if magnitude_1 == 0.0 or magnitude_2 == 0.0:
        return 0.0

    similarity = dot_product / (magnitude_1 * magnitude_2)
    return similarity * 100.0


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
    if rrc_list:
        dates1, dates2 = set(), set()
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


def _clean_scores(scores: Dict[str, float]) -> Dict[str, float]:
    return {str(k).upper().replace("AS", "").strip(): v for k, v in scores.items()}


# ==============================================================================
# Dedicated Similarity Comparison Functions
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
    """General Similarity: Computes Cosine Similarity % between full transit vectors over time."""
    ip_versions = _parse_ip_versions(ip_version)
    fig, ax = plt.subplots(figsize=DEFAULT_FIGSIZE)
    has_data = False

    for ip_ver in ip_versions:
        scores_1, scores_2, valid_dates, scope_desc = _get_common_dates_and_scores(
            asn1, asn2, ip_ver, alpha, rrc_used, rrc_list, month_interval, start_date, use_strict_viewpoint_filtering
        )
        if not valid_dates:
            continue

        similarity_pcts = []
        for d in valid_dates:
            f1 = _clean_scores(scores_1.get(d, {}))
            f2 = _clean_scores(scores_2.get(d, {}))
            
            if specific_as_list:
                targets = {str(a).strip() for a in specific_as_list}
                f1 = {k: v for k, v in f1.items() if k in targets}
                f2 = {k: v for k, v in f2.items() if k in targets}

            sim_pct = compute_cosine_similarity_pct(f1, f2)
            similarity_pcts.append(sim_pct)

        avg_sim = sum(similarity_pcts) / len(similarity_pcts) if similarity_pcts else 0.0
        print(f"[RESULT] General Hegemony Similarity for AS{asn1} vs AS{asn2} ({ip_ver.upper()}): {avg_sim:.2f}%")

        formatted_dates = format_labels_if_they_are_dates(valid_dates)
        linestyle = "-" if ip_ver == "v4" else "--"
        ip_label = f" ({ip_ver.upper()})" if len(ip_versions) > 1 else ""

        ax.plot(formatted_dates, similarity_pcts, marker="o" if ip_ver == "v4" else "^", linestyle=linestyle, linewidth=2.5, label=f"Similarity %{ip_label}")
        has_data = True

    if not has_data:
        return

    ax.set_ylabel("Hegemony Similarity (%)", fontsize=12 * text_scale)
    ax.set_xlabel("Date", fontsize=12 * text_scale)
    ax.set_ylim(-5, 105)
    ax.set_title(f"General Hegemony Similarity (%): AS{asn1} vs AS{asn2}\n[{scope_desc}] (α={alpha})", fontsize=14 * text_scale)
    ax.tick_params(axis="x", rotation=45)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper right")
    plt.tight_layout()
    plt.show()

    rrc_tag = "global" if rrc_list else rrc_used
    save_plot(fig=fig, title=f"hegemony_similarity_general_AS{asn1}_vs_AS{asn2}_{rrc_tag}.png")


def compare_hegemony_percentage(
    asn1: int,
    asn2: int,
    alpha: float = 0.34,
    ip_version: Union[str, List[str]] = "v4",
    rrc_used: Optional[str] = None,
    rrc_list: Optional[List[str]] = None,
    top_percentage: Optional[float] = 20.0,
    month_interval: int = 6,
    start_date: Optional[str] = None,
    use_strict_viewpoint_filtering: bool = False,
    text_scale: float = 1.0,
):
    """Percentage/Top X% Similarity: Cosine similarity restricted to top X% transit ASNs."""
    ip_versions = _parse_ip_versions(ip_version)
    fig, ax = plt.subplots(figsize=DEFAULT_FIGSIZE)
    has_data = False

    for ip_ver in ip_versions:
        scores_1, scores_2, valid_dates, scope_desc = _get_common_dates_and_scores(
            asn1, asn2, ip_ver, alpha, rrc_used, rrc_list, month_interval, start_date, use_strict_viewpoint_filtering
        )
        if not valid_dates:
            continue

        similarity_pcts = []
        for d in valid_dates:
            f1 = _clean_scores(scores_1.get(d, {}))
            f2 = _clean_scores(scores_2.get(d, {}))

            if top_percentage is not None:
                s1 = sorted(f1.items(), key=lambda x: x[1], reverse=True)
                s2 = sorted(f2.items(), key=lambda x: x[1], reverse=True)
                k1 = max(1, math.ceil(len(s1) * top_percentage / 100.0)) if s1 else 0
                k2 = max(1, math.ceil(len(s2) * top_percentage / 100.0)) if s2 else 0
                f1 = dict(s1[:k1])
                f2 = dict(s2[:k2])

            sim_pct = compute_cosine_similarity_pct(f1, f2)
            similarity_pcts.append(sim_pct)

        avg_sim = sum(similarity_pcts) / len(similarity_pcts) if similarity_pcts else 0.0
        print(f"[RESULT] Top {top_percentage}% Hegemony Similarity for AS{asn1} vs AS{asn2} ({ip_ver.upper()}): {avg_sim:.2f}%")

        formatted_dates = format_labels_if_they_are_dates(valid_dates)
        linestyle = "-" if ip_ver == "v4" else "--"
        ip_label = f" ({ip_ver.upper()})" if len(ip_versions) > 1 else ""

        ax.plot(formatted_dates, similarity_pcts, marker="o" if ip_ver == "v4" else "^", linestyle=linestyle, linewidth=2.5, label=f"Similarity %{ip_label}")
        has_data = True

    if not has_data:
        return

    ax.set_ylabel("Hegemony Similarity (%)", fontsize=12 * text_scale)
    ax.set_xlabel("Date", fontsize=12 * text_scale)
    ax.set_ylim(-5, 105)
    ax.set_title(f"Top {top_percentage}% Hegemony Similarity (%): AS{asn1} vs AS{asn2}\n[{scope_desc}] (α={alpha})", fontsize=14 * text_scale)
    ax.tick_params(axis="x", rotation=45)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper right")
    plt.tight_layout()
    plt.show()

    rrc_tag = "global" if rrc_list else rrc_used
    save_plot(fig=fig, title=f"hegemony_similarity_top{int(top_percentage)}pct_AS{asn1}_vs_AS{asn2}_{rrc_tag}.png")


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
    """VPP-Only Similarity: Cosine similarity restricted strictly to Google VPP transits."""
    ip_versions = _parse_ip_versions(ip_version)
    vpp_set = _get_clean_vpp_set()
    fig, ax = plt.subplots(figsize=DEFAULT_FIGSIZE)
    has_data = False

    for ip_ver in ip_versions:
        scores_1, scores_2, valid_dates, scope_desc = _get_common_dates_and_scores(
            asn1, asn2, ip_ver, alpha, rrc_used, rrc_list, month_interval, start_date, use_strict_viewpoint_filtering
        )
        if not valid_dates:
            continue

        similarity_pcts = []
        for d in valid_dates:
            f1 = {k: v for k, v in _clean_scores(scores_1.get(d, {})).items() if k in vpp_set}
            f2 = {k: v for k, v in _clean_scores(scores_2.get(d, {})).items() if k in vpp_set}

            sim_pct = compute_cosine_similarity_pct(f1, f2)
            similarity_pcts.append(sim_pct)

        avg_sim = sum(similarity_pcts) / len(similarity_pcts) if similarity_pcts else 0.0
        print(f"[RESULT] VPP-Only Hegemony Similarity for AS{asn1} vs AS{asn2} ({ip_ver.upper()}): {avg_sim:.2f}%")

        formatted_dates = format_labels_if_they_are_dates(valid_dates)
        linestyle = "-" if ip_ver == "v4" else "--"
        ip_label = f" ({ip_ver.upper()})" if len(ip_versions) > 1 else ""

        ax.plot(formatted_dates, similarity_pcts, marker="o" if ip_ver == "v4" else "^", linestyle=linestyle, linewidth=2.5, label=f"VPP Similarity %{ip_label}")
        has_data = True

    if not has_data:
        return

    ax.set_ylabel("VPP Hegemony Similarity (%)", fontsize=12 * text_scale)
    ax.set_xlabel("Date", fontsize=12 * text_scale)
    ax.set_ylim(-5, 105)
    ax.set_title(f"VPP-Only Hegemony Similarity (%): AS{asn1} vs AS{asn2}\n[{scope_desc}] (α={alpha})", fontsize=14 * text_scale)
    ax.tick_params(axis="x", rotation=45)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper right")
    plt.tight_layout()
    plt.show()

    rrc_tag = "global" if rrc_list else rrc_used
    save_plot(fig=fig, title=f"hegemony_similarity_vpp_only_AS{asn1}_vs_AS{asn2}_{rrc_tag}.png")
    
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