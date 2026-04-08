# ASes que foram removidos de uma data para a próxima
# ASes que foram adicionados de uma data para a próxima
# ASes que começaram oscilação nessa data (sair, voltar, sair) ou (voltar, sair, voltar)
# ASes que terminaram oscilação nessa data

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from datetime import datetime, timedelta
from src.ripe_bviews.bview_labels import get_date_range_title, summarized_date_labels, time_delta_title
from src.ripe_bviews.download_and_parse.load_configs import load_configs
from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data_timeline, load_bview_data_timeline_from_configs
from src.ripe_bviews.timeline.bview_timeline import load_bview_data
from src.ripe_bviews.oscillations.bview_oscillation_logic import calculate_oscillation_metrics, get_comeback_times_count_from_oscillation_info

from src.utils.graphs import plot_list_as_bar_plot, plot_list_as_line_plot, plot_stacked_line_plot
import warnings

warnings.filterwarnings('ignore', category=UserWarning, message='.*Skipping download.*')
 
config = load_configs("ixbr.json")
#config = load_configs("de-cix-amsterdam.json")

ip_version = "v4"

asn_and_prefix = config["asn_and_prefix"].get("asn"), config["asn_and_prefix"].get("prefix")

rrc = config["rrc"]
start_date = datetime.strptime(config["start_date"], "%Y-%m-%d")
end_date = datetime.strptime(config["end_date"], "%Y-%m-%d")
day_delta = timedelta(days=config.get("day_delta", 7))
time_str = config.get("time_str", "0000")

#all_stats, labels = load_bview_data_timeline(start_date, end_date, asn_and_prefix, rrc, day_delta=day_delta, time_str=time_str, time_delta_hours=config.get("time_delta_hours", 0), ip_version=ip_version)
all_stats, labels = load_bview_data_timeline_from_configs(config, ip_version=ip_version)     


   
 

 

