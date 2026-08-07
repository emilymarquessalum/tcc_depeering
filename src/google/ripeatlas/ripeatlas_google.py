
import datetime
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.utils.graphs import plot_list_as_line_plot
from cache_manager import load_latency_cache, save_latency_cache
from data_loader import group_measurement_data_by_viewpoint, load_measurement_data, extract_latencies_and_failed_measurements, check_if_measurement_passed_through_ixp
from ripeatlas_route_diversity import calculate_route_diversity, calculate_route_diversity_per_interval, calculate_asn_diversity, calculate_prefix_diversity
from src.services.caida_prefix_to_as.caida_prefix_to_AS import caida_prefix_to_AS


def print_average_latency_stats(latencies): 
    if not latencies:
        print("No latency data available for successful measurements")
        return
    
    average_latency = sum(latencies) / len(latencies)
    print(f"Average latency for successful measurements: {average_latency:.2f} ms")
    print(f"Total successful measurements with latency data: {len(latencies)}")


def plot_latency_over_time(latencies, endtimes, asn, start_date, end_date): 
    latency_for_each_endtime = []
    end_times = []
    endtime_to_latencies = {}
     
    for latency, endtime in zip(latencies, endtimes):
        if endtime not in endtime_to_latencies:
            endtime_to_latencies[endtime] = []
        endtime_to_latencies[endtime].append(latency)
     
    for endtime, latencies_list in endtime_to_latencies.items():
        average_latency_for_endtime = sum(latencies_list) / len(latencies_list)
        latency_for_each_endtime.append(average_latency_for_endtime)
        end_times.append(endtime)
     
    plot_list_as_line_plot(
        latency_for_each_endtime,
        y=end_times,
        title=f'Average Latency Over Time for ASN {asn} - From {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")} - Exclude DNS',
        xlabel='Time Intervals',
        ylabel='Average Latency (ms)'
    )


    plot_list_as_line_plot(
        latency_for_each_endtime,
        y=[i for i in range(len(latency_for_each_endtime))],
        title=f'Latency Of each Measurement for ASN {asn} - From {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")} - Exclude DNS',
        xlabel='Index',
        ylabel='Latency'
    )




def print_viewpoints(measurement_data):

    measurement_data_by_viewpoint = group_measurement_data_by_viewpoint(measurement_data)

    ordered_by_measurements_viewpoints = sorted(measurement_data_by_viewpoint.items(), key=lambda x: len(x[1]), reverse=True)
    print(f"Data from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print("Total viewpoints:", len(measurement_data_by_viewpoint))
    print("Grouping by viewpoint:")
    for viewpoint, measurements in ordered_by_measurements_viewpoints:
        print(f"Viewpoint {viewpoint} has {len(measurements)} measurements")

def print_route_diversity(measurement_data):
    route_diversity = calculate_route_diversity(measurement_data)
    print(f"Unique Paths: {route_diversity['unique_as_paths']}")
    #print(f"Unique Hop Sequences: {route_diversity['unique_hop_sequences']}")
    print(f"Total Measurements: {route_diversity['total_measurements']}") 
    print(f"Diversity ratio (unique_routes/total_measurements): {route_diversity['diversity_score']:.4f}")

def print_prefix_diversity(measurement_data):
    prefix_diversity = calculate_prefix_diversity(measurement_data, prefix_length=24)
    print(f"Unique /24 Prefixes: {prefix_diversity['unique_prefixes']}")
    print(f"Total Unique IPs: {prefix_diversity['total_unique_ips']}")
    print(f"Total IPs Seen: {prefix_diversity['total_ips_seen']}")
    print(f"Prefix Diversity Ratio (prefixes seen / measurements): {prefix_diversity['prefix_diversity_score']:.4f}")
    
    prefixes_to_asn_mapping = {}

    for prefix, count in prefix_diversity['most_common_prefixes']:
        asn = caida_prefix_to_AS(prefix)
        prefixes_to_asn_mapping[prefix] = asn
        print(f"  {prefix}: {count} occurrences, ASN: {asn}")


    
google_ases_for_search = [15169]

start_date = datetime.datetime(2024, 1, 1)
end_date = datetime.datetime.now()#datetime.datetime(2022, 1, 1)#datetime.datetime.now()
end_date = datetime.datetime(2024, 6, 1)
type_exclusion_filter = "dns"

SAMPLE_SEED_OFFSET = 10

#end_date = datetime.datetime(2023, 6, 1)

day_delta = datetime.timedelta(days=31)


for asn in google_ases_for_search:
     
    measurement_counts, dates_in_plot, measurement_data = load_measurement_data(start_date, end_date, asn, type_exclusion_filter, day_delta, seed_offset=SAMPLE_SEED_OFFSET)


    
    #print_viewpoints(measurement_data)
        
    #print_route_diversity(measurement_data)
    print_prefix_diversity(measurement_data)
      

    sys.exit(0)

    
    cached_latency_data = load_latency_cache(asn, start_date, end_date, SAMPLE_SEED_OFFSET)
    
    if cached_latency_data is not None:
        print(f"Loading latencies from cache for ASN {asn}")
        latencies = cached_latency_data['latencies']
        endtimes = cached_latency_data['endtimes']
        failed_measurements_over_time_count = cached_latency_data['failed_measurements_count']
    else: 
        latencies, endtimes, failed_measurements_over_time = extract_latencies_and_failed_measurements(measurement_data)
        failed_measurements_over_time_count = sum(len(f) for f in failed_measurements_over_time)
         
        save_latency_cache(asn, start_date, end_date, latencies, endtimes, failed_measurements_over_time_count, SAMPLE_SEED_OFFSET)

    plot_list_as_line_plot(measurement_counts, y=dates_in_plot, title=f'Measurement Counts Over Time for ASN {asn} - From {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")} - Exclude DNS', xlabel='Time Intervals', ylabel='Number of Measurements')
    print("Sum of all measurements that are traceroute or ping:", sum(measurement_counts))
    print("Total Failed Measurements from those:", failed_measurements_over_time_count)
     
    print_average_latency_stats(latencies)
    
    if latencies:
        plot_latency_over_time(latencies, endtimes, asn, start_date, end_date)
    
    # Calculate route diversity metrics
    print("\n" + "="*60)
    print(f"Route Diversity Analysis for ASN {asn}")
    print("="*60)
    
    #print(f"Average Path Length: {route_diversity['avg_path_length']:.2f}")

    #print(f"Dominant Path: {route_diversity['dominant_path']}")

    #print(f"Dominant Path Count: {route_diversity['dominant_path_count']}")
    
    # Calculate per-interval diversity
    '''
    interval_diversities = calculate_route_diversity_per_interval(measurement_data)
    print("\nDiversity per Time Interval:")
    for i, diversity in enumerate(interval_diversities):
        print(f"  Interval {i}: {diversity['unique_as_paths']} unique paths, "
              f"diversity score: {diversity['diversity_score']:.4f}")
    '''
    # Calculate ASN diversity
    asn_diversity = calculate_asn_diversity(measurement_data)
    #print(f"\nUnique ASNs in Paths: {asn_diversity['asn_count']}")
    #print("Top 10 Most Common ASNs:")
    #for asn_num, count in asn_diversity['most_common_asns']:
    #    print(f"  ASN {asn_num}: {count} occurrences")
    


    # Calculate prefix diversity (/24 networks)
    print("\n" + "="*60)
    print("Prefix Diversity Analysis (/24 networks)")
    print("="*60)
    print("Top 10 Most Common /24 Prefixes:")
    for prefix, count in prefix_diversity['most_common_prefixes']:
        print(f"  {prefix}: {count} occurrences")


