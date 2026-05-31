

 
 

import sys
from pathlib import Path
 
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent)) 
 
from src.ripe_bviews.bview_labels import get_max_labels, summarized_date_labels
from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data_timeline_from_configs
from src.ripe_bviews.download_and_parse.load_configs import load_configs, print_config
from src.ripe_bviews.read_bgpdump import BGPDumpSnapshotStats
from src.ripe_bviews.timeline.bview_vars import get_annotations, get_ip_version, get_subfolder, get_subfolder, get_title_end, get_title_start
from src.utils.graphs import create_window_with_all_rendered_graphs_this_session, plot_list_as_bar_plot, plot_list_as_line_plot, plot_stacked_line_plot


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
        


def calculate_routes_over_time(all_stats: list[BGPDumpSnapshotStats], group_by_path_length=False,
                               group_by_member=False):
    routes_over_time = []
    routes_over_time_by_length = []
    routes_over_time_by_member = []

    for stat in all_stats:

        total_routes_by_length = []  # index is path length, value is total routes with that path length
        total_routes_by_member = {}  # key is member ASN, value is total routes for that member
        total_routes = 0

        if group_by_member:
            for member_asn, member_mappings in stat.mappings.items():
                total_routes_for_member = len(member_mappings)
                total_routes_by_member[member_asn] = total_routes_for_member
                if member_asn not in routes_over_time_by_member:
                    routes_over_time_by_member[member_asn] = []
                routes_over_time_by_member[member_asn].append(total_routes_for_member)
            routes_over_time_by_member.append(total_routes_by_member)

        if group_by_path_length:
            for member_mappings in stat.mappings.values():
                for mapping in member_mappings:
                    path_length = len(mapping["as_path"])
                    if len(total_routes_by_length) <= path_length:
                        total_routes_by_length.extend([0] * (path_length - len(total_routes_by_length) + 1))
                    total_routes_by_length[path_length] = total_routes_by_length[path_length] + 1
            routes_over_time_by_length.append(total_routes_by_length)
        else:
            for member_mappings in stat.mappings.values():
                total_routes += len(member_mappings)                
            routes_over_time.append(total_routes)
    
    if group_by_path_length:
        clean_routes_over_time_by_length = []
        max_length = max(len(r) for r in routes_over_time_by_length)

        for r in routes_over_time_by_length:
            r.extend([0] * (max_length - len(r)))
            clean_routes_over_time_by_length.append(r)
            
        return clean_routes_over_time_by_length
    
    return routes_over_time



def plot_routes_over_time(all_stats, labels_summarized, title_start, title_end, subfolder, max_labels):
    routes_over_time = calculate_routes_over_time(all_stats)
    plot_list_as_line_plot(routes_over_time, labels_summarized, title=f'{title_start} Routes Over Time {title_end}', xlabel='Time', ylabel='Number of Routes', subfolder=subfolder,
                           max_labels=max_labels, annotations=get_annotations())
    
    routes_over_time_by_length = calculate_routes_over_time(all_stats, group_by_path_length=True)
    
    start_length_used = 1
    max_length_used = 5
    over_time_reorganized = []
    for i in range(start_length_used, start_length_used + max_length_used):
        path_length_group = []
        for snapshot in routes_over_time_by_length:
            if i < len(snapshot):
                path_length_group.append(snapshot[i])
            else:
                path_length_group.append(0)
        over_time_reorganized.append(path_length_group)
    plot_stacked_line_plot(
        over_time_reorganized,
        [f'Path Length {i}' for i in range(start_length_used, start_length_used + max_length_used)],
        x_labels=labels_summarized,
        title=f'{title_start} Routes Over Time by Path Length {title_end}',
    )

    route_as_path_length_distribution_in_last_snapshot = routes_over_time_by_length[-1]

    plot_list_as_bar_plot(
        [i for i in range(1,len(route_as_path_length_distribution_in_last_snapshot))],
        route_as_path_length_distribution_in_last_snapshot[1:],
        title=f'{title_start} Distribution of Path Lengths for Routes in Last Snapshot {title_end}',
        xlabel='Path Length',
        ylabel='Number of Routes',
        subfolder=subfolder,
        max_x_value=10
    )



