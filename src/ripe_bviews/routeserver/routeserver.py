
import json
import os
import datetime

import sys
from pathlib import Path
 
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent)) 

from src.utils.graphs import plot_list_as_line_plot
 

ROUTESERVER_PATH = "/home/jfpereira/routeservers_json/"

# routes_received: routes neighbour is trying to announce to the route server
# routes_filtered: not accepted
# routes_accepted: accepted routes 
# routes_exported: routes it has access to because of the RouteServer.


# loads all route server data from a single date (different hours of that date),
# stores the latest information of an AS (if the AS was visible at any time of that day that our snapshots acquired, it will be in the resulting data, even if it 
# de-peered that day, to avoid cases where the AS simply left the IXP for a few hours due to outtages and etc)
def load_all_routeserver_data_from_date(date, ixp, routeserver_name) -> dict[str, list[dict]]:


    path = ROUTESERVER_PATH + date + "/" + ixp + "/neighbors"

    try:

        available_dates = os.listdir(path)

        if len(available_dates) == 0:
            return None
        
        asn_to_data_mapping = {}

        for available_date_file in available_dates:
            with open(path + "/" + available_date_file) as f:
                file_data = json.load(f)
                asns_data = file_data[routeserver_name]["neighbors"]

                for asn_specific_data in asns_data:

                    asn = asn_specific_data["asn"]
                    asn_to_data_mapping[asn] = asn_specific_data # asn, routes_received, routes_filtered, routes_accepted, routes_exported

        return asn_to_data_mapping
    except:
        return None

def get_empty_asn_data(asn):
    return {
        "asn": asn,
        "routes_received": -1, # -1 means didnt exist
        "routes_filtered": -1,
        'routes_accepted': -1,
        "routes_exported": -1
    }

def load_routeserver_data_from_range(ixp, routeserver, start_time, end_time, interval):

    current_time = start_time

    asn_to_routes_over_time_map = {}

    while current_time <= end_time:

        date_str = current_time.strftime("%Y%m%d")
        print(f"Processing data for date: {date_str}")
        route_server_data = load_all_routeserver_data_from_date(date_str, ixp, routeserver)

        if route_server_data is None:
            print(f"  No data found for {date_str}")
            current_time += interval
            #for asn in asn_to_routes_over_time_map.keys():
            #    asn_to_routes_over_time_map[asn].append(get_empty_asn_data(asn))
                
            continue
        
        for asn in route_server_data.keys(): 
            if asn not in asn_to_routes_over_time_map:
                asn_to_routes_over_time_map[asn] = [
                    get_empty_asn_data(asn) for _ in range((end_time - start_time).days + 1)
                ]

            asn_to_routes_over_time_map[asn].append(route_server_data[asn]) 

        asns_missing = set(asn_to_routes_over_time_map.keys()) - set(route_server_data.keys())

        for asn in asns_missing:
            asn_to_routes_over_time_map[asn].append(
                get_empty_asn_data(asn)
            )

        current_time += interval

    return asn_to_routes_over_time_map




def view_top_neighbors(neighbours):
    top_neighbors = sorted(neighbours, key=lambda x: x['routes_accepted'], reverse=True)[:10]

    print("Top 10 neighbors by accepted routes:")
    for neighbor in top_neighbors:
        print(f"Neighbor ASN: {neighbor['description']}, Accepted Routes: {neighbor['routes_accepted']}")



def get_top_changes(neighbours_before, neighbours_after):
    change_map = {}
    for neighbor in neighbours_before:
        neighbor_asn = neighbor["asn"]
        accepted_routes = neighbor['routes_accepted']
        if accepted_routes > 0:
            change_map[neighbor_asn] = {"change": accepted_routes, "before": accepted_routes}
    
    for neighbor in neighbours_after:
        neighbor_asn = neighbor["asn"]
        accepted_routes = neighbor['routes_accepted']
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
            before_routes = neighbor['routes_accepted']
            break
    
    for neighbor in neighbours_after:
        if neighbor["asn"] == neighbor_asn:
            after_routes = neighbor['routes_accepted']
            break
    
    if before_routes == 0:
        return None  # Avoid division by zero

    change_percentage = ((after_routes - before_routes) / before_routes) * 100
    return change_percentage


