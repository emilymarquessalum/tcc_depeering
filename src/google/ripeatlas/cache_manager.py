from pathlib import Path
import json
import pandas as pd


def get_measurements_list_cache_path(asn, start_date, end_date, sample_size): 
    cache_dir = Path(__file__).parent / "cache"
    cache_dir.mkdir(exist_ok=True)
    return cache_dir / f"measurements_list_{asn}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}_{sample_size}.parquet"


def load_measurements_list_cache(asn, start_date, end_date, sample_size):
    cache_path = get_measurements_list_cache_path(asn, start_date, end_date, sample_size)
    if cache_path.exists():
        df = pd.read_parquet(cache_path) 
        return {
            'measurement_counts': df['measurement_counts'].tolist(),
            'dates_in_plot': df['dates_in_plot'].tolist(),
            'filtered_results_per_interval': [
                json.loads(x) for x in df['filtered_results_per_interval'].tolist()
            ]
        }
    return None


def save_measurements_list_cache(asn, start_date, end_date, data, sample_size):
    cache_path = get_measurements_list_cache_path(asn, start_date, end_date, sample_size)
     
    df = pd.DataFrame({
        'measurement_counts': data['measurement_counts'],
        'dates_in_plot': data['dates_in_plot'],
        'filtered_results_per_interval': [
            json.dumps(item) for item in data['filtered_results_per_interval']
        ]
    })
    df.to_parquet(cache_path, index=False)


def get_results_cache_dir(asn, start_date, end_date): 
    cache_dir = Path(__file__).parent / "cache" / f"results_{asn}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def load_individual_result(asn, start_date, end_date, measurement_id): 
    cache_dir = get_results_cache_dir(asn, start_date, end_date)
    cache_file = cache_dir / f"measurement_{measurement_id}.parquet"
    if cache_file.exists():
        df = pd.read_parquet(cache_file) 
        return df.to_dict(orient='records')
    return None


def save_individual_result(asn, start_date, end_date, measurement_id, result_data): 
    cache_dir = get_results_cache_dir(asn, start_date, end_date)
    cache_file = cache_dir / f"measurement_{measurement_id}.parquet"
     
    if isinstance(result_data, list):
        df = pd.DataFrame(result_data)
    else:
        df = pd.DataFrame([result_data])
        
    df.to_parquet(cache_file, index=False)


def get_latency_cache_path(asn, start_date, end_date, seed_offset=0): 
    cache_dir = Path(__file__).parent / "cache"
    cache_dir.mkdir(exist_ok=True)
    return cache_dir / f"latencies_{asn}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}_seed{seed_offset}.parquet"


def load_latency_cache(asn, start_date, end_date, seed_offset=0): 
    cache_path = get_latency_cache_path(asn, start_date, end_date, seed_offset)
    if cache_path.exists():
        df = pd.read_parquet(cache_path)
         
        meta = df.attrs if hasattr(df, 'attrs') else {}
        failed_count = meta.get('failed_measurements_count', 0)
        
        return {
            'latencies': df['latencies'].tolist(),
            'endtimes': df['endtimes'].tolist(),
            'failed_measurements_count': failed_count
        }
    return None


def save_latency_cache(asn, start_date, end_date, latencies, endtimes, failed_measurements_count, seed_offset=0):
    cache_path = get_latency_cache_path(asn, start_date, end_date, seed_offset)
    
    df = pd.DataFrame({
        'latencies': latencies,
        'endtimes': endtimes
    })
     
    df.attrs['failed_measurements_count'] = failed_measurements_count
    df.to_parquet(cache_path, index=False)