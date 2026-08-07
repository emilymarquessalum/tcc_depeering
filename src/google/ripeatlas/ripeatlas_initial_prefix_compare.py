import datetime
from pathlib import Path
import sys
from collections import Counter, defaultdict
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from data_loader import load_measurement_data


def extract_initial_prefix_from_hops(measurement, prefix_length=24):
    """
    Extract the initial prefix (first hop) from a measurement's hops.
    Returns the prefix in CIDR notation (e.g., '192.168.1.0/24')
    """
    if 'result' not in measurement or not measurement['result']:
        return None
    
    result_data = measurement['result']
    if not isinstance(result_data, list) or len(result_data) == 0:
        return None
    
    # Get the first measurement result
    first_result = result_data[0]
    if not isinstance(first_result, dict) or 'result' not in first_result:
        return None
    
    # Get the hops from the first result
    hops = first_result['result']
    if not isinstance(hops, list) or len(hops) == 0:
        return None
    
    # Find the first hop with a 'from' field
    first_ip = None
    for hop in hops:
        if isinstance(hop, dict) and 'from' in hop:
            first_ip = hop['from']
            break
    
    if not first_ip:
        return None
    
    # Convert IP to prefix
    try:
        import ipaddress
        network = ipaddress.ip_network(f"{first_ip}/{prefix_length}", strict=False)
        return str(network)
    except Exception:
        return None


def group_measurement_data_by_initial_prefix(measurement_data, prefix_length=24):
    """
    Group measurements by initial prefix of hops
    """
    prefix_to_measurements = defaultdict(list)
    
    for measurement in measurement_data:
        prefix = extract_initial_prefix_from_hops(measurement, prefix_length)
        if prefix:
            prefix_to_measurements[prefix].append(measurement)
    
    return dict(prefix_to_measurements)


