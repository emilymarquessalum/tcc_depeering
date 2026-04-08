

import sys
from pathlib import Path
 
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent)) 
 

import datetime 
from src.ripe_bviews.timeline.bview_vars import get_annotations, get_ip_version, get_title_end, get_title_start 
from src.ripe_bviews.bview_labels import summarized_date_labels
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

def calculate_routes_added_per_member(all_stats): 
    total_per_snapshot = []
    per_member_breakdown = [] 
    
    for i in range(1, len(all_stats)):
        new_mappings_with_no_new_members_or_reachables = []
        
        for mapping in all_stats[i].mappings.keys():
            # new member added, doesn't count to our metric
            if mapping not in all_stats[i-1].mappings:
                continue
            # member already exists, but might have new reachables
            # we need to find reachables that were added for this member, but that already existed
            else: 
                new_reachables_for_member = {r["reachable"] for r in all_stats[i].mappings[mapping]} - {r["reachable"] for r in all_stats[i-1].mappings[mapping]}
                if new_reachables_for_member:
                    reachables_added_that_already_existed = new_reachables_for_member & all_stats[i-1].unique_reachables
                    if reachables_added_that_already_existed:
                        new_mappings_with_no_new_members_or_reachables.append({mapping: reachables_added_that_already_existed})
        
        total = 0
        member_dict = {}
        for mapping in new_mappings_with_no_new_members_or_reachables:
            reachables = list(mapping.values())[0]
            total += len(reachables)
            member_dict[list(mapping.keys())[0]] = len(reachables)
        
        total_per_snapshot.append(total)
        per_member_breakdown.append(member_dict)
    
    return total_per_snapshot, per_member_breakdown

def calculate_routes_lost_per_member(all_stats): 
    total_per_snapshot = []
    per_member_breakdown = []
    
    for i in range(1, len(all_stats)):
        lost_mappings_with_no_removed_members_or_reachables = []
        
        for mapping in all_stats[i-1].mappings.keys():
            # mapping was removed in index i, that means the member doesn't exist anymore
            # this doesn't count to our metric 
            if mapping not in all_stats[i].mappings:
                continue
            # member still exists, but might have lost reachables
            # we need to find reachables that were lost for this member, but that still exist now (because of other connections)
            else:
                # reachables that used to exist for this member, but don't anymore
                # ex: [1,2,3] -> [2,4] would give us {1,3} as lost reachables for this member
                lost_reachables_for_member = {r["reachable"] for r in all_stats[i-1].mappings[mapping]} - {r["reachable"] for r in all_stats[i].mappings[mapping]}
                if lost_reachables_for_member:
                    # reachables lost for this member that still exist in the new stat (because of other members)
                    # ex: lost {1,3} but (1 in i unique_reachables), then getting the "&" results in {1}
                    reachables_lost_that_still_exist = lost_reachables_for_member & all_stats[i].unique_reachables
                    if reachables_lost_that_still_exist:
                        lost_mappings_with_no_removed_members_or_reachables.append({mapping: reachables_lost_that_still_exist})
        
        total = 0
        member_dict = {}
        for mapping in lost_mappings_with_no_removed_members_or_reachables:
            reachables = list(mapping.values())[0]
            total += len(reachables)
            member_dict[list(mapping.keys())[0]] = len(reachables)
        
        total_per_snapshot.append(total)
        per_member_breakdown.append(member_dict)
    
    return total_per_snapshot, per_member_breakdown

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

def calculate_routes_over_time(all_stats):
    routes_over_time = []
    for stat in all_stats:
        total_routes = 0
        for member_mappings in stat.mappings.values():
            total_routes += len(member_mappings)
        routes_over_time.append(total_routes)
    return routes_over_time

def calculate_best_path_average_over_time(all_stats):
    """Calculate the average best path length for arriving at each reachable for each day."""
    best_path_averages = []
    for stat in all_stats:
        best_path_lengths = []
        for reachable in stat.unique_reachables:
            best_length, _ = stat.get_best_as_path_length_for_reachable(reachable)
            if best_length is not None:
                best_path_lengths.append(best_length)
        
        # Calculate average for this day
        if best_path_lengths:
            average = sum(best_path_lengths) / len(best_path_lengths)
        else:
            average = 0
        best_path_averages.append(average)
    
    return best_path_averages

