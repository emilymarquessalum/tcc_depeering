import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.caidapeeringdb.caidapeeringdb_load import (
    get_all_files,
    get_asn_from_net,
    get_data,
    get_ixp_from_net,
    get_ixp_id_to_ixp_name_mapping,
)
from src.google.vpps.google_vpps_list import get_google_vpp_asn_map
from src.services.caida_customers import ASRankCustomerAnalyzer
from src.utils.graphs import (
    plot_list_as_line_plot,
    plot_lists_as_plot_list_with_multiple_lines,
)


def load_vpp_map() -> dict[int, str]:
    """Returns {vpp_asn_int: vpp_name}."""
    raw_map = get_google_vpp_asn_map()
    vpp_map: dict[int, str] = {}

    for raw_asn, entry in raw_map.items():
        try:
            asn_int = int(str(raw_asn).upper().replace("AS", "").strip())
        except (ValueError, TypeError):
            continue

        if isinstance(entry, list) and entry:
            raw_name = entry[0].get("isp_name", "")
        elif isinstance(entry, dict):
            raw_name = entry.get("isp_name", "")
        elif isinstance(entry, str):
            raw_name = entry
        else:
            raw_name = ""

        clean_name = raw_name.split("\n")[0].strip()
        vpp_map[asn_int] = clean_name if clean_name else f"VPP AS{asn_int}"

    return vpp_map


def _normalize_date_str(date_str: str) -> str:
    """Converts '2024-01-01', '2024_01_01', or '20240101' to 'YYYYMMDD'."""
    match = re.search(r"(20\d{2})[-_]?(\d{2})[-_]?(\d{2})", date_str)
    if not match:
        raise ValueError(f"Could not parse date from: {date_str}")
    return "".join(match.groups())


def match_peeringdb_files_to_dates(
    target_dates: list[str],
    all_files: Optional[list[str]] = None,
) -> dict[str, Optional[str]]:
    """
    Matches each target_date ('YYYY-MM-DD') to the exact or closest PeeringDB
    filename returned by get_all_files() (e.g., 'peeringdb_2_dump_2024_01_01.json').
    """
    files = all_files if all_files is not None else get_all_files()
    indexed_files: list[tuple[str, str]] = []

    for fname in files:
        try:
            norm = _normalize_date_str(fname)
            indexed_files.append((norm, fname))
        except ValueError:
            continue

    indexed_files.sort(key=lambda x: x[0])
    matched: dict[str, Optional[str]] = {}

    for t_date in target_dates:
        norm_target = _normalize_date_str(t_date)
        exact = next((f for d, f in indexed_files if d == norm_target), None)
        if exact:
            matched[t_date] = exact
        elif indexed_files:
            matched[t_date] = min(
                indexed_files,
                key=lambda x: abs(int(x[0]) - int(norm_target)),
            )[1]
        else:
            matched[t_date] = None

    return matched


def build_asn_to_ixps_map(
    snapshot: dict,
    connections_should_be: str = "all",
) -> dict[int, set[int]]:
    """
    Builds {asn_int: {ix_id_1, ix_id_2, ...}} for every ASN in a PeeringDB snapshot.
    `connections_should_be`: "all", "peered" (is_rs_peer=True), or "not_peered".
    """
    asn_ixps: dict[int, set[int]] = defaultdict(set)

    for conn in snapshot.get("netixlan", {}).get("data", []):
        if connections_should_be == "peered" and not conn.get("is_rs_peer"):
            continue
        if connections_should_be == "not_peered" and conn.get("is_rs_peer"):
            continue

        raw_asn = get_asn_from_net(conn)
        raw_ix = get_ixp_from_net(conn)
        if raw_asn is None or raw_ix is None:
            continue

        try:
            asn_int = int(raw_asn)
            ix_int = int(raw_ix)
            if ix_int > 0:
                asn_ixps[asn_int].add(ix_int)
        except (ValueError, TypeError):
            continue

    return asn_ixps


def _extract_customer_asns(
    customer_lists_entry: Optional[dict[str, list[str]]],
    vpp_asn: int,
    include_indirect: bool = False,
) -> set[int]:
    """
    Extracts direct or full-cone customer ASNs as integers from
    ASRankCustomerAnalyzer.get_customer_asn_lists() output.
    """
    if not customer_lists_entry:
        return set()

    key = "downstream_cone_asns_list" if include_indirect else "direct_customer_asns"
    raw_customers = customer_lists_entry.get(key, [])

    parsed: set[int] = set()
    for c in raw_customers:
        try:
            c_int = int(c)
            if c_int != vpp_asn:
                parsed.add(c_int)
        except (ValueError, TypeError):
            continue

    return parsed


