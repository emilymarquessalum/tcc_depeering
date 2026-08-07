

import sys
from pathlib import Path
import matplotlib.pyplot as plt
from datetime import datetime
import re


sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.caidapeeringdb.loaders import load_all_files
from src.utils.graphs import plot_list_as_line_plot


from src.caidapeeringdb.caidapeeringdb_load import get_all_files, get_connections_for_ixp, get_data


ixp_one = ("129", "JINX")
ixp_two = ("344", "CINX")

all_files = load_all_files({
    "start_date": "20240101",
    "end_date": "20260401",
    "intervals_in_months": 3
})


# Track connections over time
common_connections_over_time = []
lost_asns_over_time = []
dates = []
previous_common_asns = None

for file in all_files:
    # Extract date from filename
    match = re.search(r"peeringdb_2_dump_(.*?)\.json", file)
    if match:
        date_str = match.group(1)
        dates.append(date_str)
    else:
        continue
    
    data = get_data(file)
    connections_ixp_one = get_connections_for_ixp(ixp_id=ixp_one[0], data=data)
    connections_ixp_two = get_connections_for_ixp(ixp_id=ixp_two[0], data=data)
    
    # Find common ASNs
    asns_ixp_one = {conn["asn"] for conn in connections_ixp_one}
    asns_ixp_two = {conn["asn"] for conn in connections_ixp_two}
    common_asns = asns_ixp_one & asns_ixp_two
    
    common_connections_over_time.append(len(common_asns))
    
    # Calculate ASes lost since previous period
    if previous_common_asns is not None:
        lost_asns = previous_common_asns - common_asns
        lost_asns_over_time.append(len(lost_asns))
    else:
        lost_asns_over_time.append(0)
    
    print(f"{date_str}: {len(common_asns)} ASes in both {ixp_one[1]} and {ixp_two[1]}", end="")
    if previous_common_asns is not None:
        print(f" | Lost: {lost_asns_over_time[-1]}")
    else:
        print()
    
    previous_common_asns = common_asns

# Create graphs
plot_list_as_line_plot(
    common_connections_over_time,
    y=dates,
    title=f"Common ASNs in {ixp_one[1]} and {ixp_two[1]} Over Time",
    xlabel="Date",
    ylabel="Number of Common ASNs",
)

plot_list_as_line_plot(
    lost_asns_over_time,
    y=dates,
    title=f"ASNs Lost from Both {ixp_one[1]} and {ixp_two[1]} Over Time",
    xlabel="Date",
    ylabel="Number of ASNs Lost",
    positive_color='red',
    negative_color='green',
)


