from collections import defaultdict

from src.caidapeeringdb.ixp_features.continent_logic import get_continent_for_ixp


def build_asn_ixp_data_structures(asn_to_analyze, before_data, after_data, all_ixps):
    # 1. Create a lookup map for IXPs immediately
    # This turns O(N) searches into O(1) lookups
    ixp_lookup = {ixp["id"]: ixp for ixp in all_ixps}
    
    # 2. Process 'before' data efficiently
    before_peered_ixp_ids = {
        conn.get("ix_id") for conn in before_data.get("netixlan", {}).get("data", [])
        if (conn.get("asn") == asn_to_analyze or conn.get("local_asn") == asn_to_analyze)
        and conn.get("is_rs_peer", False)
    }
    
    # 3. Process 'after' data in a SINGLE pass
    all_asn_connections = []
    current_peered_ixp_ids = set()
    not_peered_ixp_ids = set()
    asn_ixp_connections_by_continent = defaultdict(lambda: defaultdict(int))

    after_raw_data = after_data.get("netixlan", {}).get("data", [])
    for conn in after_raw_data:
        asn = conn.get("asn")
        local_asn = conn.get("local_asn")
        
        if asn == asn_to_analyze or local_asn == asn_to_analyze:
            all_asn_connections.append(conn)
            ixp_id = conn.get("ix_id")
            
            # Categorize by peering status
            if conn.get("is_rs_peer", False):
                current_peered_ixp_ids.add(ixp_id)
            else:
                not_peered_ixp_ids.add(ixp_id)
            
            # Update continent counts using our lookup map
            ixp_info = ixp_lookup.get(ixp_id)
            continent = get_continent_for_ixp(ixp_id, ixp_info)
            asn_ixp_connections_by_continent[continent][ixp_id] += 1

    # 4. Build the continent_to_ixps_map efficiently
    continent_to_ixps_map = defaultdict(list)
    for ixp_id, ixp_info in ixp_lookup.items():
        continent = get_continent_for_ixp(ixp_id, ixp_info)
        continent_to_ixps_map[continent].append(ixp_id)

    # 5. Set logic (remains efficient as is)
    current_all_ixp_ids = {conn.get("ix_id") for conn in all_asn_connections}
    depeered_ixp_ids = before_peered_ixp_ids - current_peered_ixp_ids
    completely_lost_ixp_ids = before_peered_ixp_ids - current_all_ixp_ids
    depeered_with_nonpeered_ixp_ids = depeered_ixp_ids & not_peered_ixp_ids
    
    return {
        "before_peered_ixp_ids": before_peered_ixp_ids,
        "current_peered_ixp_ids": current_peered_ixp_ids,
        "not_peered_ixp_ids": not_peered_ixp_ids,
        "depeered_ixp_ids": depeered_ixp_ids,
        "completely_lost_ixp_ids": completely_lost_ixp_ids,
        "depeered_with_nonpeered_ixp_ids": depeered_with_nonpeered_ixp_ids,
        "asn_ixp_connections_by_continent": dict(asn_ixp_connections_by_continent),
        "continent_to_ixps_map": dict(continent_to_ixps_map),
        "all_asn_connections": all_asn_connections,
    }
