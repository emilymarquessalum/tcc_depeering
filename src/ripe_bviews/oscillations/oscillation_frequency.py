


# we show the number of times the oscillating ASes oscillated in the timeline.
# allowing us to see the frequency (example: most oscillating ASes oscillated only once, but some oscillated multiple times) and the distribution of the frequency (example: how many ASes oscillated once, X many oscillated twice, etc).


import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from src.ripe_bviews.bview_labels import get_date_range_title, date_range_title_config
from src.ripe_bviews.download_and_parse.load_configs import load_configs
from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data_timeline_from_configs
from src.ripe_bviews.oscillations.bview_oscillation_logic import calculate_oscillation_metrics
from src.utils.graphs import plot_list_as_bar_plot


if __name__ == "__main__":
    
    config_name = "ixbr.json"
    ip_version = "v4"
    subfolder = config_name.replace(".json", "") + "_" + ip_version
    config = load_configs(config_name)
    
    all_stats = load_bview_data_timeline_from_configs(config, ip_version=ip_version)[0]
    
    metrics = calculate_oscillation_metrics(all_stats, use_reachables=False)

    oscillating_frequency = {}
    for asn, info in metrics.oscillation_info.items():
        num_oscillations = info["oscillations"]
        if num_oscillations not in oscillating_frequency:
            oscillating_frequency[num_oscillations] = 0
        oscillating_frequency[num_oscillations] += 1 
    
    sorted_keys = sorted(oscillating_frequency.keys())
    plot_list_as_bar_plot(sorted_keys, [oscillating_frequency[k] for k in sorted_keys],
                            title=f"Frequency of Oscillations for ASes - {config.get('name', 'Unknown')} - {date_range_title_config(config)}",
                            xlabel="Number of Oscillations",
                            ylabel="Number of ASes",    
                            subfolder=subfolder)