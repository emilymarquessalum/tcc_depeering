

import sys
from pathlib import Path


  
sys.path.append(str(Path(__file__).resolve().parents[2])) 
from src.ripe_bviews.read_bviews import RIBMonitorSnapshotStats, read_bview
 
from src.ripe_bviews.read_bgpdump import read_bgpdump


if __name__ == "__main__":
    
    bgp_scanner_file = "stats_data/rrc15/bview.20260122.0000.txt_26162_187.16.216.253.json"
    bgp_dump_file = "data/rrc15/bview.20260122.0000.26162.txt"
    
    as_prefix = ("26162", "187.16.216.253")


    scanner_stats = RIBMonitorSnapshotStats(as_prefix[0], as_prefix[1], date="20260122", time="0000")
    scanner_stats.load_details(bgp_scanner_file)
    dump_stats = read_bgpdump(bgp_dump_file, as_prefix[0], as_prefix[1], date="20260122", time="0000", ip_version="v4", rrc="rrc15")

    print("Comparing scanner with dump")
    #scanner_stats.print_summary()
    #dump_stats.print_summary() 
    lines_missing_from_scanner = dump_stats.lines - scanner_stats.lines
    print(f"Lines missing from scanner: {(lines_missing_from_scanner)}")
 

    members_missing_from_scanner = dump_stats.unique_members.difference(scanner_stats.unique_members)
    print(f"Members missing from scanner: {len(members_missing_from_scanner)} out of {len(dump_stats.unique_members)}")


    print("First 5 members missing from scanner:", list(members_missing_from_scanner)[:5])
    reachables_missing_from_scanner = dump_stats.unique_reachables.difference(scanner_stats.unique_reachables)
    print(f"Reachables missing from scanner: {len(reachables_missing_from_scanner)} out of {len(dump_stats.unique_reachables)}")

