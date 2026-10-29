import re
import sys
from pathlib import Path
from matplotlib import pyplot as plt

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.caidapeeringdb.caidapeeringdb_load import (
    get_all_data,
    get_all_files,
    get_all_ixps,
    get_data,
)
from src.caidapeeringdb.ixp_features.continent_logic import organize_connections_by_continent
from src.google.vpps.google_vpps_list import get_google_vpp_asns
from src.utils.graphs import DEFAULT_FIGSIZE


def build_vpp_asn_map(data=None):
    raw_asns = get_google_vpp_asns(include_alternatives=False)
    target_asns = set()
    for asn in raw_asns:
        try:
            target_asns.add(int(str(asn).upper().replace("AS", "").strip()))
        except (ValueError, TypeError):
            continue

    vpp_asn_map = {}
    if data:
        net_data = data.get("net", {}).get("data", [])
        net_lookup = {
            int(net["asn"]): net.get("name", "Unknown VPP")
            for net in net_data
            if net.get("asn")
        }
        for asn in target_asns:
            vpp_name = net_lookup.get(asn, f"VPP AS{asn}")
            vpp_asn_map[asn] = [{"isp_name": vpp_name, "asn": asn}]
    else:
        for asn in target_asns:
            vpp_asn_map[asn] = [{"isp_name": f"VPP AS{asn}", "asn": asn}]

    return vpp_asn_map


def plot_vpp_ixp_geographical_distribution_over_time(all_files, all_snapshots, vpp_asn_map, output_dir="plots/vpps"):
    """
    Plots:
    1. The absolute geographical distribution (by continent) of IXP connections over time.
    2. The relative percentage growth of IXP connections per region over time (normalized to the first snapshot).
    """
    if not all_files or not all_snapshots:
        raise ValueError("At least one snapshot is required.")

    target_vpp_asns = set(vpp_asn_map.keys())

    # Get all unique IXPs from the latest snapshot for metadata lookups
    all_ixps = get_all_ixps(all_snapshots[-1])

    connections_over_time = []

    for file_path, snapshot in zip(all_files, all_snapshots):
        raw_date = Path(file_path).stem
        clean_date = re.sub(r"\D", "", raw_date)

        vpp_ixp_connections = []
        for conn in snapshot.get("netixlan", {}).get("data", []):
            raw_asn = conn.get("asn") if conn.get("asn") is not None else conn.get("local_asn")
            if raw_asn is None:
                continue

            try:
                conn_asn = int(raw_asn)
            except (ValueError, TypeError):
                continue

            if conn_asn in target_vpp_asns:
                vpp_ixp_connections.append(conn)

        connections_over_time.append((clean_date, vpp_ixp_connections))

    # Organize connections by continent
    continent_data_series, dates_for_plot, sorted_continents = organize_connections_by_continent(
        connections_over_time, all_ixps
    )

    labels = [date.replace("_", "-") for date in dates_for_plot]
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------
    # Plot 1: Absolute Number of IXP Connections by Region
    # ---------------------------------------------------------
    plt.figure(figsize=DEFAULT_FIGSIZE)
    for continent in sorted_continents:
        plt.plot(
            labels,
            continent_data_series[continent],
            marker="o",
            linewidth=2,
            label=continent
        )

    plt.title("Geographical Distribution of IXP Connections for VPPs Over Time", fontsize=14, pad=15)
    plt.xlabel("Date", fontsize=12)
    plt.ylabel("Number of IXP Connections", fontsize=12)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend(fontsize=11, title="Continent")

    max_labels = 12
    if len(labels) > max_labels:
        step = len(labels) // max_labels
        plt.xticks(
            ticks=range(0, len(labels), step),
            labels=[labels[i] for i in range(0, len(labels), step)],
            rotation=45,
        )
    else:
        plt.xticks(rotation=45)

    plt.tight_layout()
    plt.savefig(out_path / "vpp_ixp_geographical_distribution.png", dpi=300)
    plt.show()

    # ---------------------------------------------------------
    # Plot 2: Relative Percentage Growth Over Time (Baseline = t0)
    # ---------------------------------------------------------
    growth_series = {}
    for continent in sorted_continents:
        series = continent_data_series[continent]
        baseline = series[0] if series and series[0] > 0 else None
        
        if baseline is not None:
            # Percentage growth relative to baseline: ((val - baseline) / baseline) * 100
            growth = [((val - baseline) / baseline) * 100.0 for val in series]
        else:
            # If a region started with 0 connections, calculate growth relative to first non-zero point
            first_nonzero = next((val for val in series if val > 0), None)
            if first_nonzero:
                growth = [
                    (((val - first_nonzero) / first_nonzero) * 100.0) if val >= first_nonzero else 0.0
                    for val in series
                ]
            else:
                growth = [0.0] * len(series)

        growth_series[continent] = growth

    plt.figure(figsize=DEFAULT_FIGSIZE)
    for continent in sorted_continents:
        plt.plot(
            labels,
            growth_series[continent],
            marker="s",
            linewidth=2,
            label=continent
        )

    plt.title("Percentage Growth of IXP Connections by Region Over Time", fontsize=14, pad=15)
    plt.xlabel("Date", fontsize=12)
    plt.ylabel("Growth Rate (%)", fontsize=12)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend(fontsize=11, title="Continent")

    if len(labels) > max_labels:
        step = len(labels) // max_labels
        plt.xticks(
            ticks=range(0, len(labels), step),
            labels=[labels[i] for i in range(0, len(labels), step)],
            rotation=45,
        )
    else:
        plt.xticks(rotation=45)

    plt.tight_layout()
    plt.savefig(out_path / "vpp_ixp_geographical_growth_over_time.png", dpi=300)
    plt.show()

    return dates_for_plot, continent_data_series, growth_series


if __name__ == "__main__":
    all_files = get_all_files()
    all_snapshots = get_all_data(all_files)

    latest_snapshot = get_data(all_files[-1])
    vpp_asn_map = build_vpp_asn_map(latest_snapshot)

    plot_vpp_ixp_geographical_distribution_over_time(all_files, all_snapshots, vpp_asn_map)