
import json
import os
import datetime

import sys
from pathlib import Path
 
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent)) 

from src.utils.graphs import create_window_with_all_rendered_graphs_this_session, plot_list_as_line_plot


# routes_received: routes neighbour is trying to announce to the route server
# routes_filtered: not accepted
# routes_accepted: accepted routes 
# routes_exported: routes it has access to because of the RouteServer.


def get_routeserver(routeserver_name, date):


    folder_path = "/home/emily/Desktop/projects/furg/tcc_depeering_elixir/data/routeservers/{routeserver_name}/{date}/neighbors/".format(routeserver_name=routeserver_name, date=date)

    if not os.path.exists(folder_path):
       return None
    
    first_file = None
    for file_name in os.listdir(folder_path):
        if file_name.endswith(".json"):
            first_file = file_name
            break
    
    with open(os.path.join(folder_path, first_file), "r") as f:
        data = json.load(f)
    
    return data



def view_top_neighbors(neighbours):
    top_neighbors = sorted(neighbours, key=lambda x: x["routes_accepted"], reverse=True)[:10]

    print("Top 10 neighbors by accepted routes:")
    for neighbor in top_neighbors:
        print(f"Neighbor ASN: {neighbor['description']}, Accepted Routes: {neighbor['routes_accepted']}")



def get_top_changes(neighbours_before, neighbours_after):
    change_map = {}
    for neighbor in neighbours_before:
        neighbor_asn = neighbor["asn"]
        accepted_routes = neighbor["routes_accepted"]
        if accepted_routes > 0:
            change_map[neighbor_asn] = {"change": accepted_routes, "before": accepted_routes}
    
    for neighbor in neighbours_after:
        neighbor_asn = neighbor["asn"]
        accepted_routes = neighbor["routes_accepted"]
        if accepted_routes == 0:
            continue
        if neighbor_asn in change_map:
            change_map[neighbor_asn]["change"] = accepted_routes - change_map[neighbor_asn]["before"]    
            change_map[neighbor_asn]["after"] = accepted_routes

    change_map = {asn: info for asn, info in change_map.items() if "after" in info}

    top_changes = sorted(change_map.items(), key=lambda x: -(x[1]["change"]), reverse=True)[:10]
    
    top_changes_by_percentage = sorted(change_map.items(), key=lambda x: -(x[1]["change"] / x[1]["before"]), reverse=True)[:10]
    
    '''
    print("Top 10 neighbors by losses in accepted routes:")
    for neighbor_asn, change_info in top_changes_by_percentage:
        
        print(f"Neighbor ASN: {neighbor_asn}, Change in Accepted Routes: ({(change_info['change'] / change_info['before']) * 100:.2f}%)")
        print("From:", change_info["before"], "to:", change_info["after"])
    '''
    return top_changes_by_percentage


def get_change_percentage_of_asn(neighbor_asn, neighbours_before, neighbours_after):
    before_routes = 0
    after_routes = 0
    for neighbor in neighbours_before:
        if neighbor["asn"] == neighbor_asn:
            before_routes = neighbor["routes_accepted"]
            break
    
    for neighbor in neighbours_after:
        if neighbor["asn"] == neighbor_asn:
            after_routes = neighbor["routes_accepted"]
            break
    
    if before_routes == 0:
        return None  # Avoid division by zero

    change_percentage = ((after_routes - before_routes) / before_routes) * 100
    return change_percentage

