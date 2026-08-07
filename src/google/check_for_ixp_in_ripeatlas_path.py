import json
import ipaddress

import requests

def load_ixp_prefixes(search_term="IX.br"):
    url = "https://www.peeringdb.com/api/ix"
    params = {
        "name__contains": search_term,
        "depth": 2
    }
    
    print(f"Fetching data for '{search_term}' from PeeringDB...")
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()['data']
        print(data)
    except Exception as e:
        print(f"Error fetching data: {e}")
        return {}

    ixp_subnets = {}

    for ix in data:
        ix_name = ix['name']
        prefixes = []
         
        for ixlan in ix.get('ixlan_set', []):
            for ixpfx in ixlan.get('ixpfx_set', []):
                pfx_str = ixpfx['prefix']
                try: 
                    net = ipaddress.ip_network(pfx_str)
                    prefixes.append(net)
                except ValueError:
                    print(f"Invalid prefix '{pfx_str}' for IXP '{ix_name}', skipping.")
                    continue
        
        if prefixes:
            ixp_subnets[ix_name] = prefixes
            
    return ixp_subnets



def check_for_ixp(atlas_result):
    
    ixp_prefixes = load_ixp_prefixes()
    found_ixps = []


    for hop in atlas_result.get('hops', []):
        for packet in hop.get('result', []):
            

            hop_ip_str = packet.get('from')
            
            if not hop_ip_str:
                continue

            try:
                hop_ip = ipaddress.ip_address(hop_ip_str)
                
                for name, prefix in ixp_prefixes.items():
                    if hop_ip in prefix:
                        found_ixps.append({
                            "hop_number": hop.get('hop'),
                            "ip": hop_ip_str,
                            "ixp_name": name
                        })
            except ValueError:
                continue
                
    return found_ixps


if __name__ == "__main__":

    brazil_ixps = load_ixp_prefixes()
    for name, subnets in list(brazil_ixps.items())[:3]: # limit output to 3
        print(f"\n--- {name} ---")
        for net in subnets:
            print(f"  {str(net)}")