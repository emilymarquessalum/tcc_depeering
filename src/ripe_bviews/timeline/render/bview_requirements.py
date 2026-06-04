




from src.ripe_bviews.bview_labels import get_max_labels, summarized_date_labels
from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data_timeline_from_configs
from src.ripe_bviews.oscillations.bview_oscillation_logic_pandas import calculate_oscillation_metrics
from src.ripe_bviews.timeline.bview_timeline import get_stats_by_analyzed_period
from src.ripe_bviews.timeline.bview_timeline import get_stats_by_analyzed_period


def load_timeline(config, ip_version, all_stats=None):
    all_stats, labels = load_bview_data_timeline_from_configs(config, ip_version=ip_version,
                                                              ignored_dates=["20251205.0000", 
                                                              ], 
                                                              )    
    
    labels_summarized = summarized_date_labels(labels)
    max_labels= get_max_labels(labels)
    return all_stats, labels_summarized, max_labels


def _get_retroactive_all_stats(config, ip_version, all_stats):
    if all_stats is None:
        return load_timeline(config, ip_version)[0]
    
    return all_stats[0] if isinstance(all_stats, tuple) else all_stats


def load_timeline_weekly(config, ip_version, all_stats=None):

    if all_stats is None:
        all_stats, labels, _ = load_timeline(config, ip_version)
    else:
        all_stats, labels, _ = all_stats

    stats_analyzed, labels_analyzed = get_stats_by_analyzed_period(all_stats, labels, stats_are_daily_separated=True)

    return stats_analyzed, labels_analyzed

def load_oscillations(config, ip_version, all_stats=None):
    
    all_stats = _get_retroactive_all_stats(config, ip_version, all_stats)
    oscillation_metrics = calculate_oscillation_metrics(all_stats)
    oscillation_metrics.load_oscillating_lists()
    return oscillation_metrics