def analyze_vpp_customer_ixp_overlap_over_time(
    dates: list[str],
    include_indirect_customers: bool = False,
    connections_should_be: str = "all",
    force_refresh: bool = False,
) -> dict[str, dict]:
    """
    For each snapshot date, computes deduplicated VPP-group sets (each AS counted at most once):
      - unique_vpp_customers_total: all unique customer ASNs across all VPPs
      - unique_customers_in_any_ixp: subset present in >= 1 IXP
      - unique_customers_in_ixp_with_vpp: subset present in >= 1 IXP with at least one of their own VPPs
    """
    vpp_map = load_vpp_map()
    vpp_asns_str = [str(asn) for asn in vpp_map.keys()]
    pdb_file_map = match_peeringdb_files_to_dates(dates)

    timeline: dict[str, dict] = {}

    for target_date in dates:
        pdb_filename = pdb_file_map.get(target_date)
        if not pdb_filename:
            print(f"[{target_date}] No PeeringDB snapshot found, skipping.")
            continue

        print(f"[{target_date}] Loading PeeringDB ({pdb_filename}) & CAIDA customer lists...")
        pdb_snapshot = get_data(pdb_filename)
        asn_to_ixps = build_asn_to_ixps_map(
            pdb_snapshot,
            connections_should_be=connections_should_be,
        )
        ixp_names = get_ixp_id_to_ixp_name_mapping(pdb_snapshot)

        analyzer = ASRankCustomerAnalyzer(
            snapshot_date=target_date,
            force_refresh=force_refresh,
        )
        customer_lists_for_date = analyzer.get_customer_asn_lists(
            vpp_asns_str,
            force_refresh=force_refresh,
        )

        per_vpp_results = {}
        unique_all_customers: set[int] = set()
        unique_customers_in_any_ixp: set[int] = set()
        unique_customers_in_ixp_with_vpp: set[int] = set()

        for vpp_asn, vpp_name in vpp_map.items():
            vpp_ixps = asn_to_ixps.get(vpp_asn, set())
            customer_asns = _extract_customer_asns(
                customer_lists_entry=customer_lists_for_date.get(str(vpp_asn)),
                vpp_asn=vpp_asn,
                include_indirect=include_indirect_customers,
            )

            customers_in_any_ixp = {
                c for c in customer_asns if len(asn_to_ixps.get(c, set())) > 0
            }
            customers_in_ixp_with_vpp = {
                c for c in customer_asns if bool(asn_to_ixps.get(c, set()) & vpp_ixps)
            }

            shared_ixp_counts: dict[int, int] = defaultdict(int)
            for c in customers_in_ixp_with_vpp:
                for ix_id in asn_to_ixps.get(c, set()) & vpp_ixps:
                    shared_ixp_counts[ix_id] += 1

            top_shared_ixps = [
                {
                    "ixp_id": ix_id,
                    "ixp_name": ixp_names.get(ix_id, f"IXP {ix_id}"),
                    "shared_customers": cnt,
                }
                for ix_id, cnt in sorted(
                    shared_ixp_counts.items(), key=lambda x: x[1], reverse=True
                )[:5]
            ]

            total_cust = len(customer_asns)
            in_any_ixp_count = len(customers_in_any_ixp)
            with_vpp_count = len(customers_in_ixp_with_vpp)

            per_vpp_results[str(vpp_asn)] = {
                "asn": vpp_asn,
                "vpp_name": vpp_name,
                "vpp_ixp_count": len(vpp_ixps),
                "total_customers": total_cust,
                "customers_in_any_ixp": in_any_ixp_count,
                "customers_in_ixp_with_vpp": with_vpp_count,
                "pct_total_customers_in_ixp_with_vpp": (
                    round((with_vpp_count / total_cust) * 100.0, 2) if total_cust > 0 else 0.0
                ),
                "pct_ixp_customers_in_ixp_with_vpp": (
                    round((with_vpp_count / in_any_ixp_count) * 100.0, 2)
                    if in_any_ixp_count > 0
                    else 0.0
                ),
                "top_shared_ixps": top_shared_ixps,
                "shared_customer_asns": sorted(customers_in_ixp_with_vpp),
            }

            # Union across VPPs: an AS is counted at most once even if shared by multiple VPPs
            unique_all_customers.update(customer_asns)
            unique_customers_in_any_ixp.update(customers_in_any_ixp)
            unique_customers_in_ixp_with_vpp.update(customers_in_ixp_with_vpp)

        assert unique_customers_in_ixp_with_vpp.issubset(unique_customers_in_any_ixp)
        assert unique_customers_in_any_ixp.issubset(unique_all_customers)

        total_unique = len(unique_all_customers)
        in_any_ixp_unique = len(unique_customers_in_any_ixp)
        with_vpp_unique = len(unique_customers_in_ixp_with_vpp)

        timeline[target_date] = {
            "date": target_date,
            "peeringdb_file": pdb_filename,
            "summary": {
                "unique_vpp_customers_total": total_unique,
                "unique_customers_in_any_ixp": in_any_ixp_unique,
                "unique_customers_in_ixp_with_vpp": with_vpp_unique,
                "pct_total_customers_in_ixp_with_vpp": (
                    round((with_vpp_unique / total_unique) * 100.0, 2) if total_unique > 0 else 0.0
                ),
                "pct_ixp_customers_in_ixp_with_vpp": (
                    round((with_vpp_unique / in_any_ixp_unique) * 100.0, 2)
                    if in_any_ixp_unique > 0
                    else 0.0
                ),
            },
            "vpps": per_vpp_results,
        }

    return timeline


