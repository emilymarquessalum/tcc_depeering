

import datetime
from pathlib import Path
import sys

from src.ripe_bviews.routeserver.routeserver import asn_participations, depeering_analysis, load_routeserver_data_from_range 


sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent)) 
from src.ripe_bviews.download_and_parse.load_configs import load_configs
from src.services.looking_glass import load_ases_from_looking_glass

current_date = datetime.datetime.now()
asn_and_prefix = ("26162", "187.16.216.253") 

config = load_configs("ixbr.json")
#as_data_rib = load_bview_data(current_date, current_date + datetime.timedelta(days=1), asn_and_prefix, "rrc15")[0][0].unique_members
as_data_looking_glass_right_now = load_ases_from_looking_glass(
    looking_glass_path=config["lookingglass"],
    load_all_info=True)

#print(f"AS data from RIB: {len(as_data_rib)} ASes")
print(f"AS data from Looking Glass: {len(as_data_looking_glass_right_now)} ASes")


def bview_looking_glass(all_required_data):

    config = all_required_data['config']

    lookingglass = config["lookingglass"]

    if not lookingglass:
        print("Looking glass not available")
        return

    start_time = datetime.datetime.strptime(config["start_date"], "%Y-%m-%d")
    end_time = datetime.datetime.strptime(config["end_date"], "%Y-%m-%d")

    asn_to_routes_map = load_routeserver_data_from_range(start_time, end_time)
    
    asn_participations(asn_to_routes_map, start_time, end_time)
    depeering_analysis(asn_to_routes_map)