def plot_mapping_changes(all_stats, labels_summarized, name, ip_version, subfolder, max_labels):
    number_of_routes_added_that_did_not_add_new_members_or_reachables, number_of_routes_added_that_did_not_add_members_or_reachables_per_member = calculate_routes_added_per_member(all_stats)
    number_of_routes_lost_that_did_not_remove_members_or_reachables, number_of_routes_lost_that_did_not_remove_members_or_reachables_per_member = calculate_routes_lost_per_member(all_stats)

    net_growth_of_mappings_with_no_new_members_or_reachables = [added - lost for added, lost in zip(number_of_routes_added_that_did_not_add_new_members_or_reachables, number_of_routes_lost_that_did_not_remove_members_or_reachables)]
    accumulated_net_growth_of_mappings_with_no_new_members_or_reachables = []
    accumulated = 0
    for net_growth in net_growth_of_mappings_with_no_new_members_or_reachables:
        accumulated += net_growth
        accumulated_net_growth_of_mappings_with_no_new_members_or_reachables.append(accumulated)

    plot_list_as_line_plot(number_of_routes_added_that_did_not_add_new_members_or_reachables, labels_summarized[1:],title=f'New Mappings Added That Did Not Add New Members or Reachables - {name} - IP{ip_version}', xlabel='Time', ylabel='Number of New Mappings Added That Did Not Add New Members or Reachables', subfolder=subfolder,
                            max_labels=max_labels, annotations=get_annotations())
    plot_list_as_line_plot(number_of_routes_lost_that_did_not_remove_members_or_reachables, labels_summarized[1:],title=f'Mappings Lost That Did Not Remove Members or Reachables - {name} - IP{ip_version}', xlabel='Time', ylabel='Number of Mappings Lost That Did Not Remove Members or Reachables', subfolder=subfolder,
                            max_labels=max_labels, annotations=get_annotations()) 
    plot_list_as_line_plot(net_growth_of_mappings_with_no_new_members_or_reachables, labels_summarized[1:],title=f'Net Growth of Mappings With No New Members or Reachables - {name} - IP{ip_version}', xlabel='Time', ylabel='Net Growth of Mappings With No New Members or Reachables', subfolder=subfolder,
                            max_labels=max_labels, annotations=get_annotations())
    plot_list_as_line_plot(accumulated_net_growth_of_mappings_with_no_new_members_or_reachables, labels_summarized[1:],title=f'Accumulated Net Growth of Mappings With No New Members or Reachables - {name} - IP{ip_version}', xlabel='Time', ylabel='Accumulated Net Growth of Mappings With No New Members or Reachables', subfolder=subfolder,
                            max_labels=max_labels, annotations=get_annotations())
    
    return number_of_routes_lost_that_did_not_remove_members_or_reachables_per_member, number_of_routes_added_that_did_not_add_members_or_reachables_per_member

