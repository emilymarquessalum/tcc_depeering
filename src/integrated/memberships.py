


from pathlib import Path
import sys
 
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
                
from src.caidapeeringdb.loaders import load_all_data, load_all_files


from src.caidapeeringdb.caidapeeringdb_load import get_all_data
from src.caidapeeringdb.ixp_overtime import plot_ixps_connections_over_time
from src.ripe_bviews.download_and_parse.load_configs import load_configs


configs_ixp = load_configs("ixbr.json")
print(configs_ixp)
 

configs_ixp["intervals_in_months"] = 0
configs_ixp["intervals_in_days"] = configs_ixp["day_delta"]

peeringdb_data, dates = load_all_data(configs_ixp)

plot_ixps_connections_over_time(
                all_data=peeringdb_data,
                dates=dates,
                ixp_ids=[
                    configs_ixp["peeringdb_ixp_id"]
                ], 
                ixp_names=[
                    configs_ixp["name"]
                ],
                title_info=f"IXP " + configs_ixp["name"] + " - ", 
)
