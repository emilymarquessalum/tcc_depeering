import csv
import json
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.google.vpps.google_vpps_list import get_google_vpp_asn_map
from src.services.caida_customers import ASRankCustomerAnalyzer
from src.utils.graphs import (
    plot_list_as_line_plot,
    plot_lists_as_plot_list_with_multiple_lines,
    plot_list_as_bar_plot
)


def _extract_vpp_name(vpp_entry, fallback_asn: int) -> str:
    """
    Extracts a clean ISP/VPP name from get_google_vpp_asn_map() entries,
    handling both list-of-dicts and single-dict structures.
    """
    if isinstance(vpp_entry, list) and vpp_entry:
        raw_name = vpp_entry[0].get("isp_name", "")
    elif isinstance(vpp_entry, dict):
        raw_name = vpp_entry.get("isp_name", "")
    elif isinstance(vpp_entry, str):
        raw_name = vpp_entry
    else:
        raw_name = ""

    clean_name = raw_name.split("\n")[0].strip()
    return clean_name if clean_name else f"VPP AS{fallback_asn}"


def load_vpp_map() -> dict[str, str]:
    """
    Loads VPP ASNs from get_google_vpp_asn_map() and returns {asn_str: vpp_name}.
    """
    raw_map = get_google_vpp_asn_map()
    vpp_map: dict[str, str] = {}

    for raw_asn, entry in raw_map.items():
        try:
            asn_int = int(str(raw_asn).upper().replace("AS", "").strip())
            vpp_map[str(asn_int)] = _extract_vpp_name(entry, asn_int)
        except (ValueError, TypeError):
            continue

    return vpp_map


def analyze_vpp_customer_cones_over_dates(
    dates: list[str],
    force_refresh: bool = False,
    asn_map: Optional[dict[str, str]] = None,
) -> dict[str, dict]:
    """
    Evaluates the customer cone of every VPP across a list of snapshot dates.
    """
    vpp_map = asn_map if asn_map is not None else load_vpp_map()
    vpp_asns = list(vpp_map.keys())

    if not vpp_asns:
        raise ValueError("No valid VPP ASNs found from get_google_vpp_asn_map().")

    print(f"Number of VPP ASNs to analyze: {len(vpp_asns)}")
    vpp_timeline: dict[str, dict] = {
        asn: {
            "asn": asn,
            "vpp_name": vpp_name,
            "snapshots": {},
        }
        for asn, vpp_name in vpp_map.items()
    }

    for target_date in dates:
        analyzer = ASRankCustomerAnalyzer(
            snapshot_date=target_date,
            force_refresh=force_refresh,
        )
        cones_for_date = analyzer.get_customer_cones(vpp_asns)

        for asn in vpp_asns:
            vpp_timeline[asn]["snapshots"][target_date] = cones_for_date.get(asn)

    return vpp_timeline


def compute_accumulated_cones_over_time(
    vpp_timeline: dict[str, dict],
    dates: list[str],
    exclude_asns: Optional[set[str]] = None,
) -> dict[str, dict]:
    """
    Computes the accumulated customer cone metrics across VPPs for each date,
    optionally excluding a set of ASNs (e.g., Top-N providers).
    """
    accumulated: dict[str, dict] = {}
    excluded = exclude_asns or set()
    included_records = {
        asn: record
        for asn, record in vpp_timeline.items()
        if asn not in excluded
    }
    total_vpps = len(included_records)

    for q_date in dates:
        active_vpps = 0
        sum_direct_customers = 0
        sum_total_cone_asns = 0
        sum_downstream_cone_asns = 0
        sum_cone_prefixes = 0
        sum_cone_addresses = 0

        for record in included_records.values():
            snap = record["snapshots"].get(q_date)
            if snap is not None:
                active_vpps += 1
                sum_direct_customers += snap.get("direct_customers") or 0
                sum_total_cone_asns += snap.get("total_cone_asns") or 0
                sum_downstream_cone_asns += snap.get("downstream_cone_asns") or 0
                sum_cone_prefixes += snap.get("cone_prefixes") or 0
                sum_cone_addresses += snap.get("cone_addresses") or 0

        accumulated[q_date] = {
            "query_date": q_date,
            "active_vpps": active_vpps,
            "total_vpps": total_vpps,
            "accumulated_direct_customers": sum_direct_customers,
            "accumulated_total_cone_asns": sum_total_cone_asns,
            "accumulated_downstream_cone_asns": sum_downstream_cone_asns,
            "accumulated_cone_prefixes": sum_cone_prefixes,
            "accumulated_cone_addresses": sum_cone_addresses,
        }

    return accumulated


