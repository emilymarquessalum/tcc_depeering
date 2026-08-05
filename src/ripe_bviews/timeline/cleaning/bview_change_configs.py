





from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))
 
from src.ripe_bviews.download_and_parse.load_configs import get_all_configs, get_all_routeviews_configs, load_configs, save_configs


def change_all_configs_dates_temporarily(start_date, end_date, day_delta, only_routeviews=False):

    configs = get_all_configs() if not only_routeviews else get_all_routeviews_configs()

    for config in configs:

        config_loaded = load_configs(config)
        
        temp_start = config_loaded["start_date"]
        temp_end = config_loaded["end_date"]
        temp_day_delta = config_loaded.get("day_delta", None)
        config_loaded["start_date"] = start_date
        config_loaded["end_date"] = end_date
        config_loaded["day_delta"] = day_delta

        config_loaded["temp_start_date"] = temp_start
        config_loaded["temp_end_date"] = temp_end
        config_loaded["temp_day_delta"] = temp_day_delta
        save_configs(config_loaded, config)

def restore_all_configs_dates(only_routeviews=False):

    configs = get_all_configs() if not only_routeviews else get_all_routeviews_configs()

    for config in configs:
        config_loaded = load_configs(config)
        config_loaded["start_date"] = config_loaded["temp_start_date"] if "temp_start_date" in config_loaded else config_loaded["start_date"]
        config_loaded["end_date"] = config_loaded["temp_end_date"] if "temp_end_date" in config_loaded else config_loaded["end_date"]
        config_loaded["day_delta"] = config_loaded["temp_day_delta"] if "temp_day_delta" in config_loaded else config_loaded.get("day_delta", None)
        if "temp_start_date" in config_loaded:
            del config_loaded["temp_start_date"]
        if "temp_end_date" in config_loaded:
            del config_loaded["temp_end_date"]
        if "temp_day_delta" in config_loaded:
            del config_loaded["temp_day_delta"]

        save_configs(config_loaded, config)

if __name__ == "__main__":
    change_all_configs_dates_temporarily("2024-06-01", "2024-06-16", 15, only_routeviews=True)
    #restore_all_configs_dates(only_routeviews=True)
