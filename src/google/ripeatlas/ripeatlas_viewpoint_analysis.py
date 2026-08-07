import datetime
from pathlib import Path
import sys
import requests
from collections import defaultdict
from progress.bar import Bar

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from data_loader import group_measurement_data_by_viewpoint, load_measurement_data


def fetch_probe_info_batch(probe_ids, batch_size=100):
    """
    Fetch probe information from RIPE Atlas API in batches.
    
    Args:
        probe_ids: List of probe IDs to fetch information for
        batch_size: Number of probes to fetch per request
        
    Returns:
        Dictionary with probe_id as key and probe info as value
    """
    probe_info = {}
    
    # Convert to list and remove duplicates while preserving order
    unique_probe_ids = []
    seen = set()
    for pid in probe_ids:
        if pid not in seen:
            unique_probe_ids.append(pid)
            seen.add(pid)
    
    print(f"\nFetching information for {len(unique_probe_ids)} unique probes...")
    bar = Bar(max=len(unique_probe_ids))
    
    for i in range(0, len(unique_probe_ids), batch_size):
        batch_ids = unique_probe_ids[i:i+batch_size]
        
        # Create a filter for probes in this batch
        id_filter = ",".join(map(str, batch_ids))
        url = f"https://atlas.ripe.net/api/v2/probes/?id_in={id_filter}&fields=id,country_code,asn_v4,status,first_connected,last_connected,is_public,tags"
        
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                for probe in data.get('results', []):
                    probe_info[probe['id']] = probe
                    bar.next()
            else:
                print(f"\nWarning: API returned status {response.status_code} for batch")
                for pid in batch_ids:
                    bar.next()
        except Exception as e:
            print(f"\nError fetching batch: {e}")
            for _ in batch_ids:
                bar.next()
    
    bar.finish()
    return probe_info


def analyze_viewpoint_connectivity(measurement_data_by_viewpoint, probe_info):
    """
    Analyze connectivity status and location of viewpoints.
    
    Args:
        measurement_data_by_viewpoint: Dict of probe_id -> measurements
        probe_info: Dict of probe_id -> probe info from API
        
    Returns:
        Dictionary with analysis results
    """
    analysis = {
        'total_viewpoints': len(measurement_data_by_viewpoint),
        'connected': 0,
        'disconnected': 0,
        'unknown': 0,
        'by_country': defaultdict(int),
        'by_status': defaultdict(int),
        'connected_by_country': defaultdict(int),
        'disconnected_by_country': defaultdict(int),
        'probe_details': {}
    }
    
    for probe_id, measurements in measurement_data_by_viewpoint.items():
        info = probe_info.get(probe_id, {})
        status = info.get('status', {})
        status_name = status.get('name', 'Unknown') if isinstance(status, dict) else str(status)
        country = info.get('country_code', 'XX')
        asn = info.get('asn_v4', 'N/A')
        is_public = info.get('is_public', False)
        first_connected = info.get('first_connected')
        last_connected = info.get('last_connected')
        
        # Record probe details
        analysis['probe_details'][probe_id] = {
            'country': country,
            'status': status_name,
            'asn': asn,
            'is_public': is_public,
            'measurement_count': len(measurements),
            'first_connected': first_connected,
            'last_connected': last_connected
        }
        
        # Update statistics
        analysis['by_country'][country] += 1
        analysis['by_status'][status_name] += 1
        
        if status_name == 'Connected':
            analysis['connected'] += 1
            analysis['connected_by_country'][country] += 1
        elif status_name == 'Disconnected':
            analysis['disconnected'] += 1
            analysis['disconnected_by_country'][country] += 1
        else:
            analysis['unknown'] += 1
    
    return analysis


