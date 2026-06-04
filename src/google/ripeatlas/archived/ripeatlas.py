
import requests



def get_atlas_measurement_data(asn):
    
    request = f"/data/as-overview/data.json?resource=AS{asn}"
    request = f"/data/atlas-probe-deployment/data.json?resource=AS{asn}"
    url = f"https://stat.ripe.net{request}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data
    else:
        print(f"Error: {response.status_code}")
        print(f"Response: {response.text}")
        return None


def verify_ripestat_count(asn, monitor_ip, query_time):
    # Endpoint to get peering details for a specific RRC and time
    url = f"https://stat.ripe.net/data/ris-peerings/data.json"
    params = {
        'resource': f"AS{asn}",
        'query_time': query_time,
        'rrcs': '15'
    }
    
    response = requests.get(url, params=params).json()
    
    #print(response)
    peerings = response['data']['peerings']
    count = 0
    for rrc_entry in peerings:
        for peer in rrc_entry['peers']:
            count += 1
            #print(peer['ip'])
            if peer['ip'] == monitor_ip:
                print(f"Monitor: {peer['ip']}")
                print(f"Official Prefix Count: {peer['prefix_count']}")
                return peer['prefix_count']
    print(f"Total peers found: {count}")
    print("Monitor not found in this snapshot.")
    return None