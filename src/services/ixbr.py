


import requests

# its not always available it seems...
def get_official_members_list():

    path = "https://cadastro.ix.br/generate_json?ixp=sp"
    response = requests.get(path)
    if response.status_code == 200:
        data = response.json()
        members = set()
        for member in data.get("members", []):
            asn = member.get("asn")
            if asn:
                members.add(int(asn))
        print(f"Found {len(members)} members in official IX.br list")
        return members
    else:
        print(f"Error fetching official members list: {response.status_code}")
        return set()