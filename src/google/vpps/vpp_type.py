


import json
from pathlib import Path

import sys
from pathlib import Path




sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.caidapeeringdb.caidapeeringdb_load import get_all_files, get_asinfo_from_asn, get_asns_of_info_type, get_asns_types_peeringdb, get_data



all_files = get_all_files()

print(all_files[-1])
data = get_data(all_files[-1])
 
with open(Path(__file__).parent / "google_vpps_list.json", "r") as f:
        vpps_asn_map = json.load(f)


vpp_asns = list(vpps_asn_map.keys())


asn_types_for_vpps = get_asns_types_peeringdb(data, vpp_asns)

types = set(asn_types_for_vpps.values())

type_count = {t: 0 for t in types}

for asn, asn_type in asn_types_for_vpps.items():
    if asn_type in type_count:
        type_count[asn_type] += 1

print(type_count)
# last time I ran it: {'': 7, 'NSP': 36, 'Content': 4, 'Cable/DSL/ISP': 37, 'Route Server': 4, 'Network Services': 3}
