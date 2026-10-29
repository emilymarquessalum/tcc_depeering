import json
import statistics
import sys
from pathlib import Path
from matplotlib import pyplot as plt

# Add project root to path if needed
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.utils.graphs import DEFAULT_FIGSIZE, plot_list_as_line_plot
from src.caidapeeringdb.caidapeeringdb_load import (
    get_all_data,
    get_all_files,
    get_data,
    get_dates_from_files,
)
from src.google.vpps.google_vpps_list import get_google_vpp_asns


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
            for net in net_data if net.get("asn")
        }
        for asn in target_asns:
            vpp_name = net_lookup.get(asn, f"VPP AS{asn}")
            vpp_asn_map[asn] = [{"isp_name": vpp_name, "asn": asn}]
    else:
        for asn in target_asns:
            vpp_asn_map[asn] = [{"isp_name": f"VPP AS{asn}", "asn": asn}]

    return vpp_asn_map


def plot_vpp_ixp_speed_over_time(
    all_files, all_snapshots, convert_to_gbps=True, use_median=False
):
    """
    Plots:
    1. Average/Median speed of VPP IXP connections over time.
    2. Boxplot showing the full distribution (quantiles, median, outliers) 
       of connection speeds across PeeringDB snapshots.
    """
    if not all_files:
        raise ValueError("At least one PeeringDB snapshot is required.")

    latest_snapshot = get_data(all_files[-1])
    vpp_asn_map = build_vpp_asn_map(latest_snapshot)
    target_vpp_asns = set(vpp_asn_map.keys())

    dates = get_dates_from_files(all_files) 
    labels = [date.replace("_", "-") for date in dates]
    
    unit = "Gbps" if convert_to_gbps else "Mbps"
    divisor = 1000.0 if convert_to_gbps else 1.0

    speeds_over_time = []
    all_snapshot_speeds = []

    for snapshot in all_snapshots:
        speeds = []
        netixlan_entries = snapshot.get("netixlan", {}).get("data", [])

        for conn in netixlan_entries:
            raw_asn = conn.get("asn") if conn.get("asn") is not None else conn.get("local_asn")
            if raw_asn is None:
                continue

            try:
                conn_asn = int(raw_asn)
            except (ValueError, TypeError):
                continue

            if conn_asn in target_vpp_asns:
                speed = conn.get("speed")
                if speed is not None:
                    try:
                        speed_val = int(speed)
                        if speed_val > 0:
                            speeds.append(speed_val / divisor)
                    except (ValueError, TypeError):
                        pass

        all_snapshot_speeds.append(speeds)

        if speeds:
            val = statistics.median(speeds) if use_median else (sum(speeds) / len(speeds))
        else:
            val = 0.0

        speeds_over_time.append(round(val, 2))

    stat_type = "Median" if use_median else "Average"

    # --- Plot 1: Average/Median Line Plot ---
    plot_list_as_line_plot(
        speeds_over_time,
        y=labels,
        subfolder="vpps",
        title=f"{stat_type} VPP Connection Speed at IXPs Over Time ({unit})",
        xlabel="Date",
        ylabel=f"{stat_type} Speed ({unit})",
        max_labels=7,
        fontsize=18
    )

    # --- Plot 2: Speed Distribution Boxplot ---
    plt.figure(figsize=DEFAULT_FIGSIZE)
    
    # Downsample snapshot dates if there are too many for x-axis ticks
    max_xticks = 12
    step = max(1, len(labels) // max_xticks)
    
    sampled_indices = list(range(0, len(labels), step))
    sampled_labels = [labels[i] for i in sampled_indices]
    sampled_speeds = [all_snapshot_speeds[i] for i in sampled_indices]

    plt.boxplot(
        sampled_speeds,
        labels=sampled_labels,
        patch_artist=True,
        boxprops=dict(facecolor="#4285F4", color="#1A73E8", alpha=0.7),
        medianprops=dict(color="#D93025", linewidth=2),
        flierprops=dict(marker="o", markersize=3, markerfacecolor="#5F6368", alpha=0.5)
    )

    plt.title(f"VPP IXP Connection Speed Distribution Over Time ({unit})", fontsize=14, pad=15)
    plt.xlabel("Date", fontsize=12)
    plt.ylabel(f"Port Speed ({unit})", fontsize=12)
    plt.yscale("log")  # Using log scale to accommodate wide speed ranges (e.g., 100 Mbps to 100 Gbps+)
    plt.grid(True, which="both", linestyle="--", alpha=0.5)
    plt.xticks(rotation=45)
    plt.tight_layout()

    out_path = Path("plots/vpps")
    out_path.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path / "vpp_ixp_speed_distribution_boxplot.png", dpi=300)
    plt.show()

    return dates, speeds_over_time, all_snapshot_speeds


if __name__ == "__main__":
    all_files = get_all_files()
    all_snapshots = get_all_data(all_files)

    dates, speeds_over_time, all_snapshot_speeds = plot_vpp_ixp_speed_over_time(
        all_files=all_files,
        all_snapshots=all_snapshots,
        convert_to_gbps=True,
        use_median=True
    )
    dates, speeds_over_time, all_snapshot_speeds = plot_vpp_ixp_speed_over_time(
        all_files=all_files,
        all_snapshots=all_snapshots,
        convert_to_gbps=True,
        use_median=False
    )