def calculate_shortest_path_average_over_time(all_stats: list[BGPDumpSnapshotStats]):
    """Calculate the average shortest path length for arriving at each reachable for each day."""
    shortest_path_averages = []
    for stat in all_stats:
        shortest_path_lengths = []
        for reachable in stat.unique_reachables:
            shortest_length, _ = stat.get_shortest_as_path_length_for_reachable(reachable)
            if shortest_length is not None:
                shortest_path_lengths.append(shortest_length)
        
        # Calculate average for this day
        if shortest_path_lengths:
            average = sum(shortest_path_lengths) / len(shortest_path_lengths)
        else:
            average = 0
        shortest_path_averages.append(average)
    
    return shortest_path_averages

def calculate_routes_added_per_member(all_stats): 
    total_per_snapshot = []
    per_member_breakdown = [] 
    routes_added_that_improved_shortest_path_per_snapshot = []
    
    for i in range(1, len(all_stats)):

        routes_added_that_improved_shortest_path = 0
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
        unique_reachables_added_that_already_existed = set()

        for mapping in new_mappings_with_no_new_members_or_reachables:
            reachables = list(mapping.values())[0]
            total += len(reachables)
            member_dict[list(mapping.keys())[0]] = len(reachables)
            unique_reachables_added_that_already_existed.update(reachables)
        
        for reachable in unique_reachables_added_that_already_existed:
            shortest_path_length_before, _ = all_stats[i-1].get_shortest_as_path_length_for_reachable(reachable)
            shortest_path_length_after, _ = all_stats[i].get_shortest_as_path_length_for_reachable(reachable)
            if shortest_path_length_before is not None and shortest_path_length_after is not None and shortest_path_length_after < shortest_path_length_before:
                routes_added_that_improved_shortest_path += 1

        total_per_snapshot.append(total)
        per_member_breakdown.append(member_dict)
        routes_added_that_improved_shortest_path_per_snapshot.append(routes_added_that_improved_shortest_path)

    return total_per_snapshot, per_member_breakdown, routes_added_that_improved_shortest_path_per_snapshot

def calculate_routes_lost_that_did_not_lose_member_or_reachable_per_member(all_stats: list[BGPDumpSnapshotStats]): 
    total_per_snapshot: list[int] = [] 
    per_member_breakdown: list[dict] = []
    total_losses_that_made_shortest_path_worse_per_snapshot : list[int] = []
    
    for i in range(1, len(all_stats)):
        lost_mappings_with_no_removed_members_or_reachables : list[dict] = []
        
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
        unique_reachables_lost_that_still_exist = set()
        for mapping in lost_mappings_with_no_removed_members_or_reachables:
            reachables = list(mapping.values())[0] # get the reachables that were lost for this member, but that still exist in the new stat (because of other members)
            total += len(reachables)
            member_dict[list(mapping.keys())[0]] = len(reachables)
            unique_reachables_lost_that_still_exist.update(reachables)
        
        reachable_shortest_paths_before = [all_stats[i-1].get_shortest_as_path_length_for_reachable(reachable) for reachable in unique_reachables_lost_that_still_exist]
        reachable_shortest_paths_after = [all_stats[i].get_shortest_as_path_length_for_reachable(reachable) for reachable in unique_reachables_lost_that_still_exist]
        losses_that_made_shortest_path_worse = 0
        for before, after in zip(reachable_shortest_paths_before, reachable_shortest_paths_after):
            if before is not None and after is not None and after[0] > before[0]: # if the shortest path length for this reachable got worse after the loss, that means this loss had an impact on the shortest path, even if it didn't remove the reachable from the graph
                losses_that_made_shortest_path_worse += 1
        
        total_losses_that_made_shortest_path_worse_per_snapshot.append(losses_that_made_shortest_path_worse)
        total_per_snapshot.append(total)
        per_member_breakdown.append(member_dict)
    
    return total_per_snapshot, per_member_breakdown, total_losses_that_made_shortest_path_worse_per_snapshot


