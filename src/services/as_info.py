

# https://github.com/ipverse/as-metadata


import json


def get_asn_lookup():
    JSON_FILE = 'as.json'
    
    with open(JSON_FILE, 'r') as f:
        # Load the full list
        raw_data = json.load(f)
        
        # Transform into a dictionary for O(1) lookup
        # Key: ASN (int), Value: The metadata dict
        asn_lookup = {item['asn']: item['metadata'] for item in raw_data}
    return asn_lookup
def get_asn_type(asn_lookup, asn):
    # Standardize input (handle "AS123" or 123)
    try:
        clean_asn = int(str(asn).replace("AS", ""))
    except ValueError:
        return "Invalid ASN"

    meta = asn_lookup.get(clean_asn)
    if meta:
        return {
            "name": meta.get("description"),
            "category": meta.get("category"),   
            "role": meta.get("networkRole"),   # Tier-1, stub, etc.
            "country": meta.get("countryCode")
        }
    return {
        "name": "Unknown",
        "category": "Unknown",
        "role": "Unknown",
        "country": "Unknown"
    }



if __name__ == "__main__":
    asn_lookup = get_asn_lookup()
    my_asns = [26162, 15169]
    my_asns = []
    #my_asns = [15133, 33438]
    results = [get_asn_type(asn_lookup, a) for a in my_asns]
    print(results)