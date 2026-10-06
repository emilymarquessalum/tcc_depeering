import math
from pathlib import Path
import sys

from matplotlib import pyplot as plt

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from src.ripe_bviews.timeline.bview_load import get_all_rrcs
from src.ripe_bviews.timeline.large_files.bview_sqlite_parser import (
    get_all_dates_available_for_asn_data,
    get_hegemony_scores,
    get_interval_dates_for_asn_data,
)
from src.ripe_bviews.timeline.large_files.global_hegemony import (
    get_global_hegemony_scores,
)
from src.utils.graphs import DEFAULT_FIGSIZE, save_plot


def analyze_top10_percent_vs_others_hegemony_over_time(
    asn: int,
    alpha: float,
    ip_version: str,
    date_list: list,
    percentage: float = 20.0,
    rrc_used: str = None,
    rrc_list: list[str] = None,
    use_strict_viewpoint_filtering: bool = False,
    use_free_viewpoint_filtering: bool = False,
    use_best_next_days: int = 0,
):
    """
    Computes and plots the aggregated Hegemony percentage share of the Top X% Transit ASNs
    versus all remaining ('Others') Transit ASNs over time.
    """
    # 1. Fetch scores depending on whether it's a single RRC or Global analysis
    if rrc_list:
        print(
            f"[ANALYSIS] Computing Global Top {percentage}% vs Others across {len(rrc_list)} RRCs..."
        )
        hegemony_scores_dict, _, valid_date_list = get_global_hegemony_scores(
            asn=asn,
            ip_version=ip_version,
            date_list=date_list,
            alpha=alpha,
            rrc_list=rrc_list,
            use_strict_viewpoint_filtering=use_strict_viewpoint_filtering,
            use_free_viewpoint_filtering=use_free_viewpoint_filtering,
        )
        mode_label = f"Global ({len(rrc_list)} RRCs)"
        file_suffix = f"global_{asn}_{ip_version}"
    elif rrc_used:
        print(f"[ANALYSIS] Computing Top {percentage}% vs Others for RRC {rrc_used}...")
        hegemony_scores_dict, _, valid_date_list = get_hegemony_scores(
            asn=asn,
            rrc_used=rrc_used,
            ip_version=ip_version,
            date_list=date_list,
            alpha=alpha,
            use_strict_viewpoint_filtering=use_strict_viewpoint_filtering,
            use_free_viewpoint_filtering=use_free_viewpoint_filtering,
            use_best_next_days=use_best_next_days,
        )
        mode_label = f"RRC {rrc_used}"
        file_suffix = f"{asn}_{rrc_used}_{ip_version}"
    else:
        raise ValueError("Must provide either 'rrc_used' or 'rrc_list'.")

    if not valid_date_list:
        print("[WARNING] No valid snapshots available to process.")
        return

    top_percent_percentages = []
    others_percentages = []
    top_counts = []

    # 2. Process each date snapshot
    for date in valid_date_list:
        scores = hegemony_scores_dict.get(date, {})
        total_hegemony = sum(scores.values())

        if total_hegemony <= 0:
            top_percent_percentages.append(0.0)
            others_percentages.append(0.0)
            continue

        # Sort ASNs by score descending
        sorted_transits = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        total_asns = len(sorted_transits)

        # Calculate top X% cut-off index (at least 1 ASN)
        top_count = max(1, math.ceil(total_asns * percentage / 100))
        top_counts.append(top_count)

        # Sum top X% scores vs remaining scores
        top_score = sum(score for _, score in sorted_transits[:top_count])
        others_score = sum(score for _, score in sorted_transits[top_count:])

        # Convert to percentage of total Hegemony
        top_pct = (top_score / total_hegemony) * 100.0
        others_pct = (others_score / total_hegemony) * 100.0

        top_percent_percentages.append(top_pct)
        others_percentages.append(others_pct)

    avg_top_asns = sum(top_counts) / len(top_counts) if top_counts else 0

    # 3. Visualization
    fig, ax = plt.subplots(figsize=DEFAULT_FIGSIZE)

    ax.plot(
        valid_date_list,
        top_percent_percentages,
        marker="o",
        linewidth=2.5,
        color="tab:blue",
        label=f"Top {percentage}% Transits (~{avg_top_asns:.1f} ASNs/snapshot)",
    )

    ax.plot(
        valid_date_list,
        others_percentages,
        marker="s",
        linewidth=2.5,
        color="tab:orange",
        linestyle="--",
        label="Others (Remaining Transits)",
    )

    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("Hegemony Share (%)", fontsize=12)
    ax.set_title(
        f"Top {percentage}% vs. Others Hegemony Share Over Time [{mode_label}]\n"
        f"(Target ASN: {asn}, IP: {ip_version.upper()}, α={alpha})",
        fontsize=14,
    )
    ax.tick_params(axis="x", rotation=45)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.set_ylim(-5, 105)
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", title="Groups")

    plt.tight_layout()
    plt.show()

    save_plot(fig=fig, title=f"top{int(percentage)}pct_vs_others_hegemony_{file_suffix}.png")


if __name__ == "__main__":
    asn = 15169
    alpha = 0.34
    ip_version = "v4"

    # Ask for user input once at entry point
    user_input = input("Enter the percentage of top ASNs to consider (default 20): ").strip()
    percentage = float(user_input) if user_input else 20.0

    all_rrcs = [r["rrc"] for r in get_all_rrcs()]

    # --- 1. RUN SINGLE RRC ANALYSIS ---
    rrc_target = "rrc03"
    dates_rrc = get_interval_dates_for_asn_data(
        asn, rrc_target, ip_version, month_interval=3
    )

    analyze_top10_percent_vs_others_hegemony_over_time(
        asn=asn,
        alpha=alpha,
        ip_version=ip_version,
        date_list=dates_rrc,
        percentage=percentage,
        rrc_used=rrc_target,
        use_strict_viewpoint_filtering=True,
    )

    # --- 2. RUN GLOBAL ANALYSIS (ALL RRCs COMBINED) ---
    all_available_dates = set()
    for rrc in all_rrcs:
        all_available_dates.update(
            get_all_dates_available_for_asn_data(asn, rrc, ip_version)
        )

    sorted_dates = sorted(list(all_available_dates))

    analyze_top10_percent_vs_others_hegemony_over_time(
        asn=asn,
        alpha=alpha,
        ip_version=ip_version,
        date_list=sorted_dates,
        percentage=percentage,
        rrc_list=all_rrcs,
        use_strict_viewpoint_filtering=True,
    )