def export_and_plot_overlap(
    timeline: dict[str, dict],
    output_dir: str = "output/vpps",
    subfolder: str = "vpps",
) -> None:
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    with (out_path / "vpp_customer_ixp_overlap.json").open("w", encoding="utf-8") as f:
        json.dump(timeline, f, indent=2)

    # Per-VPP CSV
    csv_path = out_path / "vpp_customer_ixp_overlap.csv"
    fieldnames = [
        "date",
        "asn",
        "vpp_name",
        "vpp_ixp_count",
        "total_customers",
        "customers_in_any_ixp",
        "customers_in_ixp_with_vpp",
        "pct_total_customers_in_ixp_with_vpp",
        "pct_ixp_customers_in_ixp_with_vpp",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for date_str, payload in timeline.items():
            for _, vpp_row in sorted(payload["vpps"].items(), key=lambda x: int(x[0])):
                writer.writerow({
                    "date": date_str,
                    **{k: vpp_row[k] for k in fieldnames if k != "date"},
                })

    # Deduplicated VPP-Group Summary CSV
    summary_csv_path = out_path / "vpp_group_customer_ixp_overlap_summary.csv"
    summary_fields = [
        "date",
        "unique_vpp_customers_total",
        "unique_customers_in_any_ixp",
        "unique_customers_in_ixp_with_vpp",
        "pct_total_customers_in_ixp_with_vpp",
        "pct_ixp_customers_in_ixp_with_vpp",
    ]
    with summary_csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=summary_fields)
        writer.writeheader()
        for date_str, payload in timeline.items():
            writer.writerow({
                "date": date_str,
                **payload["summary"],
            })

    dates = list(timeline.keys())
    if not dates:
        return

    # Plot 1: Deduplicated counts (Total Customers -> Customers in IXP -> Customers in IXP with >=1 of their VPPs)
    lines_data = [
        {
            "data": [timeline[d]["summary"]["unique_vpp_customers_total"] for d in dates],
            "label": "Total Unique VPP Customers",
            "color": "steelblue",
            "marker": "o",
        },
        {
            "data": [timeline[d]["summary"]["unique_customers_in_any_ixp"] for d in dates],
            "label": "ASes in IXP",
            "color": "orange",
            "marker": "s",
        },
        {
            "data": [timeline[d]["summary"]["unique_customers_in_ixp_with_vpp"] for d in dates],
            "label": "ASes in IXP with at least one VPP",
            "color": "green",
            "marker": "^",
        },
    ]
    plot_lists_as_plot_list_with_multiple_lines(
        lines_data=lines_data,
        x_labels=dates,
        title="VPP Customer ASes in IXPs Over Time (Deduplicated Across VPPs)",
        xlabel="Snapshot Date",
        ylabel="Unique Customer ASNs",
        use_rotated_labels=len(dates) > 6,
        subfolder=subfolder,
    )

    # Plot 2: Percentage of IXP-present customers that share an IXP with at least one of their VPPs
    pct_ixp_series = [
        timeline[d]["summary"]["pct_ixp_customers_in_ixp_with_vpp"] for d in dates
    ]
    plot_list_as_line_plot(
        data_list=pct_ixp_series,
        y=dates,
        title="% of IXP-Present VPP Customers Sharing an IXP with Their VPP",
        xlabel="Snapshot Date",
        ylabel="Share of IXP-Present Customers (%)",
        use_rotated_labels=len(dates) > 6,
        subfolder=subfolder,
    )



