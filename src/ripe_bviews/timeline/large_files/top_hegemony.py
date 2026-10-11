import math
from pathlib import Path
import sys
from typing import List, Optional

from matplotlib import pyplot as plt
from pyparsing.common import Union

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from src.ripe_bviews.timeline.bview_load import get_all_rrcs
from src.ripe_bviews.timeline.large_files.bview_sqlite_parser import (
    get_all_dates_available_for_asn_data,
    get_hegemony_scores,
    get_interval_dates_for_asn_data,
)
from src.ripe_bviews.timeline.large_files.global_hegemony import (
    _parse_ip_versions,
    get_global_hegemony_scores,
)
from src.utils.graphs import DEFAULT_FIGSIZE, save_plot


def analyze_top10_percent_vs_others_hegemony_over_time(
    asn: int,
    alpha: float,
    ip_version: Union[str, List[str]] = "v4",
    date_list: Optional[list] = None,
    percentage: float = 20.0,
    rrc_used: Optional[str] = None,
    rrc_list: Optional[list[str]] = None,
    use_strict_viewpoint_filtering: bool = False,
    use_free_viewpoint_filtering: bool = False,
    use_best_next_days: int = 0,
    text_scale: float = 1.0,
    show_both_ip_versions: bool = False,
    start_date=None,
    month_interval: int = 3,
):
    """
    Computes and plots the aggregated Hegemony percentage share of the Top X% Transit ASNs
    versus all remaining ('Others') Transit ASNs over time.
    """
    ip_versions = _parse_ip_versions(ip_version, show_both_ip_versions)

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
        # Resolve date list per IP version
        if date_list is None:
            if rrc_list:
                all_available_dates = set()
                for rrc in rrc_list:
                    all_available_dates.update(
                        get_all_dates_available_for_asn_data(asn, rrc, ip_ver, start_date=start_date)
                    )
                current_date_list = sorted(list(all_available_dates))
            elif rrc_used:
                current_date_list = get_interval_dates_for_asn_data(
                    asn, rrc_used, ip_ver, month_interval=month_interval, start_date=start_date
                )
            else:
                raise ValueError("Must provide either 'rrc_used' or 'rrc_list'.")
        else:
            current_date_list = date_list

        if not current_date_list:
            print(f"[WARNING] No dates available for ASN {asn} ({ip_ver.upper()}).")
            continue

        # Fetch scores depending on mode
        if rrc_list:
            print(
                f"[ANALYSIS] Computing Global Top {percentage}% vs Others ({ip_ver.upper()}) across {len(rrc_list)} RRCs..."
            )
            hegemony_scores_dict, _, valid_date_list = get_global_hegemony_scores(
                asn=asn,
                ip_version=ip_ver,
                date_list=current_date_list,
                alpha=alpha,
                rrc_list=rrc_list,
                use_strict_viewpoint_filtering=use_strict_viewpoint_filtering,
                use_free_viewpoint_filtering=use_free_viewpoint_filtering,
            )
            mode_label = f"Global ({len(rrc_list)} RRCs)"
            mode_file_suffix = f"global_{asn}"
        elif rrc_used:
            print(f"[ANALYSIS] Computing Top {percentage}% vs Others ({ip_ver.upper()}) for RRC {rrc_used}...")
            hegemony_scores_dict, _, valid_date_list = get_hegemony_scores(
                asn=asn,
                rrc_used=rrc_used,
                ip_version=ip_ver,
                date_list=current_date_list,
                alpha=alpha,
                use_strict_viewpoint_filtering=use_strict_viewpoint_filtering,
                use_free_viewpoint_filtering=use_free_viewpoint_filtering,
                use_best_next_days=use_best_next_days,
            )
            mode_label = f"RRC {rrc_used}"
            mode_file_suffix = f"{asn}_{rrc_used}"

        if not valid_date_list:
            print(f"[WARNING] No valid snapshots available to process for IP version {ip_ver.upper()}.")
            continue

        top_percent_percentages = []
        others_percentages = []
        top_counts = []

        for date in valid_date_list:
            scores = hegemony_scores_dict.get(date, {})
            total_hegemony = sum(scores.values())

            if total_hegemony <= 0:
                top_percent_percentages.append(0.0)
                others_percentages.append(0.0)
                continue

            sorted_transits = sorted(scores.items(), key=lambda item: item[1], reverse=True)
            total_asns = len(sorted_transits)

            top_count = max(1, math.ceil(total_asns * percentage / 100.0))
            top_counts.append(top_count)

            top_score = sum(score for _, score in sorted_transits[:top_count])
            others_score = sum(score for _, score in sorted_transits[top_count:])

            top_pct = (top_score / total_hegemony) * 100.0
            others_pct = (others_score / total_hegemony) * 100.0

            top_percent_percentages.append(top_pct)
            others_percentages.append(others_pct)

        avg_top_asns = sum(top_counts) / len(top_counts) if top_counts else 0

        linestyle = "-" if ip_ver == "v4" else "--"
        label_suffix = f" ({ip_ver.upper()})" if len(ip_versions) > 1 else ""

        ax.plot(
            valid_date_list,
            top_percent_percentages,
            marker="o" if ip_ver == "v4" else "^",
            linewidth=2.5,
            color="tab:blue",
            linestyle=linestyle,
            label=f"Top {percentage}% Transits (~{avg_top_asns:.1f} ASNs){label_suffix}",
        )

        ax.plot(
            valid_date_list,
            others_percentages,
            marker="s" if ip_ver == "v4" else "D",
            linewidth=2.5,
            color="tab:orange",
            linestyle=linestyle,
            label=f"Others (Remaining Transits){label_suffix}",
        )
        has_data = True

    if not has_data:
        print("[WARNING] No data plotted.")
        plt.close(fig)
        return

    ax.set_xlabel("Date", fontsize=12 * text_scale)
    ax.set_ylabel("Hegemony Share (%)", fontsize=12 * text_scale)

    ip_desc = "IPv4 & IPv6" if len(ip_versions) > 1 else ip_versions[0].upper()
    ax.set_title(
        f"Top {percentage}% vs. Others Hegemony Share Over Time [{mode_label}]\n"
        f"(Target ASN: {asn}, IP: {ip_desc}, α={alpha})",
        fontsize=14 * text_scale,
    )
    ax.tick_params(axis="both", labelsize=10 * text_scale)
    ax.tick_params(axis="x", rotation=45)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.set_ylim(-5, 105)
    ax.legend(
        bbox_to_anchor=(1.02, 1),
        loc="upper left",
        title="Groups",
        fontsize=10 * text_scale,
        title_fontsize=11 * text_scale,
    )

    plt.tight_layout()
    plt.show()

    save_suffix = "both" if len(ip_versions) > 1 else ip_versions[0]
    save_plot(fig=fig, title=f"top{int(percentage)}pct_vs_others_hegemony_{mode_file_suffix}_{save_suffix}.png")


if __name__ == "__main__":
    asn = 15169
    alpha = 0.34
    ip_version = "both"

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