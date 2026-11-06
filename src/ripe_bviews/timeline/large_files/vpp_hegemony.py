"""Plot VPP vs. Non-VPP hegemony share over time for RIPE RIS RRCs."""

from pathlib import Path
import sys
from typing import Dict, List, Optional, Sequence, Set, Tuple, Union

from matplotlib import pyplot as plt

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from src.google.vpps.google_vpps_list import get_google_vpp_asn_map, get_google_vpp_asns
from src.ripe_bviews.timeline.bview_load import get_all_rrcs
from src.ripe_bviews.timeline.large_files.bview_sqlite_parser import (
    get_hegemony_scores,
    get_interval_dates_for_asn_data,
)
from src.ripe_bviews.timeline.large_files.over_time_global import _parse_ip_versions
from src.utils.graphs import DEFAULT_FIGSIZE, format_labels_if_they_are_dates, save_plot


def _get_clean_vpp_set() -> Set[str]:
    """Return normalized VPP ASN strings."""
    return set(get_google_vpp_asn_map().keys())


def compare_vpp_and_non_vpp_hegemony_over_time(
    asn: int,
    rrc_used: str,
    alpha: float = 0.34,
    ip_version: Union[str, Sequence[str]] = "v4",
    date_list: Optional[List[str]] = None,
    use_strict_viewpoint_filtering: bool = True,
    use_best_next_days: int = 0,
    show_as_percentage: bool = False,
    top_n: Optional[int] = 5,
    month_interval: int = 6,
    start_date: Optional[str] = None,
    text_scale: float = 1.0,
    show: bool = False,
) -> List[plt.Figure]:
    """Save plots of VPP vs Non-VPP hegemony over time for a single RRC."""
    if top_n is not None and (not isinstance(top_n, int) or top_n <= 0):
        raise ValueError("top_n must be a positive integer or None")

    clean_vpp_set = _get_clean_vpp_set()
    figures: List[plt.Figure] = []

    plt.rcParams.update({
        "font.size": 10 * text_scale,
        "axes.titlesize": 14 * text_scale,
        "axes.labelsize": 12 * text_scale,
        "xtick.labelsize": 10 * text_scale,
        "ytick.labelsize": 10 * text_scale,
        "legend.fontsize": 10 * text_scale,
        "figure.titlesize": 16 * text_scale,
    })

    for ip_ver in _parse_ip_versions(ip_version):
        dates = date_list
        if dates is None:
            dates = get_interval_dates_for_asn_data(
                asn,
                rrc_used,
                ip_ver,
                month_interval=month_interval,
                start_date=start_date,
            )

        if not dates:
            print(f"[WARNING] No snapshots available for RRC {rrc_used} ({ip_ver.upper()}).")
            continue

        hegemony_scores_dict, _, valid_dates = get_hegemony_scores(
            asn,
            rrc_used,
            ip_ver,
            dates,
            alpha,
            use_strict_viewpoint_filtering=use_strict_viewpoint_filtering,
            use_best_next_days=use_best_next_days,
        )

        if not valid_dates:
            print(f"[WARNING] No valid snapshots available for RRC {rrc_used} ({ip_ver.upper()}).")
            continue

        hegemony_over_time_vpp_or_not_vpp: List[Tuple[float, float]] = []

        for date in valid_dates:
            date_scores = hegemony_scores_dict.get(date, {})
            total_hegemony = sum(date_scores.values())

            if total_hegemony <= 0.0:
                hegemony_over_time_vpp_or_not_vpp.append((0.0, 0.0))
                continue

            cleaned_date_scores = {
                str(raw_asn).upper().replace("AS", "").strip(): score
                for raw_asn, score in date_scores.items()
            }

            if top_n is not None:
                sorted_items = sorted(cleaned_date_scores.items(), key=lambda x: x[1], reverse=True)
                target_items = sorted_items[:top_n]
            else:
                target_items = list(cleaned_date_scores.items())

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

        fig, ax = plt.subplots(figsize=DEFAULT_FIGSIZE)
        formatted_dates = format_labels_if_they_are_dates(valid_dates)
        scope_str = f" (Top {top_n} ASes)" if top_n is not None else ""

        ax.plot(
            formatted_dates,
            [h[0] for h in hegemony_over_time_vpp_or_not_vpp],
            marker="o",
            linewidth=2.5,
            color="tab:blue",
            label=f"VPP Hegemony{scope_str}",
        )

        ax.plot(
            formatted_dates,
            [h[1] for h in hegemony_over_time_vpp_or_not_vpp],
            marker="s",
            linewidth=2.5,
            color="tab:orange",
            label=f"Non-VPP Hegemony{scope_str}",
        )

        ax.set_xlabel("Date", fontsize=12 * text_scale)
        ax.set_ylabel(
            "Hegemony Percentage (%)" if show_as_percentage else "Hegemony Score",
            fontsize=12 * text_scale,
        )
        ax.tick_params(axis="both", labelsize=10 * text_scale)
        ax.tick_params(axis="x", rotation=45)
        ax.grid(True, linestyle="--", alpha=0.5)
        ax.legend(
            bbox_to_anchor=(0.5, 1.05),
            loc="lower center",
            ncol=2,
            title=f"Is-VPP ({rrc_used.upper()})",
        )

        fig.tight_layout()
        file_tag = f"top{top_n}" if top_n is not None else "all"
        save_plot(
            fig=fig,
            title=f"hegemony_over_time_by_vpp_feature_{asn}_{rrc_used}_{ip_ver}_{file_tag}.png",
        )

        if show:
            plt.show()
        else:
            plt.close(fig)
        figures.append(fig)

    return figures


def vpp_hegemony(
    asn: int,
    alpha: float = 0.34,
    rrc_used: Optional[str] = None,
    **kwargs,
) -> Dict[str, List[plt.Figure]]:
    """Plot VPP vs Non-VPP hegemony for one RRC, or for every configured RRC when omitted."""
    rrcs = [rrc_used] if rrc_used is not None else [item["rrc"] for item in get_all_rrcs()]
    results: Dict[str, List[plt.Figure]] = {}
    for rrc in rrcs:
        results[rrc] = compare_vpp_and_non_vpp_hegemony_over_time(
            asn,
            rrc_used=rrc,
            alpha=alpha,
            **kwargs,
        )
    return results


if __name__ == "__main__":
    target_asn = int(input("Enter target ASN (default 15169): ") or "15169")
    top_n_input = input("Enter number of top ASes to include (default 5, or 'all'): ").strip().lower()

    if top_n_input in ("", "5"):
        top_n = 5
    elif top_n_input == "all":
        top_n = None
    else:
        top_n = int(top_n_input)

    vpp_hegemony(
        target_asn,
        top_n=top_n,
        ip_version="both",
        show_as_percentage=True,
    )