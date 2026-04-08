
import datetime
import os
import sys
from pathlib import Path 
import warnings

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))  
from src.ripe_bviews.download_and_parse.load_bview_data import  load_bview_data_from_api
from src.ripe_bviews.download_and_parse.load_configs import load_configs, print_config 
 

 
warnings.filterwarnings('ignore', category=UserWarning, message='.*Skipping download.*')

ip_version = "v4"
config = load_configs("ixbr.json")
config = load_configs("de-cix-amsterdam.json")
print_config(config, ip_version=ip_version)
name = config.get("name", "Unknown")
asn_and_prefix = config["asn_and_prefix"].get("asn"), config["asn_and_prefix"].get("prefix")
if ip_version == "v4":
    asn_and_prefix = config["asn_and_prefix_v6"].get("asn"), config["asn_and_prefix_v6"].get("prefix")

rrc = config["rrc"]
start_date = datetime.datetime.strptime(config["start_date"], "%Y-%m-%d")
end_date = datetime.datetime.strptime(config["end_date"], "%Y-%m-%d")
day_delta = datetime.timedelta(days=config.get("day_delta", 7))
time_str = config.get("time_str", "0000")
time_delta_hours = config.get("time_delta_hours", 0) 





if __name__ == "__main__":
    results_zipped = load_bview_data_from_api(config, ip_version=ip_version)
     