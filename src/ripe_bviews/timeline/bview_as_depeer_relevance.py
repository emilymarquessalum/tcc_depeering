

# Mostly implemented to think about depeering events,
# "depeering news", and what could be specifically described about a time period.

import sys
from pathlib import Path

from src.ripe_bviews.read_bgpdump import BGPDumpSnapshotStats
 
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent)) 
 

import datetime 
from src.ripe_bviews.timeline.bview_vars import get_annotations, get_ip_version, get_subfolder, get_title_end, get_title_start 
from src.ripe_bviews.bview_labels import summarized_date_labels
from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data_timeline_from_configs
from src.ripe_bviews.download_and_parse.load_configs import load_configs, print_config 
from src.ripe_bviews.oscillations.bview_oscillation_logic import OscillationMetrics, calculate_oscillation_metrics 
import warnings 
from src.utils.graphs import create_window_with_all_rendered_graphs_this_session, plot_list_as_bar_plot, plot_list_as_line_plot, plot_map_as_bar_plot, plot_stacked_line_plot



def check_reachable_lost_routes_categories(all_stats, labels_summarized, config, title_start, title_end, subfolder, max_labels, should_remove_prepend=True):
    """Categorize reachables into groups based on AS path length changes when they lost routes."""
    reachable_lost_routes_but_still_in_ixp_with_same_as_path_length = []
    reachable_lost_routes_but_still_in_ixp_with_worse_as_path_length = []
    reachable_lost_routes_but_still_in_ixp_with_better_as_path_length = []
    reachable_lost_all_routes = []
    reachable_lost_but_members_still_connected = []
    
    # for index i, the number of reachables that lost routes but still in IXP with same/worse/better AS path length is calculated by comparing the reachables and their providing members in stat i with the previous stat (i-1)
    all_counts_reachable_lost_routes_but_still_in_ixp_with_same_as_path_length: list[int] = []
    all_counts_reachable_lost_routes_but_still_in_ixp_with_worse_as_path_length: list[int] = []
    all_counts_reachable_lost_routes_but_still_in_ixp_with_better_as_path_length: list[int] = []
    
    # for index i, a map that tells us for map[i][n] the number of reachables that have a path length change of n (compared to previous stat) among the reachables that lost routes but still in IXP at index i 
    all_reachable_lost_routes_but_still_in_ixp_linked_to_path_length_change: list[
        dict
    ] = []

    all_counts_reachable_lost_all_members: list[int] = []
    all_counts_reachable_lost_but_members_still_connected: list[int] = []
    
    # Routes lost because members left the IXP
    all_counts_routes_lost_by_member_departure: list[int] = []
    # Routes lost but the member is still in the IXP
    all_counts_routes_lost_member_still_present: list[int] = []
    
    for i, stat in enumerate(all_stats[1:], 1):
        previous_stat: BGPDumpSnapshotStats = all_stats[i - 1]
        
        prev_map = previous_stat.get_all_reachables_to_members_map() 
        curr_map = stat.get_all_reachables_to_members_map()

        lost_routes_same_as_path_count = 0
        lost_routes_worse_as_path_count = 0
        lost_routes_better_as_path_count = 0
        lost_all_count = 0
        lost_but_members_still_connected_count = 0
        routes_lost_by_member_departure_count = 0
        routes_lost_member_still_present_count = 0
        path_length_changes: dict[int, int] = {}
        
        all_previously_reachable = previous_stat.unique_reachables
        
        for reachable in all_previously_reachable:
            prev_members = prev_map.get(reachable, set())
            if not prev_members:
                continue
                
            curr_members = curr_map.get(reachable, set())
            prev_count = len(prev_members)
            curr_count = len(curr_members)
            
            if curr_count < prev_count:
                if curr_count > 0:
                    # Get AS path lengths for previous and current members
                    prev_as_paths = []
                    curr_as_paths = []
                    
                    for member in prev_members:
                        member_reachables = previous_stat.mappings.get(str(member), [])
                        for reach_info in member_reachables:
                            if reach_info.get("reachable") == reachable:
                                as_path = reach_info.get("as_path", [])
                                # remove prepend
                                if should_remove_prepend and len(as_path) > 1:
                                    as_path = [asn for idx, asn in enumerate(as_path) if idx == 0 or asn != as_path[idx - 1]]
                                as_path_length = len(as_path) if as_path else 0
                                prev_as_paths.append(as_path_length)
                    
                    for member in curr_members:
                        member_reachables = stat.mappings.get(str(member), [])
                        for reach_info in member_reachables:
                            if reach_info.get("reachable") == reachable:
                                as_path = reach_info.get("as_path", [])
                                if should_remove_prepend and len(as_path) > 1:
                                    as_path = [asn for idx, asn in enumerate(as_path) if idx == 0 or asn != as_path[idx - 1]]
                                as_path_length = len(as_path) if as_path else 0
                                curr_as_paths.append(as_path_length)
                    
                    # Compare minimum AS path lengths
                    min_prev_as_path = min(prev_as_paths) if prev_as_paths else 0
                    min_curr_as_path = min(curr_as_paths) if curr_as_paths else 0
                    
                    # Calculate the change in AS path length
                    as_path_length_change =  min_prev_as_path - min_curr_as_path
                    path_length_changes[as_path_length_change] = path_length_changes.get(as_path_length_change, 0) + 1
                    # no change
                    if min_curr_as_path == min_prev_as_path:
                        lost_routes_same_as_path_count += 1
                        reachable_lost_routes_but_still_in_ixp_with_same_as_path_length.append(reachable)
                    # current as path is worse (longer) than previous
                    elif min_curr_as_path > min_prev_as_path:
                        lost_routes_worse_as_path_count += 1
                        reachable_lost_routes_but_still_in_ixp_with_worse_as_path_length.append(reachable)
                    # current as path is better (shorter) than previous
                    else:
                        lost_routes_better_as_path_count += 1
                        reachable_lost_routes_but_still_in_ixp_with_better_as_path_length.append(reachable)
                    # Routes were lost but reachable still has members (curr_count > 0)
                    routes_lost_member_still_present_count += 1
                else:  
                    # Reachable completely lost (curr_count == 0)
                    # Check if at least one member that provided access is still a member
                    at_least_one_member_still_connected = any(int(member) in stat.unique_members for member in prev_members)
                    if at_least_one_member_still_connected:
                        lost_but_members_still_connected_count += 1
                        routes_lost_member_still_present_count += 1
                        reachable_lost_but_members_still_connected.append(reachable)
                    else:
                        # All members were lost, so this reachable lost all routes from members
                        lost_all_count += 1
                        routes_lost_by_member_departure_count += 1
                        reachable_lost_all_routes.append(reachable)

        all_reachable_lost_routes_but_still_in_ixp_linked_to_path_length_change.append(path_length_changes)

        all_counts_reachable_lost_routes_but_still_in_ixp_with_same_as_path_length.append(lost_routes_same_as_path_count)
        all_counts_reachable_lost_routes_but_still_in_ixp_with_worse_as_path_length.append(lost_routes_worse_as_path_count)
        all_counts_reachable_lost_routes_but_still_in_ixp_with_better_as_path_length.append(lost_routes_better_as_path_count)
        all_counts_reachable_lost_all_members.append(lost_all_count)
        all_counts_reachable_lost_but_members_still_connected.append(lost_but_members_still_connected_count)
        all_counts_routes_lost_by_member_departure.append(routes_lost_by_member_departure_count)
        all_counts_routes_lost_member_still_present.append(routes_lost_member_still_present_count)
    
    start_date = datetime.strptime(config["start_date"], "%Y-%m-%d")
    end_date = datetime.strptime(config["end_date"], "%Y-%m-%d")

    total_route_loss_map = {}
    for map in all_reachable_lost_routes_but_still_in_ixp_linked_to_path_length_change:
        for change, count in map.items():
            total_route_loss_map[change] = total_route_loss_map.get(change, 0) + count
    
    if 0 in total_route_loss_map:
        del total_route_loss_map[0]


    title_start = title_start + " (Prepend filtered)" if should_remove_prepend else " (With prepend)"

    plot_map_as_bar_plot(total_route_loss_map, title=f"Total Route Loss by AS Path Length Change - {get_ip_version(config)} - {get_date_range_title(start_date, end_date)}", xlabel="AS Path Length Change", ylabel="Count of Reachable ASes", subfolder=subfolder )
     
     
    plot_list_as_bar_plot(
        ["Still in IXP (Same AS Path Length)", 
                         "Still in IXP (Worse AS Path Length)",
                         "Still in IXP (Better AS Path Length)",
                         "Lost (Members Still Connected)",
                         "Lost All Routes from Members"],
                       y= 
        [sum(all_counts_reachable_lost_routes_but_still_in_ixp_with_same_as_path_length), 
                           sum(all_counts_reachable_lost_routes_but_still_in_ixp_with_worse_as_path_length),
                           sum(all_counts_reachable_lost_routes_but_still_in_ixp_with_better_as_path_length),
                           sum(all_counts_reachable_lost_but_members_still_connected),
                           sum(all_counts_reachable_lost_all_members)], 
                        title=title_start + f"Count of Reachable ASes that Lost Routes - {get_ip_version(config)} - {get_date_range_title(start_date, end_date)}", 
                        xlabel="Date",  
                        ylabel="Count of Reachable ASes", subfolder=subfolder, max_labels=max_labels)
    plot_list_as_bar_plot(
        [
            "Still in IXP (Same AS Path Length)", 
                         "Still in IXP (Worse AS Path Length)",
                         "Still in IXP (Better AS Path Length)",
        ],
        [sum(all_counts_reachable_lost_routes_but_still_in_ixp_with_same_as_path_length),
         sum(all_counts_reachable_lost_routes_but_still_in_ixp_with_worse_as_path_length),
         sum(all_counts_reachable_lost_routes_but_still_in_ixp_with_better_as_path_length)],
         title=title_start+f"Count of Reachable ASes that Lost Routes but Still in IXP with Different AS Path Lengths - {get_ip_version(config)} - {get_date_range_title(start_date, end_date)}",
            xlabel="Date",
            ylabel="Count of Reachable ASes", subfolder=subfolder, max_labels=max_labels,
            use_colors=True,
            use_rotated_labels=False
    )
    plot_list_as_bar_plot(
         [
            "Still in IXP (Same AS Path Length)", 
                         "Still in IXP (Worse AS Path Length)",
                         "Still in IXP (Better AS Path Length)",
        ],
         [
            sum(set(all_counts_reachable_lost_routes_but_still_in_ixp_with_same_as_path_length)),
         sum(set(all_counts_reachable_lost_routes_but_still_in_ixp_with_worse_as_path_length)),
         sum(set(all_counts_reachable_lost_routes_but_still_in_ixp_with_better_as_path_length))
         ],
         title=title_start+f"Count of Unique Reachable ASes that Lost Routes but Still in IXP with Different AS Path Lengths - {get_ip_version(config)} - {get_date_range_title(start_date, end_date)}",
            xlabel="Date",
            ylabel="Count of Reachable ASes", subfolder=subfolder, max_labels=max_labels,
            use_colors=True,
            use_rotated_labels=False
    )
    plot_stacked_line_plot([all_counts_reachable_lost_routes_but_still_in_ixp_with_same_as_path_length, 
                           all_counts_reachable_lost_routes_but_still_in_ixp_with_worse_as_path_length,
                           all_counts_reachable_lost_routes_but_still_in_ixp_with_better_as_path_length,
                           all_counts_reachable_lost_but_members_still_connected,
                           all_counts_reachable_lost_all_members],
                        ["Still in IXP (Has another with Same AS Path Length)", 
                         "Still in IXP (Has another with Worse AS Path Length)",
                         "Still in IXP (Has another with Better AS Path Length)",
                         "Lost (Members Still Connected)",
                         "Lost All Routes from Members"],
                        x_labels=labels_summarized[1:], 
                        title=title_start + f"Reachable ASes that Lost Routes over Time - {get_ip_version(config)} - {get_date_range_title(start_date, end_date)}", 
                        xlabel="Date", 
                        ylabel="Count of Reachable ASes", subfolder=subfolder,  max_labels=max_labels)
    plot_stacked_line_plot(
        [all_counts_reachable_lost_routes_but_still_in_ixp_with_same_as_path_length, 
         all_counts_reachable_lost_routes_but_still_in_ixp_with_worse_as_path_length,
         all_counts_reachable_lost_routes_but_still_in_ixp_with_better_as_path_length],
        ["Still in IXP (Has another with Same AS Path Length)", 
         "Still in IXP (Has another with Worse AS Path Length)",
         "Still in IXP (Has another with Better AS Path Length)"],
        x_labels=labels_summarized[1:],
        title=title_start + f"Reachable ASes that Lost Routes but Still in IXP with Different AS Path Lengths - {get_ip_version(config)} - {get_date_range_title(start_date, end_date)}", 
        xlabel="Date", 
        ylabel="Count of Reachable ASes", subfolder=subfolder,  max_labels=max_labels
    )
    plot_stacked_line_plot(
        [all_counts_reachable_lost_but_members_still_connected, all_counts_reachable_lost_all_members],
        ["Lost Reachable (Members Still Connected)", "Lost all Members"],
        x_labels=labels_summarized[1:],
        title=title_start + f"Reachable ASes that Lost Routes - Lost but Members Still Connected vs Lost All Routes - {get_ip_version(config)} - {get_date_range_title(start_date, end_date)}", 
        xlabel="Date", 
        ylabel="Count of Reachable ASes", subfolder=subfolder,  max_labels=max_labels
    )

    plot_stacked_line_plot(
        [
            all_counts_routes_lost_by_member_departure,
            all_counts_routes_lost_member_still_present
        ],
        [
            "Routes lost by member departure",
            "Routes lost but member still present"
        ],
        x_labels=labels_summarized[1:],
        title=title_start + f"Routes Lost by Member Departure vs Routes Lost but Member Still Present - {get_ip_version(config)} - {get_date_range_title(start_date, end_date)}",
        xlabel="Date",
        ylabel="Count of Routes Lost", subfolder=subfolder, max_labels=max_labels
    )

    print(f"\n--- Reachables that Lost Routes ---")
    print(f"Reachable ASes that lost routes but still have other members (same AS path length): {len(reachable_lost_routes_but_still_in_ixp_with_same_as_path_length)}")
    print(f"Reachable ASes that lost routes but still have other members (worse AS path length): {len(reachable_lost_routes_but_still_in_ixp_with_worse_as_path_length)}")
    print(f"Reachable ASes that lost routes but still have other members (better AS path length): {len(reachable_lost_routes_but_still_in_ixp_with_better_as_path_length)}")
    print(f"Reachable ASes that were lost but members they were connected to are still members: {len(reachable_lost_but_members_still_connected)}")
    print(f"Reachable ASes that lost all routes from members: {len(reachable_lost_all_routes)}")



