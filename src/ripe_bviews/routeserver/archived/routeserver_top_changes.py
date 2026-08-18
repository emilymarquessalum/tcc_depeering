





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



def depeering_analysis():
    return
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