if __name__ == "__main__":


    start_time = datetime.datetime.strptime("2025-08-16 00:00", "%Y-%m-%d %H:%M")
    end_time = datetime.datetime.strptime("2025-10-16 00:00", "%Y-%m-%d %H:%M")

    current_time = start_time

    asn_to_routes_map = {}

    while current_time <= end_time:
        date_str = current_time.strftime("%Y%m%d")
        print(f"Processing data for date: {date_str}")
        route_server_data = get_routeserver("ix-br", date_str)
        if route_server_data is None:
            print(f"  No data found for {date_str}")
            current_time += datetime.timedelta(days=1)
            continue
        neighbours = route_server_data["SP-rs2-v4"]["neighbors"]
 
        asns_missing = [k for k in (asn_to_routes_map).keys()]
        asns_processed_today = set()
        for neighbor in neighbours:
            asn = neighbor["asn"]
            if asn in asns_processed_today:
                continue  # Skip duplicates for the same day
            asns_processed_today.add(asn)
            asns_missing.remove(asn) if asn in asns_missing else None
            routes_accepted = neighbor["routes_accepted"]
            if asn not in asn_to_routes_map:
                asn_to_routes_map[asn] = []
                for i in range((current_time - start_time).days):
                    asn_to_routes_map[asn].append((start_time + datetime.timedelta(days=i), -1))
            asn_to_routes_map[asn].append((current_time, routes_accepted))
        
        for asn in asns_missing:
            asn_to_routes_map[asn].append((current_time, -1))
        current_time += datetime.timedelta(days=1)
    
    asns_that_left_at_some_point = set()
    asns_that_had_routes_but_then_had_zero_routes = set()
    for asn, routes_data in asn_to_routes_map.items():
        index_of_first_zero = next((i for i, (_, routes) in enumerate(routes_data) if routes == 0), None)
        if index_of_first_zero is not None:
            if any(routes > 0 for _, routes in routes_data[:index_of_first_zero]):
                asns_that_had_routes_but_then_had_zero_routes.add(asn)
        if any(routes == -1 for _, routes in routes_data):
            asns_that_left_at_some_point.add(asn)
    
    print(f"ASNs that left at some point (total: {len(asns_that_left_at_some_point)}):")
    if len(asns_that_left_at_some_point) <= 5:
        for asn in asns_that_left_at_some_point:
            print(f"ASN: {asn}")
            for date, routes in asn_to_routes_map[asn]:
                print(f"  Date: {date.strftime('%Y-%m-%d')}, Accepted Routes: {routes}")
    
    #asns_that_had_routes_but_then_had_zero_routes_and_has_increase_of_
    print(f"Sample of 3 ASNs that had routes but then had zero routes (total: {len(asns_that_had_routes_but_then_had_zero_routes)}):")
    for asn in list(asns_that_had_routes_but_then_had_zero_routes)[:3]:
        print(f"ASN: {asn}")
        for date, routes in asn_to_routes_map[asn]:
            print(f"  Date: {date.strftime('%Y-%m-%d')}, Accepted Routes: {routes}")
    #get_top_changes(neighbours, neighbours_two)

    asns_that_lost_more_than_ten_percent_between_i_minus_two_and_i_minus_one = []
    asns_that_did_not_lose_more_than_ten_percent_between_i_minus_two_and_i_minus_one = []
    for asn in asns_that_had_routes_but_then_had_zero_routes:

        all_indexes_of_zero = [i for i, (_, routes) in enumerate(asn_to_routes_map[asn]) if routes == 0]

        for index_of_zero in all_indexes_of_zero:
            if index_of_zero >= 2:
                routes_i_minus_two = asn_to_routes_map[asn][index_of_zero - 2][1]
                routes_i_minus_one = asn_to_routes_map[asn][index_of_zero - 1][1]
                values_are_higher_than_zero = routes_i_minus_two > 0 and routes_i_minus_one > 0

                there_was_a_decrement = routes_i_minus_one < routes_i_minus_two
                if values_are_higher_than_zero and there_was_a_decrement:
                    percentage_loss = ((routes_i_minus_two - routes_i_minus_one) / routes_i_minus_two) * 100
                    if percentage_loss > 10:
                        asns_that_lost_more_than_ten_percent_between_i_minus_two_and_i_minus_one.append((asn, percentage_loss,
                                                                                                        
                                                                                                        routes_i_minus_two, routes_i_minus_one
                                                                                                        ))
                    else:
                        asns_that_did_not_lose_more_than_ten_percent_between_i_minus_two_and_i_minus_one.append((asn, percentage_loss,
                                                                                                                routes_i_minus_two, routes_i_minus_one
                                                                                                        ))
    
    print(f"Top 3 ASNs that lost more than 10% between i-2 and i-1 (total: {len(asns_that_lost_more_than_ten_percent_between_i_minus_two_and_i_minus_one)}):")
    for asn, percentage_loss, routes_i_minus_two, routes_i_minus_one in asns_that_lost_more_than_ten_percent_between_i_minus_two_and_i_minus_one[:3]:
        print(f"ASN: {asn}, Percentage Loss: {percentage_loss:.2f}%")
        for date, routes in asn_to_routes_map[asn]:
            print(f"  Date: {date.strftime('%Y-%m-%d')}, Accepted Routes: {routes}")
            print(f"    Routes i-2: {routes_i_minus_two}, Routes i-1: {routes_i_minus_one}")
    

    total_asns_at_any_point = len(asn_to_routes_map)
    print(f"Total ASNs observed at any point: {total_asns_at_any_point}")
    consistent_asns = set()
    
    for asn, routes_data in asn_to_routes_map.items():
        if all(routes > 0 for _, routes in routes_data):
            consistent_asns.add(asn)
    
    print(f"ASNs that consistently had routes accepted: {len(consistent_asns)} ({len(consistent_asns)/len(asn_to_routes_map)*100:.2f}%)")

    completely_silent_asns = set()
    for asn, routes_data in asn_to_routes_map.items():
        if all(routes == 0 for _, routes in routes_data):
            completely_silent_asns.add(asn)
    print(f"ASNs with zero routes accepted always: {len(completely_silent_asns)} ({len(completely_silent_asns)/len(asn_to_routes_map)*100:.2f}%)")

    asns_that_had_zero_routes_only_once = set()
    for asn, routes_data in asn_to_routes_map.items():
        if sum(1 for _, routes in routes_data if routes == 0) == 1 and all(routes >= 0 for _, routes in routes_data):
            asns_that_had_zero_routes_only_once.add(asn)
    print(f"ASNs that had zero routes only once: {len(asns_that_had_zero_routes_only_once)} ({len(asns_that_had_zero_routes_only_once)/len(asn_to_routes_map)*100:.2f}%)")

    asns_that_had_zero_routes_more_than_once = set()
    for asn, routes_data in asn_to_routes_map.items():
        if sum(1 for _, routes in routes_data if routes == 0) > 1 and all(routes >= 0 for _, routes in routes_data):
            asns_that_had_zero_routes_more_than_once.add(asn)
    print(f"ASNs that had zero routes more than once: {len(asns_that_had_zero_routes_more_than_once)} ({len(asns_that_had_zero_routes_more_than_once)/len(asn_to_routes_map)*100:.2f}%)")

    total_routes_over_time = []
    dates_list = []
    for date_index in range((end_time - start_time).days + 1):
        current_date = start_time + datetime.timedelta(days=date_index)
        dates_list.append(current_date)
        
        total_routes_for_date = 0
        asns_with_data_for_date = 0
        
        for asn in asn_to_routes_map:
            # Check if this ASN has data at this index
            if date_index < len(asn_to_routes_map[asn]):
                routes = asn_to_routes_map[asn][date_index][1]
                if routes >= 0:  # Only count valid routes (exclude -1 for missing data)
                    total_routes_for_date += routes
                    asns_with_data_for_date += 1
        
        total_routes_over_time.append(total_routes_for_date)

    plot_list_as_line_plot(total_routes_over_time, 
                           y=[date.strftime('%Y-%m-%d') for date in dates_list],
                           title="Total Accepted Routes Over Time", 
                        )
    
    
    create_window_with_all_rendered_graphs_this_session()
    
    most_changed_consistent_asns = []

    for asn in consistent_asns:
        routes_data = asn_to_routes_map[asn]
        if routes_data[0][1] <= 0 or routes_data[-1][1] <= 0:
            continue  # Skip if first or last entry is invalid
        change_percentage = ((routes_data[-1][1] - routes_data[0][1]) / routes_data[0][1]) * 100
        most_changed_consistent_asns.append((asn, change_percentage))
    
    for asn, change_percentage in sorted(most_changed_consistent_asns, key=lambda x: -abs(x[1]))[:3]:
        print(f"ASN: {asn}, Change Percentage: {change_percentage:.2f}%")

        for date, routes in asn_to_routes_map[asn]:
            print(f"  Date: {date.strftime('%Y-%m-%d')}, Accepted Routes: {routes}")
        
    

    # always negative, or always positive
    consistent_asns_with_most_straightforward_change = []

    for asn in consistent_asns:
        routes_data = asn_to_routes_map[asn]
        changes = [routes_data[i][1] - routes_data[i-1][1] for i in range(1, len(routes_data))]
        if all(change >= 0 for change in changes) or all(change <= 0 for change in changes):
            total_change_percentage = ((routes_data[-1][1] - routes_data[0][1]) / routes_data[0][1]) * 100
            consistent_asns_with_most_straightforward_change.append((asn, total_change_percentage))
    
    print("Consistent ASNs with the most straightforward change (always increasing or always decreasing):")
    for asn, change_percentage in sorted(consistent_asns_with_most_straightforward_change, key=lambda x: -abs(x[1]))[:3]:
        print(f"ASN: {asn}, Total Change Percentage: {change_percentage:.2f}%")

        #for date, routes in asn_to_routes_map[asn]:
        #    print(f"  Date: {date.strftime('%Y-%m-%d')}, Accepted Routes: {routes}")

    
    # 3 or more consecutive changes in the same direction
    consistent_asns_with_long_period_of_straightforward_change = []
    streak_indices_map = {}  # Store streak indices for each ASN

    for asn in consistent_asns:
        routes_data = asn_to_routes_map[asn]
        # Filter out entries with -1 (missing data) for calculating changes
        valid_routes_data = [(date, routes) for date, routes in routes_data if routes >= 0]
        
        if len(valid_routes_data) < 2:
            continue  # Skip if not enough valid data points
        
        changes = [valid_routes_data[i][1] - valid_routes_data[i-1][1] for i in range(1, len(valid_routes_data))]
        max_consecutive_changes = 0
        current_consecutive_changes = 1
        current_streak_start = 0

        start_index_of_best_streak = 0
        end_index_of_best_streak = 0
        for i in range(1, len(changes)):
            if (changes[i] >= 0 and changes[i-1] >= 0) or (changes[i] <= 0 and changes[i-1] <= 0):
                current_consecutive_changes += 1
            else:
                if current_consecutive_changes > max_consecutive_changes:
                    max_consecutive_changes = current_consecutive_changes
                    start_index_of_best_streak = current_streak_start
                    end_index_of_best_streak = i - 1
                current_streak_start = i
                current_consecutive_changes = 1
        
        if current_consecutive_changes > max_consecutive_changes:
            max_consecutive_changes = current_consecutive_changes
            start_index_of_best_streak = current_streak_start
            end_index_of_best_streak = len(changes) - 1

        if max_consecutive_changes >= 3:
            routes_data = asn_to_routes_map[asn]
            valid_routes_data_full = [(date, routes) for date, routes in routes_data if routes >= 0]
            if len(valid_routes_data_full) >= 2:
                total_change_percentage = ((valid_routes_data_full[-1][1] - valid_routes_data_full[0][1]) / valid_routes_data_full[0][1]) * 100
                streak_indices_map[asn] = (max_consecutive_changes, start_index_of_best_streak, end_index_of_best_streak)
                consistent_asns_with_long_period_of_straightforward_change.append((asn, total_change_percentage))
    
    print(f"Consistent ASNs with a long period of straightforward change (3 or more) ({len(consistent_asns_with_long_period_of_straightforward_change)}):")
    for asn, change_percentage in sorted(consistent_asns_with_long_period_of_straightforward_change, key=lambda x: -abs(x[1]))[:5]:
        print(f"ASN: {asn}, Total Change Percentage: {change_percentage:.2f}%")
        
        routes_data = asn_to_routes_map[asn]
        max_consecutive_changes, start_index_of_best_streak, end_index_of_best_streak = streak_indices_map[asn]
 
        i = 0

        if False:
            for date, routes in asn_to_routes_map[asn]:
                if i == start_index_of_best_streak:
                    print("---")
                print(f"  Date: {date.strftime('%Y-%m-%d')}, Accepted Routes: {routes}")
                if i == end_index_of_best_streak:
                    print("---")
                i += 1

focused_asn = 267458

#for date, routes in asn_to_routes_map[focused_asn]:
#    print(f"Date: {date.strftime('%Y-%m-%d')}, Accepted Routes: {routes}")