def print_analysis_summary(analysis):
    """
    Print a summary of the viewpoint analysis.
    
    Args:
        analysis: Dictionary from analyze_viewpoint_connectivity
    """
    print("\n" + "="*70)
    print("VIEWPOINT CONNECTIVITY AND LOCATION ANALYSIS")
    print("="*70)
    
    total = analysis['total_viewpoints']
    print(f"\nTotal Viewpoints (Probes): {total}")
    print(f"  Connected:     {analysis['connected']} ({100*analysis['connected']/total:.1f}%)")
    print(f"  Disconnected:  {analysis['disconnected']} ({100*analysis['disconnected']/total:.1f}%)")
    print(f"  Unknown:       {analysis['unknown']} ({100*analysis['unknown']/total:.1f}%)")
    
    print("\n" + "-"*70)
    print("BREAKDOWN BY STATUS:")
    print("-"*70)
    for status, count in sorted(analysis['by_status'].items(), key=lambda x: x[1], reverse=True):
        print(f"  {status}: {count}")
    
    print("\n" + "-"*70)
    print("BREAKDOWN BY COUNTRY (All Probes):")
    print("-"*70)
    for country in sorted(analysis['by_country'].keys()):
        count = analysis['by_country'][country]
        connected_count = analysis['connected_by_country'].get(country, 0)
        disconnected_count = analysis['disconnected_by_country'].get(country, 0)
        print(f"  {country}: {count} total (Connected: {connected_count}, Disconnected: {disconnected_count})")
    
    print("\n" + "-"*70)
    print("TOP 15 COUNTRIES BY PROBE COUNT:")
    print("-"*70)
    top_countries = sorted(analysis['by_country'].items(), key=lambda x: x[1], reverse=True)[:15]
    for country, count in top_countries:
        connected_count = analysis['connected_by_country'].get(country, 0)
        print(f"  {country}: {count} probes (Connected: {connected_count})")
    
    print("\n" + "-"*70)
    print("PROBES THAT ARE DISCONNECTED:")
    print("-"*70)
    disconnected_probes = [
        (pid, details) for pid, details in analysis['probe_details'].items()
        if details['status'] == 'Disconnected'
    ]
    
    if disconnected_probes:
        print(f"Total disconnected: {len(disconnected_probes)}")
        # Show first 20 disconnected probes
        for probe_id, details in sorted(disconnected_probes, key=lambda x: x[0])[:20]:
            print(f"  Probe {probe_id}: {details['country']} (ASN: {details['asn']}, Measurements: {details['measurement_count']})")
        if len(disconnected_probes) > 20:
            print(f"  ... and {len(disconnected_probes) - 20} more")
    else:
        print("  All probes are still connected!")
    
    print("\n" + "="*70)


def export_probe_details_csv(analysis, filename='viewpoint_probe_details.csv'):
    """
    Export detailed probe information to CSV.
    
    Args:
        analysis: Dictionary from analyze_viewpoint_connectivity
        filename: Output CSV filename
    """
    import csv
    
    with open(filename, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'probe_id', 'country', 'status', 'asn', 'is_public', 
            'measurement_count', 'first_connected', 'last_connected'
        ])
        writer.writeheader()
        
        for probe_id, details in analysis['probe_details'].items():
            writer.writerow({
                'probe_id': probe_id,
                'country': details['country'],
                'status': details['status'],
                'asn': details['asn'],
                'is_public': details['is_public'],
                'measurement_count': details['measurement_count'],
                'first_connected': details['first_connected'],
                'last_connected': details['last_connected']
            })
    
    print(f"\nProbe details exported to {filename}")

print("Doesnt work")
sys.exit(0)
# Configuration
google_asn = 15169
start_date = datetime.datetime(2024, 1, 1)
end_date = datetime.datetime(2024, 6, 1)
type_exclusion_filter = "dns"
day_delta = datetime.timedelta(days=31)
sample_size = 50
seed_offset = 10

# Load measurement data
print(f"Loading measurements for ASN {google_asn} from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}...")
measurement_counts, dates_in_plot, measurement_data = load_measurement_data(
    start_date, end_date, google_asn, type_exclusion_filter, day_delta, 
    sample_size=sample_size, seed_offset=seed_offset
)

# Group by viewpoint
print("\nGrouping measurements by viewpoint...")
measurement_data_by_viewpoint = group_measurement_data_by_viewpoint(measurement_data)

# Extract probe IDs
probe_ids = list(measurement_data_by_viewpoint.keys())
print(f"Found {len(probe_ids)} unique viewpoints (probes) that measured to Google")

# Fetch probe information from RIPE Atlas API
probe_info = fetch_probe_info_batch(probe_ids, batch_size=100)

# Analyze connectivity
analysis = analyze_viewpoint_connectivity(measurement_data_by_viewpoint, probe_info)

# Print summary
print_analysis_summary(analysis)

# Export to CSV
try:
    export_probe_details_csv(analysis)
except Exception as e:
    print(f"Warning: Could not export CSV: {e}")

print("\nAnalysis complete!")
