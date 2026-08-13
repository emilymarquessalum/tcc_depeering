import os
import sys
import requests
import json
from collections import defaultdict
import re
from definitions import ROOT_DIR

def download_peeringdb_dump(date):
    url = f"https://publicdata.caida.org/datasets/peeringdb/{date.split('_')[0]}/{date.split('_')[1]}/peeringdb_2_dump_{date}.json"

    output_folder = f"{ROOT_DIR}/caida-peeringdb/"

    file_path = output_folder + f"peeringdb_2_dump_{date}.json"

    if not os.path.exists(file_path):
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            data = r.json()
            with open(file_path, "w") as f:
                json.dump(data, f)


def get_asn_from_net(net):
    if "asn" in net:
        return net["asn"]
    elif "local_asn" in net:
        return net["local_asn"]
    else:
        print(f"Warning: No ASN found for net entry: {net}")
        return None
    

def ixp_name_short_format(ixp_name):
   return ixp_name.replace("Digital Realty", "DR").replace("New York","NY")[:11]

'''
def get_connections_for_asn(asn: int, data, key="netixlan", connections_should_be="peered"):

    net_data = data[key]["data"]

    ixp_connections = []

    for net in net_data:
        asn_of_net: int = get_asn_from_net(net)
        if asn_of_net is None:
            print(f"Warning: No ASN found for net entry: {net}")
            return []
        if asn_of_net == asn:
            ixp_connections.append(net)

    if not ixp_connections:
        return []
    
    connections_that_are_peered = [conn for conn in ixp_connections if conn["is_rs_peer"]] if "is_rs_peer" in ixp_connections[0] else []
    connections_that_are_not_peered = [conn for conn in ixp_connections if not conn["is_rs_peer"]] if "is_rs_peer" in ixp_connections[0] else []
    
    connections_with_mapped_ix_id = {}

    connections_to_consider = connections_that_are_peered if connections_should_be == "peered" else connections_that_are_not_peered if connections_should_be == "not_peered" else ixp_connections
    for conn in connections_to_consider:
        ix_id = conn["ix_id"]
        if ix_id not in connections_with_mapped_ix_id:
            connections_with_mapped_ix_id[ix_id] = []
        if not ix_id or ix_id == 0 or ix_id == "0":
            print(f"Warning: No ix_id found for connection entry: {conn}")
            continue
        connections_with_mapped_ix_id[ix_id].append(conn)

    latest_connections__per_ix_id = []
    all_connections = connections_with_mapped_ix_id.items()
    for ix_id, connections in all_connections:
        latest_connection = max(connections, key=lambda c: c["updated"])
        latest_connections__per_ix_id.append(latest_connection)

    return latest_connections__per_ix_id
'''

def get_facilities_from_asn(asn: int, data, key="netfac"):

    net_data = data[key]["data"]

    facilities = []

    for net in net_data:
        asn_of_net: int = get_asn_from_net(net)
        if asn_of_net is None:
            print(f"Warning: No ASN found for net entry: {net}")
            return []
        if asn_of_net == asn:
            facilities.append(net)

    return facilities


def get_ixps_of_facility(facility_id: int, data, key="ixfac"):
    ix_data = data[key]["data"]

    ixps_in_facility = []

    for ix in ix_data:
        if "fac_id" in ix and ix["fac_id"] == facility_id:
            ixps_in_facility.append(ix)

    return ixps_in_facility


def get_ases_by_number_of_lost_peered_connections(all_files, base_path=None,
                                                  get_biggest_gains_instead_of_losses=False):
    # Sort files upfront so we know exactly which are the 'start' and 'end' snapshots
    all_files.sort()
    if not all_files:
        return []

    if base_path is None:
        base_path = f"{ROOT_DIR}/caida-peeringdb/"

    first_file = all_files[0]
    last_file = all_files[-1]
    
    # We only need to track the count of connections for the start and end states
    # This avoids storing every intermediate state in memory
    start_counts = defaultdict(int)
    end_counts = defaultdict(int)

    def process_file(filename, count_dict):
        full_path = os.path.join(base_path, filename)
        with open(full_path, "r") as f:
            data = json.load(f)
            # Use a generator expression for faster filtering
            for conn in data.get("netixlan", {}).get("data", []):
                if conn.get("is_rs_peer"):
                    asn = get_asn_from_net(conn)
                    count_dict[asn] += 1

    # Process only the relevant boundaries
    process_file(first_file, start_counts)
    process_file(last_file, end_counts)

    # Calculate losses
    # We iterate over start_counts because an AS must exist at the start to "lose" connections
    results = []
    for asn, start_total in start_counts.items():
        end_total = end_counts.get(asn, 0)
        results.append((asn, start_total - end_total))

    # Sort by the number of lost connections descending
    if get_biggest_gains_instead_of_losses:
        return sorted(results, key=lambda x: x[1], reverse=False)  # Gains would be negative losses
    return sorted(results, key=lambda x: x[1], reverse=True)


