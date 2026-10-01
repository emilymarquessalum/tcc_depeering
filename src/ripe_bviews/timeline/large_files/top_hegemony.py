import math
from pathlib import Path
import sys

from matplotlib import pyplot as plt

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

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
    rrc_used: str = None,
    rrc_list: list[str] = None,
    use_strict_viewpoint_filtering: bool = False,
    use_free_viewpoint_filtering: bool = False,
    use_best_next_days: int = 0,
):
    """
    Computes and plots the aggregated Hegemony percentage share of the Top 10% Transit ASNs
    versus all remaining ('Others') Transit ASNs over time.
    """
    # 1. Fetch scores depending on whether it's a single RRC or Global analysis
    if rrc_list:
        print(
            f"[ANALYSIS] Computing Global Top 10% vs Others across {len(rrc_list)} RRCs..."
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
        print(f"[ANALYSIS] Computing Top 10% vs Others for RRC {rrc_used}...")
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

    top10_percent_percentages = []
    others_percentages = []

    percentage = 20

    # 2. Process each date snapshot
    for date in valid_date_list:
        scores = hegemony_scores_dict.get(date, {})
        total_hegemony = sum(scores.values())

        if total_hegemony <= 0:
            top10_percent_percentages.append(0.0)
            others_percentages.append(0.0)
            continue

        # Sort ASNs by score descending
        sorted_transits = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        total_asns = len(sorted_transits)

        # Calculate top 10% cut-off index (at least 1 ASN)
        top10_count = max(1, math.ceil(total_asns * percentage / 100))

        # Sum top 10% scores vs remaining scores
        top10_score = sum(score for _, score in sorted_transits[:top10_count])
        others_score = sum(score for _, score in sorted_transits[top10_count:])

        # Convert to percentage of total Hegemony
        top10_pct = (top10_score / total_hegemony) * 100.0
        others_pct = (others_score / total_hegemony) * 100.0

        top10_percent_percentages.append(top10_pct)
        others_percentages.append(others_pct)

    # 3. Visualization
    fig, ax = plt.subplots(figsize=DEFAULT_FIGSIZE)

    ax.plot(
        valid_date_list,
        top10_percent_percentages,
        marker="o",
        linewidth=2.5,
        color="tab:blue",
        label=f"Top {percentage}% Transits (Aggregated)",
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
    ax.set_ylim(-5, 105)  # Percentage boundary
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", title="Groups")

    plt.tight_layout()
    plt.show()

    save_plot(fig=fig, title=f"top{percentage}pct_vs_others_hegemony_{file_suffix}.png")


if __name__ == "__main__":
    asn = 15169
    alpha = 0.34
    ip_version = "v4"

    all_rrcs = [
        "rrc03", "rrc04", "rrc05", "rrc06", "rrc07", "rrc08", "rrc09", "rrc10",
        "rrc11", "rrc12", "rrc13", "rrc14", "rrc15", "rrc16", "rrc17", "rrc18",
        "rrc19", "rrc20", "rrc21", "rrc22"
    ]

    # --- 1. RUN SINGLE RRC ANALYSIS ---
    rrc_target = "rrc03"
    dates_rrc = get_interval_dates_for_asn_data(
        asn, rrc_target, ip_version, month_interval=6
    )

    analyze_top10_percent_vs_others_hegemony_over_time(
        asn=asn,
        alpha=alpha,
        ip_version=ip_version,
        date_list=dates_rrc,
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
        rrc_list=all_rrcs,
        use_strict_viewpoint_filtering=True,
    )