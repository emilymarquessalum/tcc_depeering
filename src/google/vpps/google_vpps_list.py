


import json
import sys
from time import sleep
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent

from src.services.peeringdb import get_asns_by_name


# dont use it, we dont need it.
def create_list_of_vpp_asns_from_names():
    vpps_silver = []
    vpps_gold = []

    vpps_data = json.loads(open(SCRIPT_DIR / "google_vpps.json", "r").read())

    vpps_silver = vpps_data.get("silver", [])
    vpps_gold = vpps_data.get("gold", [])

    vpps_asn_map = {}

    for provider in vpps_silver + vpps_gold:
        isp_name = provider.get("isp_name", "")
        isp_name_first_line = isp_name.split("\n")[0]
        isp_name_first_line_parenthesis_section = isp_name_first_line.split("(")[1] + isp_name_first_line.split(")")[0] if "(" in isp_name_first_line and ")" in isp_name_first_line else None
        if isp_name_first_line_parenthesis_section:
            split = isp_name_first_line.split(isp_name_first_line_parenthesis_section)
            isp_name_first_line = split[0] + (split[1] if len(split) > 1 else "")
        
        isp_name_first_line = isp_name_first_line.strip()

        #sleep(3)
        data = get_asns_by_name(isp_name_first_line)
        if data and len(data) > 0:
            best_name_match = None
            for entry in data:
                entry_name = entry.get("name", "").lower()
                if isp_name_first_line.lower() in entry_name or entry_name in isp_name_first_line.lower():
                    best_name_match = entry
                    break
            if best_name_match:
                data = [best_name_match]
            asn = data[0].get("asn")
            vpps_asn_map[asn] = provider

    with open(SCRIPT_DIR / "google_vpps_list.json", "w") as f:
        json.dump(vpps_asn_map, f, indent=4)

    quantity_of_success = len(vpps_asn_map)
    total_quantity = len(vpps_silver) + len(vpps_gold)  
    print(f"Successfully mapped {quantity_of_success} out of {total_quantity} VPPS to ASNs.")

def get_google_vpp_asns():
    with open(SCRIPT_DIR / "google_vpps_list.json", "r") as f:
        vpps_asn_map = json.load(f)
    return list(vpps_asn_map.keys())


if __name__ == "__main__":
    create_list_of_vpp_asns_from_names()