def get_data(file: str):
    with open((_folder + file) if file.startswith("peeringdb_2_dump_") else file, "r") as f:
        data = json.load(f)
    return data

def get_all_data(files):
    all_data = []
    for file in files:
        data = get_data(file)
        all_data.append(data)
    return all_data


# This function gives us the connections to 
# IXPs for specific ASNs over time.
def load_connections_over_time_for_asns(all_files, asns_to_search, connections_should_be="all"):
    # Normalize asns_to_search to a set for O(1) lookup
    search_ids = {a[0] if isinstance(a, tuple) else a for a in asns_to_search}
    
    # Pre-populate the results dictionary
    connections_over_time_by_asn = {asn: [] for asn in search_ids}

    # Pre-compile the regex pattern outside the loop
    file_date_pattern = re.compile(r"peeringdb_2_dump_(.*?)\.json")

    for file in all_files: 
        # Extract date string efficiently
        match = file_date_pattern.search(file)
        file_date_str = match.group(1) if match else "unknown"
        
        data = get_data(file)
        
        # Group only the relevant data for ASNs we care about
        current_file_data = defaultdict(list)
        for net in data.get("netixlan", {}).get("data", []):
            asn = get_asn_from_net(net)
            if asn in search_ids:  # Early filtering!
                current_file_data[asn].append(net)

        # Only process the ASNs that actually had data in this file, 
        # or append empty lists for missing ones to preserve the timeline.
        for asn in search_ids:
            asn_conns = current_file_data[asn] # Defaults to [] if not found in defaultdict
            processed_conns = process_connections(asn_conns, connections_should_be)
            connections_over_time_by_asn[asn].append((file_date_str, processed_conns))


    # returns a dict of asn -> list of (date_str, connections) tuples, where connections is a list of connection dicts for that date
    return connections_over_time_by_asn


def get_connections_for_ixp(ixp_id: int, data, key="netixlan", connections_should_be="peered"):
    ixp_connections = [conn for conn in data.get(key, {}).get("data", []) if str(conn.get("ix_id")) == str(ixp_id)]

    return process_connections(ixp_connections, connections_should_be, one_connection_per_ix=False)


def process_connections(ixp_connections, connections_should_be, one_connection_per_ix=True) -> list[dict]: 
    if not ixp_connections:
        return []

    # Pre-determine filtering criteria outside the loop
    filter_by_status = connections_should_be != "all"
    target_status = (connections_should_be == "peered") if filter_by_status else None

    if one_connection_per_ix:
        latest_per_ix = {}
        
        for conn in ixp_connections:
            # 1. Combined Filter & Extract (Saves an entire loop pass)
            if filter_by_status and conn.get("is_rs_peer") != target_status:
                continue
                
            ix_id = conn.get("ix_id")
            if not ix_id: 
                continue
            
            
            updated_time = conn.get("updated", "")
            
            # 3. One-pass deduplication
            existing = latest_per_ix.get(ix_id)
            if not existing or updated_time > existing.get("updated", ""):
                latest_per_ix[ix_id] = conn

        return list(latest_per_ix.values())

    # If deduplication isn't needed, just return the filtered list
    if filter_by_status:
        return [c for c in ixp_connections if c.get("is_rs_peer") == target_status]
        
    return ixp_connections

def get_asn_to_name_map(data):
    return data['as_set']["data"][0]

def get_asns_types_peeringdb(data, asns: list, silent: bool=False) -> dict[int, str]:
    asn_information = data["net"]["data"] 

    asn_to_type = {}
    for asn in asns:
        for net in asn_information:
            if get_asn_from_net(net) == int(asn):
                asn_to_type[asn] = net.get("info_type", "unknown")
                break
        else:
            if not silent:
                print(f"Warning: ASN {asn} not found in 'net' data.")
            asn_to_type[asn] = "unknown"

    return asn_to_type


def get_types_to_asns(data, asns: list, silent: bool=False) -> dict[str, list[int]]:
    
    asns_types = get_asns_types_peeringdb(data, asns, silent=silent)
    types_to_asns = defaultdict(list)
    for asn, asn_type in asns_types.items():
        types_to_asns[asn_type].append(asn)
    return types_to_asns

def get_all_asn_info_types(data):
    asn_information = data["net"]["data"] 

    types = set()
    for net in asn_information:
        info_type = net.get("info_type")
        if info_type:
            types.add(info_type)
    return types

def get_asns_of_info_type(data, info_type): 
    return [ 
        (get_asn_from_net(net), net.get("name", "Unknown"), "") # Assuming net has a 'name' key
        for net in data.get("net", {}).get("data", [])
        if net.get("info_type") == info_type and (get_asn_from_net(net) is not None)
    ]

