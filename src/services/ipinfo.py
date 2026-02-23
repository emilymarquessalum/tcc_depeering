


from os import environ
import requests
from dotenv import load_dotenv

load_dotenv("../../.env") 

def get_info_from_asn(asn):
    path = f"https://ipinfo.io/lite/AS{asn}/json?token={environ.get('IP_INFO_TOKEN')}"
    token = environ.get("IP_INFO_TOKEN")
    try:
        response = requests.get(path, headers={"Authorization": f"Bearer {token}"})
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data for AS{asn}: {e}")
        return None
    
    
if __name__ == "__main__":
    asn = 26162  # Example ASN
    info = get_info_from_asn(asn)
    print(info)