def plot_member_routes_lost_that_did_not_remove_new_ases(number_of_routes_lost_that_did_not_remove_members_or_reachables_per_member, labels_summarized, name, ip_version, subfolder, max_labels, top_n_number=2):
    number_of_routes_lost_that_did_not_remove_members_or_reachables_per_member_list_of_lists = []
    all_members_in_list_of_routes_lost_that_did_not_remove_members_or_reachables_per_member = set()
    for stat in number_of_routes_lost_that_did_not_remove_members_or_reachables_per_member:
        member_list = list(stat.keys())
        all_members_in_list_of_routes_lost_that_did_not_remove_members_or_reachables_per_member.update(member_list)

    for stat in number_of_routes_lost_that_did_not_remove_members_or_reachables_per_member:
        count = []
        for member in all_members_in_list_of_routes_lost_that_did_not_remove_members_or_reachables_per_member:
            count.append(stat.get(member, 0))
        number_of_routes_lost_that_did_not_remove_members_or_reachables_per_member_list_of_lists.append(count)
    ten_most_relevant_ases_from_number_of_routes_lost_that_did_not_remove_members_or_reachables_per_member = sorted(all_members_in_list_of_routes_lost_that_did_not_remove_members_or_reachables_per_member, key=lambda member: sum(stat.get(member, 0) for stat in number_of_routes_lost_that_did_not_remove_members_or_reachables_per_member), reverse=True)[:10]
    
    number_of_routes_lost_that_did_not_remove_members_or_reachables_per_member_list_of_lists_top_n = []
    for member in ten_most_relevant_ases_from_number_of_routes_lost_that_did_not_remove_members_or_reachables_per_member[:top_n_number]:
        member_list = [] 
        for stat in number_of_routes_lost_that_did_not_remove_members_or_reachables_per_member:
            member_list.append(stat.get(member, 0))
        number_of_routes_lost_that_did_not_remove_members_or_reachables_per_member_list_of_lists_top_n.append(member_list)
    
    if len(ten_most_relevant_ases_from_number_of_routes_lost_that_did_not_remove_members_or_reachables_per_member) == 0:
        print("No members had routes lost that did not remove members or reachables, skipping the plot.") 
    else:
        print(labels_summarized)
        print(number_of_routes_lost_that_did_not_remove_members_or_reachables_per_member_list_of_lists_top_n)
        
        labels = labels_summarized
        if len(labels) > len(number_of_routes_lost_that_did_not_remove_members_or_reachables_per_member_list_of_lists_top_n[0]):
            labels = labels_summarized[:len(number_of_routes_lost_that_did_not_remove_members_or_reachables_per_member_list_of_lists_top_n[0])]
        print(labels)
        plot_stacked_line_plot(
            number_of_routes_lost_that_did_not_remove_members_or_reachables_per_member_list_of_lists_top_n,
            ten_most_relevant_ases_from_number_of_routes_lost_that_did_not_remove_members_or_reachables_per_member[:top_n_number],
            x_labels=labels,
            title=f'Routes Lost That Did Not Remove Members or Reachables Per Member - {name} - IP{ip_version}',
            xlabel='Time',
            ylabel='Number of Routes Lost That Did Not Remove Members or Reachables',
            subfolder=subfolder,
            max_labels=max_labels
        )

    sum_of_routes_lost_that_did_not_remove_members_or_reachables_per_member = []
    for asn in ten_most_relevant_ases_from_number_of_routes_lost_that_did_not_remove_members_or_reachables_per_member[:top_n_number]:
        total = 0
        for stat in number_of_routes_lost_that_did_not_remove_members_or_reachables_per_member:
            total += stat.get(asn, 0)
        sum_of_routes_lost_that_did_not_remove_members_or_reachables_per_member.append(total)

    if len(ten_most_relevant_ases_from_number_of_routes_lost_that_did_not_remove_members_or_reachables_per_member) == 0:
        print("No members had routes lost that did not remove members or reachables, skipping the plot.")
    else:
        plot_list_as_bar_plot(
            
            ten_most_relevant_ases_from_number_of_routes_lost_that_did_not_remove_members_or_reachables_per_member[:top_n_number],
            sum_of_routes_lost_that_did_not_remove_members_or_reachables_per_member,
            title=f'Sum of Routes Lost That Did Not Remove Members or Reachables Per Member - Top {top_n_number} - {name} - IP{ip_version}',
            xlabel='Time',
            ylabel='Sum of Number of Routes Lost That Did Not Remove Members or Reachables',
            subfolder=subfolder, 
            max_labels=max_labels
        )

