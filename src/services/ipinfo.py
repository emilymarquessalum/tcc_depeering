


from os import environ
import requests
from dotenv import load_dotenv

load_dotenv(".env")
load_dotenv("../../.env")
load_dotenv("../../../.env") 

def get_info_from_asn(asn):
    path = f"https://ipinfo.io/lite/AS{asn}/json?token={environ.get('IP_INFO_TOKEN')}"
    token = environ.get("IP_INFO_TOKEN")

    if token is None:
        print("Error: IP_INFO_TOKEN not found in environment variables.")
        return None
    
    try:
        response = requests.get(path, headers={"Authorization": f"Bearer {token}"})
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data for AS{asn}: {e}")
        return None
    
import requests
import json
from os import environ

# cant use it without a non-lite token
def get_batch_asn_info(asn_list):
    token = environ.get("IP_INFO_TOKEN")
    # Batch endpoint: you post an array of URLs
    url = f"https://ipinfo.io/batch?token={token}"
    
    # Construct the paths for the batch request
    # Format: ["/AS15169", "/AS13335", ...]
    req_paths = [f"/AS{asn}" for asn in asn_list]
    
    try:
        response = requests.post(url, json=req_paths)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Batch error: {e}")
        return {} 
    


    
if __name__ == "__main__":

    if False:
        asn = 26162  # Example ASN
        info = get_info_from_asn(asn)
        print(info)
    
    if True:
        all_asns = ["15169", "13335", "16509"] # ... up to 30,000
        chunk_size = 1000
        results = {}

        for i in range(0, len(all_asns), chunk_size):
            chunk = all_asns[i:i + chunk_size]
            batch_data = get_batch_asn_info(chunk)
            results.update(batch_data)

        print(json.dumps(results, indent=2))