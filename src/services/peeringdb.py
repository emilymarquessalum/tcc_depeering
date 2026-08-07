import requests

 

def get_asns_by_name(isp_name):
    url = f"https://www.peeringdb.com/api/net?name__contains={isp_name}"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json().get('data', [])
        if len(data) == 0:
            print(f"No ASNs found for ISP name containing '{isp_name}'")
            return []
        for entry in data:
            print(f"ASN: {entry['asn']} | Name: {entry['name']}")
        return data
    else:
        print("Error fetching data")
 


def get_peeringdb_info(asn):
    # PeeringDB API - Free, No Token
    url = f"https://www.peeringdb.com/api/net?asn={asn}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        # PeeringDB returns a list, even for a single ASN
        if not data['data']:
            return f"AS{asn} not found in PeeringDB."
            
        net_info = data['data'][0]
        
        return {
            "asn": net_info['asn'],
            "name": net_info['name'],
            "type": net_info['info_type'],  # NSP (ISP), Content, Cable/DSL, etc.
            "website": net_info['website'],
            "policy": net_info['policy_general'] # Open, Selective, Restrictive
        }

    except requests.exceptions.RequestException as e:
        print(f"Connection Error: {e}")
        return None

if __name__ == "__main__":
    # Test with Verizon (AS701) - A Tier 1 ISP
    print("--- AS 701 (Verizon) ---")
    print(get_peeringdb_info(701))
    
    print("\n--- AS 265405 ---")
    print(get_peeringdb_info(265405))