def plot_accumulated_vpp_connections_overlap(
    dates: list[str],
    include_indirect_customers: bool = True,
    connections_should_be: str = "all",
    force_refresh: bool = False,
    subfolder: str = "vpps",
) -> dict[str, dict[str, int]]:
    """
    Standalone analysis & plot of accumulated (ASN, VPP) relationships over time.
    Defaults to `include_indirect_customers=True` (full downstream cone per VPP).
    """
    vpp_map = load_vpp_map()
    vpp_asns_str = [str(asn) for asn in vpp_map.keys()]
    pdb_file_map = match_peeringdb_files_to_dates(dates)

    valid_dates: list[str] = []
    total_connections: list[int] = []
    as_in_ixp_connections: list[int] = []
    shared_ixp_connections: list[int] = []
    results_by_date: dict[str, dict[str, int]] = {}

    for target_date in dates:
        pdb_filename = pdb_file_map.get(target_date)
        if not pdb_filename:
            print(f"[{target_date}] No PeeringDB snapshot found, skipping.")
            continue

        pdb_snapshot = get_data(pdb_filename)
        asn_to_ixps = build_asn_to_ixps_map(
            pdb_snapshot,
            connections_should_be=connections_should_be,
        )

        analyzer = ASRankCustomerAnalyzer(
            snapshot_date=target_date,
            force_refresh=force_refresh,
        )
        customer_lists_for_date = analyzer.get_customer_asn_lists(
            vpp_asns_str,
            force_refresh=force_refresh,
        )

        date_total = 0
        date_in_ixp = 0
        date_shared_ixp = 0

        for vpp_asn in vpp_map:
            vpp_ixps = asn_to_ixps.get(vpp_asn, set())
            customer_asns = _extract_customer_asns(
                customer_lists_entry=customer_lists_for_date.get(str(vpp_asn)),
                vpp_asn=vpp_asn,
                include_indirect=include_indirect_customers,
            )

            for c in customer_asns:
                c_ixps = asn_to_ixps.get(c, set())
                date_total += 1
                if c_ixps:
                    date_in_ixp += 1
                    if c_ixps & vpp_ixps:
                        date_shared_ixp += 1

        print(
            f"[{target_date}] VPPs={len(vpp_map)} | "
            f"Total ASNxVPP={date_total} | In IXP={date_in_ixp} | Shared IXP={date_shared_ixp}"
        )

        valid_dates.append(target_date)
        total_connections.append(date_total)
        as_in_ixp_connections.append(date_in_ixp)
        shared_ixp_connections.append(date_shared_ixp)
        results_by_date[target_date] = {
            "total_vpp_connections": date_total,
            "connections_as_in_any_ixp": date_in_ixp,
            "connections_as_in_ixp_with_vpp": date_shared_ixp,
        }

    if not valid_dates:
        return results_by_date

    lines_data = [
        {
            "data": total_connections,
            "label": "Total VPP Customer Connections",
            "color": "steelblue",
            "marker": "o",
        },
        {
            "data": as_in_ixp_connections,
            "label": "AS in IXP",
            "color": "orange",
            "marker": "s",
        },
        {
            "data": shared_ixp_connections,
            "label": "AS in IXP with VPP",
            "color": "green",
            "marker": "^",
        },
    ]

    plot_lists_as_plot_list_with_multiple_lines(
        lines_data=lines_data,
        x_labels=valid_dates,
        title="Accumulated VPP Customer Connections in IXPs Over Time (All ASNxVPP Pairs)",
        xlabel="Snapshot Date",
        ylabel="Accumulated Customer-VPP Connections",
        use_rotated_labels=len(valid_dates) > 6,
        subfolder=subfolder,
    )

    return results_by_date

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
    ]

    overlap_timeline = analyze_vpp_customer_ixp_overlap_over_time(
        dates=target_dates,
        include_indirect_customers=False,  # False = direct customers; True = full downstream cone
        connections_should_be="all",       # "all" = any IXP presence; "peered" = is_rs_peer=True only
    )

    plot_accumulated_vpp_connections_overlap(
        dates=target_dates,
        include_indirect_customers=True,  # True = full downstream cone (~200k+); False = direct customers only
        connections_should_be="all",
    )
    export_and_plot_overlap(overlap_timeline)
