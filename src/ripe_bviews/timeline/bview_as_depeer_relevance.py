

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


def get_peak_change_dates(all_stats, labels, look_at_added=False, change_in="members"):
    max_change = -1
    max_change_index = -1
    
    for i in range(1, len(all_stats)):
        if change_in == "reachables":
            current_ases = set(all_stats[i].unique_reachables)
            previous_ases = set(all_stats[i-1].unique_reachables)
        else:  # members
            current_ases = set(all_stats[i].unique_members)
            previous_ases = set(all_stats[i-1].unique_members)
        
        if look_at_added:
            change = len(current_ases - previous_ases)
        else:
            change = len(previous_ases - current_ases)
        
        if change > max_change:
            max_change = change
            max_change_index = i
    
    if max_change_index == -1:
        return None, None
    
    previous_date = labels[max_change_index - 1]
    current_date = labels[max_change_index]
    
    return previous_date, current_date


def analyze_asn_changes_between_dates(all_stats, labels, previous_date, current_date, change_in="members"):
    prev_idx = labels.index(previous_date)
    curr_idx = labels.index(current_date)
    
    prev_stat = all_stats[prev_idx]
    curr_stat = all_stats[curr_idx]
    
    # Helper to map: { reachable_asn: { member_id: count_of_routes } }
    def build_reachable_map(stat):
        rmap = {}
        for member_str, mappings in stat.mappings.items():
            m_id = int(member_str) if member_str.isdigit() else member_str
            for entry in mappings:
                r_asn = entry["reachable"]
                if r_asn not in rmap:
                    rmap[r_asn] = {}
                rmap[r_asn][m_id] = rmap[r_asn].get(m_id, 0) + 1
        return rmap

    if change_in == "reachables":
        prev_reach_map = build_reachable_map(prev_stat)
        curr_reach_map = build_reachable_map(curr_stat)
        
        prev_set = set(prev_reach_map.keys())
        curr_set = set(curr_reach_map.keys())
        
        reachables_lost = prev_set - curr_set
        reachables_kept = prev_set & curr_set
        
        reachable_loss_info = {}
        for r in reachables_lost:
            members_map = prev_reach_map[r]
            reachable_loss_info[r] = {
                "members_lost_count": len(members_map),
                "members": set(members_map.keys()),
                "routes_lost": sum(members_map.values()),
                "routes_before": sum(members_map.values())
            }
            
        reachable_routes_lost_info = {}
        for r in reachables_kept:
            p_members = prev_reach_map[r]
            c_members = curr_reach_map.get(r, {})
            
            routes_before = sum(p_members.values())
            routes_after = sum(c_members.values())
            
            if routes_before > routes_after:
                # Find members who specifically lost routes for THIS reachable
                affected = {m for m in p_members if p_members[m] > c_members.get(m, 0)}
                reachable_routes_lost_info[r] = {
                    "routes_before": routes_before,
                    "routes_after": routes_after,
                    "routes_lost": routes_before - routes_after,
                    "members_affected": len(affected),
                    "members": affected
                }
        
        lost_sorted = sorted(reachable_loss_info.items(), key=lambda x: x[1]["members_lost_count"], reverse=True)
        routes_lost_sorted = sorted(reachable_routes_lost_info.items(), key=lambda x: x[1]["routes_lost"], reverse=True)
        return lost_sorted, routes_lost_sorted

    else:
        # Optimized Member Logic
        prev_m = set(prev_stat.unique_members)
        curr_m = set(curr_stat.unique_members)
        
        asns_lost = prev_m - curr_m
        asns_kept_routes_lost = {}
        
        for asn in (prev_m & curr_m):
            p_count = len(prev_stat.mappings.get(str(asn), []))
            c_count = len(curr_stat.mappings.get(str(asn), []))
            if p_count > c_count:
                asns_kept_routes_lost[asn] = (p_count, c_count)
        
        # Pre-calculate counts to avoid repeated len() in sort
        lost_with_counts = [(asn, len(prev_stat.mappings.get(str(asn), []))) for asn in asns_lost]
        
        asns_lost_sorted = sorted(lost_with_counts, key=lambda x: x[1], reverse=True)
        asns_kept_sorted = sorted(asns_kept_routes_lost.items(), key=lambda x: x[1][0] - x[1][1], reverse=True)
        
        return asns_kept_sorted, asns_lost_sorted


