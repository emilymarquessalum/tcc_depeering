"""Plot the highest-hegemony transit ASes over time for RIPE RIS RRCs."""

from pathlib import Path
import sys
from typing import Dict, List, Optional, Sequence, Tuple, Union

from matplotlib import pyplot as plt

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from src.ripe_bviews.timeline.bview_load import get_all_rrcs
from src.ripe_bviews.timeline.large_files.bview_sqlite_parser import (
    get_hegemony_scores,
    get_interval_dates_for_asn_data,
    get_top_five_asns_over_time,
)
from src.utils.graphs import DEFAULT_FIGSIZE, save_plot


def _parse_ip_versions(
    ip_version: Union[str, Sequence[str]],
) -> List[str]:
    """Normalize an IP-version argument to one or both supported values."""
    values = [ip_version] if isinstance(ip_version, str) else list(ip_version)
    versions: List[str] = []
    for value in values:
        normalized = str(value).lower().replace("ip", "").strip()
        if normalized in {"both", "v4_v6", "v4v6"}:
            return ["v4", "v6"]
        if normalized in {"v4", "v6"} and normalized not in versions:
            versions.append(normalized)
    return versions or ["v4"]


def plot_top_asns_over_time(
    asn: int,
    rrc_used: str,
    alpha: float = 0.34,
    top_n: int = 5,
    ip_version: Union[str, Sequence[str]] = "v4",
    date_list: Optional[List[str]] = None,
    use_strict_viewpoint_filtering: bool = True,
    use_free_viewpoint_filtering: bool = False,
    use_best_next_days: int = 0,
    show_as_percentage: bool = False,
    month_interval: int = 6,
    start_date: Optional[str] = None,
    text_scale: float = 1.0,
    show: bool = False,
) -> List[plt.Figure]:
    """Save plots of the top ``top_n`` transit ASes for one RRC.

    An ASN is plotted if it appears in the top ``top_n`` on at least one
    snapshot. Its score is zero on snapshots where it is not present.
    """
    if not isinstance(top_n, int) or top_n <= 0:
        raise ValueError("top_n must be a positive integer")
    if use_best_next_days < 0:
        raise ValueError("use_best_next_days must not be negative")

    figures: List[plt.Figure] = []
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

        scores, viewpoint_counts, valid_dates = get_hegemony_scores(
            asn,
            rrc_used,
            ip_ver,
            dates,
            alpha,
            use_strict_viewpoint_filtering,
            use_free_viewpoint_filtering=use_free_viewpoint_filtering,
            use_best_next_days=use_best_next_days,
        )
        if not valid_dates:
            print(f"[WARNING] No valid snapshots available for RRC {rrc_used} ({ip_ver.upper()}).")
            continue

        top_scores, top_asns = get_top_five_asns_over_time(
            scores,
            valid_dates,
            top_n=top_n,
        )
        if not top_asns:
            print(f"[WARNING] No transit ASes available for RRC {rrc_used} ({ip_ver.upper()}).")
            continue

        totals = [sum(scores[date].values()) for date in valid_dates]
        fig, ax = plt.subplots(figsize=DEFAULT_FIGSIZE)
        cmap = plt.get_cmap("tab20")
        for index, target_asn in enumerate(top_asns):
            values = [top_scores[date_index][index] for date_index in range(len(valid_dates))]
            if show_as_percentage:
                values = [
                    value / total * 100.0 if total > 0 else 0.0
                    for value, total in zip(values, totals)
                ]
            ax.plot(
                valid_dates,
                values,
                marker="o",
                linewidth=2.0,
                color=cmap(index % 20),
                label=f"AS{target_asn}",
            )

        ax.set_xlabel("Date", fontsize=12 * text_scale)
        ax.set_ylabel(
            "Hegemony (%)" if show_as_percentage else "Hegemony Score",
            fontsize=12 * text_scale,
        )
        ax.set_title(
            f"Top {top_n} ASes Over Time\n"
            f"(Target ASN: {asn}, RRC: {rrc_used.upper()}, IP: {ip_ver.upper()}, α={alpha})",
            fontsize=14 * text_scale,
        )
        ax.tick_params(axis="both", labelsize=10 * text_scale)
        ax.tick_params(axis="x", rotation=45)
        ax.grid(True, linestyle="--", alpha=0.5)
        ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", title="Transit AS")

        fig.tight_layout()
        save_plot(
            fig=fig,
            title=f"top{top_n}_asns_over_time_{asn}_{rrc_used}_{ip_ver}.png",
        )
        if show:
            plt.show()
        else:
            plt.close(fig)
        figures.append(fig)

    return figures


def over_time(
    asn: int,
    alpha: float = 0.34,
    rrc_used: Optional[str] = None,
    **kwargs,
) -> Dict[str, List[plt.Figure]]:
    """Plot top ASes for one RRC, or for every configured RRC when omitted."""
    rrcs = [rrc_used] if rrc_used is not None else [item["rrc"] for item in get_all_rrcs()]
    results: Dict[str, List[plt.Figure]] = {}
    for rrc in rrcs:
        results[rrc] = plot_top_asns_over_time(asn, rrc, alpha=alpha, **kwargs)
    return results


if __name__ == "__main__":
    target_asn = int(input("Enter target ASN (default 15169): ") or "15169")
    top_n = int(input("Enter number of top ASes (default 5): ") or "5")
    over_time(
        target_asn,
        top_n=top_n,
        ip_version="both",
        show_as_percentage=True,
    )