def depeering_analysis(asn_to_routes_over_time_map):
    asns_that_left_at_some_point = set()
    asns_that_had_routes_but_then_had_zero_routes = set()
    for asn, routes_data in asn_to_routes_over_time_map.items():
        index_of_first_zero = next((i for i, routes in enumerate(routes_data) if routes['routes_accepted'] == 0), None)
        if index_of_first_zero is not None:
            if any(routes['routes_accepted'] > 0 for routes in routes_data[:index_of_first_zero]):
                asns_that_had_routes_but_then_had_zero_routes.add(asn)
        if any(routes['routes_accepted'] == -1 for routes in routes_data):
            asns_that_left_at_some_point.add(asn)
    
    print(f"ASNs that left at some point (total: {len(asns_that_left_at_some_point)}):")
    if len(asns_that_left_at_some_point) <= 5:
        for asn in asns_that_left_at_some_point:
            print(f"ASN: {asn}")
            for i, routes in enumerate(asn_to_routes_over_time_map[asn]):
                print(f"  i: {i}, Accepted Routes: {routes['routes_accepted']}")
    
    #asns_that_had_routes_but_then_had_zero_routes_and_has_increase_of_
    print(f"Sample of 3 ASNs that had routes but then had zero routes (total: {len(asns_that_had_routes_but_then_had_zero_routes)}):")
    for asn in list(asns_that_had_routes_but_then_had_zero_routes)[:3]:
        print(f"ASN: {asn}")
        for i, routes in enumerate(asn_to_routes_over_time_map[asn]):
            print(f"  i: {i}, Accepted Routes: {routes}")
    #get_top_changes(neighbours, neighbours_two)

    asns_that_lost_more_than_ten_percent_between_i_minus_two_and_i_minus_one = []
    asns_that_did_not_lose_more_than_ten_percent_between_i_minus_two_and_i_minus_one = []
    for asn in asns_that_had_routes_but_then_had_zero_routes:

        all_indexes_of_zero = [i for i, routes in enumerate(asn_to_routes_over_time_map[asn]) if routes['routes_accepted'] == 0]

        for index_of_zero in all_indexes_of_zero:
            if index_of_zero >= 2:
                routes_i_minus_two = asn_to_routes_over_time_map[asn][index_of_zero - 2]['routes_accepted']
                routes_i_minus_one = asn_to_routes_over_time_map[asn][index_of_zero - 1]['routes_accepted']
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
        for  routes in asn_to_routes_over_time_map[asn]:
            #print(f"  Date: {date.strftime('%Y-%m-%d')}, Accepted Routes: {routes}")
            print(f"    Routes i-2: {routes_i_minus_two}, Routes i-1: {routes_i_minus_one}") 