def plot_member_routes_that_did_not_add_new_ases(number_of_routes_added_that_did_not_add_members_or_reachables_per_member, labels_summarized, name, ip_version, subfolder, max_labels, top_n_number=2):
    number_of_routes_added_that_did_not_add_members_or_reachables_per_member_list_of_lists = []
    all_members_in_list_of_routes_added_that_did_not_add_members_or_reachables_per_member = set()
    for stat in number_of_routes_added_that_did_not_add_members_or_reachables_per_member:
        member_list = list(stat.keys())
        all_members_in_list_of_routes_added_that_did_not_add_members_or_reachables_per_member.update(member_list)

    for stat in number_of_routes_added_that_did_not_add_members_or_reachables_per_member:
        count = []
        for member in all_members_in_list_of_routes_added_that_did_not_add_members_or_reachables_per_member:
            count.append(stat.get(member, 0))
        number_of_routes_added_that_did_not_add_members_or_reachables_per_member_list_of_lists.append(count)
    ten_most_relevant_ases_from_number_of_routes_added_that_did_not_add_members_or_reachables_per_member = sorted(all_members_in_list_of_routes_added_that_did_not_add_members_or_reachables_per_member, key=lambda member: sum(stat.get(member, 0) for stat in number_of_routes_added_that_did_not_add_members_or_reachables_per_member), reverse=True)[:10]
     
    number_of_routes_added_that_did_not_add_members_or_reachables_per_member_list_of_lists_top_n = []
    for member in ten_most_relevant_ases_from_number_of_routes_added_that_did_not_add_members_or_reachables_per_member[:top_n_number]:
        member_list = [] 
        for stat in number_of_routes_added_that_did_not_add_members_or_reachables_per_member:
            member_list.append(stat.get(member, 0))
        number_of_routes_added_that_did_not_add_members_or_reachables_per_member_list_of_lists_top_n.append(member_list)
    
    if len(ten_most_relevant_ases_from_number_of_routes_added_that_did_not_add_members_or_reachables_per_member) == 0:
        print("No members had routes added that did not add members or reachables, skipping the plot.")
    else:

        labels = labels_summarized
        if len(labels) > len(number_of_routes_added_that_did_not_add_members_or_reachables_per_member_list_of_lists_top_n[0]):
            labels = labels_summarized[:len(number_of_routes_added_that_did_not_add_members_or_reachables_per_member_list_of_lists_top_n[0])]
        plot_stacked_line_plot(
            number_of_routes_added_that_did_not_add_members_or_reachables_per_member_list_of_lists_top_n,
            ten_most_relevant_ases_from_number_of_routes_added_that_did_not_add_members_or_reachables_per_member[:top_n_number],
            x_labels=labels,
            title=f'Routes Added That Did Not Add New Members or Reachables Per Member - {name} - IP{ip_version}',
            xlabel='Time',
            ylabel='Number of Routes Added That Did Not Add New Members or Reachables',
            subfolder=subfolder,
            max_labels=max_labels
        )
    sum_of_routes_added_that_did_not_add_members_or_reachables_per_member = []
    for asn in ten_most_relevant_ases_from_number_of_routes_added_that_did_not_add_members_or_reachables_per_member[:top_n_number]:
        total = 0
        for stat in number_of_routes_added_that_did_not_add_members_or_reachables_per_member:
            total += stat.get(asn, 0)
        sum_of_routes_added_that_did_not_add_members_or_reachables_per_member.append(total)
    
    if len(ten_most_relevant_ases_from_number_of_routes_added_that_did_not_add_members_or_reachables_per_member) == 0:
        print("No members had routes added that did not add members or reachables, skipping the plot.")
    else:
        plot_list_as_bar_plot(
            ten_most_relevant_ases_from_number_of_routes_added_that_did_not_add_members_or_reachables_per_member[:top_n_number],
            sum_of_routes_added_that_did_not_add_members_or_reachables_per_member,
            title=f'Sum of Routes Added That Did Not Add New Members or Reachables Per Member - Top {top_n_number} - {name} - IP{ip_version}',
            xlabel='Time',
            ylabel='Sum of Number of Routes Added That Did Not Add New Members or Reachables',
            subfolder=subfolder, 
            max_labels=max_labels
        )
        
