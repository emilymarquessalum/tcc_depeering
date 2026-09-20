


from src.utils.graphs import plot_list_as_line_plot


import matplotlib.pyplot as plt
import numpy as np

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

def plot_enhanced_latency(latencies, endtimes, event_date=None, bin_size='1D'):
    """
    Groups latencies into uniform time intervals (e.g. daily) so p50 and min 
    can actually be calculated across multiple measurements.
    """
    # Create binned dictionary grouped by date (e.g., YYYY-MM-DD)
    endtime_to_latencies = {}
    for latency, endtime in zip(latencies, endtimes):
        if hasattr(endtime, 'strftime'):
            # Group by day; use '%Y-%m-%d %H:00' for hourly binning
            time_key = endtime.strftime('%Y-%m-%d')
        else:
            time_key = endtime

        endtime_to_latencies.setdefault(time_key, []).append(latency)

    # Sort keys chronologically
    sorted_keys = sorted(endtime_to_latencies.keys())
    
    # Convert string keys back to datetime objects for accurate plotting
    from datetime import datetime
    times = [datetime.strptime(k, '%Y-%m-%d') if isinstance(k, str) else k for k in sorted_keys]
    
    p50_latencies = [np.median(endtime_to_latencies[k]) for k in sorted_keys]
    min_latencies = [np.min(endtime_to_latencies[k]) for k in sorted_keys]

    plt.figure(figsize=(12, 6))
    plt.plot(times, p50_latencies, label='Median Latency (p50)', color='blue', linewidth=1.5)
    plt.plot(times, min_latencies, label='Min Latency (Path Shift)', color='green', linestyle='--', linewidth=1.5)

    if event_date:
        plt.axvline(x=event_date, color='red', linestyle=':', label='De-peering Event', linewidth=2)

    # Format X-axis for formatted date labels
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    plt.gca().xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    plt.gcf().autofmt_xdate()

    plt.title("Latency & Path Shift Over Time (FL-IX Probes)")
    plt.xlabel("Date")
    plt.ylabel("RTT (ms)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()


# LOW Relevance (doesnt provide a lot of insight)
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