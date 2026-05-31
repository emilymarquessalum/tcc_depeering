


import sys
from pathlib import Path
import warnings

 
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent)) 
from src.utils.graphs import create_window_with_all_rendered_graphs_this_session, plot_list_as_heat_map, plot_list_as_line_plot

from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data_timeline_from_configs
from src.ripe_bviews.download_and_parse.load_configs import load_configs, print_config
from src.ripe_bviews.read_bgpdump import BGPDumpSnapshotStats
from src.ripe_bviews.timeline.bview_vars import get_ip_version, get_labels_info, get_subfolder, get_subfolder, get_title_start
 
from src.ripe_bviews.oscillations.bview_oscillation_logic import calculate_oscillation_metrics, OscillationMetrics

warnings.filterwarnings('ignore', category=UserWarning, message='.*')
relevant_cdns = [
    {"asn": "15169", "name": "Google"},
    {"asn": "32934", "name": "Meta"},   
    {"asn": "2906", "name": "Netflix"}
]

def get_reach_relevance_to_connectivity(asn: str, stat: BGPDumpSnapshotStats):
    
    total_existing_paths = 0
    paths_from_asn = len(stat.mappings[asn] if asn in stat.mappings else [])
    for asn_in_stat, paths in stat.mappings.items():
        if asn_in_stat != asn:
            total_existing_paths += len(paths)
    reach_relevance = paths_from_asn / total_existing_paths if total_existing_paths > 0 else 0
    return reach_relevance

def get_reach_uniqueness_of_reachables_from_asn(asn: str, stat: BGPDumpSnapshotStats): 
    paths_from_asn = stat.mappings.get(asn, [])
    
    if not paths_from_asn:
        return 0
    
    target_reachables = {path["reachable"] for path in paths_from_asn if "reachable" in path}
     
    other_reachables = set()
    for asn_in_stat, paths in stat.mappings.items():
        if asn_in_stat != asn:
            for path in paths:
                if "reachable" in path:
                    other_reachables.add(path["reachable"])
 
    unique_reachables = target_reachables - other_reachables
    
    return len(unique_reachables) / len(target_reachables) if target_reachables else 0

def get_average_reach_relevance_to_connectivity_over_time(asn: str, all_stats: list[BGPDumpSnapshotStats]):
    reach_relevance_over_time = []
    for stat in all_stats:
        reach_relevance = get_reach_relevance_to_connectivity(asn, stat)
        reach_relevance_over_time.append(reach_relevance)
    
    average_reach_relevance = sum(reach_relevance_over_time) / len(reach_relevance_over_time) if reach_relevance_over_time else 0
    return average_reach_relevance

def get_average_reach_uniqueness_of_reachables_from_asn_over_time(asn: str, all_stats: list[BGPDumpSnapshotStats]):
    reach_uniqueness_over_time = []
    for stat in all_stats:
        reach_uniqueness = get_reach_uniqueness_of_reachables_from_asn(asn, stat)
        reach_uniqueness_over_time.append(reach_uniqueness)
    
    average_reach_uniqueness = sum(reach_uniqueness_over_time) / len(reach_uniqueness_over_time) if reach_uniqueness_over_time else 0
    return average_reach_uniqueness

def get_average_number_of_paths_from_asn_over_time(asn: str, all_stats: list[BGPDumpSnapshotStats]):
    paths_over_time = []
    for stat in all_stats:
        member_mappings = stat.mappings.get(asn, [])
        paths_from_asn = len(member_mappings)
        paths_over_time.append(paths_from_asn)
    
    average_paths = sum(paths_over_time) / len(paths_over_time) if paths_over_time else 0
    return average_paths
 


def get_reach_quality_of_reachables_from_asn(asn: str, stat: BGPDumpSnapshotStats): 
    
    paths_from_asn = stat.mappings.get(asn, [])
    
    if not paths_from_asn:
        return 0
    
    times_the_asn_is_the_shortest_path = 0
    times_the_asn_is_not_the_shortest_path = 0
    times_the_asn_is_the_worst_path = 0
    times_the_asn_is_the_only_path_length = 0

    reachables = stat.get_all_reachables_for_member(asn)
    #print(f"AS {asn} reachables: {len(reachables)}")
    for reachable in reachables:
        
        shortest_as_path_length_from_asn = stat.get_shortest_as_path_length_for_member_to_reach_asn(asn, reachable)[0]

        shortest_as__path_length_for_reachable = stat.get_shortest_as_path_length_for_reachable(reachable)[0]
        worst_as_path_length_for_reachable = stat.get_worst_as_path_length_for_reachable(reachable)[0]
         
        # the shortest can only be the worst if there is no other option
        if shortest_as__path_length_for_reachable == worst_as_path_length_for_reachable:
            times_the_asn_is_the_only_path_length += 1
            continue
  
        
        if shortest_as_path_length_from_asn == shortest_as__path_length_for_reachable:
            times_the_asn_is_the_shortest_path += 1
            continue

        times_the_asn_is_not_the_shortest_path += 1

        if shortest_as_path_length_from_asn == worst_as_path_length_for_reachable:
            times_the_asn_is_the_worst_path += 1

    print(f"For {asn}")
    print(f"Shortest paths: {times_the_asn_is_the_shortest_path}")
    print(f"Not shortest paths: {times_the_asn_is_not_the_shortest_path}")
    print(f"Longest paths: {times_the_asn_is_the_worst_path}")
    print(f"Only path lengths: {times_the_asn_is_the_only_path_length}") 

