
import datetime
from pathlib import Path
import sys

from matplotlib import pyplot as plt
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.google.ripeatlas.ripeatlas_latency import plot_enhanced_latency, plot_latency_over_time
from src.utils.graphs import plot_list_as_line_plot
from cache_manager import load_latency_cache, save_latency_cache
from data_loader import group_measurement_data_by_viewpoint, load_measurement_data, extract_latencies_and_failed_measurements
from ripeatlas_route_diversity import calculate_route_diversity, calculate_route_diversity_per_interval, calculate_asn_diversity, calculate_prefix_diversity, print_prefix_diversity
from src.services.caida_prefix_to_as.caida_prefix_to_AS import caida_prefix_to_AS


def print_average_latency_stats(latencies): 
    if not latencies:
        print("No latency data available for successful measurements")
        return
    
    average_latency = sum(latencies) / len(latencies)
    print(f"Average latency for successful measurements: {average_latency:.2f} ms")
    print(f"Total successful measurements with latency data: {len(latencies)}")




def plot_latency_boxplot_over_time(
    latencies, endtimes, asn, start_date, end_date
):
    endtime_to_latencies = {}

    # Group raw latencies by each unique endtime
    for latency, endtime in zip(latencies, endtimes):
        if endtime not in endtime_to_latencies:
            endtime_to_latencies[endtime] = []
        endtime_to_latencies[endtime].append(latency)

    # Preserve order of timestamps and extract corresponding latency lists
    end_times = list(endtime_to_latencies.keys())
    data = [endtime_to_latencies[et] for et in end_times]

    # Create the figure
    fig, ax = plt.subplots(figsize=(10, 6))

    # Plot the boxplots for each timestamp group
    ax.boxplot(data, tick_labels=[str(et) for et in end_times])

    # Title and Labels
    start_str = (
        start_date.strftime("%Y-%m-%d")
        if hasattr(start_date, "strftime")
        else start_date
    )
    end_str = (
        end_date.strftime("%Y-%m-%d")
        if hasattr(end_date, "strftime")
        else end_date
    )

    ax.set_title(
        f"Latency Distribution Over Time for ASN {asn} - From {start_str} to {end_str} - Exclude DNS"
    )
    ax.set_xlabel("Time Intervals")
    ax.set_ylabel("Latency (ms)")

    # Formatting options for readability
    ax.tick_params(axis="x", rotation=45)
    ax.grid(True, linestyle="--", alpha=0.6)

    plt.tight_layout()
    plt.show()



def print_viewpoints(measurement_data):

    measurement_data_by_viewpoint = group_measurement_data_by_viewpoint(measurement_data)

    ordered_by_measurements_viewpoints = sorted(measurement_data_by_viewpoint.items(), key=lambda x: len(x[1]), reverse=True)
    print(f"Data from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print("Total viewpoints:", len(measurement_data_by_viewpoint))
    print("Grouping by viewpoint:")
    for viewpoint, measurements in ordered_by_measurements_viewpoints:
        print(f"Viewpoint {viewpoint} has {len(measurements)} measurements")



    
google_ases_for_search = [15169]
probe_ids = [10515, 10704]

start_date = datetime.datetime(2024, 1, 1)
end_date = datetime.datetime.now()#datetime.datetime(2022, 1, 1)#datetime.datetime.now()
#end_date = datetime.datetime(2024, 6, 1)
type_exclusion_filter = "dns"

SAMPLE_SEED_OFFSET = 10

#end_date = datetime.datetime(2023, 6, 1)

day_delta = datetime.timedelta(days=31)


for asn in google_ases_for_search:
     
    measurement_counts, dates_in_plot, measurement_data = load_measurement_data(start_date, end_date, asn, type_exclusion_filter, day_delta, seed_offset=SAMPLE_SEED_OFFSET,
                                                                                probe_ids=probe_ids)


     
    #print_viewpoints(measurement_data)
        
    #print_route_diversity(measurement_data)
    print_prefix_diversity(measurement_data)
    
    cached_latency_data = load_latency_cache(asn, start_date, end_date, SAMPLE_SEED_OFFSET)
    
    if cached_latency_data is not None:
        print(f"Loading latencies from cache for ASN {asn}")
        latencies = cached_latency_data['latencies']
        endtimes = cached_latency_data['endtimes']
        failed_measurements_over_time_count = cached_latency_data['failed_measurements_count']
    else: 
        latencies, endtimes, failed_measurements_over_time = extract_latencies_and_failed_measurements(
            measurement_data, 
            dates_in_plot=dates_in_plot
        )
        failed_measurements_over_time_count = sum(len(f) for f in failed_measurements_over_time)
         
        save_latency_cache(asn, start_date, end_date, latencies, endtimes, failed_measurements_over_time_count, SAMPLE_SEED_OFFSET)

    plot_list_as_line_plot(measurement_counts, y=dates_in_plot, title=f'Measurement Counts Over Time for ASN {asn} - From {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")} - Exclude DNS', xlabel='Time Intervals', ylabel='Number of Measurements')
    print("Sum of all measurements that are traceroute or ping:", sum(measurement_counts))
    print("Total Failed Measurements from those:", failed_measurements_over_time_count)
     
    #sys.exit(0)
    print_average_latency_stats(latencies)
    
    if latencies:
        print("Total measurements:", len(endtimes))
        print("Unique timestamps:", len(set(endtimes)))
        print("Sample timestamps:", endtimes[:5])
        plot_enhanced_latency(latencies, endtimes, event_date=None)
        #plot_latency_over_time(latencies, endtimes, asn, start_date, end_date)
        #plot_latency_boxplot_over_time(latencies, endtimes, asn, start_date, end_date)
    
    # Calculate route diversity metrics
    print("\n" + "="*60)
    print(f"Route Diversity Analysis for ASN {asn}")
    print("="*60)
    
    #print(f"Average Path Length: {route_diversity['avg_path_length']:.2f}")

    #print(f"Dominant Path: {route_diversity['dominant_path']}")

    #print(f"Dominant Path Count: {route_diversity['dominant_path_count']}")
    
    # Calculate per-interval diversity 
    interval_diversities = calculate_route_diversity_per_interval(measurement_data)
    metric_key = 'diversity_score'

    # Extract the selected metric across all time intervals
    metric_values = [interval[metric_key] for interval in interval_diversities]

    # Plot the extracted metric over time
    plot_list_as_line_plot(
        metric_values, 
        title=f'{metric_key.replace("_", " ").title()} Over Time for ASN {asn} - From {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")}',
        xlabel='Time Intervals',
        ylabel=metric_key.replace('_', ' ').title()
    ) 
    # Calculate ASN diversity
    asn_diversity = calculate_asn_diversity(measurement_data)
    #print(f"\nUnique ASNs in Paths: {asn_diversity['asn_count']}")
    #print("Top 10 Most Common ASNs:")
    #for asn_num, count in asn_diversity['most_common_asns']:
    #    print(f"  ASN {asn_num}: {count} occurrences")
    

 