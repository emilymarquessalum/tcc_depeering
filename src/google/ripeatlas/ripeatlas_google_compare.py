import datetime
from pathlib import Path
import sys
from collections import Counter
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import pandas as pd
from tableone import TableOne

from data_loader import group_measurement_data_by_viewpoint, load_measurement_data
from ripeatlas_route_diversity import calculate_route_diversity, calculate_prefix_diversity


def match_viewpoints(year1=2024, year2=2026):
    """
    Compare viewpoints between Google measurements in two years (Jan-Jun)
    
    Args:
        year1: First year to compare (default: 2024)
        year2: Second year to compare (default: 2026)
    """
    google_asn = 15169
    type_exclusion_filter = "dns"
    day_delta = datetime.timedelta(days=31)
    SAMPLE_SEED_OFFSET = 16
    
    # Load year1 data (Jan 1 - Jun 1)
    start_date_year1 = datetime.datetime(year1, 1, 1)
    end_date_year1 = datetime.datetime(year1, 6, 1)
    
    print(f"Loading {year1} measurement data (Jan 1 - Jun 1)...")
    _, _, measurement_data_year1 = load_measurement_data(
        start_date_year1, end_date_year1, google_asn, 
        type_exclusion_filter, day_delta, 
        sample_size=100,
        seed_offset=SAMPLE_SEED_OFFSET
    )
    
    measurement_data_by_viewpoint_year1 = group_measurement_data_by_viewpoint(measurement_data_year1)
    viewpoints_year1 = set(measurement_data_by_viewpoint_year1.keys())
    measurements_year1 = list(measurement_data_year1)
    
    print(f"✓ Loaded {len(measurements_year1)} measurements from {len(viewpoints_year1)} viewpoints in {year1}")
    
    # Load year2 data (Jan 1 - Jun 1)
    start_date_year2 = datetime.datetime(year2, 1, 1)
    end_date_year2 = datetime.datetime(year2, 6, 1)
    
    print(f"Loading {year2} measurement data (Jan 1 - Jun 1)...")
    _, _, measurement_data_year2 = load_measurement_data(
        start_date_year2, end_date_year2, google_asn, 
        type_exclusion_filter, day_delta, 
        sample_size=100,
        seed_offset=SAMPLE_SEED_OFFSET
    )
    
    measurement_data_by_viewpoint_year2 = group_measurement_data_by_viewpoint(measurement_data_year2)
    viewpoints_year2 = set(measurement_data_by_viewpoint_year2.keys())
    measurements_year2 = list(measurement_data_year2)
    
    print(f"✓ Loaded {len(measurements_year2)} measurements from {len(viewpoints_year2)} viewpoints in {year2}")
    
    # Calculate matching viewpoints
    matching_viewpoints = viewpoints_year1.intersection(viewpoints_year2)
    total_unique_viewpoints = viewpoints_year1.union(viewpoints_year2)
    
    print("\n" + "="*70)
    print(f"VIEWPOINT COMPARISON: {year1} vs {year2}")
    print("="*70)
    
    # 1. Percentage of viewpoint matching
    viewpoint_match_percentage = (len(matching_viewpoints) / len(total_unique_viewpoints)) * 100
    print(f"\n1. VIEWPOINT MATCHING:")
    print(f"   Total unique viewpoints ({year1} & {year2}): {len(total_unique_viewpoints)}")
    print(f"   Matching viewpoints: {len(matching_viewpoints)}")
    print(f"   % of viewpoint matching: {viewpoint_match_percentage:.2f}%")
    
    # 2. Percentage of measurements without matching viewpoints
    viewpoints_only_year1 = viewpoints_year1 - viewpoints_year2
    viewpoints_only_year2 = viewpoints_year2 - viewpoints_year1
    
    measurements_without_viewpoint_year1 = sum(
        len(measurement_data_by_viewpoint_year1[vp]) 
        for vp in viewpoints_only_year1
    )
    
    measurements_without_viewpoint_year2 = sum(
        len(measurement_data_by_viewpoint_year2[vp]) 
        for vp in viewpoints_only_year2
    )
    
    pct_year1_no_match_year2 = (measurements_without_viewpoint_year1 / len(measurements_year1)) * 100
    pct_year2_no_match_year1 = (measurements_without_viewpoint_year2 / len(measurements_year2)) * 100
    
    print(f"\n2. MEASUREMENTS WITHOUT MATCHING VIEWPOINTS:")
    print(f"   {year1} measurements with viewpoints NOT in {year2}:")
    print(f"      Count: {measurements_without_viewpoint_year1} / {len(measurements_year1)}")
    print(f"      Percentage: {pct_year1_no_match_year2:.2f}%")
    print(f"      (Affected viewpoints: {len(viewpoints_only_year1)})")
    
    print(f"\n   {year2} measurements with viewpoints NOT in {year1}:")
    print(f"      Count: {measurements_without_viewpoint_year2} / {len(measurements_year2)}")
    print(f"      Percentage: {pct_year2_no_match_year1:.2f}%")
    print(f"      (Affected viewpoints: {len(viewpoints_only_year2)})")
    
    # 3. Top 5 viewpoints
    viewpoint_counts_year1 = Counter({vp: len(measurement_data_by_viewpoint_year1[vp]) 
                                     for vp in viewpoints_year1})
    viewpoint_counts_year2 = Counter({vp: len(measurement_data_by_viewpoint_year2[vp]) 
                                     for vp in viewpoints_year2})
    
    top5_year1 = viewpoint_counts_year1.most_common(5)
    top5_year2 = viewpoint_counts_year2.most_common(5)
    
    print(f"\n3. TOP 5 VIEWPOINTS:")
    print(f"\n   {year1} (Jan 1 - Jun 1):")
    for i, (viewpoint, count) in enumerate(top5_year1, 1):
        in_year2 = f"✓ in {year2}" if viewpoint in viewpoints_year2 else f"✗ NOT in {year2}"
        print(f"      {i}. Viewpoint {viewpoint}: {count} measurements {in_year2}")
    
    print(f"\n   {year2} (Jan 1 - Jun 1):")
    for i, (viewpoint, count) in enumerate(top5_year2, 1):
        in_year1 = f"✓ in {year1}" if viewpoint in viewpoints_year1 else f"✗ NOT in {year1}"
        print(f"      {i}. Viewpoint {viewpoint}: {count} measurements {in_year1}")
    
    print("\n" + "="*70)