def get_aspath_data_from_asn_over_time(asn: str, all_stats: list[BGPDumpSnapshotStats]):
    aspath_data_over_time = [] 
    reachable_asns_over_time = []
    # as path length
    for stat in all_stats:
        paths = stat.mappings.get(asn, [])
        aspath_lengths = [len(path["as_path"]) for path in paths]
        aspath_data_over_time.append(aspath_lengths)
        reachable_asns_over_time.append([path["reachable"] for path in paths])

    return aspath_data_over_time, reachable_asns_over_time

def get_aspath_data_to_asn_over_time(asn: str, all_stats: list[BGPDumpSnapshotStats]) -> tuple[list[list[int]], list[set[str]]]:
    aspath_data_over_time = [] 
    members_that_allow_asn_to_be_reachable_over_time = []
    # as path length
    for stat in all_stats:
        members = stat.get_all_members_that_allow_asn_to_be_reachable(asn)
        aspath_lengths = []
        members_that_allow_asn_to_be_reachable_over_time.append(members)
        for member in members:
            paths = stat.mappings.get(member, [])
            for path in paths:
                if str(path["reachable"]) == asn:
                    aspath_lengths.append(len(path["as_path"]))
        aspath_data_over_time.append(aspath_lengths)
    return aspath_data_over_time, members_that_allow_asn_to_be_reachable_over_time

def get_asn_presence_list(all_stats: list[BGPDumpSnapshotStats], asn: str):
    return [1 if int(asn) in stat.unique_members else 0 for stat in all_stats]


# Considers how long the AS was present in the timeline
def get_asn_confiability(asn: str, all_stats: list[BGPDumpSnapshotStats]):
    
    presence = get_asn_presence_list(all_stats, asn)
    confiability = sum(presence) / len(presence) if presence else 0
    return confiability

# Considers how much of the time present in the timeline the AS was oscillating 
# ex: 50%: 50% of snapshots where the AS was present was it returning from an oscillation 
def get_asn_consistency(asn: str, all_stats: list[BGPDumpSnapshotStats], oscillation_metrics: OscillationMetrics):
    presence = get_asn_presence_list(all_stats, asn)
    if not presence:
        return 0
    
    oscillation_count = oscillation_metrics.get_as_oscillation_count(asn)
    consistency = 1 - (oscillation_count / sum(presence)) if sum(presence) > 0 else 0
    return consistency


config = load_configs("ixbr.json")
ip_version = get_ip_version(config)

title_start = get_title_start(config) 
subfolder = get_subfolder(config, ip_version) + "AS_metrics/"
print_config(config, ip_version)
all_stats, labels = load_bview_data_timeline_from_configs(config, ip_version=ip_version)       


def check_asn_connectivity_metrics(asn_to_consider: str, all_stats: list[BGPDumpSnapshotStats]):

    reach_relevance_to_connectivity = get_average_reach_relevance_to_connectivity_over_time(asn_to_consider, all_stats)
    reach_uniqueness_of_reachables = get_average_reach_uniqueness_of_reachables_from_asn_over_time(asn_to_consider, all_stats)
    print(f"Average reach_relevance to connectivity for AS {asn_to_consider}: {reach_relevance_to_connectivity:.2%}")
    print(f"Average reach_uniqueness of reachables from AS {asn_to_consider}: {reach_uniqueness_of_reachables:.2%}")
    

