
import datetime
import os
import sys
from pathlib import Path 
import warnings
# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))  

from src.ripe_bviews.download_and_parse.load_bview_data import  load_bview_asn_data_from_collector_api, load_bview_data_from_api
from src.ripe_bviews.download_and_parse.load_configs import get_all_routeviews_configs, load_configs, print_config  
from src.ripe_bviews.timeline.bview_vars import get_ip_version
 
warnings.filterwarnings('ignore', category=UserWarning, message='.*Skipping download.*')


def bview_load_all_routeviews_data(all_required_data):

    configs_for_routeviews = get_all_routeviews_configs()
    for config_file in configs_for_routeviews:
        print(f"\n\n=== Starting load for RouteViews config: {config_file} ===")
        config = load_configs(f"routeviews_specific/{config_file}")
        ip_version = get_ip_version(config)
        print_config(config, ip_version=ip_version)
        bview_load_data_routeviews({"config": config, "ip_version": ip_version})

def bview_load_data_routeviews(all_required_data):
    config = all_required_data.get("config")
    ip_version = get_ip_version(config)
    print_config(config, ip_version=ip_version)
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"Starting RouteViews data load at {current_time} for config: {config['name']}")

    try:
        load_bview_data_from_api(config, ip_version=ip_version, load_from_routeviews=True)
    except Exception as e:
        print(f"Error during RouteViews data load: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("RouteViews data load interrupted by user.")
        end_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"RouteViews data load interrupted at {end_time} for config: {config['name']}")
        
        sys.exit(0)

    end_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"Finished RouteViews data load at {end_time} for config: {config['name']}")

    total_time = datetime.datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S") - datetime.datetime.strptime(current_time, "%Y-%m-%d %H:%M:%S")
    print(f"Total time taken for RouteViews data load: {total_time} (in seconds: {total_time.total_seconds()})")

def bview_load_data(all_required_data):
    config = all_required_data.get("config")
    ip_version = get_ip_version(config) 
    print_config(config, ip_version=ip_version)
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"Starting data load at {current_time} for config: {config['name']}")

    try:
        load_bview_data_from_api(config, ip_version=ip_version)
    except Exception as e:
        print(f"Error during data load: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("Data load interrupted by user.")
        end_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"Data load interrupted at {end_time} for config: {config['name']}")
        
        sys.exit(0)

    end_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"Finished data load at {end_time} for config: {config['name']}")

    total_time = datetime.datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S") - datetime.datetime.strptime(current_time, "%Y-%m-%d %H:%M:%S")
    print(f"Total time taken: {total_time} (in seconds: {total_time.total_seconds()})")

 
def load_asn_collector_rrc_data(all_required_data):
    config = all_required_data.get("config")
    ip_version = get_ip_version(config)
  
    
    origin_asn = None
    while not origin_asn:
        origin_asn = input("Digite o ASN para o qual deseja buscar dados de coletores: ").strip()
    
    load_bview_asn_data_from_collector_api(config, origin_asn, ip_version=ip_version, load_from_routeviews=False)