def print_metrics_table(periods, google_asn=15169, type_exclusion_filter="dns"):
    """
    Calculate and print route diversity and prefix diversity metrics in a table format
    for multiple time periods.
    
    Args:
        periods: List of tuples, each containing (start_date, end_date)
                 where dates are datetime.datetime objects
        google_asn: The ASN to analyze (default: 15169 for Google)
        type_exclusion_filter: Type of measurements to exclude (default: "dns")
    
    Example:
        periods = [
            (datetime.datetime(2024, 1, 1), datetime.datetime(2024, 6, 1)),
            (datetime.datetime(2025, 1, 1), datetime.datetime(2025, 6, 1)),
            (datetime.datetime(2026, 1, 1), datetime.datetime(2026, 6, 1)),
        ]
        print_metrics_table(periods)
    """
    day_delta = datetime.timedelta(days=31)
    SAMPLE_SEED_OFFSET = 16
    
    # Collect metrics for each period
    metrics_list = []
    
    for start_date, end_date in periods:
        print(f"Loading {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}...")
        
        try:
            # Load measurement data
            _, _, measurement_data = load_measurement_data(
                start_date, end_date, google_asn,
                type_exclusion_filter, day_delta,
                sample_size=100,
                seed_offset=SAMPLE_SEED_OFFSET
            )
            
            if not measurement_data:
                print(f"  ⚠ No data available for this period")
                metrics_list.append({
                    'Period': f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
                    'Unique Paths': 'N/A',
                    'Total Measurements': 'N/A',
                    'Diversity Ratio': 'N/A',
                    'Unique /24 Prefixes': 'N/A',
                    'Total Unique IPs': 'N/A',
                    'Total IPs Seen': 'N/A',
                    'Prefix Diversity Ratio': 'N/A',
                })
                continue
            
            # Calculate route diversity
            route_diversity = calculate_route_diversity(measurement_data)
            
            # Calculate prefix diversity
            prefix_diversity = calculate_prefix_diversity(measurement_data, prefix_length=24)
            
            metrics_list.append({
                'Period': f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
                'Unique Paths': route_diversity['unique_as_paths'],
                'Total Measurements': route_diversity['total_measurements'],
                'Diversity Ratio': f"{route_diversity['diversity_score']:.4f}",
                'Avg Path Length': f"{route_diversity['avg_path_length']:.2f}",
                'Path Length Dist': route_diversity['path_length_distribution'],
                'Unique /24 Prefixes': prefix_diversity['unique_prefixes'],
                'Total Unique IPs': prefix_diversity['total_unique_ips'],
                'Total IPs Seen': prefix_diversity['total_ips_seen'],
                'Prefix Diversity Ratio': f"{prefix_diversity['prefix_diversity_score']:.4f}",
            })
            
        except Exception as e:
            print(f"  ✗ Error processing period: {e}")
            metrics_list.append({
                'Period': f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
                'Unique Paths': 'ERROR',
                'Total Measurements': 'ERROR',
                'Diversity Ratio': 'ERROR',
                'Unique /24 Prefixes': 'ERROR',
                'Total Unique IPs': 'ERROR',
                'Total IPs Seen': 'ERROR',
                'Prefix Diversity Ratio': 'ERROR',
            })
    
    # Print table
    if not metrics_list:
        print("No metrics to display")
        return
     

    df_for_paths = pd.DataFrame([{
        'Period': m['Period'],
        'Total Measurements': m['Total Measurements'],
        'Unique Paths': m['Unique Paths'],
        'Diversity Ratio': str(float(m['Diversity Ratio'])*100)[:5] + "\%"
    } for m in metrics_list])

    df_for_ip = pd.DataFrame([{
        'Period': m['Period'],
        #'Unique /24 Prefixes': m['Unique /24 Prefixes'],
        'Total IPs Seen': m['Total IPs Seen'],
        'Total Unique IPs': m['Total Unique IPs'],
        'IP Diversity Ratio': str(float(m['Prefix Diversity Ratio'])*100)[:5] + "\%"
    } for m in metrics_list])
    
    # Tried using this but it displays a lot of uneeded things
    '''
    table = TableOne(
        data=df,
        columns=['Unique Paths', 'Total Measurements', 'Diversity Ratio', 
                 'Unique /24 Prefixes', 'Total Unique IPs', 'Total IPs Seen', 'Prefix Diversity Ratio'],
        groupby='Period',
        pval=False,
        htest=False
    )'''

    # Convert directly to a clean, publication-ready LaTeX block
    latex_code_ips = df_for_ip.to_latex(
        index=False, 
        caption="IP-Diversity Metrics for Different Time Periods, for Google (AS15169) RIPE Atlas Measurements", 
        label="tab:viewpoints_comparison",
        column_format="lccc" # Aligns columns: left, center, center, center
    )

    
    print(latex_code_ips)

    latex_code_paths = df_for_paths.to_latex(
        index=False, 
        caption="Route-Diversity Metrics for Different Time Periods, for Google (AS15169) RIPE Atlas Measurements", 
        label="tab:route_diversity_comparison",
        column_format="lccc" # Aligns columns: left, center, center, center
    )

    print(latex_code_paths)

    # Create path length table
    df_for_path_length = pd.DataFrame([{
        'Period': m['Period'],
        'Avg Path Length': m['Avg Path Length'],
        'Path Length Distribution': str(m['Path Length Dist']).replace("'", "")
    } for m in metrics_list])

    latex_code_path_length = df_for_path_length.to_latex(
        index=False, 
        caption="AS Path Length Metrics for Different Time Periods, for Google (AS15169) RIPE Atlas Measurements", 
        label="tab:path_length_comparison",
        column_format="lcc"
    )

    print(latex_code_path_length)

if __name__ == "__main__":
    # Compare any two years (default: 2024 vs 2026)
    # Examples: match_viewpoints(2024, 2025) or match_viewpoints(2025, 2026)
    #match_viewpoints(year1=2025, year2=2026)

    # Print metrics table for multiple periods
    periods_to_analyze = [
        (datetime.datetime(2024, 1, 1), datetime.datetime(2024, 6, 1)),
        (datetime.datetime(2025, 1, 1), datetime.datetime(2025, 6, 1)),
        (datetime.datetime(2026, 1, 1), datetime.datetime(2026, 6, 1)),
    ]
    print_metrics_table(periods_to_analyze)
