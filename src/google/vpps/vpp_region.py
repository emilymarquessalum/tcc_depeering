


import json

import sys
from pathlib import Path




sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.utils.graphs import plot_map_as_bar_plot
from src.utils.regions_and_locations import REGION_TO_COLOR_MAP

 


vpps_data = json.load(open(Path(__file__).parent / "google_vpps.json", "r"))

gold_vpps = (vpps_data["gold"])
silver_vpps = (vpps_data["silver"])

all_vpps = gold_vpps + silver_vpps

def plot_vpp_count_by_region(vpp_list, title_suffix=""):
    vpp_count_by_region = {}

    for vpp in vpp_list:
        regions = vpp.get("sales_region", []).split(",")
        for region in regions:
            region = region.strip().replace("-", " ")  
            if region not in vpp_count_by_region:
                vpp_count_by_region[region] = 0
            vpp_count_by_region[region] += 1

    print(vpp_count_by_region)


    plot_map_as_bar_plot(vpp_count_by_region, title=f"Number of Google VPPs by Region (non-exclusively), {title_suffix}", 
                        sort_by_size=True,
                        xlabel="Region", ylabel="Number of VPPs", 
                        colors=REGION_TO_COLOR_MAP)
    

if __name__ == "__main__":
    plot_vpp_count_by_region(gold_vpps, title_suffix="(Gold)")
    plot_vpp_count_by_region(silver_vpps, title_suffix="(Silver)")
    plot_vpp_count_by_region(all_vpps, title_suffix="(Gold + Silver)")