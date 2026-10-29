
import sys
from pathlib import Path 



sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
import json
import os
import src.caidapeeringdb.caidapeeringdb_load as pdb


def load_asns_jsonl(filepath="asns.jsonl") -> list[dict]:
    """Reads the local CAIDA ASRank jsonl file into a list of dictionaries."""
    asns = []
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Could not find '{filepath}'. Make sure it exists in the working directory.")
    
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                asns.append(json.loads(line.strip()))
    return asns

def enrich_ases_with_peeringdb(asns_jsonl_path="asns.jsonl", output_json_path="asns_with_peeringdb.json") -> list[dict]:
    """
    Enriches each AS from asns.jsonl with PeeringDB history over time.
    Adds a 'peeringdb_timeline' field mapped as:
        Date -> {
            "peerings": [...],
            "route-server-peerings": [...]
        }
    """
    print("Loading AS list from asns.jsonl...")
    as_list = load_asns_jsonl(asns_jsonl_path)
    
    # Extract unique ASNs (convert to integer to match PeeringDB schema)
    target_asns = []
    for item in as_list:
        try:
            target_asns.append(int(item["asn"]))
        except (KeyError, ValueError):
            continue
            
    # Retrieve sorted PeeringDB snapshot files available in the directory/ROOT_DIR
    all_files = pdb.get_all_files()
    if not all_files:
        print("Warning: No PeeringDB snapshot files found via caidapeeringdb_load.get_all_files().")
        print("Attempting to download recent snapshot...")
        pdb.get_most_recent_data()
        all_files = pdb.get_all_files()

    print(f"Processing {len(all_files)} PeeringDB snapshots for {len(target_asns)} ASNs...")
    
    # Load raw connections timeline across all snapshots (returns all connection objects)
    # pdb.load_connections_over_time_for_asns returns: dict[asn, list[(date_str, [conn_dicts])]]
    raw_timeline_by_asn = pdb.load_connections_over_time_for_asns(
        all_files, 
        asns_to_search=target_asns, 
        connections_should_be="all"
    )

    # Build local fast-lookup map for ASN -> dataset dictionary object
    asn_to_object = {int(item["asn"]): item for item in as_list if "asn" in item}

    for asn_int, timeline in raw_timeline_by_asn.items():
        if asn_int not in asn_to_object:
            continue
            
        target_obj = asn_to_object[asn_int]
        history_map = {}

        for date_str, connections in timeline:
            peerings = []
            route_server_peerings = []

            for conn in connections:
                # Classify peerings based on is_rs_peer boolean field
                if conn.get("is_rs_peer"):
                    route_server_peerings.append(conn)
                else:
                    peerings.append(conn)

            history_map[date_str] = {
                "peerings": peerings,
                "route-server-peerings": route_server_peerings
            }

        target_obj["peeringdb_timeline"] = history_map

    print(f"Writing enriched data to {output_json_path}...")
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(as_list, f, indent=2)

    print("Successfully finished processing!")
    return as_list

if __name__ == "__main__":
    enriched_data = enrich_ases_with_peeringdb()
    
    # Preview sample output for the first AS
    if enriched_data:
        sample_as = enriched_data[0]
        print(f"\nSample Output for AS{sample_as.get('asn')} ({sample_as.get('asnName')}):")
        timeline = sample_as.get("peeringdb_timeline", {})
        for date, conns in list(timeline.items())[:2]:  # Print first 2 months
            print(f"  Date: {date}")
            print(f"    Peerings count: {len(conns['peerings'])}")
            print(f"    Route Server Peerings count: {len(conns['route-server-peerings'])}")

        