def get_cdns_info():
    for cdn in relevant_cdns:
        cdn_asn = cdn["asn"]
        aspath_data_over_time, members_that_allow_asn_to_be_reachable_over_time = get_aspath_data_to_asn_over_time(cdn_asn, all_stats)
        
        average_aspath_length_over_time = [sum(lengths) / len(lengths) if lengths else 0 for lengths in aspath_data_over_time]
        if average_aspath_length_over_time == [0] * len(average_aspath_length_over_time):
            print(f"No paths to AS {cdn_asn} ({cdn['name']}) found in the data (not reachable).")
            is_member = any(cdn_asn in stat.mappings for stat in all_stats)
            # member but not reachable (very weird but can happen apparently)
            if is_member:
                print(f"AS {cdn_asn} is a member.")
                '''
                asn_presence_list = get_asn_presence_list(all_stats, cdn_asn)
                plot_list_as_line_plot(asn_presence_list,
                                        y=labels_summarized, max_labels=max_labels,
                                    title=f"{title_start} Presence of AS {cdn_asn} ({cdn['name']}) Over Time", 
                                    subfolder=subfolder)
                '''

                cdn_member_aspath_data, cdn_member_reachable_asns = get_aspath_data_from_asn_over_time(cdn_asn, all_stats)
                number_of_paths_over_time = [len(paths) for paths in cdn_member_aspath_data]
                print(f"For {cdn}, reachables: {cdn_member_reachable_asns}")
                '''
                plot_list_as_line_plot(number_of_paths_over_time,
                                        y=labels_summarized, max_labels=max_labels,
                                    title=f"{title_start} Number of Paths from AS {cdn_asn} ({cdn['name']}) Over Time", 
                                    subfolder=subfolder)
                '''

                '''
                plot_list_as_line_plot(
                    [sum(lengths) / len(lengths) if lengths else 0 for lengths in cdn_member_aspath_data],
                    y=labels_summarized, max_labels=max_labels,
                    title=f"{title_start} Average AS Path Length from AS {cdn_asn} ({cdn['name']})",  
                    subfolder=subfolder) 
                '''
            continue

        #print(f"AS {cdn} members that give access to AS {cdn_asn}: {members_that_allow_asn_to_be_reachable_over_time}")

        is_exclusively_direct_peering = all(members == {cdn_asn} for members in members_that_allow_asn_to_be_reachable_over_time)
        if is_exclusively_direct_peering:
            print(f"AS {cdn_asn} ({cdn['name']}) is directly peering with the monitored AS throughout the timeline (only the ASN gives access to itself, {cdn_asn}->{cdn_asn}).")
            continue
        plot_list_as_line_plot(
        average_aspath_length_over_time  ,
            y=labels_summarized, max_labels=max_labels,
                            
                            title=f"{title_start} Average AS Path Length to AS {cdn_asn} ({cdn['name']})",  
                            
                            subfolder=subfolder)

        number_of_paths_over_time = [len(paths) for paths in aspath_data_over_time]
        plot_list_as_line_plot(number_of_paths_over_time,
                                y=labels_summarized, max_labels=max_labels,
                            title=f"{title_start} Number of Paths to AS {cdn_asn} ({cdn['name']}) Over Time", 
                            subfolder=subfolder)



def show_asn_confiability_consistency():
        consistency_confiability_list = []
        oscillation_metrics = calculate_oscillation_metrics(all_stats) 
        all_unique_members = set()
        for stat in all_stats:
            all_unique_members.update(stat.unique_members)

        for member in all_unique_members:
            member_consistency = get_asn_consistency(member, all_stats, oscillation_metrics)
            member_confiability = get_asn_confiability(member, all_stats)
            consistency_confiability_list.append((member, member_consistency, member_confiability))

        consistency_confiability_map = [
            [0,0,0],
            [0,0,0],
            [0,0,0]
        ]

        # creates 9 different categories based on the thresholds for consistency and confiability
        high_confiability_threshold = 0.9
        low_confiability_threshold = 0.2
        high_consistency_threshold = 0.9
        low_consistency_threshold = 0.2

        for member, consistency, confiability in consistency_confiability_list:
            confiability_index = 0
            if confiability >= high_confiability_threshold:
                confiability_index = 2
            elif confiability >= low_confiability_threshold:
                confiability_index = 1
            consistency_index = 0
            if consistency >= high_consistency_threshold:
                consistency_index = 2
            elif consistency >= low_consistency_threshold:
                consistency_index = 1
            consistency_confiability_map[consistency_index][confiability_index] += 1

        plot_list_as_heat_map(
            consistency_confiability_map,
            x_labels=["Low Conf.", "Medium Conf.", "High Conf."],
            y_labels=["Low Cons.", "Medium Cons.", "High Cons."],
            title=f"{title_start} Consistency vs Confiability of ASes in the Timeline",  
            subfolder=subfolder
        )

if __name__ == "__main__":

    # heavy to run
    #check_asn_connectivity_metrics("264943", [all_stats[0]]) 
    #check_asn_connectivity_metrics("6939", [all_stats[0], all_stats[1]])
    #check_asn_connectivity_metrics("9498", [all_stats[0], all_stats[1]])

    get_reach_quality_of_reachables_from_asn("6939", all_stats[0])
    labels_summarized, max_labels = get_labels_info(labels)

    create_window_with_all_rendered_graphs_this_session()
    #show_asn_confiability_consistency() 