if __name__ == "__main__":
    config = load_configs("ixbr.json")
    ip_version = get_ip_version(config)
    print_config(config, ip_version)
    #config = load_configs("AMS-IX.json")

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
    
    change_in = "reachables"

    start, end = get_peak_change_dates(all_stats, labels, look_at_added=False,
                                       change_in=change_in)
    print(f"Peak loss between {start} and {end}")
    print(f"Lost Members between {start} and {end}:")
    print(len(set(all_stats[labels.index(start)].unique_members) - set(all_stats[labels.index(end)].unique_members)))
    print(f"Lost Reachables between {start} and {end}:")
    print(len(set(all_stats[labels.index(start)].unique_reachables) - set(all_stats[labels.index(end)].unique_reachables)))
    
    reachables_lost_sorted, reachables_lost_routes_sorted = analyze_asn_changes_between_dates(all_stats, labels, start, end, change_in=change_in)
    members_kept_sorted, members_lost_sorted = analyze_asn_changes_between_dates(all_stats, labels, start, end, change_in="members")
    
    top_n = 3


    print(f"\nTop {top_n} Reachables that were completely lost (from total {len(reachables_lost_sorted)}):")
    for reachable, loss_info in reachables_lost_sorted[:top_n]:
        members_list = ", ".join(str(m) for m in loss_info["members"])
        print(f"Reachable ASN {reachable} had {loss_info['routes_before']} routes before being lost and was lost by {loss_info['members_lost_count']} members: {members_list}")
    
    print(f"\nTop {top_n} Reachables that lost routes but stayed reachable (from total {len(reachables_lost_routes_sorted)}):")
    for reachable, loss_info in reachables_lost_routes_sorted[:top_n]:
        members_list = ", ".join(str(m) for m in loss_info["members"])
        print(f"Reachable ASN {reachable} lost {loss_info['routes_lost']} routes (from {loss_info['routes_before']} to {loss_info['routes_after']}) across {loss_info['members_affected']} members: {members_list}")
    
    print(f"\nTop {top_n} Members that left (from total {len(members_lost_sorted)}):")
    for member, routes_before in members_lost_sorted[:top_n]:
        print(f"Member ASN {member} was lost and had {routes_before} routes.")
    
    print(f"\nTop {top_n} Members that lost routes but stayed in IXP (from total {len(members_kept_sorted)}):")
    for member, (routes_before, routes_after) in members_kept_sorted[:top_n]:
        print(f"Member ASN {member} lost {routes_before - routes_after} routes (from {routes_before} to {routes_after}).")
    
    
     

    # Analyze match between top member's route losses and lost reachables
    if members_kept_sorted:
        top_member, (routes_before, routes_after) = members_kept_sorted[0]
        
        # Get all reachables that the top member had routes to in the "before" state
        prev_idx = labels.index(start)
        prev_stat = all_stats[prev_idx]
        
        top_member_reachables = set()
        member_mappings = prev_stat.mappings.get(str(top_member), [])
        for entry in member_mappings:
            top_member_reachables.add(entry["reachable"])
        
        # Get lost reachables
        lost_reachables_set = {r for r, _ in reachables_lost_sorted}
        
        # Calculate overlap
        overlap = top_member_reachables & lost_reachables_set
        match_ratio = len(overlap) / len(lost_reachables_set) if lost_reachables_set else 0
        
        print(f"\nTop Member ASN {top_member} analysis:")
        #print(f"  Reachables it had before: {len(top_member_reachables)}")
        print(f"  Reachables lost that it had routes for: {len(overlap)} out of {len(lost_reachables_set)}")
        print(f"  Match ratio: {match_ratio:.2%}")