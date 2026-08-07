



import sys
from pathlib import Path

from src.ripe_bviews.timeline.path_improvements.bview_routes_improvements import calculate_average_path_length
from src.utils.print import print_information
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent)) 

from src.ripe_bviews.timeline.as_info_type.bview_info_type_graphs import plot_categories_from_ipverse_data
from src.ripe_bviews.timeline.as_info_type.bview_timeline_by_as_info_type import get_cnae_from_asn, refine_ipverse_info_list_simplified
from src.services.as_info import get_asn_lookup_from_ipverse, get_asn_type_from_ipverse
from src.services.nicbr import get_prefix_to_asn_mapping_data 
 
 
from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data_timeline_from_configs
 
 
from src.ripe_bviews.timeline.bview_vars import  get_labels_info, get_subfolder, get_title_end, get_title_start 
 
from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data_timeline_from_configs
from src.ripe_bviews.download_and_parse.load_configs import load_configs, print_config 
from src.ripe_bviews.oscillations.bview_oscillation_logic import OscillationMetrics, calculate_oscillation_metrics 
import warnings 
from src.utils.graphs import create_window_with_all_rendered_graphs_this_session, plot_list_as_bar_plot, plot_list_as_line_plot, plot_map_as_bar_plot, plot_stacked_line_plot

 
warnings.filterwarnings('ignore', category=UserWarning, message='.*') 
 



