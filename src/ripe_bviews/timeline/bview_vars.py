


import sys
from pathlib import Path

from matplotlib.offsetbox import AnchoredText

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from datetime import datetime, timedelta

from src.ripe_bviews.bview_labels import get_date_range_title, summarized_date_labels



def is_tcc_mode():
    return True

def get_ip_version(config) -> str:
    return "v4"
 
def get_title_start(config):

    return f"{config.get('name')} - "

def get_title_end(config):
     return get_date_range_title(config["start_date"], config["end_date"])


def get_subfolder(config, ip_version):
    rrc = config["rrc"] if "rrc" in config else config["routeserver-folder-name"]
    start_date = datetime.strptime(config["start_date"], "%Y-%m-%d")
    end_date = datetime.strptime(config["end_date"], "%Y-%m-%d")
    day_delta = timedelta(days=config.get("day_delta", 7))
    time_str = config.get("time_str", "0000")
    
    return rrc + "/" + ip_version + "/" + start_date.strftime("%Y%m%d") + "_" + end_date.strftime("%Y%m%d") + "_" + time_str + "/" + str(day_delta.days) + "days" + "/"
  
def get_labels_info(labels):
    labels_summarized = summarized_date_labels(labels)
    max_labels=len(labels)//10 if len(labels) > 20 else None
    return labels_summarized, max_labels


def get_annotations():
        return []
        return [AnchoredText("Sample Interval: 8 Hours", 
                      prop=dict(size=12, style='italic'), 
                      frameon=True, 
                      loc='lower right')]