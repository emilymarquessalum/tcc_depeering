

import datetime
from pathlib import Path
import sys 


sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.ripe_bviews.timeline.bview_timeline import load_bview_data
from src.services.looking_glass import load_ases_from_looking_glass

current_date = datetime.datetime.now()
asn_and_prefix = ("26162", "187.16.216.253") 

as_data_rib = load_bview_data(current_date, current_date + datetime.timedelta(days=1), asn_and_prefix, "rrc15")[0][0].unique_members
as_data_looking_glass_right_now = load_ases_from_looking_glass(load_all_info=True)

print(f"AS data from RIB: {len(as_data_rib)} ASes")
print(f"AS data from Looking Glass: {len(as_data_looking_glass_right_now)} ASes")
