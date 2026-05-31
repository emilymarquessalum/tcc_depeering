

import sys
from pathlib import Path



sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent)) 
 

import datetime 
from src.ripe_bviews.timeline.bview_timeline_routes import plot_routes_over_time
from src.services.aspop import get_aspop
 
from src.ripe_bviews.timeline.path_improvements.bview_routes_improvements import plot_routes_added_that_improved_shortest_path, plot_shortest_path_average_over_time

from src.ripe_bviews.read_bgpdump import BGPDumpSnapshotStats
from src.ripe_bviews.timeline.bview_vars import get_annotations, get_ip_version, get_subfolder, get_title_end, get_title_start 
from src.ripe_bviews.bview_labels import get_max_labels, summarized_date_labels
from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data_timeline_from_configs
from src.ripe_bviews.download_and_parse.load_configs import load_configs, print_config 
from src.ripe_bviews.oscillations.bview_oscillation_logic import OscillationMetrics, calculate_oscillation_metrics 
import warnings 
from src.utils.graphs import create_window_with_all_rendered_graphs_this_session, plot_list_as_bar_plot, plot_list_as_line_plot, plot_stacked_line_plot

 
warnings.filterwarnings('ignore', category=UserWarning, message='.*') 
 


def plot_added_removed_asnes_over_time(metrics: OscillationMetrics, labels_summarized, max_labels, title_start, title_end, subfolder):
    plot_list_as_line_plot(metrics.removed_asns_over_time, labels_summarized[1:], 
                        max_labels=max_labels,
                        title=title_start + "De-Peered ASes Over Time" + title_end, xlabel="Date", ylabel="Number of Removed ASes", subfolder=subfolder)
    plot_list_as_line_plot(metrics.added_asns_over_time, labels_summarized[1:],  
                        max_labels=max_labels,
                        title=title_start + "Newly-Peered ASes Over Time" + title_end, xlabel="Date", ylabel="Number of New ASes", subfolder=subfolder)


def get_first_and_last_index_seen_for_asns(ases_removed_that_did_not_come_back, list_of_ases):
    first_and_last_index_seen_for_asns = {}
    for asn in ases_removed_that_did_not_come_back:
        first_index = None
        last_index = None
        
        for i, stat in enumerate(list_of_ases):
            if asn in stat and first_index is None:
                first_index = i
            if first_index is not None and asn not in stat:
                last_index = i
                break
        first_and_last_index_seen_for_asns[asn] = [first_index, last_index]
    
    return first_and_last_index_seen_for_asns

# if retroactive is zero, only considers ASes that were present in the first stat  
# retroactive n, considers ASes that were present in the first stat and also ASes that were added in the following n stats  
def get_ases_that_did_not_come_back(list_of_ases, retrospective=0):
    # get ASes that existed in the first stat
    ases_removed_that_did_not_come_back = list_of_ases[0].copy()
    # remove ASes that came back in any of the following stats
    for i, stat in enumerate(list_of_ases[1:], 1):
        ases_removed_that_did_not_come_back -= stat # remove ASes that came back in this stat
        if i <= retrospective:
            ases_removed_that_did_not_come_back |= stat # add ASes that were added
            
    # the result becomes the ASes that were removed and did not come back
    # (because if they had come back, they would have been removed from the set)
    return ases_removed_that_did_not_come_back


def analyze_member_and_reachable_departures(all_stats):
    all_asns = set()
    for stat in all_stats:
        all_asns.update(stat.unique_members)
    
    all_reachables = set()
    for stat in all_stats:
        all_reachables.update(stat.unique_reachables)
    
    total_member_departures = 0
    for asn in all_asns:
        presence = [asn in stat.unique_members for stat in all_stats]
        for i in range(1, len(presence)):
            if presence[i-1] and not presence[i]:
                total_member_departures += 1
    
    total_reachable_departures = 0
    for asn in all_reachables:
        presence = [asn in stat.unique_reachables for stat in all_stats]
        for i in range(1, len(presence)):
            if presence[i-1] and not presence[i]:
                total_reachable_departures += 1
    
    return total_member_departures, total_reachable_departures


def get_period_delta():
    
    # just so we represent the main used options
    period_options = {
        "daily": datetime.timedelta(days=1),
        "weekly": datetime.timedelta(weeks=1),
        "biweekly": datetime.timedelta(weeks=2),
        "monthly": datetime.timedelta(days=30),
        "quarterly": datetime.timedelta(days=90),
        "yearly": datetime.timedelta(days=365)
    }

    #return period_options["daily"]
    return period_options["weekly"]
    return period_options["monthly"]
    

