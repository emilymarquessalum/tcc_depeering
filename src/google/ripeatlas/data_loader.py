 
from datetime import datetime
import random
import requests
from progress.bar import Bar

from cache_manager import (
    load_interval_cache,
    load_measurements_list_cache,
    save_interval_cache,
    save_measurements_list_cache,
    load_individual_result,
    save_individual_result
)
from src.google.ripeatlas.ripeatlas_probe_status import check_probe_changes


def fetch_measurement_data(asn, start_date, end_date, max_results=None, max_iterations=None): 
    # Pass date to Unix timestamp
    start_date_ts = int(start_date.timestamp())
    end_date_ts = int(end_date.timestamp())  
    fields = "type,id,status"
    
    # Base URL for initial request
    url = f"https://atlas.ripe.net/api/v2/measurements/?target_asn={asn}&start_time__gte={start_date_ts}&start_time__lte={end_date_ts}&fields={fields}&page_size=500"
 
    all_results = []

    i = 0
    
    while url:
        if max_iterations is not None and i >= max_iterations:
            break
        i += 1
        print(f"Fetching: {url}")
        response = requests.get(url)
        
        if response.status_code != 200:
            print(f"Error fetching data: {response.status_code}")
            break
            
        data = response.json()
        results = data.get("results", [])
        all_results.extend(results)
        
        # Stop early if max_results is set and reached
        if max_results and len(all_results) >= max_results:
            all_results = all_results[:max_results]
            break
            
        # RIPE Atlas API provides the complete URL for the next page in data['next']
        url = data.get("next")

    return {
        'count': len(all_results), 
        'results': all_results
    }


def load_measurement_data(
    start_date,
    end_date,
    asn,
    type_exclusion_filter,
    day_delta,
    sample_size=50,
    seed_offset=0,
    probe_ids=None,
    check_for_probe_info_matching=False
):
    probe_set = set(probe_ids) if probe_ids is not None else None
    cache_suffix = f"_probes_v2_{'_'.join(map(str, sorted(probe_set)))}" if probe_set else "_v2"

    measurement_counts = []
    filtered_results_per_interval = []
    dates_in_plot = []

    current_date = start_date
    number_of_intervals = ((end_date - start_date).days) // 30
    
    print(f"Processing {number_of_intervals} intervals for ASN {asn}...")
    bar = Bar(max=number_of_intervals)

    for i in range(number_of_intervals):
        interval_start = current_date
        interval_end = current_date + day_delta

        # 1. Try loading interval from cache (Interval-Granular)
        cached_interval = load_interval_cache(asn, interval_start, interval_end, cache_suffix)

        if cached_interval is not None:
            filtered_results = cached_interval['filtered_results']
            date_str = cached_interval['date_str']
        else:
            # 2. Cache miss -> Fetch ONLY this specific interval from RIPE API
            data = fetch_measurement_data(asn, interval_start, interval_end, max_results=1000, max_iterations=10)
            results = data.get("results", [])
            filtered_results = []

            for result in results:
                if result.get("type") == type_exclusion_filter:
                    continue

                probe_id = result.get("prb_id") or result.get("probe_id")
                if probe_set is not None and probe_id and probe_id not in probe_set:
                    continue

                filtered_results.append(result)

            # Date string formatting
            if interval_start.month == 1:
                date_str = interval_start.strftime('%Y')
            else:
                date_str = interval_start.strftime('%b %M')[:-2] + interval_start.strftime('%Y')[2:]

            # Save individual interval cache
            save_interval_cache(asn, interval_start, interval_end, {
                'measurement_count': len(filtered_results),
                'date_str': date_str,
                'filtered_results': filtered_results
            }, cache_suffix)

        measurement_counts.append(len(filtered_results))
        filtered_results_per_interval.append(filtered_results)
        dates_in_plot.append(date_str)

        current_date += day_delta
        bar.next()
    bar.finish()

    # 3. Sample and fetch detailed results per interval
    measurement_data = []
    bar = Bar(max=len(filtered_results_per_interval))

    for idx, filtered_results in enumerate(filtered_results_per_interval):
        interval_start = start_date + idx * day_delta
        
        # Seed depends ONLY on ASN + Interval Start Date (Stable across range extensions)
        seed = (hash((asn, interval_start.date())) + seed_offset) % (2**32)
        rng = random.Random(seed)

        sample = rng.sample(filtered_results, min(sample_size, len(filtered_results)))

        for result in sample:
            measurement_id = result.get("id")
            if measurement_id:
                # Global lookup: decoupled from overall start/end dates
                cached_result = load_individual_result(asn, measurement_id)

                if cached_result is not None:
                    result["result"] = cached_result
                else:
                    try:
                        results_url = f"https://atlas.ripe.net/api/v2/measurements/{measurement_id}/results/"
                        response = requests.get(results_url)
                        if response.status_code == 200:
                            measurement_results = response.json()
                            result["result"] = measurement_results
                            save_individual_result(asn, measurement_id, measurement_results)
                    except Exception as e:
                        print(f"Error fetching results for measurement {measurement_id}: {e}")

        measurement_data.append(filtered_results)
        bar.next()
    bar.finish()

    return measurement_counts, dates_in_plot, measurement_data


