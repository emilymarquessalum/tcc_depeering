




from datetime import datetime, timedelta

from src.ripe_bviews.bview_labels import get_max_labels, summarized_date_labels
from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data_from_api, load_bview_data_timeline_from_configs
from src.ripe_bviews.download_and_parse.load_configs import get_all_configs, get_all_routeviews_configs, load_configs 
from src.ripe_bviews.oscillations.bview_oscillation_logic import calculate_oscillation_metrics
from src.ripe_bviews.timeline.bview_timeline import get_stats_by_analyzed_period
from src.ripe_bviews.timeline.bview_timeline import get_stats_by_analyzed_period
from src.ripe_bviews.timeline.bview_vars import get_ip_version



def load_all_timelines_first_date(_config, _ip_version, _all_stats):
    configs = get_all_configs()

    first_dates = {}
    for config_name, config in configs.items():
        pass        


def load_all_routeviews_timelines_first_date_function(all_required_data):
    
    
    configs = get_all_configs()
    #configs = get_all_routeviews_configs()
    
    for config_path in configs:

        config = load_configs(config_path)
        if "routeserver-folder-name" not in config:
            continue
        
        config["end_date"] = (datetime.strptime(config['start_date'], "%Y-%m-%d") + timedelta(
            days=config["day_delta"], hours=config.get("time_delta_hours", 0)
        ) ).strftime("%Y-%m-%d") 
        load_bview_data_from_api(config, ip_version=get_ip_version(config), load_from_routeviews=True)
  
 

def load_all_routeviews_timelines_first_date(config, ip_version, all_stats):
 
    configs = get_all_configs()

    data = {}
     
    loss_acceptange = 10
    loss_acceptance_count = 0

    for config_path in configs:

        config = load_configs(config_path)
        if "routeserver-folder-name" not in config:
            continue
        
        config["end_date"] = (datetime.strptime(config['start_date'], "%Y-%m-%d") + timedelta(
            days=config["day_delta"], hours=config.get("time_delta_hours", 0)
        ) ).strftime("%Y-%m-%d") 
        try:
            all_stats, labels = load_bview_data_timeline_from_configs(config, ip_version=ip_version,
                                                                ignored_dates=["20251205.0000", 
                                                                ], 
                                load_from_routeviews=True
                                                                )    
            
            data[config["name"]] = all_stats

        except Exception as e:
            loss_acceptance_count += 1
            print(f"[WARNING] Failed to load data for config {config['name']}: {e}. Loss acceptance count: {loss_acceptance_count}/{loss_acceptange}")
            if loss_acceptance_count > loss_acceptange:
                print(f"[ERROR] Exceeded loss acceptance limit of {loss_acceptange}. Aborting.")
                raise e
    return data 

    

def load_timeline(config, ip_version, all_stats=None, load_from_routeviews=False, max_iterations=None):

    if "rrc" not in config:
        load_from_routeviews = True

    load_from_both = False

    if "use" in config:
        if config["use"] == "rrc":
            load_from_routeviews = False
        elif config["use"] == "routeserver-folder-name":
            load_from_routeviews = True
        elif config["use"] == "both":
            load_from_both = True
        else:
            print(f"Invalid value for 'use' in config: {config['use']}. Using default use of routeserver: {load_from_routeviews}.") 
    
    print("[DEBUG] loading options - load_from_routeviews:", load_from_routeviews, "load_from_both:", load_from_both)
    all_stats, labels = load_bview_data_timeline_from_configs(config, ip_version=ip_version,
                                                              ignored_dates=["20251205.0000", 
                                                                             "20251124.0000" # for whatever reason this date didnt load
                                                              ], 
                            load_from_routeviews=load_from_routeviews,
                            load_from_both_routeviews_and_rrc=load_from_both,
                            max_iterations=max_iterations
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
    oscillation_metrics = calculate_oscillation_metrics(
        all_stats,
        snapshots_for_real_depeering=config.get("snapshots_for_real_depeering", 0),
    )
    oscillation_metrics.load_oscillating_lists()
    return oscillation_metrics