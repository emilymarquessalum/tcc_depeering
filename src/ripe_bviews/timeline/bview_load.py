
import datetime
import os
import sys
from pathlib import Path 
import warnings
# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))  

from src.ripe_bviews.download_and_parse.load_bview_data import  load_bview_data_from_api
from src.ripe_bviews.download_and_parse.load_configs import load_configs, print_config  
from src.ripe_bviews.timeline.bview_vars import get_ip_version
 
warnings.filterwarnings('ignore', category=UserWarning, message='.*Skipping download.*')



def load_bview_data(all_required_data):
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


if __name__ == "__main__":

    config = load_configs("ixbr.json")
    
    config = load_configs("AMS-IX.json")
    #config = load_configs("MIX-IT.json")
    config = load_configs("NAPAfrica.json")

    ip_version = get_ip_version(config)

    load_bview_data({"config": config, "ip_version": ip_version})