def plot_mapping_changes(all_stats, labels_summarized, name, ip_version, subfolder, max_labels):

    number_of_routes_added_that_did_not_add_new_members_or_reachables, number_of_routes_added_that_did_not_add_members_or_reachables_per_member, routes_added_that_improved_shortest_path_per_snapshot = calculate_routes_added_per_member(all_stats)
    number_of_routes_lost_that_did_not_remove_members_or_reachables, number_of_routes_lost_that_did_not_remove_members_or_reachables_per_member, total_losses_that_made_shortest_path_longer_per_snapshot = calculate_routes_lost_that_did_not_lose_member_or_reachable_per_member(all_stats)

    net_growth_of_mappings_with_no_new_members_or_reachables = [added - lost for added, lost in zip(number_of_routes_added_that_did_not_add_new_members_or_reachables, number_of_routes_lost_that_did_not_remove_members_or_reachables)]
    accumulated_net_growth_of_mappings_with_no_new_members_or_reachables = []
    accumulated = 0
    for net_growth in net_growth_of_mappings_with_no_new_members_or_reachables:
        accumulated += net_growth
        accumulated_net_growth_of_mappings_with_no_new_members_or_reachables.append(accumulated)

    plot_list_as_line_plot(total_losses_that_made_shortest_path_longer_per_snapshot, labels_summarized[1:],title=f'Number of Routes Lost That Made Shortest Path Longer - {name} - IP{ip_version}', xlabel='Time', ylabel='Number of Routes Lost That Made Shortest Path Longer', subfolder=subfolder,
                            max_labels=max_labels, annotations=get_annotations())
    
    total_losses_that_did_not_made_shortest_path_longer_per_snapshot = [lost - worse for lost, worse in zip(number_of_routes_lost_that_did_not_remove_members_or_reachables, total_losses_that_made_shortest_path_longer_per_snapshot)]
    plot_stacked_line_plot(
        [total_losses_that_made_shortest_path_longer_per_snapshot, total_losses_that_did_not_made_shortest_path_longer_per_snapshot],
        ['Made Shortest Path Longer', 'Did Not Make Shortest Path Longer'],
        x_labels=labels_summarized[1:],
        title=f'Number of Routes Lost That Did Not Remove Members or Reachables Per Snapshot - {name} - IP{ip_version}',
        xlabel='Time',
        ylabel='Number of Routes Lost That Did Not Remove Members or Reachables',
        subfolder=subfolder,
        max_labels=max_labels
    )

    total_gains_that_did_not_made_shortest_path_better_per_snapshot = [added - improved for added, improved in zip(number_of_routes_added_that_did_not_add_new_members_or_reachables, routes_added_that_improved_shortest_path_per_snapshot)]
    plot_stacked_line_plot(
        [routes_added_that_improved_shortest_path_per_snapshot, total_gains_that_did_not_made_shortest_path_better_per_snapshot],
        ['Made Shortest Path Shorter', 'Did Not Make Shortest Path Shorter'],
        x_labels=labels_summarized[1:],
        title=f'Number of Routes Added That Did Not Add New Members or Reachables Per Snapshot - {name} - IP{ip_version}',
        xlabel='Time',
        ylabel='Number of Routes Added That Did Not Add New Members or Reachables',
        subfolder=subfolder,
        max_labels=max_labels 
    )

    net_growth_route_shortest_path_improvement_per_snapshot = [improved - worse for improved, worse in zip(routes_added_that_improved_shortest_path_per_snapshot, total_losses_that_made_shortest_path_longer_per_snapshot)]
    plot_list_as_line_plot(net_growth_route_shortest_path_improvement_per_snapshot, labels_summarized[1:],title=f'Net Growth of Routes That Improved Shortest Path - {name} - IP{ip_version}', xlabel='Time', ylabel='Net Growth of Routes That Improved Shortest Path', subfolder=subfolder,
                            max_labels=max_labels, annotations=get_annotations())

    plot_list_as_line_plot(number_of_routes_added_that_did_not_add_new_members_or_reachables, labels_summarized[1:],title=f'New Mappings Added That Did Not Add New Members or Reachables - {name} - IP{ip_version}', xlabel='Time', ylabel='Number of New Mappings Added That Did Not Add New Members or Reachables', subfolder=subfolder,
                            max_labels=max_labels, annotations=get_annotations())
    plot_list_as_line_plot(number_of_routes_lost_that_did_not_remove_members_or_reachables, labels_summarized[1:],title=f'Mappings Lost That Did Not Remove Members or Reachables - {name} - IP{ip_version}', xlabel='Time', ylabel='Number of Mappings Lost That Did Not Remove Members or Reachables', subfolder=subfolder,
                            max_labels=max_labels, annotations=get_annotations()) 
    plot_list_as_line_plot(net_growth_of_mappings_with_no_new_members_or_reachables, labels_summarized[1:],title=f'Net Growth of Mappings With No New Members or Reachables - {name} - IP{ip_version}', xlabel='Time', ylabel='Net Growth of Mappings With No New Members or Reachables', subfolder=subfolder,
                            max_labels=max_labels, annotations=get_annotations())
    plot_list_as_line_plot(accumulated_net_growth_of_mappings_with_no_new_members_or_reachables, labels_summarized[1:],title=f'Accumulated Net Growth of Mappings With No New Members or Reachables - {name} - IP{ip_version}', xlabel='Time', ylabel='Accumulated Net Growth of Mappings With No New Members or Reachables', subfolder=subfolder,
                            max_labels=max_labels, annotations=get_annotations())
    
    return number_of_routes_lost_that_did_not_remove_members_or_reachables_per_member, number_of_routes_added_that_did_not_add_members_or_reachables_per_member, total_losses_that_made_shortest_path_longer_per_snapshot


