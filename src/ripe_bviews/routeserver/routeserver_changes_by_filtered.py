import json
import os
import datetime

import sys
from pathlib import Path
 
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent)) 

from src.utils.graphs import create_window_with_all_rendered_graphs_this_session, create_window_with_all_rendered_graphs_this_session, plot_list_as_line_plot, plot_stacked_line_plot


def get_routeserver(routeserver_name, date):
    """Get routeserver data for a specific date."""
    folder_path = "/home/emily/Desktop/projects/furg/tcc_depeering_elixir/data/routeservers/{routeserver_name}/{date}/neighbors/".format(
        routeserver_name=routeserver_name, date=date
    )

    first_file = None
    for file_name in os.listdir(folder_path):
        if file_name.endswith(".json"):
            first_file = file_name
            break
    
    with open(os.path.join(folder_path, first_file), "r") as f:
        data = json.load(f)
    
    return data


if __name__ == "__main__":

    start_time = datetime.datetime(2025, 8, 16)
    end_time = datetime.datetime(2025, 11, 6)

    current_time = start_time

    # Store metrics for each ASN over time
    asn_to_metrics_map = {}  # asn -> [(date, routes_received, routes_accepted, routes_filtered), ...]

    while current_time <= end_time:
        date_str = current_time.strftime("%Y%m%d")
        print(f"Processing data for date: {date_str}")
        
        try:
            route_server_data = get_routeserver("ix-br", date_str)
            neighbours = route_server_data["SP-rs2-v4"]["neighbors"]
        except Exception as e:
            print(f"  Error loading data for {date_str}: {e}")
            current_time += datetime.timedelta(days=1)
            continue

        asns_processed_today = set()
        for neighbor in neighbours:
            asn = neighbor["asn"]
            if asn in asns_processed_today:
                continue  # Skip duplicates for the same day
            asns_processed_today.add(asn)

            routes_accepted = neighbor.get("routes_accepted", 0)
            routes_received = neighbor.get("routes_received", 0)
            routes_filtered = routes_received - routes_accepted if routes_received >= routes_accepted else 0

            if asn not in asn_to_metrics_map:
                asn_to_metrics_map[asn] = []

            asn_to_metrics_map[asn].append({
                "date": current_time,
                "routes_received": routes_received,
                "routes_accepted": routes_accepted,
                "routes_filtered": routes_filtered
            })

        current_time += datetime.timedelta(days=1)

    # Analyze changes and filtering impact
    asns_with_negative_changes = []
    
    for asn, metrics_data in asn_to_metrics_map.items():
        if len(metrics_data) < 2:
            continue

        for i in range(1, len(metrics_data)):
            prev_metrics = metrics_data[i - 1]
            curr_metrics = metrics_data[i]

            accepted_change = curr_metrics["routes_accepted"] - prev_metrics["routes_accepted"]
            received_change = curr_metrics["routes_received"] - prev_metrics["routes_received"]

            # Only look at negative changes in accepted routes
            if accepted_change < 0:
                # Calculate routes that went to filtering instead of being accepted
                # Since received = accepted + filtered, if accepted decreased by X but received only decreased by Y,
                # then X - Y routes went to filtering
                routes_to_filtering = -(accepted_change - received_change)  # received_change - accepted_change
                
                if routes_to_filtering > 0:
                    percentage_due_to_filtering = (routes_to_filtering / -accepted_change) * 100
                    
                    asns_with_negative_changes.append({
                        "asn": asn,
                        "date": curr_metrics["date"],
                        "accepted_change": accepted_change,
                        "received_change": received_change,
                        "routes_to_filtering": routes_to_filtering,
                        "percentage_due_to_filtering": percentage_due_to_filtering,
                        "prev_accepted": prev_metrics["routes_accepted"],
                        "curr_accepted": curr_metrics["routes_accepted"],
                        "prev_received": prev_metrics["routes_received"],
                        "curr_received": curr_metrics["routes_received"]
                    })

    # Sort by magnitude of change
    asns_with_negative_changes.sort(key=lambda x: -abs(x["accepted_change"]))

    print(f"\nTop 20 ASNs with largest negative accepted route changes (and filtering contribution):")
    print("-" * 120)
    for change_info in asns_with_negative_changes[:20]:
        print(f"ASN: {change_info['asn']}, Date: {change_info['date'].strftime('%Y-%m-%d')}")
        print(f"  Routes Accepted: {change_info['prev_accepted']} -> {change_info['curr_accepted']} (change: {change_info['accepted_change']})")
        print(f"  Routes Received: {change_info['prev_received']} -> {change_info['curr_received']} (change: {change_info['received_change']})")
        print(f"  Routes to Filtering: {change_info['routes_to_filtering']} routes ({change_info['percentage_due_to_filtering']:.2f}%)")
        print()

    # Aggregate over time for plotting
    total_accepted_decrease_over_time = []
    total_filtering_contribution_over_time = []
    dates_for_plot = []

    current_time = start_time
    while current_time <= end_time:
        date_str = current_time.strftime("%Y%m%d")
        
        # Sum changes for this date
        total_accepted_decrease = sum(
            abs(change["accepted_change"]) for change in asns_with_negative_changes
            if change["date"] == current_time and change["accepted_change"] < 0
        )
        
        total_filtering_contrib = sum(
            change["routes_to_filtering"] for change in asns_with_negative_changes
            if change["date"] == current_time and change["accepted_change"] < 0
        )
        
        if total_accepted_decrease > 0 or total_filtering_contrib > 0:
            total_accepted_decrease_over_time.append(total_accepted_decrease)
            total_filtering_contribution_over_time.append(total_filtering_contrib)
            dates_for_plot.append(current_time)
        
        current_time += datetime.timedelta(days=1)

    # Plot the data
    print(f"\nPlotting data for {len(dates_for_plot)} dates with changes...")
    
    if dates_for_plot:
        plot_list_as_line_plot(
            total_accepted_decrease_over_time,
            y=dates_for_plot,
            title="Accepted Routes Lost Over Time (ix-br)"
        )
        
        plot_list_as_line_plot(
            total_filtering_contribution_over_time,
            y=dates_for_plot,
            title="Routes Changed By Filtering Over Time (ix-br)"
        )
        
        # Calculate routes lost without filtering
        routes_lost_without_filtering = [
            total_accepted_decrease_over_time[i] - total_filtering_contribution_over_time[i]
            for i in range(len(total_accepted_decrease_over_time))
        ]
        
        # Plot stacked line plot
        date_labels = [date.strftime('%Y-%m-%d') for date in dates_for_plot]
        plot_stacked_line_plot(
            [routes_lost_without_filtering, total_filtering_contribution_over_time],
            labels=["Routes Lost (No Filtering)", "Routes Lost to Filtering"],
            x_labels=date_labels,
            title="Route Losses Breakdown Over Time (ix-br)",
            xlabel="Date",
            ylabel="Number of Routes Lost",
            colors=["#d62728", "#2ca02c"],  # Red for actual loss, green for filtering
            max_labels=10
        )

        create_window_with_all_rendered_graphs_this_session()