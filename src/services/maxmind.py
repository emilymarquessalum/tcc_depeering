
# got it by signing up:
# https://www.maxmind.com/en/geolite2/signup
# after logging in, it will redirect you to a page with "Database Products and Subscriptions"
# where you can download the latest data.
import bisect
import csv

import ipaddress

folder = "GeoLite2-Country-CSV_20260428/"


country_blocks_file_v4 = folder + "GeoLite2-Country-Blocks-IPv4.csv"
# Example:
# network,geoname_id,registered_country_geoname_id,represented_country_geoname_id,is_anonymous_proxy,is_satellite_provider,is_anycast
# 1.0.0.0/24,,2077456,,0,0,

country_blocks_file_v6 = folder + "GeoLite2-Country-Blocks-IPv6.csv"

country_locations_file = folder + "GeoLite2-Country-Locations-en.csv"
# Example:
# geoname_id,locale_code,continent_code,continent_name,country_iso_code,country_name,is_in_european_union
# 2077456,en,OC,Oceania,AU,Australia,0
def load_ip_block_to_country_mapping(ip_version="v4"):
    country_locations = {}
    with open(country_locations_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            country_locations[row["geoname_id"]] = row["country_name"]
    
    blocks_file = country_blocks_file_v4 if ip_version == "v4" else country_blocks_file_v6
    
    # We will maintain two parallel lists
    # 1. A sorted list of raw integer network addresses (for lightning-fast binary search)
    network_addresses = []
    # 2. A list of tuples holding the actual network object and country name
    network_data = []

    temporary_list = []
    with open(blocks_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            network_str = row['network']
            country_id = row['registered_country_geoname_id'] or row['geoname_id']
            country_name = country_locations.get(country_id, "Unknown Country")
            
            network_obj = ipaddress.ip_network(network_str)
            temporary_list.append((network_obj, country_name))
            
    # Sort everything by the starting network IP address
    temporary_list.sort(key=lambda x: x[0].network_address)
    
    # Split into parallel arrays so lookup has ZERO overhead
    for network_obj, country_name in temporary_list:
        # Storing the raw int value makes bisect comparisons insanely fast
        network_addresses.append(int(network_obj.network_address))
        network_data.append((network_obj, country_name))
        
    return network_addresses, network_data

def find_country_by_ip(ip_address_str, network_addresses, network_data):
    """
    Looks up an IP using Binary Search with zero list-recreation overhead.
    Time Complexity: True O(log N)
    """
    try:
        ip_obj = ipaddress.ip_address(ip_address_str)
        ip_int = int(ip_obj)  # Compare raw integers instead of complex objects
    except ValueError:
        return "Invalid IP Address format"

    # Find where this IP integer would fit in our sorted list of network integers
    idx = bisect.bisect_right(network_addresses, ip_int) - 1

    if idx >= 0:
        network, country_name = network_data[idx]
        # Verify the IP is actually inside this subnet block
        if ip_obj in network:
            return country_name

    return "Country Not Found"


