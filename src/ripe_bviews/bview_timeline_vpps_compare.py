
from datetime import datetime, timedelta
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.graphs import plot_list_as_line_plot

from src.google.google_vpps_list import get_google_vpp_asns
from src.ripe_bviews.timeline.bview_timeline import load_bview_data

start_date = datetime(2025, 10, 20)
end_date = datetime(2026, 1, 1)#datetime.datetime(202

all_stats, labels = load_bview_data(start_date, end_date, ("26162", "187.16.216.253"), "rrc15", day_delta=timedelta(days=3))

vpp_ases = get_google_vpp_asns()

match_counts_over_time = []

vpps_not_always_present = set()
vpps_asns_present = set()
for stat in all_stats:
    unique_members = stat.unique_members
    match_count = sum(1 for asn in vpp_ases if str(asn) in unique_members)
    match_counts_over_time.append(match_count)
    vpps_asns_present.update(str(asn) for asn in vpp_ases if str(asn) in unique_members)
    for vpp_asn in vpps_asns_present:
        if vpp_asn not in unique_members:
            vpps_not_always_present.add(vpp_asn)

plot_list_as_line_plot(
    match_counts_over_time, 
    title="Google VPP ASNs Presence Over Time",
    xlabel="Time Intervals",
    ylabel="Number of Google VPP ASNs Present")
print(f"VPP ASNs present in the timeline: {vpps_asns_present}")
print(f"VPP ASNs not always present: {vpps_not_always_present}")