#shortest_path_average_over_time = calculate_shortest_path_average_over_time(all_stats)
#plot_list_as_line_plot(shortest_path_average_over_time, labels_summarized, title=f'{title_start} Route Shortest Path Average Over Time {title_end}', xlabel='Time', ylabel='Average Shortest Path Length', subfolder=subfolder,
#                       max_labels=max_labels, annotations=get_annotations())

#number_of_routes_lost_that_did_not_remove_members_or_reachables_per_member, number_of_routes_added_that_did_not_add_members_or_reachables_per_member = 

if __name__ == "__main__":
    config = load_configs("AMS-IX.json")
    config = load_configs("ixbr.json")

    ip_version = get_ip_version(config)
    print_config(config, ip_version)

    name = config.get("name", "Unknown")
    
    
    all_stats, labels = load_bview_data_timeline_from_configs(config, ip_version=ip_version,
                                                              ignored_dates=["20251205.0000"])    

    labels_summarized = summarized_date_labels(labels)
    title_start = get_title_start(config)
    title_end = get_title_end(config)
    subfolder = get_subfolder(config, ip_version)
    max_labels = get_max_labels(labels)
    
    #plot_mapping_changes(all_stats, labels_summarized, name, ip_version, subfolder, max_labels)
    plot_routes_over_time(all_stats, labels_summarized, title_start, title_end, subfolder, max_labels)

 
    create_window_with_all_rendered_graphs_this_session()
'''  
top_n_number = 2
plot_member_routes_lost_that_did_not_remove_new_ases(number_of_routes_lost_that_did_not_remove_members_or_reachables_per_member, labels_summarized, name, ip_version, subfolder, max_labels, top_n_number)
plot_member_routes_that_did_not_add_new_ases(number_of_routes_added_that_did_not_add_members_or_reachables_per_member, labels_summarized, name, ip_version, subfolder, max_labels, top_n_number)
'''  