def calculate_latency(measurement) -> tuple[float, float]: 
    if not measurement or not isinstance(measurement, dict):
        return None, None
     
    if "result" not in measurement:
        return None, None
    
    results = measurement["result"]
    if not isinstance(results, list) or len(results) == 0:
        return None, None
     
    first_result = results[0]
    if not isinstance(first_result, dict):
        return None, None

    # Extract timestamp from result structure
    raw_ts = (
        first_result.get("endtime") 
        or first_result.get("timestamp") 
        or measurement.get("start_time")
        or measurement.get("timestamp")
    )
    
    # Convert epoch integer/float to datetime object
    if raw_ts is not None:
        try:
            timestamp = datetime.fromtimestamp(int(raw_ts))
        except (ValueError, TypeError):
            timestamp = raw_ts
    else:
        timestamp = None
    
    hops = first_result.get("result", [])
    if not isinstance(hops, list) or len(hops) == 0:
        return None, None

    # Iterate hops backwards to get the target/final destination RTT
    for hop in reversed(hops):
        if isinstance(hop, dict):
            # Ping results store RTT directly or in result array
            if "rtt" in hop:
                return hop["rtt"], timestamp
            elif "result" in hop and isinstance(hop["result"], list):
                for sub_hop in hop["result"]:
                    if isinstance(sub_hop, dict) and "rtt" in sub_hop:
                        return sub_hop["rtt"], timestamp
    
    return None, None

def extract_latencies_and_failed_measurements(measurement_data, dates_in_plot=None): 
    failed_measurements_over_time = []
    latencies = []
    endtimes = []
    
    for interval_idx, measurement_list in enumerate(measurement_data):
        fallback_date = dates_in_plot[interval_idx] if (dates_in_plot and interval_idx < len(dates_in_plot)) else None
        failed_measurements = []
        
        for measurement in measurement_list:
            # Skip items where execution details were not fetched
            if "result" not in measurement:
                continue

            status = measurement.get("status", {})
            status_name = status.get("name") if isinstance(status, dict) else str(status)
            
            if status_name == "Failed":
                failed_measurements.append(measurement)
            else: 
                latency, endtime = calculate_latency(measurement)
                
                # If timestamp is missing or raw epoch integer, resolve to string/datetime
                resolved_endtime = endtime if endtime is not None else fallback_date
                
                if latency is not None and resolved_endtime is not None:
                    latencies.append(latency)
                    endtimes.append(resolved_endtime)
                    
        failed_measurements_over_time.append(failed_measurements)
    
    return latencies, endtimes, failed_measurements_over_time


def group_measurement_data_by_viewpoint(measurement_data): 
    measurement_data_by_viewpoint = {}
    #print(len(measurement_data))

    for measurement_list in measurement_data:
        #print(measurement_list[0]) 
        #print("\n")
        for measurement in measurement_list:

            measurement_results = measurement.get("result")

            if not measurement_results:
                print(f"Warning: Measurement {measurement.get('id')} has no results")
                continue
            if len(measurement_results) == 0:
                continue
            probe_id = measurement_results[0].get("prb_id")
                 
            
            if probe_id:
                    if probe_id not in measurement_data_by_viewpoint:
                        measurement_data_by_viewpoint[probe_id] = []
                    measurement_data_by_viewpoint[probe_id].append(measurement)
        
    return measurement_data_by_viewpoint


def check_if_measurement_passed_through_ixp(): 
    results_url = "https://atlas.ripe.net/api/v2/measurements/85621261/results/"
    response = requests.get(results_url)
    data = response.json()

    hops = data[0]["result"]
    measurement_traces = [[] for _ in range(3)] 
    #print(len(measurement_traces))
    for hop in hops:
        #print(f"hop {hop["hop"]}")
        hop_results = hop["result"]
        #print(len(hop_results))
        for i in range(len(hop_results)):
            measurement_traces[i].append(hop_results[i])
    
    #print(measurement_traces[0][1])
    for trace in measurement_traces[0]: 
        print(trace)
    # now we would need the methodology for checking if a prefix is from an IXP,  