def get_all_asns(data):
    return [get_asn_from_net(net) for net in data.get("net", {}).get("data", []) if get_asn_from_net(net) is not None]

def get_asinfo_from_asn(data, asn: int):
    asn_information = data["net"]["data"] 

    # info like: name, asn, looking_glass, info_type, info_scope (which seems to be the location, at least for some) 
    for net in asn_information:
        if get_asn_from_net(net) == asn:
            return net
    print(f"Warning: ASN {asn} not found in 'net' data.")
    return None

def get_all_ixps(data) -> list[dict]:
    # id, name, city, country, region_continent, created, updated...
    return list(data.get("ix", {}).get("data", []))



def is_asn_in_ixp(asn: int, ixp_id: int, data, key="netixlan", connections_should_be="peered"):
    connections = get_connections_for_ixp(ixp_id, data, key=key, connections_should_be=connections_should_be)
    for conn in connections:
        if get_asn_from_net(conn) == asn:
            return True
    return False

def get_unique_ixps_from_data_list(data_list):
    unique_ixps = []
    for data in data_list:
        ixps = get_all_ixps(data)
        for ixp in ixps:
            ixp_id = ixp.get("id")
            if ixp_id is not None and all(existing_ixp.get("id") != ixp_id for existing_ixp in unique_ixps):
                unique_ixps.append(ixp)
    return unique_ixps


def get_ixp_id_to_ixp_name_mapping(data):
    return {ixp["id"]: ixp["name"] for ixp in data.get("ix", {}).get("data", []) if "id" in ixp and "name" in ixp}


def get_organization(org_id: int, data, key="org"):
    org_data = data[key]["data"]

    for org in org_data:
        if "id" in org and org["id"] == org_id:
            return org

    return None

def get_all_organizations(data, key="org"):
    org_data = data[key]["data"]
    return org_data

def get_all_ixps_from_organization(org_id: int, data):

    all_ixps = get_all_ixps(data)
    organizations = []

    for ixp in all_ixps:
        org_id_of_ixp = ixp.get("org_id")
        if org_id_of_ixp == org_id:
            organizations.append(ixp)

    return organizations

def get_all_unique_organization_ids_from_ixps(data):
    all_ixps = get_all_ixps(data)
    org_ids = set()

    for ixp in all_ixps:
        org_id_of_ixp = ixp.get("org_id")
        if org_id_of_ixp is not None:
            org_ids.add(org_id_of_ixp)

    return list(org_ids)

def get_all_organizations_that_own_ixps(data, key="org"):
    
    org_data = data[key]["data"]
    org_ids_with_ixps = get_all_unique_organization_ids_from_ixps(data)

    organizations_with_ixps = []
    for org in org_data:
        if "id" in org and org["id"] in org_ids_with_ixps:
            organizations_with_ixps.append(org)

    return organizations_with_ixps
 

_folder = f"{ROOT_DIR}/caida-peeringdb/"
def get_all_files():
    return [f for f in os.listdir(_folder) if f.startswith("peeringdb_2_dump_") and f.endswith(".json")]

def get_file_from_date(date):
    return _folder + f"peeringdb_2_dump_{date}.json"

def get_dates_from_files(all_files):
    file_date_pattern = re.compile(r"peeringdb_2_dump_(.*?)\.json")
    dates = []
    for file in all_files:
        match = file_date_pattern.search(file)
        dates.append(match.group(1) if match else "unknown")
    return dates

def get_most_recent_file():
    all_files = get_all_files()
    if not all_files:
        return None
    all_files.sort()
    return all_files[-1]


def get_most_recent_data():
    most_recent_file = get_most_recent_file()
    if most_recent_file is None:

        download_peeringdb_dump("2026_06_30")
        most_recent_file = get_most_recent_file()
        if most_recent_file is None:
            print("Error: No PeeringDB dump files found even after attempting to download the most recent one.")
            return None  
     
    return get_data(most_recent_file)

if __name__ == "__main__":


    download_peeringdb_dump("2026_04_30") 
    sys.exit(0)
    if False:
        for i in range(2,4,1):
            date = "2026_" + str(i).zfill(2) + "_01"
            date = "2026_" + "05_" + str(i).zfill(2) 
            date = "2024_" + str(i).zfill(2) + "_01"
            download_peeringdb_dump(date)
        sys.exit(0)
   
    all_files = get_all_files()
    
    data = get_data(all_files[-1])
    #print(get_all_ixps(data)[0])
    print((get_all_organizations_that_own_ixps(data))[0])
    sys.exit(0)
    
    print(get_asinfo_from_asn(data, 15669))
    connections = get_connections_for_ixp(1, data, connections_should_be="peered")
    if connections:
        print((connections[0]))
         
    #print(get_asns_types(data, [15169, 15133, 33438]))
    #print(get_asns_types(data, [20940, 13335, 139341]))

    #print(len(get_all_asns(data)))