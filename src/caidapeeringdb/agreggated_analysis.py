
import sys
from pathlib import Path
from collections import defaultdict
import numpy as np



sys.path.insert(0, str(Path(__file__).parent.parent.parent))


from src.caidapeeringdb.caidapeeringdb_load import get_all_data, get_all_files, get_asn_from_net, get_connections_for_ixp, get_dates_from_files


def get_aggregated_ixp_connections_for_asn(
    all_files, target_asn, connections_should_be="peered"
):
    """Finds all IXPs that `target_asn` was connected to at any point across all snapshots,

    and calculates the aggregated total connections across those IXPs for each snapshot date.
    """
    all_data = get_all_data(all_files)
    dates = get_dates_from_files(all_files)

    # Step 1: Collect every IXP ID the ASN was connected to in any snapshot
    ever_connected_ixp_ids = set()
    for data in all_data:
        for conn in data.get("netixlan", {}).get("data", []):
            if get_asn_from_net(conn) == target_asn:
                ix_id = conn.get("ix_id")
                if ix_id is not None:
                    ever_connected_ixp_ids.add(ix_id)

    # Step 2: Calculate connections per snapshot (aggregated total & per-IXP breakdown)
    aggregated_totals_over_time = []
    per_ixp_connections_over_time = {
        ixp_id: [] for ixp_id in ever_connected_ixp_ids
    }

    for date, data in zip(dates, all_data):
        snapshot_total = 0

        for ixp_id in ever_connected_ixp_ids:
            ixp_conns = get_connections_for_ixp(
                ixp_id,
                data,
                key="netixlan",
                connections_should_be=connections_should_be,
            )
            count = len(ixp_conns)
            per_ixp_connections_over_time[ixp_id].append((date, count))
            snapshot_total += count

        aggregated_totals_over_time.append((date, snapshot_total))

    return (
        ever_connected_ixp_ids,
        aggregated_totals_over_time,
        per_ixp_connections_over_time,
    )

from src.utils.graphs import plot_list_as_line_plot, plot_stacked_line_plot

def plot_aggregated_ixp_connections_for_asn(all_files, target_asn, connections_should_be="peered"):
    # 1. Retrieve the aggregated data
    ixp_ids, totals, breakdown = get_aggregated_ixp_connections_for_asn(
        all_files, target_asn, connections_should_be
    )

    # 2. Separate dates and totals for plotting
    dates = [date for date, total in totals]
    aggregated_counts = [total for date, total in totals]

    # 3. Plot the total aggregated line
    # Note: In your repo's graph utils, 'y' is used for the categorical x-axis labels (dates)
    plot_list_as_line_plot(
        aggregated_counts,
        y=dates,
        subfolder=f"peeringdb_connections/{target_asn}",
        title=f"Aggregated IXP Connections for AS{target_asn} over time ({connections_should_be})",
        xlabel="Date",
        ylabel="Total Connections Across Ever-Connected IXPs"
    )

    # Optional: Plot the stacked breakdown by IXP
    # Ensure there aren't too many IXPs to stack cleanly, or filter to top N
    if len(ixp_ids) <= 15:
        ixp_labels = [f"IXP {ixp_id}" for ixp_id in ixp_ids]
        ixp_series = []
        for ixp_id in ixp_ids:
            counts = [count for date, count in breakdown[ixp_id]]
            ixp_series.append(counts)
            
        plot_stacked_line_plot(
            ixp_series,
            ixp_labels,
            x_labels=dates,
            subfolder=f"peeringdb_connections/{target_asn}",
            title=f"IXP Connection Breakdown for AS{target_asn} over time",
            xlabel="Date",
            ylabel="Connections per IXP"
        )


if __name__ == "__main__":
    all_files = get_all_files()  #[cite: 3]
    target_asn = 15169  # Google

    ixp_ids, totals, breakdown = get_aggregated_ixp_connections_for_asn(
        all_files, target_asn, connections_should_be="peered"
    )

    print(
        f"ASN {target_asn} was connected to {len(ixp_ids)} distinct IXPs across all snapshots."
    )
    for date, total_connections in totals:
        print(
            f"Date: {date} | Total Peered Connections Across All {len(ixp_ids)} IXPs: {total_connections}"
        )

    plot_aggregated_ixp_connections_for_asn(all_files, target_asn, connections_should_be="peered")