def get_stats_by_analyzed_period(all_stats: list[BGPDumpSnapshotStats], labels: list[str], stats_are_daily_separated=True):

    period_delta = get_period_delta()
    stats_by_period = []
    labels_by_period = []
    current_period_start = all_stats[0].date_as_datetime() 

    # more efficient option, but only works if each stat represents a day
    if stats_are_daily_separated:
        period_index_delta = period_delta.days
        for i in range(0, len(all_stats), period_index_delta):
            labels_by_period.append(labels[i])
            stats_by_period.append(all_stats[i])
        return stats_by_period, labels_by_period

    for stat in all_stats:
        stat_date = stat.date_as_datetime()
        
        if stat_date >= current_period_start + period_delta:
            stats_by_period.append(stat)
            #labels_by_period.append(labels[])
            current_period_start += period_delta
        else:
            if stats_by_period:
                stats_by_period[-1] = stat
            else:
                stats_by_period.append(stat)
                #labels_by_period.append(labels[])
                current_period_start = stat_date
    return stats_by_period, labels_by_period


def print_retroactive_loss(all_stats, config, ip_version):
    retroactive = max(int(0.1 * len(all_stats)), 1)
    
    print_config(config, ip_version)
    print(f"ASes that were present in the first {retroactive} snapshots (from total of {len(all_stats)}, ({(retroactive/len(all_stats))*100:.2f}%).")
    ases_removed_that_did_not_come_back = get_ases_that_did_not_come_back([stat.unique_members for stat in all_stats],
                                                                          retrospective=retroactive)
    print(f"ASes that existed in the first {retroactive} snapshots, but were removed and did not come back: {len(ases_removed_that_did_not_come_back)}")

    ases_reachable_removed_that_did_not_come_back = get_ases_that_did_not_come_back([stat.unique_reachables for stat in all_stats],
                                                                                    retrospective=retroactive)
    print(f"Reachable ASes that existed in the first {retroactive} snapshots, but were removed and did not come back: {len(ases_reachable_removed_that_did_not_come_back)}")
    

