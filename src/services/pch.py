import json
import requests
import pandas as pd

# 1. Fetch live active IXP directory using the correct PCH API structure
print("Fetching live data from Packet Clearing House...")
url = "https://www.pch.net/api/ixp/directory"
params = {"status": "Active"}

response = requests.get(url, params=params)

if response.status_code != 200:
    print(f"Error fetching data: {response.status_code}")
    exit()

ixp_data = response.json()

# 2. Process data: handle nested dictionary and group by ISO country code
ix_list = ixp_data.get("results", ixp_data) if isinstance(ixp_data, dict) else ixp_data
country_metrics = {}

for ix in ix_list:
    country = ix.get("ctry")
    participants = int(ix.get("prts", 0) or 0)
    
    if not country:
        continue
        
    if country not in country_metrics:
        country_metrics[country] = {"ixp_count": 0, "total_participants": 0}
        
    country_metrics[country]["ixp_count"] += 1
    country_metrics[country]["total_participants"] += participants

# 3. Apply the IXP Maturity Model logic using ISO codes
global_stages_list = []
GLOBAL_HUBS = ["US", "GB", "DE", "NL", "SG", "JP"]  # ISO codes

for country, data in country_metrics.items():
    ixp_count = data["ixp_count"]
    total_parts = data["total_participants"]
    
    if country in GLOBAL_HUBS:
        stage = 5
        desc = "Global Continental Interconnection Hub"
    elif ixp_count > 1 and total_parts > 150:
        stage = 4
        desc = "Regional & Content-Rich Phase (Decentralized/CDNs Present)"
    elif ixp_count >= 1:
        stage = 3
        desc = "Single/Emerging National IXP Phase"
    else:
        stage = 2 
        desc = "Internal Transit Phase / Private ISP Interconnection Only"
        
    global_stages_list.append({
        "Country_ISO": country,
        "IXP_Count": ixp_count,
        "Total_Estimated_Participants": total_parts,
        "IXP_Maturity_Stage": stage,
        "Status_Description": desc
    })

# 4. Turn into a DataFrame, sort, and save
df = pd.DataFrame(global_stages_list)
df = df.sort_values(by=["IXP_Maturity_Stage", "IXP_Count"], ascending=[True, False])

output_file = "global_countries_ixp_stages.csv"
df.to_csv(output_file, index=False)

print(f"\nSuccess! Categorized {len(df)} countries from live PCH data.")
print(f"File saved to your directory as: '{output_file}'")