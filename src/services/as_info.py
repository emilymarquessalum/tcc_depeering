

# https://github.com/ipverse/as-metadata

# valid AS categories:
# isp, hosting, business. education_research, government_admin

import json


def get_asn_lookup_from_ipverse():
    JSON_FILE = 'as.json'
    
    with open(JSON_FILE, 'r') as f:
        # Load the full list
        raw_data = json.load(f)
        
        # Transform into a dictionary for O(1) lookup
        # Key: ASN (int), Value: The metadata dict
        asn_lookup = {item['asn']: item['metadata'] for item in raw_data}
    return asn_lookup
def get_asn_type_from_ipverse(asn_lookup, asn):
    # Standardize input (handle "AS123" or 123)


    error_result = {
        "name": "Unknown",
        "category": "unknown",
        "role": "Unknown",
        "country": "Unknown",
        "asn": asn
    }
    try:
        clean_asn = int(str(asn).replace("AS", ""))
    except ValueError:
        print(f"Warning: Invalid ASN format '{asn}'. Returning 'Unknown' for all fields.")
        return error_result

    meta = asn_lookup.get(clean_asn)
    if meta:
        return {
            "name": meta.get("description") or "Unknown",
            "category": meta.get("category", "unknown") or "unknown",   
            "role": meta.get("networkRole") or "Unknown",   # Tier-1, stub, etc.
            "country": meta.get("countryCode") or "Unknown",
            "asn": clean_asn 
        }
    return error_result



if __name__ == "__main__":
    asn_lookup = get_asn_lookup_from_ipverse()
    my_asns = [26162, 15169]
    #my_asns = []
    #my_asns = [15133, 33438]
    results = [get_asn_type_from_ipverse(asn_lookup, a) for a in my_asns]
    print(results)