def compute_top_vpps_over_time(
    vpp_timeline: dict[str, dict],
    dates: list[str],
    top_n: int = 3,
    sort_metric: str = "downstream_cone_asns",
) -> dict[str, list[dict]]:
    """
    Identifies the top N VPPs per snapshot date ranked by `sort_metric`.
    """
    top_over_time: dict[str, list[dict]] = {}

    for q_date in dates:
        candidates = []
        for asn, record in vpp_timeline.items():
            snap = record["snapshots"].get(q_date)
            if snap is not None:
                candidates.append({
                    "asn": asn,
                    "vpp_name": record["vpp_name"],
                    "caida_rank": snap.get("rank"),
                    "direct_customers": snap.get("direct_customers") or 0,
                    "total_cone_asns": snap.get("total_cone_asns") or 0,
                    "downstream_cone_asns": snap.get("downstream_cone_asns") or 0,
                    "cone_prefixes": snap.get("cone_prefixes") or 0,
                    "cone_addresses": snap.get("cone_addresses") or 0,
                })

        candidates.sort(
            key=lambda x: (
                x.get(sort_metric) or 0,
                x["total_cone_asns"],
                x["direct_customers"],
            ),
            reverse=True,
        )

        top_over_time[q_date] = [
            {"vpp_rank": idx, **item}
            for idx, item in enumerate(candidates[:top_n], start=1)
        ]

    return top_over_time


