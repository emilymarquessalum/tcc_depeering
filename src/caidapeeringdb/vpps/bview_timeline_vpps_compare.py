
from datetime import datetime, timedelta
import sys
from pathlib import Path

from src.ripe_bviews.bview_labels import get_date_range_title
from src.ripe_bviews.read_bgpdump import BGPDumpSnapshotStats


sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data
from src.utils.graphs import plot_list_as_line_plot

from src.google.vpps.google_vpps_list import get_google_vpp_asns 

start_date = datetime(2025, 10, 20)
end_date = datetime(2026, 1, 1)#datetime.datetime(202


def bview_check_for_vpps(all_required_data):

    all_stats, _, _ = all_required_data["timeline"]
    config = all_required_data["config"]
    all_stats : list[BGPDumpSnapshotStats] = all_stats
    vpp_ases = get_google_vpp_asns()

    match_counts_over_time = []

    print(f"Considering {len(vpp_ases)} Google VPP ASNs...")
    print(f"For {config['name']} from {config['start_date']} to {config['end_date']}")


    vpps_not_always_present = set()
    vpps_asns_present = set()
    for stat in all_stats:
        unique_members = stat.unique_members
        match_count = sum(1 for asn in vpp_ases if int(asn) in unique_members)
        match_counts_over_time.append(match_count)
        vpps_asns_present.update(int(asn) for asn in vpp_ases if int(asn) in unique_members)
        for vpp_asn in vpps_asns_present:
            if vpp_asn not in unique_members:
                vpps_not_always_present.add(vpp_asn) 

    print(f"VPP ASNs present in the timeline: {len(vpps_asns_present)} {vpps_asns_present if len(vpps_asns_present) > 0 else ''}")
    print(f"VPP ASNs not always present: {len(vpps_not_always_present)} {vpps_not_always_present if len(vpps_not_always_present) > 0 else ''}")

    plot_list_as_line_plot(
        match_counts_over_time,  
        title=f"Google VPP ASNs Presence Over Time in {config['name']} - {get_date_range_title(config['start_date'], config['end_date'])}",
        xlabel="Time Intervals",
        ylabel="Number of Google VPP ASNs Present")