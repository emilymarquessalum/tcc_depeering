 
import random
import requests
from progress.bar import Bar

from cache_manager import (
    load_measurements_list_cache,
    save_measurements_list_cache,
    load_individual_result,
    save_individual_result
)


def fetch_measurement_data(asn, start_date, end_date): 
    # pass date to Unix timestamp
    start_date_ts = int(start_date.timestamp())
    end_date_ts = int(end_date.timestamp())  
    fields = "type,"
    route = f"https://atlas.ripe.net/api/v2/measurements/?target_asn={asn}&start_time__gte={start_date_ts}&start_time__lte={end_date_ts}&fields={fields}"
 
    print(route)    
    #return {'count': 0, 'results': []}

    response = requests.get(route)
    if response.status_code == 200:
        data = response.json()
        #print(data) 
        return data 
    else:
        print(f"Error fetching data: {response.status_code}")
    return {'count': 0, 'results': []}


def load_measurement_data(start_date, end_date, asn, type_exclusion_filter, day_delta, sample_size=50, seed_offset=0):
 
    measurement_list_cache = load_measurements_list_cache(asn, start_date, end_date, sample_size)
    
    if measurement_list_cache is not None:
        print(f"Loading measurement list from cache for ASN {asn}")
        measurement_counts = measurement_list_cache['measurement_counts']
        dates_in_plot = measurement_list_cache['dates_in_plot']
        filtered_results_per_interval = measurement_list_cache['filtered_results_per_interval']
    else:
        print(f"Fetching measurement list from API for ASN {asn}")
        measurement_counts = []
        filtered_results_per_interval = []
        dates_in_plot = []
        
        current_date = start_date
        number_of_intervals = ((end_date - start_date).days) // 30
        i = 0
        bar = Bar(max=number_of_intervals)
        while i < number_of_intervals:
            data = fetch_measurement_data(asn, current_date, current_date + day_delta)
            results = data["results"]
            filtered_results = []
            
            for result in results: 
                if result.get("type") == type_exclusion_filter:
                    continue
                filtered_results.append(result)
            
            measurement_counts.append(len(filtered_results))
            filtered_results_per_interval.append(filtered_results)
             
            date_value = start_date + i * day_delta
            if date_value.month == 1:
                date_str = date_value.strftime('%Y')
            else:
                date_str = date_value.strftime('%b %M')[:-2]
                date_str = date_str + date_value.strftime('%Y')[2:]
            dates_in_plot.append(date_str)
            
            current_date += day_delta
            i += 1
            bar.next()
        bar.finish()
         
        save_measurements_list_cache(asn, start_date, end_date, {
            'measurement_counts': measurement_counts,
            'dates_in_plot': dates_in_plot,
            'filtered_results_per_interval': filtered_results_per_interval
        }, sample_size  )
     
    measurement_data = []
    bar = Bar(max=len(filtered_results_per_interval))
     
    seed = (hash((asn, start_date.date(), end_date.date())) + seed_offset) % (2**32)
    rng = random.Random(seed)
    
    for filtered_results in filtered_results_per_interval: 
        sample = rng.sample(filtered_results, min(sample_size, len(filtered_results)))
        
        for result in sample: 
            measurement_id = result.get("id")
            if measurement_id: 
                cached_result = load_individual_result(asn, start_date, end_date, measurement_id)
                
                if cached_result is not None:
                    result["result"] = cached_result
                else:
                    try:
                        results_url = f"https://atlas.ripe.net/api/v2/measurements/{measurement_id}/results/"
                        response = requests.get(results_url)
                        if response.status_code == 200:
                            measurement_results = response.json() 
                            result["result"] = measurement_results 
                            save_individual_result(asn, start_date, end_date, measurement_id, measurement_results)
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
    if not isinstance(first_result, dict) or "result" not in first_result:
        return None, None
    
    hops = first_result["result"]
    if not isinstance(hops, list) or len(hops) == 0:
        return None, None
    
    endtime = first_result.get("endtime")
 
    for hop in reversed(hops):
        if isinstance(hop, dict) and "rtt" in hop:
            rtt = hop["rtt"]
            return rtt, endtime
    
    return None, None


def extract_latencies_and_failed_measurements(measurement_data): 
    failed_measurements_over_time = []
    latencies = []
    endtimes = []
    debug_count = 0
     
    total_measurements = sum(len(ml) for ml in measurement_data)
    measurements_with_results = sum(1 for ml in measurement_data for m in ml if "result" in m)
    print(f"DEBUG: Total measurements: {total_measurements}, with results: {measurements_with_results}")
    
    for measurement_list in measurement_data:
        failed_measurements = []
        for measurement in measurement_list:
            status = measurement.get("status", {})
            status_name = status.get("name") if isinstance(status, dict) else str(status)
            
            if status_name == "Failed":
                failed_measurements.append(measurement)
            else: 
                if debug_count < 2:
                    print(f"DEBUG: Measurement {debug_count} keys: {measurement.keys()}")
                    if "result" in measurement:
                        print(f"DEBUG: Result type: {type(measurement['result'])}, length: {len(measurement['result']) if isinstance(measurement['result'], list) else 'N/A'}")
                    debug_count += 1
                 
                latency, endtime = calculate_latency(measurement)
                if latency is not None:
                    latencies.append(latency)
                    endtimes.append(endtime)
                    
        failed_measurements_over_time.append(failed_measurements)
    
    return latencies, endtimes, failed_measurements_over_time


def group_measurement_data_by_viewpoint(measurement_data):
    """
    Organizes measurement data by viewpoint (probe).
    
    Args:
        measurement_data: A list of measurement lists to be grouped by viewpoint
        
    Returns:
        measurement_data_by_viewpoint: A dictionary with viewpoint IDs as keys 
                                       and lists of measurements from that viewpoint as values
    """
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