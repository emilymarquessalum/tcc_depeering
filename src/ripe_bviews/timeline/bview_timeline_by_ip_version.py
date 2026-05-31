



import sys
from pathlib import Path
 
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent)) 
 
from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data_timeline_from_configs
 

import datetime 
from src.ripe_bviews.timeline.bview_vars import get_annotations, get_ip_version, get_labels_info, get_subfolder, get_title_end, get_title_start 
from src.ripe_bviews.bview_labels import summarized_date_labels
from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data_timeline_from_configs
from src.ripe_bviews.download_and_parse.load_configs import load_configs, print_config 
from src.ripe_bviews.oscillations.bview_oscillation_logic import OscillationMetrics, calculate_oscillation_metrics 
import warnings 
from src.utils.graphs import create_window_with_all_rendered_graphs_this_session, plot_list_as_bar_plot, plot_list_as_line_plot, plot_stacked_line_plot

 
warnings.filterwarnings('ignore', category=UserWarning, message='.*') 
 



def bview_timeline_ip_version():

    config = load_configs("ixbr.json")

    #config = load_configs("AMS-IX.json")
    
    ip_version = get_ip_version(config)
    
    print_config(config, ip_version)

    name = config.get("name", "Unknown") 
  
    rrc = config["rrc"]
    start_date = datetime.datetime.strptime(config["start_date"], "%Y-%m-%d")
    end_date = datetime.datetime.strptime(config["end_date"], "%Y-%m-%d")
    day_delta = datetime.timedelta(days=config.get("day_delta", 7))
    time_str = config.get("time_str", "0000") 

    all_stats_v4, labels = load_bview_data_timeline_from_configs(config, ip_version="v4",
                                                              ignored_dates=["20251205.0000"])       
    
    
    all_stats_v6, labels = load_bview_data_timeline_from_configs(config, ip_version="v6",
                                                              ignored_dates=["20251205.0000"])       
    
 
    title_start = get_title_start(config)
    title_end = get_title_end(config)
    
    #subfolder = rrc + "_" + start_date.strftime("%Y%m%d") + "_" + end_date.strftime("%Y%m%d")   
    subfolder = get_subfolder(config, "both_versions")
    subfolder = subfolder  + "/timeline"
 
    labels_summarized, max_labels = get_labels_info(labels)
    

    members_only_v4 = []
    members_only_v6 = []
    members_both = []

    focused_index = 0
    
    focused_member_history_v4 = all_stats_v4[focused_index].unique_members
    focused_member_history_v6 = all_stats_v6[focused_index].unique_members

    for asn in focused_member_history_v4:
        if asn not in focused_member_history_v6:
            members_only_v4.append(asn)
        else:
            members_both.append(asn)

    for asn in focused_member_history_v6:
        if asn not in focused_member_history_v4:
            members_only_v6.append(asn)

    total_percentage = len(members_only_v4) + len(members_only_v6) + len(members_both)
    if total_percentage > 0: 
        plot_list_as_bar_plot(["Only IPv4", "Only IPv6", "Both"], [len(members_only_v4)/total_percentage, len(members_only_v6)/total_percentage, len(members_both)/total_percentage],
                            is_percentage=True,
                            title=f'{title_start} Member ASes at by IP Version - {labels_summarized[focused_index].replace("/", ".")}', 
                            xlabel='IP Version Membership', ylabel='Number of Member ASes', subfolder=subfolder)
    
    
    focused_reachable_v4 = all_stats_v4[focused_index].unique_reachables
    focused_reachable_v6 = all_stats_v6[focused_index].unique_reachables

    reachables_only_v4  = []
    reachables_only_v6 = []
    reachables_both = []

    for asn in focused_reachable_v4:
        if asn not in focused_reachable_v6:
            reachables_only_v4.append(asn)
        else:
            reachables_both.append(asn)
    
    for asn in focused_reachable_v6:
        if asn not in focused_reachable_v4:
            reachables_only_v6.append(asn)
    
    total_percentage = len(reachables_only_v4) + len(reachables_only_v6) + len(reachables_both)
    if total_percentage > 0:
        plot_list_as_bar_plot(["Only IPv4", "Only IPv6", "Both"], [len(reachables_only_v4)/total_percentage, len(reachables_only_v6)/total_percentage, len(reachables_both)/total_percentage],
                            is_percentage=True,
                            title=f'{title_start} Reachable ASes at by IP Version - {labels_summarized[focused_index].replace("/", ".")}', 
                            xlabel='IP Version Membership', ylabel='Number of Reachable ASes', subfolder=subfolder)
    
    ''' 
    plot_stacked_line_plot([member_history_v4, member_history_v6], 
                           ["IPv4", "IPv6"],
                           x_labels=labels_summarized,title=f'{title_start} Member ASes Over Time by IP Version - {title_end}', xlabel='Time', ylabel='Number of Member ASes', subfolder=subfolder, 
                           max_labels=max_labels, annotations=get_annotations())
    '''



if __name__ == "__main__":
    bview_timeline_ip_version()
    create_window_with_all_rendered_graphs_this_session()
    
