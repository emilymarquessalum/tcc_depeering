
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

config = load_configs("ixbr.json")
 
#config = load_configs("AMS-IX.json")
#config = load_configs("MIX-IT.json")

ip_version = get_ip_version(config)

print_config(config, ip_version=ip_version)


if __name__ == "__main__":
    load_bview_data_from_api(config, ip_version=ip_version)
     