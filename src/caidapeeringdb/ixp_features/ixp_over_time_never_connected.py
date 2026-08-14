





from src.caidapeeringdb.caidapeeringdb_load import get_asn_from_net, get_dates_from_files, get_ixp_from_net, get_unique_ixps_from_data_list
from src.caidapeeringdb.ixp_overtime import plot_ixp_connections_over_time_by_category, plot_ixp_statistics_connections_over_time, plot_ixps_connections_over_time


def get_ixps_that_never_had_connections_with_asns(asn_to_analyze, all_data, all_ixps=None): 
    ixps_with_connections = set()

    print(f"Analyzing {len(all_data)} data entries...")

    if all_ixps is None:
        print("Getting all unique IXPs from data list...")
        all_ixps = get_unique_ixps_from_data_list(all_data)

    for data in all_data:
        conns = data.get("netixlan", {}).get("data", [])
        for conn in conns:
            if get_asn_from_net(conn) == asn_to_analyze and get_ixp_from_net(conn) is not None:
                ixps_with_connections.add(get_ixp_from_net(conn)) 

 
    all_ixp_ids = [] 
    for ixp in all_ixps:
        all_ixp_ids.append(ixp.get("id"))
        
    ixps_never_connected = set(all_ixp_ids) - ixps_with_connections

    if ixps_never_connected is None or len(ixps_never_connected) == 0: 
        print(f"No IXPs found that never connected to ASN {asn_to_analyze}, meaning this AS is connected to all {len(all_ixp_ids)} IXPs. To fact check, the amount of connections it actually has is {len(ixps_with_connections)}.")
        return []
    else:
        print(ixps_with_connections)

        print(f"Connected % of ASN {asn_to_analyze} to IXPs: {len(ixps_with_connections)}/{len(all_ixp_ids)} = {len(ixps_with_connections)/len(all_ixp_ids)*100:.2f}%")
    return ixps_never_connected 
    
        


def plot_ixp_connections_over_time_for_ixps_that_never_connected_to_ases(all_data, all_files, asn_to_analyze, all_ixps):


    
    ixps_never_connected = get_ixps_that_never_had_connections_with_asns(asn_to_analyze, all_data, all_ixps=all_ixps)

    ixps_at_some_point_connected = [ixp.get("id") for ixp in all_ixps if ixp.get("id") not in ixps_never_connected]
    
    dates = get_dates_from_files(all_files)


    if len(ixps_never_connected) == 0:
        print(f"No IXPs found that never connected to ASN {asn_to_analyze}. Skipping plot.")
        return
    plot_ixp_statistics_connections_over_time(
        all_data=all_data,
        dates=dates,
        ixp_ids=ixps_never_connected, 
        title_info="IXPs that never connected to ASN " + str(asn_to_analyze),
    )

    
    plot_ixp_statistics_connections_over_time(
        all_data=all_data,
        dates=dates,
        ixp_ids=ixps_at_some_point_connected, 
        title_info="IXPs that at some point connected to ASN " + str(asn_to_analyze),
    )

    