def asn_participations(asn_to_routes_map, start_time, end_time):


    most_changed_consistent_asns = []

    total_asns_at_any_point = len(asn_to_routes_map)
    print(f"Total ASNs observed at any point: {total_asns_at_any_point}")
    consistent_asns = set()
    
    for asn, routes_data in asn_to_routes_map.items():
        if all(routes['routes_accepted'] > 0 for  routes in routes_data):
            consistent_asns.add(asn)
    
    print(f"ASNs that consistently had routes accepted: {len(consistent_asns)} ({len(consistent_asns)/len(asn_to_routes_map)*100:.2f}%)")

    completely_silent_asns = set()
    for asn, routes_data in asn_to_routes_map.items():
        if all(routes['routes_accepted'] == 0 for routes in routes_data):
            completely_silent_asns.add(asn)

    print(f"ASNs with zero routes accepted always: {len(completely_silent_asns)} ({len(completely_silent_asns)/len(asn_to_routes_map)*100:.2f}%)")

    no_routes_exported = 0
    for asn in completely_silent_asns:
        routes_exported = sum([routes['routes_exported'] for routes in asn_to_routes_map[asn]])
        if routes_exported == 0:
            no_routes_exported += 1
    #followup question, how many have more than 50% visibility 

    print(f"For those ASNs, how many don't have 'routes exported': {no_routes_exported}") 

    asns_that_had_zero_routes_only_once = set()
    for asn, routes_data in asn_to_routes_map.items():
        if sum(1 for routes in routes_data if routes['routes_accepted'] == 0) == 1 and all(routes['routes_accepted'] >= 0 for routes in routes_data):
            asns_that_had_zero_routes_only_once.add(asn)
    print(f"ASNs that had zero routes only once: {len(asns_that_had_zero_routes_only_once)} ({len(asns_that_had_zero_routes_only_once)/len(asn_to_routes_map)*100:.2f}%)")

    asns_that_had_zero_routes_more_than_once = set()
    for asn, routes_data in asn_to_routes_map.items():
        if sum(1 for routes in routes_data if routes['routes_accepted'] == 0) > 1 and all(routes['routes_accepted'] >= 0 for routes in routes_data):
            asns_that_had_zero_routes_more_than_once.add(asn)
    print(f"ASNs that had zero routes more than once: {len(asns_that_had_zero_routes_more_than_once)} ({len(asns_that_had_zero_routes_more_than_once)/len(asn_to_routes_map)*100:.2f}%)")

    total_routes_over_time = []
    dates_list = []
    for date_index in range((end_time - start_time).days + 1):
        current_date = start_time + datetime.timedelta(days=date_index)
        
        total_routes_for_date = 0
        asns_with_data_for_date = 0
        
        for asn in asn_to_routes_map: 
            routes = asn_to_routes_map[asn][date_index]['routes_accepted']
            if routes >= 0:  # Only count valid routes (exclude -1 for missing data)
                total_routes_for_date += routes
                asns_with_data_for_date += 1

        if total_routes_for_date == 0:
            continue
        total_routes_over_time.append(total_routes_for_date)
        dates_list.append(current_date)

    plot_list_as_line_plot(total_routes_over_time, 
                           y=[date.strftime('%Y-%m-%d') for date in dates_list],
                           title="Total Accepted Routes Over Time", 
                        )


        
    

    # always negative, or always positive
    consistent_asns_with_most_straightforward_change = []

    for asn in consistent_asns:
        routes_data = asn_to_routes_map[asn]
        changes = [routes_data[i]['routes_accepted'] - routes_data[i-1]['routes_accepted'] for i in range(1, len(routes_data))]
        if all(change >= 0 for change in changes) or all(change <= 0 for change in changes):
            total_change_percentage = ((routes_data[-1]['routes_accepted'] - routes_data[0]['routes_accepted']) / routes_data[0]['routes_accepted']) * 100
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
        valid_routes_data = [routes['routes_accepted'] for routes in routes_data if routes['routes_accepted'] >= 0]
        
        if len(valid_routes_data) < 2:
            continue  # Skip if not enough valid data points
        
        changes = [valid_routes_data[i] - valid_routes_data[i-1] for i in range(1, len(valid_routes_data))]
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
            valid_routes_data_full = [routes['routes_accepted'] for routes in routes_data if routes >= 0]
            if len(valid_routes_data_full) >= 2:
                total_change_percentage = ((valid_routes_data_full[-1] - valid_routes_data_full[0]) / valid_routes_data_full[0]) * 100
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

if __name__ == "__main__":


    start_time = datetime.datetime.strptime("2025-08-16 00:00", "%Y-%m-%d %H:%M")
    end_time = datetime.datetime.strptime("2025-10-16 00:00", "%Y-%m-%d %H:%M")

    asn_to_routes_map = load_routeserver_data_from_range("ix-br", "SP-rs2-v4", start_time, end_time, datetime.timedelta(days=1))
    
    asn_participations(asn_to_routes_map, start_time, end_time)
    depeering_analysis(asn_to_routes_map)

    
    
    #create_window_with_all_rendered_graphs_this_session()
    

    

focused_asn = 267458

#for date, routes in asn_to_routes_map[focused_asn]:
#    print(f"Date: {date.strftime('%Y-%m-%d')}, Accepted Routes: {routes}")