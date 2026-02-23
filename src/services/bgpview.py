import requests


def get_asn_details(asn):
    # BGPView API - completely free, no token needed
    url = f"https://api.bgpview.io/asn/{asn}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        # The structure is slightly different, so we parse it here
        return {
            "asn": data['data']['asn'],
            "name": data['data']['name'],
            "description": data['data']['description_short'],
            "country": data['data']['country_code'],
            "website": data['data']['website'],
            # BGPView doesn't have a simple "ISP" tag, but the name usually reveals it
            "upstreams": len(data['data'].get('upstreams', []))
        }
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__": 
    info = get_asn_details(265405)
    
    if info:
        print(f"Name: {info['name']}")
        print(f"Desc: {info['description']}")
        print(f"Country: {info['country']}")