def plot_vpp_cone_analyses(
    vpp_timeline: dict[str, dict],
    accumulated_cones: dict[str, dict],
    top_vpps: dict[str, list[dict]],
    dates: list[str],
    metric: str = "downstream_cone_asns",
    subfolder: str = "vpps",
    top_n: int = 3,
    accumulated_without_top: Optional[dict[str, dict]] = None,
) -> None:
    """
    Generates and saves line plots for:
      1. Accumulated customer cones across all VPPs over time.
      2. Accumulated customer cones excluding Top N VPPs over time (if provided).
      3. Top N VPPs customer cone progression over time.
    """
    acc_metric_key = f"accumulated_{metric}"

    # 1. Accumulated Customer Cones Over Time (All VPPs)
    acc_values = [accumulated_cones[d][acc_metric_key] for d in dates]

    plot_list_as_line_plot(
        data_list=acc_values,
        y=dates,
        title="Accumulated VPP Customer Cones Over Time",
        xlabel="Snapshot Date",
        ylabel="Accumulated Downstream Cone ASNs",
        positive_color="steelblue",
        negative_color="red",
        use_fill=True,
        use_rotated_labels=len(dates) > 6,
        subfolder=subfolder,
    )

    acc_lines_data = [
        {
            "data": [accumulated_cones[d]["accumulated_downstream_cone_asns"] for d in dates],
            "label": "Downstream Cone ASNs",
            "color": "steelblue",
            "marker": "o",
        },
        {
            "data": [accumulated_cones[d]["accumulated_direct_customers"] for d in dates],
            "label": "Direct Customers",
            "color": "orange",
            "marker": "s",
        },
    ]

    plot_lists_as_plot_list_with_multiple_lines(
        lines_data=acc_lines_data,
        x_labels=dates,
        title="Accumulated VPP Customer Cone Metrics Over Time",
        xlabel="Snapshot Date",
        ylabel="Accumulated Count",
        use_rotated_labels=len(dates) > 6,
        subfolder=subfolder,
    )

    # 2. Accumulated Customer Cones Over Time (Without Top N)
    if accumulated_without_top is not None:
        acc_no_top_values = [accumulated_without_top[d][acc_metric_key] for d in dates]

        plot_list_as_line_plot(
            data_list=acc_no_top_values,
            y=dates,
            title=f"Accumulated VPP Customer Cones Over Time (Without Top {top_n})",
            xlabel="Snapshot Date",
            ylabel="Accumulated Downstream Cone ASNs",
            positive_color="teal",
            negative_color="red",
            use_fill=True,
            use_rotated_labels=len(dates) > 6,
            subfolder=subfolder,
        )

        acc_no_top_lines_data = [
            {
                "data": [
                    accumulated_without_top[d]["accumulated_downstream_cone_asns"]
                    for d in dates
                ],
                "label": "Downstream Cone ASNs",
                "color": "teal",
                "marker": "o",
            },
            {
                "data": [
                    accumulated_without_top[d]["accumulated_direct_customers"]
                    for d in dates
                ],
                "label": "Direct Customers",
                "color": "darkorange",
                "marker": "s",
            },
        ]

        plot_lists_as_plot_list_with_multiple_lines(
            lines_data=acc_no_top_lines_data,
            x_labels=dates,
            title=f"Accumulated VPP Customer Cone Metrics Over Time (Without Top {top_n})",
            xlabel="Snapshot Date",
            ylabel="Accumulated Count",
            use_rotated_labels=len(dates) > 6,
            subfolder=subfolder,
        )

    # 3. Top N VPPs Over Time
    top_asns_ordered: list[str] = []
    for d in dates:
        for entry in top_vpps.get(d, []):
            if entry["asn"] not in top_asns_ordered:
                top_asns_ordered.append(entry["asn"])

    top_lines_data = []
    for asn in top_asns_ordered:
        record = vpp_timeline[asn]
        series = []
        for d in dates:
            snap = record["snapshots"].get(d)
            series.append((snap.get(metric) or 0) if snap is not None else 0)

        top_lines_data.append({
            "data": series,
            "label": f"AS{asn} ({record['vpp_name']})",
        })

    if top_lines_data:
        plot_lists_as_plot_list_with_multiple_lines(
            lines_data=top_lines_data,
            x_labels=dates,
            title=f"Top {top_n} VPPs Customer Cone Over Time",
            xlabel="Snapshot Date",
            ylabel="Downstream Cone ASNs",
            use_rotated_labels=len(dates) > 6,
            subfolder=subfolder,
        )


def plot_vpp_cone_change_distribution(
    vpp_timeline: dict[str, dict],
    start_date: str,
    end_date: str,
    metric: str = "downstream_cone_asns",
    subfolder: str = "vpps",
) -> dict[str, int]:
    """
    Computes percentage change for each VPP between `start_date` and `end_date`
    and plots a barplot of how many VPPs fell into -50%..-10% and +10%..+50% bins
    using `plot_list_as_bar_plot`.
    """

    missing_in_pair = [
        f"AS{asn} ({rec['vpp_name']})"
        for asn, rec in vpp_timeline.items()
        if rec["snapshots"].get(start_date) is None or rec["snapshots"].get(end_date) is None
    ]
    print(f"Missing in {start_date} or {end_date} ({len(missing_in_pair)}): {missing_in_pair}")

    bin_labels = [
        "≤ -50%", "-40%", "-30%", "-20%", "-10%",
        "0% (±10%)",
        "+10%", "+20%", "+30%", "+40%", "≥ +50%",
    ]
    bin_counts: dict[str, int] = {label: 0 for label in bin_labels}

    for record in vpp_timeline.values():
        snap_start = record["snapshots"].get(start_date)
        snap_end = record["snapshots"].get(end_date)

        if snap_start is None or snap_end is None:
            continue

        val_start = snap_start.get(metric) or 0
        val_end = snap_end.get(metric) or 0

        if val_start <= 0:
            continue

        pct_change = ((val_end - val_start) / val_start) * 100.0

        if pct_change <= -10.0:
            bucket = max(-50, int(pct_change / 10) * 10)
            label = "≤ -50%" if bucket == -50 else f"{bucket}%"
            bin_counts[label] += 1
        elif pct_change >= 10.0:
            bucket = min(50, int(pct_change / 10) * 10)
            label = "≥ +50%" if bucket == 50 else f"+{bucket}%"
            bin_counts[label] += 1
        else:
            bin_counts["0% (±10%)"] += 1

    counts = [bin_counts[label] for label in bin_labels]
    bar_colors = [
        "red" if label.startswith(("-", "≤")) else "steelblue"
        for label in bin_labels
    ]

    plot_list_as_bar_plot(
        data_list= bin_labels,
        y=counts,
        title=f"VPP Customer Cone Growth vs. Decrease ({start_date} to {end_date})",
        xlabel="Percentage Change Bracket",
        ylabel="Number of VPPs",
        subfolder=subfolder,
        use_colors=True,
        colors=bar_colors,
        show_values=True,
        value_format="{:.0f}",
    )

    return bin_counts


