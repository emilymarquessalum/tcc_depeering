

# website: https://ixpdb.euro-ix.net/en/

import requests

# Each IXP has its own id inside their system, we could do a name match if we 
# wanted to automate it but I just need to focus on one or two IXPs so I will get it 
# manually.
def get_participants_of_ixp(ixp_id):
    path = f"/provider/{ixp_id}/participants"

    response = requests.get("https://api.ixpdb.net/v1/" + path)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to get participants for IXP {ixp_id}. Status code: {response.status_code}")
        return None


ixp_sao_paulo_id = 791 

if __name__ == "__main__":
    participants = get_participants_of_ixp(ixp_sao_paulo_id)

    if participants:
        print(f"Participants of IXP {ixp_sao_paulo_id}:")
        for participant in participants:
            print(f"- ASN: {participant['asn']}, Name: {participant['name']}")
    else:
        print("No participants found or failed to retrieve data.")