def compare_initial_prefixes_2024_vs_2026():
    """
    Compare initial prefixes (grouped viewpoints) between Google measurements in 2024 (Jan-Jun) and 2026
    """
    google_asn = 15169
    type_exclusion_filter = "dns"
    day_delta = datetime.timedelta(days=31)
    SAMPLE_SEED_OFFSET = 10
    PREFIX_LENGTH = 24
    
    # Load 2024 data (Jan 1 - Jun 1)
    start_date_2024 = datetime.datetime(2024, 1, 1)
    end_date_2024 = datetime.datetime(2024, 6, 1)
    
    print("Loading 2024 measurement data (Jan 1 - Jun 1)...")
    _, _, measurement_data_2024_nested = load_measurement_data(
        start_date_2024, end_date_2024, google_asn, 
        type_exclusion_filter, day_delta, seed_offset=SAMPLE_SEED_OFFSET
    )
    
    # Flatten the nested list structure
    measurement_data_2024 = [m for interval in measurement_data_2024_nested for m in interval]
    
    measurement_data_by_prefix_2024 = group_measurement_data_by_initial_prefix(measurement_data_2024, PREFIX_LENGTH)
    prefixes_2024 = set(measurement_data_by_prefix_2024.keys())
    measurements_2024 = list(measurement_data_2024)
    
    print(f"✓ Loaded {len(measurements_2024)} measurements from {len(prefixes_2024)} initial prefixes in 2024")
    
    # Load 2026 data (Jan 1 - Jun 1)
    start_date_2026 = datetime.datetime(2026, 1, 1)
    end_date_2026 = datetime.datetime(2026, 6, 1)
    
    print("Loading 2026 measurement data (Jan 1 - Jun 1)...")
    _, _, measurement_data_2026_nested = load_measurement_data(
        start_date_2026, end_date_2026, google_asn, 
        type_exclusion_filter, day_delta, seed_offset=SAMPLE_SEED_OFFSET
    )
    
    # Flatten the nested list structure
    measurement_data_2026 = [m for interval in measurement_data_2026_nested for m in interval]
    
    measurement_data_by_prefix_2026 = group_measurement_data_by_initial_prefix(measurement_data_2026, PREFIX_LENGTH)
    prefixes_2026 = set(measurement_data_by_prefix_2026.keys())
    measurements_2026 = list(measurement_data_2026)
    
    print(f"✓ Loaded {len(measurements_2026)} measurements from {len(prefixes_2026)} initial prefixes in 2026")
    
    # Calculate matching prefixes
    matching_prefixes = prefixes_2024.intersection(prefixes_2026)
    total_unique_prefixes = prefixes_2024.union(prefixes_2026)
    
    print("\n" + "="*70)
    print("INITIAL PREFIX COMPARISON: 2024 vs 2026 (/24 networks)")
    print("="*70)
    
    # 1. Percentage of prefix matching
    prefix_match_percentage = (len(matching_prefixes) / len(total_unique_prefixes)) * 100 if total_unique_prefixes else 0
    print(f"\n1. PREFIX MATCHING:")
    print(f"   Total unique prefixes (2024 ∪ 2026): {len(total_unique_prefixes)}")
    print(f"   Matching prefixes: {len(matching_prefixes)}")
    print(f"   % of prefix matching: {prefix_match_percentage:.2f}%")
    
    # 2. Percentage of measurements without matching prefixes
    prefixes_only_2024 = prefixes_2024 - prefixes_2026
    prefixes_only_2026 = prefixes_2026 - prefixes_2024
    
    measurements_without_prefix_2024 = sum(
        len(measurement_data_by_prefix_2024[prefix]) 
        for prefix in prefixes_only_2024
    )
    
    measurements_without_prefix_2026 = sum(
        len(measurement_data_by_prefix_2026[prefix]) 
        for prefix in prefixes_only_2026
    )
    
    pct_2024_no_match_2026 = (measurements_without_prefix_2024 / len(measurements_2024)) * 100 if measurements_2024 else 0
    pct_2026_no_match_2024 = (measurements_without_prefix_2026 / len(measurements_2026)) * 100 if measurements_2026 else 0
    
    print(f"\n2. MEASUREMENTS WITHOUT MATCHING PREFIXES:")
    print(f"   2024 measurements with prefixes NOT in 2026:")
    print(f"      Count: {measurements_without_prefix_2024} / {len(measurements_2024)}")
    print(f"      Percentage: {pct_2024_no_match_2026:.2f}%")
    print(f"      (Affected prefixes: {len(prefixes_only_2024)})")
    
    print(f"\n   2026 measurements with prefixes NOT in 2024:")
    print(f"      Count: {measurements_without_prefix_2026} / {len(measurements_2026)}")
    print(f"      Percentage: {pct_2026_no_match_2024:.2f}%")
    print(f"      (Affected prefixes: {len(prefixes_only_2026)})")
    
    # 3. Top 5 prefixes
    prefix_counts_2024 = Counter({prefix: len(measurement_data_by_prefix_2024[prefix]) 
                                   for prefix in prefixes_2024})
    prefix_counts_2026 = Counter({prefix: len(measurement_data_by_prefix_2026[prefix]) 
                                   for prefix in prefixes_2026})
    
    top5_2024 = prefix_counts_2024.most_common(5)
    top5_2026 = prefix_counts_2026.most_common(5)
    
    print(f"\n3. TOP 5 INITIAL PREFIXES:")
    print(f"\n   2024 (Jan 1 - Jun 1):")
    for i, (prefix, count) in enumerate(top5_2024, 1):
        in_2026 = "✓ in 2026" if prefix in prefixes_2026 else "✗ NOT in 2026"
        print(f"      {i}. Prefix {prefix}: {count} measurements {in_2026}")
    
    print(f"\n   2026 (Jan 1 - Jun 1):")
    for i, (prefix, count) in enumerate(top5_2026, 1):
        in_2024 = "✓ in 2024" if prefix in prefixes_2024 else "✗ NOT in 2024"
        print(f"      {i}. Prefix {prefix}: {count} measurements {in_2024}")
    
    # 4. All prefix comparison counts
    print(f"\n4. ALL PREFIX COMPARISON COUNTS:")
    print(f"\n   Prefixes present in BOTH 2024 and 2026:")
    matching_prefix_counts = sorted(
        [(prefix, prefix_counts_2024[prefix], prefix_counts_2026[prefix]) 
         for prefix in matching_prefixes],
        key=lambda x: x[1] + x[2],
        reverse=True
    )
    if matching_prefix_counts:
        for prefix, count_2024, count_2026 in matching_prefix_counts:
            print(f"      {prefix}: 2024={count_2024}, 2026={count_2026}")
    else:
        print(f"      (None)")
    
    print(f"\n   Prefixes ONLY in 2024 (not in 2026):")
    only_2024_counts = sorted(
        [(prefix, prefix_counts_2024[prefix]) for prefix in prefixes_only_2024],
        key=lambda x: x[1],
        reverse=True
    )
    if only_2024_counts:
        for prefix, count in only_2024_counts:
            print(f"      {prefix}: {count} measurements")
    else:
        print(f"      (None)")
    
    print(f"\n   Prefixes ONLY in 2026 (not in 2024):")
    only_2026_counts = sorted(
        [(prefix, prefix_counts_2026[prefix]) for prefix in prefixes_only_2026],
        key=lambda x: x[1],
        reverse=True
    )
    if only_2026_counts:
        for prefix, count in only_2026_counts:
            print(f"      {prefix}: {count} measurements")
    else:
        print(f"      (None)")
    
    print("\n" + "="*70)


if __name__ == "__main__":
    compare_initial_prefixes_2024_vs_2026()