def bview_simple_timeline():

    config = load_configs("ixbr.json")

    #config = load_configs("AMS-IX.json")
    ip_version = get_ip_version(config)
    print_config(config, ip_version)

    name = config.get("name", "Unknown") 
   
    all_stats, labels = load_bview_data_timeline_from_configs(config, ip_version=ip_version,
                                                              ignored_dates=["20251205.0000", 
                                                              ], 
                                                              )    


    for stat in all_stats:
        stat.check_consistency()
        
    stats_analyzed, labels_analyzed = get_stats_by_analyzed_period(all_stats, labels, stats_are_daily_separated=True)

    member_history = [stat.members for stat in all_stats]
    reachable_history = [stat.reachables for stat in all_stats]


    member_history_analyzed = [stat.members for stat in stats_analyzed]
    reachable_history_analyzed = [stat.reachables for stat in stats_analyzed]
 
    title_start = get_title_start(config)
    title_end = get_title_end(config)
    
    #subfolder = rrc + "_" + start_date.strftime("%Y%m%d") + "_" + end_date.strftime("%Y%m%d")   
    subfolder = get_subfolder(config, ip_version)
    subfolder = subfolder  + "/timeline"
    

    oscillation_metrics = calculate_oscillation_metrics(all_stats)
    oscillation_metrics.load_oscillating_lists()
    plot_added_removed_asnes_over_time(oscillation_metrics, summarized_date_labels(labels), max_labels=len(labels)//10 if len(labels) > 20 else None, title_start=title_start, title_end=title_end, subfolder=subfolder)
    
    #print_retroactive_loss(all_stats, config, ip_version)
    #first_and_last_index_seen_for_members_removed_that_did_not_come_back = get_first_and_last_index_seen_for_asns(ases_removed_that_did_not_come_back, [stat.unique_members for stat in all_stats])           
    #print(f"Members removed that did not come back with their first and last seen indices: {first_and_last_index_seen_for_members_removed_that_did_not_come_back}")
    
    #print(ases_reachable_removed_that_did_not_come_back)
    #first_and_last_index_seen_for_reachables_removed_that_did_not_come_back = get_first_and_last_index_seen_for_asns(ases_reachable_removed_that_did_not_come_back, [stat.unique_reachables for stat in all_stats])           
    #print(f"Reachables removed that did not come back with their first and last seen indices: {first_and_last_index_seen_for_reachables_removed_that_did_not_come_back}")
    
    print("---")
    #reachables_metrics = calculate_oscillation_metrics(all_stats, use_reachables=True)
    #oscillating_reachables = set(reachables_metrics.oscillation_info.keys()) 
    #print(f"Oscillating Reachable ASes (left and came back): {len(oscillating_reachables)}")
    
    #total_member_departures, total_reachable_departures = analyze_member_and_reachable_departures(all_stats) 
    #print(f"Total times member ASes left: {total_member_departures}")
    #print(f"Total times reachable ASes left: {total_reachable_departures}")
    
    labels_summarized = summarized_date_labels(labels)
    max_labels= get_max_labels(labels)
    


    members_who_are_also_reachables = set()
    for stat in all_stats:
        members_who_are_also_reachables.update(stat.unique_members - stat.unique_reachables)
    #print(f"Member ASes that are not also reachables: {len(members_who_are_also_reachables)}")
    

    #max_labels = None

    plot_list_as_line_plot(member_history, labels_summarized,title=f'Member ASes Over Time - {name} - IP{ip_version}', xlabel='Time', ylabel='Number of Member ASes', subfolder=subfolder, 
                           max_labels=max_labels, annotations=get_annotations())
    plot_list_as_line_plot(reachable_history, labels_summarized, title=f'{title_start} Reachable ASes Over Time {title_end}', xlabel='Time', ylabel='Number of Reachable ASes', subfolder=subfolder,
                           max_labels=max_labels, annotations=get_annotations())
    
 

    plot_list_as_line_plot(member_history_analyzed, labels_analyzed,title=f'Member ASes Over Time - Weekly - {name} - IP{ip_version}', xlabel='Time', ylabel='Number of Member ASes', subfolder=subfolder, 
                           max_labels=max_labels, annotations=get_annotations())
    plot_list_as_line_plot(reachable_history_analyzed, labels_analyzed, title=f'{title_start} Reachable ASes Over Time - Weekly - {title_end}', xlabel='Time', ylabel='Number of Reachable ASes', subfolder=subfolder,
                           max_labels=max_labels, annotations=get_annotations())

    reachable_change_over_time = [len(stat.unique_reachables) - len(stat.unique_members) for stat in all_stats]
    plot_list_as_line_plot(reachable_change_over_time, labels_summarized, title=f'{title_start} Change in Reachable ASes Over Time (Reachables - Members) {title_end}', xlabel='Time', ylabel='Number of Reachable ASes - Number of Member ASes', subfolder=subfolder,
                           max_labels=max_labels, annotations=get_annotations())

    plot_routes_over_time(all_stats, labels_summarized, title_start, title_end, subfolder, max_labels)
    #print(oscillation_metrics.all_removed_asns_over_time)
    #print(oscillation_metrics.all_added_asns_over_time)

    top_n_members_by_reachability = sorted(all_stats[0].unique_members, key=lambda asn: len(all_stats[0].get_all_reachables_for_member(asn)), reverse=True)[:10]
    member_reachability_from_top_n = [len(all_stats[0].get_all_reachables_for_member(asn)) for asn in top_n_members_by_reachability]
    
    reachability_total = len(all_stats[0].unique_reachables)
    member_reachability_from_top_n = [(count / reachability_total) * 100 for count in member_reachability_from_top_n]
    plot_list_as_bar_plot(top_n_members_by_reachability, member_reachability_from_top_n, title=f'Top {len(top_n_members_by_reachability)} Member ASes by AS Reachability - {name} - IP{ip_version}', xlabel='Member AS', ylabel='Number of ASes', subfolder=subfolder)


    plot_shortest_path_average_over_time(all_stats, labels_summarized, title_start, title_end, subfolder, max_labels)
    plot_routes_added_that_improved_shortest_path(all_stats, labels_summarized, title_start, title_end, subfolder, max_labels)
    def calculate_aspop():
        aspop = get_aspop()

        total_users = 0
        ases_not_found = 0
        ases_that_gave_zero_users = 0

        for member in all_stats[0].unique_members:
            member_was_found = False
            for aspop_entry in aspop:
                if str(aspop_entry['asn']) == str(member):
                    total_users += aspop_entry['users']
                    member_was_found = True
                    if aspop_entry['users'] == 0:
                        ases_that_gave_zero_users += 1
                    break
                    
            if not member_was_found:
                ases_not_found += 1
                
        print(f"For {name}, {ip_version}, in the first snapshot, considering {len(all_stats[0].unique_members)} member ASes...")
        print(f"Total users directly served by the IXP (added together Member 'users') according to ASPOP data: {total_users:,}")
        print(f"Giving us an average of {int(total_users/len(all_stats[0].unique_members))} users per member AS.")
        print(f"ASes not found in ASPOP data: {ases_not_found}")
        print(f"ASes that gave zero users: {ases_that_gave_zero_users}")

if __name__ == "__main__":  
    bview_simple_timeline()  
    create_window_with_all_rendered_graphs_this_session()