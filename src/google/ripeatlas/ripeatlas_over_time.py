import datetime
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.utils.graphs import plot_list_as_line_plot
from data_loader import load_measurement_data


def extract_probe_id(measurement):
    """Extract probe ID from a measurement dict."""
    if not isinstance(measurement, dict):
        return None
    
    measurement_results = measurement.get("result")
    if not measurement_results or not isinstance(measurement_results, list) or len(measurement_results) == 0:
        return None
    
    first_result = measurement_results[0]
    if not isinstance(first_result, dict):
        return None
    
    return first_result.get("prb_id")


def plot_viewpoints_over_time(asn, start_date, end_date, type_exclusion_filter="dns", 
                               day_delta=None, sample_size=100, seed_offset=10):
    """
    Plot the number of unique viewpoints over time for a given ASN.
    
    Args:
        asn: Autonomous System Number to analyze
        start_date: Start date (datetime object)
        end_date: End date (datetime object)
        type_exclusion_filter: Type of measurements to exclude (default: "dns")
        day_delta: Time interval for grouping (default: 31 days)
        sample_size: Number of samples per interval (default: 100)
        seed_offset: Random seed offset (default: 10)
    """
    if day_delta is None:
        day_delta = datetime.timedelta(days=31)
     
    print(f"Loading measurement data for ASN {asn} from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}...")
    
    measurement_counts, _, measurement_data = load_measurement_data(
        start_date, end_date, asn, type_exclusion_filter, 
        day_delta, sample_size=sample_size, seed_offset=seed_offset
    )
    
    # measurement_data is a list of lists (one list per interval)
    # Each element is a list of measurement dicts
    viewpoint_counts_per_interval = []
    intervals = []
    current_date = start_date
    
    for interval_measurements in measurement_data:
        # Count unique viewpoints in this interval
        viewpoints_in_interval = set()
        
        for measurement in interval_measurements:
            probe_id = extract_probe_id(measurement)
            if probe_id:
                viewpoints_in_interval.add(probe_id)
        
        viewpoint_counts_per_interval.append(len(viewpoints_in_interval))
        intervals.append(current_date)
        current_date += day_delta
    
    print(f"✓ Loaded {sum(measurement_counts)} total measurements")
    print(f"✓ Found data across {len(intervals)} time intervals")
    print(f"✓ Viewpoint counts per interval: {viewpoint_counts_per_interval}")
    
    # Plot viewpoints over time
    plot_list_as_line_plot(
        viewpoint_counts_per_interval,
        y=list(range(len(viewpoint_counts_per_interval))),
        title=f'Number of Viewpoints Over Time for ASN {asn} - From {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")}',
        xlabel='Time Interval Index',
        ylabel='Number of Unique Viewpoints'
    )
    
    # Also plot with dates on y-axis for better readability
    plot_list_as_line_plot(
        viewpoint_counts_per_interval,
        y=intervals,
        title=f'Number of Viewpoints Over Time for ASN {asn} - From {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")} (by Date)',
        xlabel='Time',
        ylabel='Number of Unique Viewpoints'
    )
    
    return viewpoint_counts_per_interval, intervals


if __name__ == "__main__":
    # Example usage
    google_asn = 15169
    start_date = datetime.datetime(2024, 1, 1)
    end_date = datetime.datetime(2025, 6, 1)
    
    viewpoint_counts, intervals = plot_viewpoints_over_time(
        asn=google_asn,
        start_date=start_date,
        end_date=end_date,
        day_delta=datetime.timedelta(days=31),
        seed_offset=10
    )
