



import json
import os
from pathlib import Path
import sys



sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))  


from src.services.nicbr import get_asns_nicbr_has
from src.caidapeeringdb.caidapeeringdb_load import get_all_asns, get_most_recent_data
from src.ripe_bviews.timeline.as_info_type.bview_timeline_by_as_info_type import create_asn_to_astype_map


if __name__ == "__main__":

    
    asns = get_asns_nicbr_has() 

    with open("asns_br.json", "w") as f:
        print(f"Saving {len(asns)} ASNs to asns_br.json", asns)
        json.dump(
            asns.tolist() , f, indent=4)

    if not os.path.exists("asn_to_category_map.json"):

        caida_data = get_most_recent_data()


        unique_ases = get_all_asns(caida_data)
        as_to_category_map = create_asn_to_astype_map(unique_ases, caida_data, cnpj_mapping_dict=None)

        with open("asn_to_category_map.json", "w") as f:
            json.dump(as_to_category_map, f, indent=4)
        