def debug_missing_vpps(
    vpp_timeline: dict[str, dict],
    dates: list[str],
) -> dict[str, list[dict]]:
    """
    Logs and returns VPPs that were not found (snapshot is None) across all dates
    or missing on specific snapshot dates.
    """
    never_found = []
    partially_missing = []

    for asn, record in sorted(vpp_timeline.items(), key=lambda x: int(x[0])):
        missing_dates = [
            d for d in dates if record["snapshots"].get(d) is None
        ]

        if len(missing_dates) == len(dates):
            never_found.append({
                "asn": asn,
                "vpp_name": record["vpp_name"],
            })
        elif missing_dates:
            partially_missing.append({
                "asn": asn,
                "vpp_name": record["vpp_name"],
                "missing_dates": missing_dates,
            })

    print(f"Total VPPs tracked: {len(vpp_timeline)}")
    print(f"VPPs NEVER found on any date ({len(never_found)}):")
    for item in never_found:
        print(f"  - AS{item['asn']} ({item['vpp_name']})")

    print(f"\nVPPs missing on SOME dates ({len(partially_missing)}):")
    for item in partially_missing:
        print(f"  - AS{item['asn']} ({item['vpp_name']}): missing on {item['missing_dates']}")

    return {
        "never_found": never_found,
        "partially_missing": partially_missing,
    }


