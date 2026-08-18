
import json
import os
import datetime

import sys
from pathlib import Path
from typing import Dict, Generator, List

from attr import dataclass
 
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent)) 

from src.ripe_bviews.routeserver.routeserver_parse import load_routeserver_data_from_range
from src.utils.graphs import plot_list_as_line_plot, plot_stacked_line_plot
 





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


@dataclass
class DepeeringEvent:
    asn: int
    start_index: int
    duration: int
    returned: bool


def extract_depeering_events(asn_to_routes_map: Dict[int, List[dict]]) -> Generator[DepeeringEvent, None, None]:
    """
    Scans each ASN's route history and yields each distinct de-peering event.
    """
    for asn, routes_data in asn_to_routes_map.items():
        num_timesteps = len(routes_data)
        t = 0
        while t < num_timesteps:
            if routes_data[t]['routes_accepted'] == -1:
                start_index = t
                while t < num_timesteps and routes_data[t]['routes_accepted'] == -1:
                    t += 1
                
                duration = t - start_index
                returned = (t < num_timesteps)
                
                yield DepeeringEvent(
                    asn=asn,
                    start_index=start_index,
                    duration=duration,
                    returned=returned,
                )
            else:
                t += 1


def bucket_depeering_events(events: Generator[DepeeringEvent, None, None], num_timesteps: int):
    """
    Categorizes events by their departure date and duration (<7d, 7-30d, >30d).
    """
    total_depeerings = [0] * num_timesteps
    
    # 3 buckets: [<= 7, 7-30, > 30]
    all_buckets = [[0] * num_timesteps for _ in range(3)]
    returned_buckets = [[0] * num_timesteps for _ in range(3)]
    unreturned_buckets = [[0] * num_timesteps for _ in range(3)]

    for event in events:
        t = event.start_index
        total_depeerings[t] += 1

        # Determine duration bucket index: 0 (<=7), 1 (7-30), 2 (>30)
        if event.duration <= 7:
            bucket_idx = 0
        elif event.duration <= 30:
            bucket_idx = 1
        else:
            bucket_idx = 2

        all_buckets[bucket_idx][t] += 1
        if event.returned:
            returned_buckets[bucket_idx][t] += 1
        else:
            unreturned_buckets[bucket_idx][t] += 1

    return total_depeerings, all_buckets, returned_buckets, unreturned_buckets

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



    if not asn_to_routes_over_time_map:
        return

    sample_asn = next(iter(asn_to_routes_over_time_map))
    num_timesteps = len(asn_to_routes_over_time_map[sample_asn])

    # Construct X-axis labels
    if start_time is not None:
        dates_list = [(start_time + datetime.timedelta(days=i)).strftime('%Y-%m-%d') for i in range(num_timesteps)]
    else:
        dates_list = [f"T{i}" for i in range(num_timesteps)]

    # 1. Extract and Bucket Events
    events = extract_depeering_events(asn_to_routes_over_time_map)
    total_events, all_buckets, returned_buckets, unreturned_buckets = bucket_depeering_events(events, num_timesteps)

    # 2. Render Plots
    bucket_labels = ["<= 7 days", "7-30 days", "> 30 days"]

    plot_list_as_line_plot(
        data_list=total_events,
        y=dates_list,
        title="De-peerings Over Time (By Departure Date)",
    )

    plot_stacked_line_plot(
        data_lists=all_buckets,
        labels=dates_list,
        x_labels=bucket_labels,
        title="All De-peerings Over Time by Duration",
    )

    plot_stacked_line_plot(
        data_lists=returned_buckets,
        labels=dates_list,
        x_labels=bucket_labels,
        title="Temporary De-peerings (Returned) by Duration",
    )

    plot_stacked_line_plot(
        data_lists=unreturned_buckets,
        labels=dates_list,
        x_labels=bucket_labels,
        title="Permanent De-peerings (Did Not Return) by Duration",
    )


    



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
            valid_routes_data_full = [routes['routes_accepted'] for routes in routes_data if routes['routes_accepted'] >= 0]
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
    end_time = datetime.datetime.strptime("2025-08-19 00:00", "%Y-%m-%d %H:%M")

    asn_to_routes_map = load_routeserver_data_from_range("ix-br", "SP-rs2-v4", start_time, end_time, datetime.timedelta(days=1))
    
    asn_participations(asn_to_routes_map, start_time, end_time)
    depeering_analysis(asn_to_routes_map)

    
    
    #create_window_with_all_rendered_graphs_this_session()
    

    

focused_asn = 267458

#for date, routes in asn_to_routes_map[focused_asn]:
#    print(f"Date: {date.strftime('%Y-%m-%d')}, Accepted Routes: {routes}")