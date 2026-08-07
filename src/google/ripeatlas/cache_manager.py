 
import json
from pathlib import Path


def get_measurements_list_cache_path(asn, start_date, end_date, sample_size): 
    cache_dir = Path(__file__).parent / "cache"
    cache_dir.mkdir(exist_ok=True)
    cache_file = cache_dir / f"measurements_list_{asn}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}_{sample_size}.json"
    return cache_file


def load_measurements_list_cache(asn, start_date, end_date, sample_size):
    cache_path = get_measurements_list_cache_path(asn, start_date, end_date, sample_size)
    if cache_path.exists():
        with open(cache_path, 'r') as f:
            return json.load(f)
    return None


def save_measurements_list_cache(asn, start_date, end_date, data, sample_size):
    cache_path = get_measurements_list_cache_path(asn, start_date, end_date, sample_size)
    with open(cache_path, 'w') as f:
        json.dump(data, f, indent=2)


def get_results_cache_dir(asn, start_date, end_date): 
    cache_dir = Path(__file__).parent / "cache" / f"results_{asn}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def load_individual_result(asn, start_date, end_date, measurement_id): 
    cache_dir = get_results_cache_dir(asn, start_date, end_date)
    cache_file = cache_dir / f"measurement_{measurement_id}.json"
    if cache_file.exists():
        with open(cache_file, 'r') as f:
            return json.load(f)
    return None


def save_individual_result(asn, start_date, end_date, measurement_id, result_data): 
    cache_dir = get_results_cache_dir(asn, start_date, end_date)
    cache_file = cache_dir / f"measurement_{measurement_id}.json"
    with open(cache_file, 'w') as f:
        json.dump(result_data, f, indent=2)


def get_latency_cache_path(asn, start_date, end_date, seed_offset=0): 
    cache_dir = Path(__file__).parent / "cache"
    cache_dir.mkdir(exist_ok=True)
    cache_file = cache_dir / f"latencies_{asn}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}_seed{seed_offset}.json"
    return cache_file


def load_latency_cache(asn, start_date, end_date, seed_offset=0): 
    cache_path = get_latency_cache_path(asn, start_date, end_date, seed_offset)
    if cache_path.exists():
        with open(cache_path, 'r') as f:
            return json.load(f)
    return None


def save_latency_cache(asn, start_date, end_date, latencies, endtimes, failed_measurements_count, seed_offset=0):
 
    cache_path = get_latency_cache_path(asn, start_date, end_date, seed_offset)
    data = {
        'latencies': latencies,
        'endtimes': endtimes,
        'failed_measurements_count': failed_measurements_count
    }
    with open(cache_path, 'w') as f:
        json.dump(data, f, indent=2)
