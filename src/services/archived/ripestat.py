


import requests

# gives me info like:
# {'type': 'as', 'resource': '26162', 'block': {'resource': '25600-26623', 'desc': 'Assigned by ARIN', 'name': 'IANA 16-bit Autonomous System (AS) Numbers Registry'}, 'holder': 'Nucleo de Inf. e Coord. do Ponto BR - NIC.', 'announced': False, 'query_starttime': '2026-04-30T08:00:00', 'query_endtime': '2026-04-30T08:00:00'}
# not very useful for me, so archived
def get_ripe_type(asn):
    url = f"https://stat.ripe.net/data/as-overview/data.json?resource=AS{asn}"
    data = requests.get(url).json()
    
    return data['data'] 


if __name__ == "__main__":
    asn = 26162
    print(get_ripe_type(asn))