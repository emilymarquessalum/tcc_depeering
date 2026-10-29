
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
import re
from matplotlib import pyplot as plt

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from services.asrank import fetch_all_asrank, find_closest_similar_ases_fast, get_asn_info
from src.caidapeeringdb.caidapeeringdb_load import get_all_data, get_all_files, get_data
from src.caidapeeringdb.vpps.main import build_vpp_asn_map



def load_similar_ases():
    all_files = get_all_files()
    latest_file = all_files[-1]  
    
    latest_snapshot = get_data(all_files[-1]) 
    print(f"Latest PeeringDB snapshot: {latest_file} with {len(latest_snapshot.get('netixlan', {}).get('data', []))} netixlan entries.")
    vpp_asn_map = build_vpp_asn_map(latest_snapshot)
    vpp_asns = vpp_asn_map.keys()
 
    all_asns = fetch_all_asrank(limit=10000) 
    asn_to_idx = {item['asn']: idx for idx, item in enumerate(all_asns)}
    similar_ases = find_closest_similar_ases_fast(vpp_asns, all_asns=all_asns, asn_to_idx=asn_to_idx)

    with open("vpp_asn_similar_asrank.json", "w") as f:
        json.dump(similar_ases, f, indent=4)


if __name__ == "__main__":

    load_similar_ases()

    