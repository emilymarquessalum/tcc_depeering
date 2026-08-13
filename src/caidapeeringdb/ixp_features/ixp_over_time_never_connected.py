





from src.caidapeeringdb.caidapeeringdb_load import get_asn_from_net, get_dates_from_files, get_unique_ixps_from_data_list
from src.caidapeeringdb.ixp_overtime import plot_ixp_connections_over_time_by_category, plot_ixps_connections_over_time


def get_ixps_that_never_had_connections_with_asns(asn_to_analyze, all_data, all_ixps=None): 
    ixps_with_connections = set()

    if all_ixps is None:
        all_ixps = get_unique_ixps_from_data_list(all_data)

    for data in all_data:
        conns = data.get("netixlan", {}).get("data", [])
        for conn in conns:
            if get_asn_from_net(conn) == asn_to_analyze and conn.get("ix_id") is not None:
                ixps_with_connections.add(conn.get("ix_id"))

 
    all_ixp_ids = [ix["ix"] for ix in all_ixps if "ix" in ix] 
    ixps_never_connected = set(all_ixp_ids) - ixps_with_connections

    if ixps_never_connected is None or len(ixps_never_connected) == 0: 
        print(f"No IXPs found that never connected to ASN {asn_to_analyze}, meaning this AS is connected to all {len(all_ixp_ids)} IXPs. To fact check, the amount of connections it actually has is {len(ixps_with_connections)}.")
        return []
    
    return ixps_never_connected
    
        


def plot_ixp_connections_over_time_for_ixps_that_never_connected_to_ases(all_data, all_files, asn_to_analyze, all_ixps):

    ixps_never_connected = get_ixps_that_never_had_connections_with_asns(asn_to_analyze, all_data, all_ixps=all_ixps)

    dates = get_dates_from_files(all_files)


    if len(ixps_never_connected) == 0:
        print(f"No IXPs found that never connected to ASN {asn_to_analyze}. Skipping plot.")
        return
    plot_ixps_connections_over_time(
        all_data=all_data,
        dates=dates,
        ixp_ids=ixps_never_connected
    )