def bview_timeline_ip_version(all_required_data):

    config = all_required_data["config"]

    ixp_name = config.get("name")
    
    peeringdb_data = all_required_data["caida_data"]

    all_stats_v4, labels = load_bview_data_timeline_from_configs(config, ip_version="v4",
                                                                 load_from_routeviews=True,
                                                                 load_from_both_routeviews_and_rrc=False,
                                                              ignored_dates=["20251205.0000"])       
    
    
    all_stats_v6, labels = load_bview_data_timeline_from_configs(config, ip_version="v6",
                                                                 load_from_routeviews=True,  load_from_both_routeviews_and_rrc=False,
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
        
        prefixes_it_announces = all_stats_v4[focused_index].get_unique_prefixes_for_member(asn) 

        if len(prefixes_it_announces) == 1 and list(prefixes_it_announces)[0] in ["0.0.0.0/0", "::/0"]:
            # Skip default routes for ownership/reachability analysis
            continue
        
        if asn not in focused_member_history_v6:
            members_only_v4.append(asn)
        else:
            members_both.append(asn)

    for asn in focused_member_history_v6:
        prefixes_it_announces = all_stats_v6[focused_index].get_unique_prefixes_for_member(asn)
    
    
        if len(prefixes_it_announces) == 1 and list(prefixes_it_announces)[0] in ["0.0.0.0/0", "::/0"]:
            # Skip default routes for ownership/reachability analysis
            continue

        if asn not in focused_member_history_v4:
            members_only_v6.append(asn)
        

    total_percentage = len(members_only_v4) + len(members_only_v6) + len(members_both)
    if total_percentage > 0: 
        plot_list_as_bar_plot(["Only IPv4", "Only IPv6", "Both"], [len(members_only_v4)/total_percentage, len(members_only_v6)/total_percentage, len(members_both)/total_percentage],
                            is_percentage=True,
                            title=f'{title_start} Number of Member ASes announccing, by IP Version - {labels_summarized[focused_index].replace("/", ".")}', 
                            xlabel='IP Version Membership', ylabel='Number of Member ASes', subfolder=subfolder)
    
    
    with open("members_only_v4.txt", "w") as f:
        f.write("[")
        for asn in members_only_v4:
            f.write(f'"{asn}", ')
        f.write("]")
    print(f"Saved members_only_v4 to members_only_v4.txt with {len(members_only_v4)} ASes.")


    asn_lookup = get_asn_lookup_from_ipverse()
    cnae_mapping_count = {}


    check_asn_types = input("Check asn types? (y/n)")

    if check_asn_types == "y":
        results_for_ipverse = [get_asn_type_from_ipverse(asn_lookup, a) for a in members_only_v4]

        results_for_ipverse = refine_ipverse_info_list_simplified(
            asn_lookup,
            results_for_ipverse, 
            None,
            peeringdb_data
        ) 


        print(cnae_mapping_count) 

        if len(cnae_mapping_count) > 0:
            plot_map_as_bar_plot(cnae_mapping_count,
                                title="CNAE From ASes that had type unknown and only IPv4 announcements")
        else:
            
            prefix_to_asn_nic_mapping_df = get_prefix_to_asn_mapping_data()
    
            for asn in members_only_v4:
                cnae = get_cnae_from_asn(int(asn), prefix_to_asn_nic_mapping_df)
                if cnae == None:
                    cnae = "not-available"
                if cnae not in cnae_mapping_count:
                    cnae_mapping_count[cnae] = 0
                cnae_mapping_count[cnae] += 1  
            
            print(cnae_mapping_count)
            plot_map_as_bar_plot(cnae_mapping_count,
                                title="CNAE From ASes with only IPv4 announcements",
                                sort_by_size=True,
                                sort_by_size_cut=5
                                )
            
        plot_categories_from_ipverse_data(results_for_ipverse, f"{ixp_name} Missing IPv6", labels)

    focused_reachable_v4 = all_stats_v4[focused_index].unique_reachables
    focused_reachable_v6 = all_stats_v6[focused_index].unique_reachables

    reachables_only_v4  = []
    reachables_only_v6 = []
    reachables_both = [] 

    focused_asn = "6939" # Hurricane
 
    set_reachable_v4 = set(focused_reachable_v4)
    set_reachable_v6 = set(focused_reachable_v6)

    # 2. Convert mapping lists into dictionaries for O(1) key lookups
    # Assumes 'reachable' values are unique per mapping list.
    if focused_asn in all_stats_v4[focused_index].mappings and focused_asn in all_stats_v6[focused_index].mappings:
        mapping_v4_lookup = {m["reachable"]: m for m in all_stats_v4[focused_index].mappings[focused_asn]}
        mapping_v6_lookup = {m["reachable"]: m for m in all_stats_v6[focused_index].mappings[focused_asn]}
    else:
        mapping_v4_lookup = {}
        mapping_v6_lookup = {}
        
    # Initialize result lists
    reachables_only_v4 = []
    reachables_only_v6 = []
    reachables_both = []

    reachables_only_v4_focused_asn = [] 
    reachables_only_v6_focused_asn = [] 
    reachables_both_focused_asn = []  


    for asn in focused_reachable_v4:
        if asn not in set_reachable_v6:   
            reachables_only_v4.append(asn)
            if asn in mapping_v4_lookup:  # O(1) check
                reachables_only_v4_focused_asn.append(mapping_v4_lookup[asn]) 
        else:
            reachables_both.append(asn)
            if asn in mapping_v4_lookup:  
                reachables_both_focused_asn.append(mapping_v4_lookup[asn]) 

    # 4. Process v6 reachables
    for asn in focused_reachable_v6:
        if asn not in set_reachable_v4:  
            reachables_only_v6.append(asn)
            if asn in mapping_v6_lookup:  
                reachables_only_v6_focused_asn.append(mapping_v6_lookup[asn]) 
    
    total_percentage = len(reachables_only_v4) + len(reachables_only_v6) + len(reachables_both)
    if total_percentage > 0:
        plot_list_as_bar_plot(["Only IPv4", "Only IPv6", "Both"], [len(reachables_only_v4)/total_percentage, len(reachables_only_v6)/total_percentage, len(reachables_both)/total_percentage],
                            is_percentage=True,
                            title=f'{title_start} Reachable ASes at by IP Version - {labels_summarized[focused_index].replace("/", ".")}', 
                            xlabel='IP Version Membership', ylabel='Number of Reachable ASes', subfolder=subfolder)
    
   
    plot_list_as_bar_plot(["Only IPv4", "Only IPv6", "Both"], [len(reachables_only_v4_focused_asn), len(reachables_only_v6_focused_asn), len(reachables_both_focused_asn)],
                            title=f'{title_start} Reachable ASes at by IP Version for ASN {focused_asn} - {labels_summarized[focused_index].replace("/", ".")}', 
                            xlabel='IP Version Membership', ylabel='Number of Reachable ASes', subfolder=subfolder)
    
    plot_list_as_bar_plot(["Only IPv4", "Only IPv6", "Both"],  
                          [len(reachables_only_v4_focused_asn)/len(reachables_only_v4), 
                           
                       len(reachables_only_v6_focused_asn)/len(reachables_only_v6), len(reachables_both_focused_asn)/len(reachables_both)],
                           data_annotated_values=[
                               f"{len(reachables_only_v4_focused_asn)}",
                                 f"{len(reachables_only_v6_focused_asn)}",
                                    f"{len(reachables_both_focused_asn)}"
                           ],
                            is_percentage=True,
                            title=f'{title_start} Reachable ASes at by IP Version for ASN {focused_asn} - {labels_summarized[focused_index].replace("/", ".")}', 
                            xlabel='IP Version Membership', ylabel='Percentage of Reachable ASes', subfolder=subfolder)

    ''' 
    plot_stacked_line_plot([member_history_v4, member_history_v6], 
                           ["IPv4", "IPv6"],
                           x_labels=labels_summarized,title=f'{title_start} Member ASes Over Time by IP Version - {title_end}', xlabel='Time', ylabel='Number of Member ASes', subfolder=subfolder, 
                           max_labels=max_labels, annotations=get_annotations())
    '''


    # more routes in IPv4 or IPv6?
    routes_more_v4 = 0
    routes_more_v6 = 0
    routes_same = 0
    routes_both_zero = 0


    # routes are more specific (prefix mask) in IPv4 or IPv6?
    specific_more_v4 = 0
    specific_more_v6 = 0
    specific_both_zero_or_same = 0

    # routers are, on average, shorter (AS_PATH) in IPv4 of IPv6? For each AS
    shorter_v4 = 0
    shorter_v6 = 0
    shorter_same = 0

    # Quick debug print to check types and content
    if len(focused_member_history_v4) > 0:
        sample_asn = list(focused_member_history_v4)[0]
        sample_prefixes = all_stats_v4[focused_index].get_unique_prefixes_for_member(sample_asn)
        print(f"[DEBUG] Sample ASN: {sample_asn} (Type: {type(sample_asn)})")
        print(f"[DEBUG] Sample Prefixes retrieved: {sample_prefixes}")

    # Set versions for reliable O(1) cross-referencing lookups
    # Ensure lookups work regardless of string or integer types
    v6_member_set = {str(x) for x in focused_member_history_v6}

    for asn in focused_member_history_v4:
        
        asn_lookup = asn 
        
        # Fetch prefixes
        prefixes_v4 = all_stats_v4[focused_index].get_unique_prefixes_for_member(asn_lookup) or []
        prefixes_v4 = [p for p in prefixes_v4 if p not in ["0.0.0.0/0", "::/0"]]
        
        prefixes_v6 = []
        if str(asn) in v6_member_set or asn in focused_member_history_v6:
            # Try to match the key type used in the v6 dataset
            v6_key = asn if asn in focused_member_history_v6 else str(asn)
            prefixes_v6 = all_stats_v6[focused_index].get_unique_prefixes_for_member(v6_key) or []
            prefixes_v6 = [p for p in prefixes_v6 if p not in ["0.0.0.0/0", "::/0"]]

        v4_count = len(prefixes_v4)
        v6_count = len(prefixes_v6)

        # 1. Total Route Comparison Logic
        if v4_count > v6_count:
            routes_more_v4 += 1
        elif v6_count > v4_count:
            routes_more_v6 += 1
        else:
            if v4_count > 0:
                routes_same += 1
            else:
                routes_both_zero += 1

        # 2. More Specific Route Comparison Logic
        v4_specifics = sum(1 for p in prefixes_v4 if '/' in p and int(p.split('/')[-1]) > 24)
        v6_specifics = sum(1 for p in prefixes_v6 if '/' in p and int(p.split('/')[-1]) > 48)

        if v4_specifics > v6_specifics:
            specific_more_v4 += 1
        elif v6_specifics > v4_specifics:
            specific_more_v6 += 1
        else:
            specific_both_zero_or_same += 1

        average_as_path_length_v4 = calculate_average_path_length(all_stats_v4[focused_index],
        for_asn=str(asn))
        average_as_path_length_v6 = calculate_average_path_length(all_stats_v6[focused_index],
        for_asn=str(asn))
        if average_as_path_length_v4 == -1 or average_as_path_length_v6 == -1:
            pass
        else:
            if average_as_path_length_v4 > average_as_path_length_v6:
                shorter_v6 += 1 
            elif average_as_path_length_v6 > average_as_path_length_v4:
                shorter_v4 += 1
            else:
                shorter_same += 1

    # Handle ASes exclusively present in the IPv6 timeline
    v4_member_set = {str(x) for x in focused_member_history_v4}
    for asn in focused_member_history_v6:
        if str(asn) not in v4_member_set and asn not in focused_member_history_v4:
            prefixes_v6 = all_stats_v6[focused_index].get_unique_prefixes_for_member(asn) or []
            prefixes_v6 = [p for p in prefixes_v6 if p not in ["0.0.0.0/0", "::/0"]]
            
            if len(prefixes_v6) > 0:
                routes_more_v6 += 1
            else:
                routes_both_zero += 1
                
            v6_specifics = sum(1 for p in prefixes_v6 if '/' in p and int(p.split('/')[-1]) > 48)
            if v6_specifics > 0:
                specific_more_v6 += 1
            else:
                specific_both_zero_or_same += 1

    
    print_information("Route Announcement Balance",
                      {
                          "More v4 routes": f"{routes_more_v4} ASes",
                          "More v6 routes": f"{routes_more_v6} ASes",
                          "Same active routes in both": f"{routes_same} ASes"
                      }
    )   
    
    print_information("IP Version with Shorter Routes (for ASes that exist in both)",
                      {
                          "Shorter Average in v4 routes": f"{shorter_v4} ASes",
                          "Shorter Average in v6 routes": f"{shorter_v6} ASes", 
                          "Same average in both": f"{shorter_same} ASes"
                      }
    )   
    

    #print(f"Zero routes in both: {routes_both_zero} ASes")
    #print(f"More specific v4 routes: {specific_more_v4} ASes | More specific v6 routes: {specific_more_v6} ASes | Both same/zero: {specific_both_zero_or_same} ASes\n")

    # Plot Total Routes Breakdown (Excluding dual-zeroes to keep the graph meaningful)
    if (routes_more_v4 + routes_more_v6 + routes_same) > 0:
        plot_list_as_bar_plot(
            ["More IPv4", "More IPv6", "Same (Active)"], 
            [routes_more_v4, routes_more_v6, routes_same],
            title=f'{title_start} Route Announcement Majority by AS - {labels_summarized[focused_index].replace("/", ".")}', 
            xlabel='Majority Category', ylabel='Number of ASes', subfolder=subfolder
        )