def bview_simple_timeline():

    config = load_configs("ixbr.json")
    ip_version = get_ip_version(config)
    print_config(config, ip_version)
    #config = load_configs("de-cix-amsterdam.json")

    name = config.get("name", "Unknown") 
  
    rrc = config["rrc"]
    start_date = datetime.datetime.strptime(config["start_date"], "%Y-%m-%d")
    end_date = datetime.datetime.strptime(config["end_date"], "%Y-%m-%d")
    day_delta = datetime.timedelta(days=config.get("day_delta", 7))
    time_str = config.get("time_str", "0000") 

    all_stats, labels = load_bview_data_timeline_from_configs(config, ip_version=ip_version)       
    member_history = [stat.members for stat in all_stats]
    reachable_history = [stat.reachables for stat in all_stats]
 
    title_start = get_title_start(config)
    title_end = get_title_end(config)
    
    #subfolder = rrc + "_" + start_date.strftime("%Y%m%d") + "_" + end_date.strftime("%Y%m%d")   
    subfolder = rrc + "/" + ip_version + "/" + start_date.strftime("%Y%m%d") + "_" + end_date.strftime("%Y%m%d") + "_" + time_str + "/" + str(day_delta.days) + "days" + "/"
    subfolder = subfolder  + "/timeline"
    

    oscillation_metrics = calculate_oscillation_metrics(all_stats)
    oscillation_metrics.load_oscillating_lists()
    plot_added_removed_asnes_over_time(oscillation_metrics, summarized_date_labels(labels), max_labels=len(labels)//10 if len(labels) > 20 else None, title_start=title_start, title_end=title_end, subfolder=subfolder)
    
    retroactive = max(int(0.1 * len(all_stats)), 1)
    print(f"Considering ASes that were present in the first {retroactive} snapshots out of {len(all_stats)} total snapshots ({(retroactive/len(all_stats))*100:.2f}%) for the retrospective analysis.")
    ases_removed_that_did_not_come_back = get_ases_that_did_not_come_back([stat.unique_members for stat in all_stats],
                                                                          retrospective=retroactive)
    print(f"ASes that existed in the first {retroactive} snapshots, but were removed and did not come back: {len(ases_removed_that_did_not_come_back)}")

    #first_and_last_index_seen_for_members_removed_that_did_not_come_back = get_first_and_last_index_seen_for_asns(ases_removed_that_did_not_come_back, [stat.unique_members for stat in all_stats])           
    #print(f"Members removed that did not come back with their first and last seen indices: {first_and_last_index_seen_for_members_removed_that_did_not_come_back}")
    
    ases_reachable_removed_that_did_not_come_back = get_ases_that_did_not_come_back([stat.unique_reachables for stat in all_stats],
                                                                                    retrospective=retroactive)
    print(f"Reachable ASes that existed in the first {retroactive} snapshots, but were removed and did not come back: {len(ases_reachable_removed_that_did_not_come_back)}")
    #print(ases_reachable_removed_that_did_not_come_back)
    #first_and_last_index_seen_for_reachables_removed_that_did_not_come_back = get_first_and_last_index_seen_for_asns(ases_reachable_removed_that_did_not_come_back, [stat.unique_reachables for stat in all_stats])           
    #print(f"Reachables removed that did not come back with their first and last seen indices: {first_and_last_index_seen_for_reachables_removed_that_did_not_come_back}")
    
    print("---")
    reachables_metrics = calculate_oscillation_metrics(all_stats, use_reachables=True)
    oscillating_reachables = set(reachables_metrics.oscillation_info.keys()) 
    
    print(f"Oscillating Reachable ASes (left and came back): {len(oscillating_reachables)}")
    
    total_member_departures, total_reachable_departures = analyze_member_and_reachable_departures(all_stats)
    
    print(f"Total times member ASes left: {total_member_departures}")
    print(f"Total times reachable ASes left: {total_reachable_departures}")
    
    labels_summarized = summarized_date_labels(labels)
    max_labels=len(labels)//10 if len(labels) > 20 else None
    
    '''
    number_of_routes_lost_that_did_not_remove_members_or_reachables_per_member, number_of_routes_added_that_did_not_add_members_or_reachables_per_member = plot_mapping_changes(all_stats, labels_summarized, name, ip_version, subfolder, max_labels)
    
    top_n_number = 2
    plot_member_routes_lost_that_did_not_remove_new_ases(number_of_routes_lost_that_did_not_remove_members_or_reachables_per_member, labels_summarized, name, ip_version, subfolder, max_labels, top_n_number)
    plot_member_routes_that_did_not_add_new_ases(number_of_routes_added_that_did_not_add_members_or_reachables_per_member, labels_summarized, name, ip_version, subfolder, max_labels, top_n_number)
    '''
    members_who_are_also_reachables = set()
    for stat in all_stats:
        members_who_are_also_reachables.update(stat.unique_members - stat.unique_reachables)
    print(f"Member ASes that are not also reachables: {len(members_who_are_also_reachables)}")
    
    plot_list_as_line_plot(member_history, labels_summarized,title=f'Member ASes Over Time - {name} - IP{ip_version}', xlabel='Time', ylabel='Number of Member ASes', subfolder=subfolder, 
                           max_labels=max_labels, annotations=get_annotations())
    plot_list_as_line_plot(reachable_history, labels_summarized, title=f'{title_start} Reachable ASes Over Time {title_end}', xlabel='Time', ylabel='Number of Reachable ASes', subfolder=subfolder,
                           max_labels=max_labels, annotations=get_annotations())

    reachable_change_over_time = [len(stat.unique_reachables) - len(stat.unique_members) for stat in all_stats]
    plot_list_as_line_plot(reachable_change_over_time, labels_summarized, title=f'{title_start} Change in Reachable ASes Over Time (Reachables - Members) {title_end}', xlabel='Time', ylabel='Number of Reachable ASes - Number of Member ASes', subfolder=subfolder,
                           max_labels=max_labels, annotations=get_annotations())

    routes_over_time = calculate_routes_over_time(all_stats)
    plot_list_as_line_plot(routes_over_time, labels_summarized, title=f'{title_start} Routes Over Time {title_end}', xlabel='Time', ylabel='Number of Routes', subfolder=subfolder,
                           max_labels=max_labels, annotations=get_annotations())
    
    #best_path_average_over_time = calculate_best_path_average_over_time(all_stats)
    #plot_list_as_line_plot(best_path_average_over_time, labels_summarized, title=f'{title_start} Route Best Path Average Over Time {title_end}', xlabel='Time', ylabel='Average Best Path Length', subfolder=subfolder,
    #                       max_labels=max_labels, annotations=get_annotations())
    
if __name__ == "__main__":
    bview_simple_timeline()  
    create_window_with_all_rendered_graphs_this_session()