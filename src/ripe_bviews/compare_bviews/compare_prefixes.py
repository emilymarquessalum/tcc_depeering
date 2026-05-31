


import sys
from pathlib import Path



sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
import warnings

warnings.filterwarnings('ignore', category=UserWarning, message='.*Skipping download.*')

from src.ripe_bviews.compare_bviews.compare_bviews import get_stats_from_compared_ixps
from src.ripe_bviews.read_bgpdump import BGPDumpSnapshotStats


def get_prefixes_in_common(stats_ixp1: BGPDumpSnapshotStats, stats_ixp2: BGPDumpSnapshotStats):
    prefixes_in_common = set([p  for p in stats_ixp1.get_unique_prefix_mappings()]).intersection(set([p for p in stats_ixp2.get_unique_prefix_mappings()]))
    return prefixes_in_common 


if __name__ == "__main__":
    
    all_stats_ix1, all_stats_ix2, configs_ix1, configs_ix2, subfolder, labels_ix1 = get_stats_from_compared_ixps()
    
    prefixes_in_common = get_prefixes_in_common(all_stats_ix1[0], all_stats_ix2[0])

    print(f"Total unique prefixes in IXP1 (that members own): {len(all_stats_ix1[0].get_unique_prefix_mappings())}")
    print(f"Total unique prefixes in IXP2 (that members own): {len(all_stats_ix2[0].get_unique_prefix_mappings())}")
    print(f"Prefixes in common (that members own): {len(prefixes_in_common)}")
