
 
# "rs1.saopaulo.sp.ix.br"
import requests


def load_ases_from_looking_glass(load_all_info=False):
    path = "https://lg.ix.br/api/v1/routeservers/SP-rs1-v4/neighbors"

    response = requests.get(path)
    ases = set()
    asn_to_info_map = {}
    if response.status_code == 200:
        data = response.json() 
        neighbours = data.get("neighbors", [])
        print(f"Found {len(neighbours)} neighbors (looking glass)")
        for neighbor in neighbours:
            if load_all_info:
                asn_to_info_map[neighbor.get("asn")] = neighbor
            ases.add(neighbor.get("asn"))
    else:
        print(f"Error fetching data (looking glass: {response.status_code})")

    if load_all_info:
        ases_info = []
        for asn in ases:
            info = asn_to_info_map.get(asn, {"asn": asn})
            ases_info.append(info)
        return ases_info
    
    return list(ases)

if __name__ == "__main__":
    ases = load_ases_from_looking_glass(load_all_info=True)
    print(f"Loaded {len(ases)} ASes (looking-glass)")  
    #print(ases[0])
    #routes_accepted, routes_exported