def bview_depeering_routes_impact(all_required_data):

    all_stats, labels_summarized, max_labels = all_required_data["timeline"]
    
    config = all_required_data["config"]
    title_start = get_title_start(config)
    title_end = get_title_end(config)
    subfolder = get_subfolder(config, get_ip_version(config)) + "/depeering_routes_impact/"
    
    # categories: 
    # 1) lost routes but still in IXP with same AS path length, 
    # 2) lost routes but still in IXP with worse AS path length, 
    # 3) lost routes but still in IXP with better AS path length, 
    # 4) lost but members still connected, 
    # 5) lost all routes from members
    check_reachable_lost_routes_categories(all_stats, labels_summarized, config, title_start,title_end, subfolder, max_labels)


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


def print_depeered_relevance_based_on_routes():
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


def print_depeering_event_details():
    start, end = get_peak_change_dates(all_stats, labels, look_at_added=False,
                                       change_in=change_in)
    print(f"Peak loss between {start} and {end}")
    print(f"Lost Members between {start} and {end}:")
    print(len(set(all_stats[labels.index(start)].unique_members) - set(all_stats[labels.index(end)].unique_members)))
    print(f"Lost Reachables between {start} and {end}:")
    print(len(set(all_stats[labels.index(start)].unique_reachables) - set(all_stats[labels.index(end)].unique_reachables)))
    
    


def plot_added_removed_asnes_over_time(metrics: OscillationMetrics, labels_summarized, max_labels, title_start, title_end, subfolder):
    plot_list_as_line_plot(metrics.removed_asns_over_time, labels_summarized[1:], 
                        max_labels=max_labels,
                        title=title_start + "De-Peered ASes Over Time" + title_end, xlabel="Date", ylabel="Number of Removed ASes", subfolder=subfolder)
    plot_list_as_line_plot(metrics.added_asns_over_time, labels_summarized[1:],  
                        max_labels=max_labels,
                        title=title_start + "Newly-Peered ASes Over Time" + title_end, xlabel="Date", ylabel="Number of New ASes", subfolder=subfolder)

def bview_depeering(all_required_data):

    oscillation_metrics = all_required_data["oscillations"]
    plot_added_removed_asnes_over_time(oscillation_metrics, labels_summarized, max_labels=max_labels, title_start=title_start, title_end=title_end, subfolder=subfolder)
    
    