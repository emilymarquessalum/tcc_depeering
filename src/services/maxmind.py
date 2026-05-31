
# got it by signing up:
# https://www.maxmind.com/en/geolite2/signup
# after logging in, it will redirect you to a page with "Database Products and Subscriptions"
# where you can download the latest data.

import csv


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


    country_locations = []

    with open(country_locations_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            country_locations.append({
                "geoname_id": row["geoname_id"],
                "country_name": row["country_name"],
            })
    
    ip_block_to_country_name_mapping = {}
    with open(country_blocks_file_v4 if ip_version == "v4" else country_blocks_file_v6, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            network = row['network']
            country_id = row['registered_country_geoname_id']
            country_name = next((loc["country_name"] for loc in country_locations if loc["geoname_id"] == country_id), None)
            ip_block_to_country_name_mapping[network] = country_name

    return ip_block_to_country_name_mapping
 