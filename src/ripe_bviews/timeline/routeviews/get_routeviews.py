

# made this to facilitate getting data for the routeviews, but 
# it doesnt provide us with the ASN and prefix to analyze the BGP dumps.

import json
import os
import re
import requests
from bs4 import BeautifulSoup

ROUTEVIEWS_LIST_URL = "https://archive.routeviews.org"
PATH_TO_CONFIG_FOLDER = "/home/emily/Desktop/projects/furg/tcc_depeering/src/ripe_bviews/configs/routeviews_specific"

# Ensure the output directory exists
os.makedirs(PATH_TO_CONFIG_FOLDER, exist_ok=True)

def generate_routeviews_configs():
    try:
        # 1. Fetch the page instantly without a browser
        response = requests.get(ROUTEVIEWS_LIST_URL, timeout=10)
        response.raise_for_status()
        
        # 2. Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        li_elements = soup.find_all('li')
    except Exception as e:
        print(f"Error fetching Route Views list: {e}")
        return

    # Combined Regex: Group 1 = IXP Name (optional), Group 2 = Route Server Domain
    # This matches: "... from IXP_NAME (FRR bgpd, from DOMAIN)" OR "... (FRR bgpd, from DOMAIN)"
    pattern = re.compile(r'(?:from\s+(.*?)\s+)?\(FRR\s+bgpd,\s+from\s+([^)]+)\)')

    start_date = "2025-12-01"
    end_date = "2026-01-30"

    for li in li_elements:
        text = li.get_text(strip=True)
        match = pattern.search(text)
        
        if match:
            # Extract both groups safely from the same line
            ixp_raw = match.group(1)
            route_server = match.group(2)
            
            # Fallback if there is no specific IXP name in the text (e.g., route-views5)
            # It replaces spaces with underscores for safe filenames
            ixp_name = ixp_raw.replace(" ", "_") if ixp_raw else route_server.split('.')[0]
            
            # Construct the config
            config = {
                "routeserver-folder-name": route_server.replace(".routeviews.org", ""),
                "name": ixp_name,
                "start_date": start_date,
                "end_date": end_date,
                "day_delta": 15,
            }   
            
            # Save individual JSON file
            save_path = os.path.join(PATH_TO_CONFIG_FOLDER, f"{ixp_name}.json")
            with open(save_path, "w") as f:
                json.dump(config, f, indent=4)
                
    print("Configuration files successfully generated!")

if __name__ == "__main__":
    generate_routeviews_configs()