def export_vpp_cones(
    vpp_timeline: dict[str, dict],
    dates: list[str],
    output_dir: str = "output/vpps",
    accumulated: Optional[dict[str, dict]] = None,
    accumulated_without_top: Optional[dict[str, dict]] = None,
    top_vpps: Optional[dict[str, list[dict]]] = None,
    top_n: int = 3,
) -> dict[str, Path]:
    """
    Saves the per-VPP customer cone timeline (JSON & CSV), plus optional
    accumulated totals, accumulated-without-top-N totals, and top-N rankings CSVs.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    exported_files: dict[str, Path] = {}

    json_file = out_path / "vpp_customer_cones_timeline.json"
    with json_file.open("w", encoding="utf-8") as f:
        json.dump(vpp_timeline, f, indent=2)
    exported_files["timeline_json"] = json_file

    csv_file = out_path / "vpp_customer_cones_timeline.csv"
    fieldnames = [
        "asn",
        "vpp_name",
        "query_date",
        "caida_snapshot_date",
        "rank",
        "direct_customers",
        "total_cone_asns",
        "downstream_cone_asns",
        "cone_prefixes",
        "cone_addresses",
    ]

    with csv_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for asn, record in sorted(vpp_timeline.items(), key=lambda x: int(x[0])):
            for q_date in dates:
                snap: Optional[dict] = record["snapshots"].get(q_date)
                writer.writerow({
                    "asn": asn,
                    "vpp_name": record["vpp_name"],
                    "query_date": q_date,
                    "caida_snapshot_date": snap["snapshot_date"] if snap else None,
                    "rank": snap["rank"] if snap else None,
                    "direct_customers": snap["direct_customers"] if snap else None,
                    "total_cone_asns": snap["total_cone_asns"] if snap else None,
                    "downstream_cone_asns": snap["downstream_cone_asns"] if snap else None,
                    "cone_prefixes": snap["cone_prefixes"] if snap else None,
                    "cone_addresses": snap["cone_addresses"] if snap else None,
                })
    exported_files["timeline_csv"] = csv_file

    acc_fields = [
        "query_date",
        "active_vpps",
        "total_vpps",
        "accumulated_direct_customers",
        "accumulated_total_cone_asns",
        "accumulated_downstream_cone_asns",
        "accumulated_cone_prefixes",
        "accumulated_cone_addresses",
    ]

    if accumulated is not None:
        acc_csv = out_path / "vpp_accumulated_cones.csv"
        with acc_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=acc_fields)
            writer.writeheader()
            for q_date in dates:
                if q_date in accumulated:
                    writer.writerow(accumulated[q_date])
        exported_files["accumulated_csv"] = acc_csv

    if accumulated_without_top is not None:
        acc_no_top_csv = out_path / f"vpp_accumulated_cones_without_top_{top_n}.csv"
        with acc_no_top_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=acc_fields)
            writer.writeheader()
            for q_date in dates:
                if q_date in accumulated_without_top:
                    writer.writerow(accumulated_without_top[q_date])
        exported_files["accumulated_without_top_csv"] = acc_no_top_csv

    if top_vpps is not None:
        top_csv = out_path / f"vpp_top_{top_n}_cones.csv"
        top_fields = [
            "query_date",
            "vpp_rank",
            "asn",
            "vpp_name",
            "caida_rank",
            "direct_customers",
            "total_cone_asns",
            "downstream_cone_asns",
            "cone_prefixes",
            "cone_addresses",
        ]
        with top_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=top_fields)
            writer.writeheader()
            for q_date in dates:
                for row in top_vpps.get(q_date, []):
                    writer.writerow({"query_date": q_date, **row})
        exported_files["top_csv"] = top_csv

    return exported_files


if __name__ == "__main__":
    target_dates = [
        "2022-01-01",
        "2022-06-01",
        "2023-01-01",
        "2023-06-01",
        "2024-01-01",
        "2024-06-01",
        "2025-01-01",
        "2025-06-01",
        "2026-01-01",
        #"2026-06-01",
    ]

    results = analyze_vpp_customer_cones_over_dates(
        dates=target_dates,
    )

    #missing_report = debug_missing_vpps(results, target_dates)
    #print(f"\nMissing VPPs Report: {json.dumps(missing_report, indent=2)}")

    accumulated_cones = compute_accumulated_cones_over_time(results, target_dates)

    top_n = 5
    top_vpps = compute_top_vpps_over_time(
        results,
        target_dates,
        top_n=top_n,
        sort_metric="downstream_cone_asns",
    )

    top_n_asns = {
        entry["asn"]
        for entries in top_vpps.values()
        for entry in entries
    }

    accumulated_without_top = compute_accumulated_cones_over_time(
        results,
        target_dates,
        exclude_asns=top_n_asns,
    )

    plot_vpp_cone_change_distribution(
        vpp_timeline=results,
        start_date="2022-01-01",
        end_date="2026-01-01",
        metric="downstream_cone_asns",
        subfolder="vpps",
    )
    export_vpp_cones(
        results,
        target_dates,
        accumulated=accumulated_cones,
        accumulated_without_top=accumulated_without_top,
        top_vpps=top_vpps,
        top_n=top_n,
    )

    plot_vpp_cone_analyses(
        vpp_timeline=results,
        accumulated_cones=accumulated_cones,
        top_vpps=top_vpps,
        dates=target_dates,
        metric="downstream_cone_asns",
        subfolder="vpps",
        top_n=top_n,
        accumulated_without_top=accumulated_without_top,
    )