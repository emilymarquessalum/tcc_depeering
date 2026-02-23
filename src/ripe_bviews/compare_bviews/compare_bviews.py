
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
import warnings

warnings.filterwarnings('ignore', category=UserWarning, message='.*Skipping download.*')
from src.ripe_bviews.download_and_parse.load_configs import load_configs
from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data_timeline_from_configs
from src.ripe_bviews.oscillations.bview_oscillation_logic import OscillationMetrics, calculate_oscillation_metrics

# Static features (we are not very interested in those): ASes in common (memberXreachable)
# Timeline features: Which ASes that left the IXP1 also left IXP2 at that timeframe or in a different one
class RIBCompare:

    def __init__(self):
        
        self.ases_that_left_at_the_same_time = set()
        self.ases_that_left = set()
        self.ases_that_left_only_ixp1 = set()
        self.ases_that_left_only_ixp2 = set()

    def load_data(self, oscillation_metrics_1: OscillationMetrics, oscillation_metrics_2: OscillationMetrics):
        
        total_range = min(len(oscillation_metrics_1.all_removed_asns_over_time), len(oscillation_metrics_2.all_removed_asns_over_time))
        ases_that_left_ixp1 = set()
        ases_that_left_ixp2 = set()

        for i in range(total_range):
            ases_removed_1 = oscillation_metrics_1.all_removed_asns_over_time[i]
            ases_removed_2 = oscillation_metrics_2.all_removed_asns_over_time[i]

            ases_left_at_the_same_time = ases_removed_1.intersection(ases_removed_2)
            self.ases_that_left_at_the_same_time.update(ases_left_at_the_same_time)
            ases_that_left_ixp1.update(ases_removed_1) 
            ases_that_left_ixp2.update(ases_removed_2)
            self.ases_that_left_only_ixp1.update(ases_removed_1 - ases_removed_2)
            self.ases_that_left_only_ixp2.update(ases_removed_2 - ases_removed_1)
        
        self.ases_that_left = ases_that_left_ixp1.intersection(ases_that_left_ixp2)

    def print_comparison_results(self):
        print("Considering ASes that left both IXPs,")
        print(f"ASes that left at the same time: {len(self.ases_that_left_at_the_same_time)}")
        print(f"ASes that left in different times: {len(self.ases_that_left)}")
        print(f"ASes that left only IXP1: {len(self.ases_that_left_only_ixp1)}")
        print(f"ASes that left only IXP2: {len(self.ases_that_left_only_ixp2)}")

if __name__ == "__main__":

    configs_ix1 = load_configs("ixbr.json")
    configs_ix2 = load_configs("de-cix-amsterdam.json")

    all_stats_ix1 = load_bview_data_timeline_from_configs(configs_ix1)[0]
    all_stats_ix2 = load_bview_data_timeline_from_configs(configs_ix2)[0]

    members_in_common = set(all_stats_ix1[0].unique_members).intersection(set(all_stats_ix2[0].unique_members))
    print(f"ASes in common (memberXreachable) at the start: {len(members_in_common)}")
    reachables_in_common = set(all_stats_ix1[0].unique_reachables).intersection(set(all_stats_ix2[0].unique_reachables))
    print(f"ASes in common (reachableXreachable) at the start: {len(reachables_in_common)}")
    metrics_ix1 = calculate_oscillation_metrics(all_stats_ix1)
    metrics_ix2 = calculate_oscillation_metrics(all_stats_ix2)

    metrics_ix1.load_oscillating_lists()
    metrics_ix2.load_oscillating_lists()

    comparer = RIBCompare()
    comparer.load_data(metrics_ix1, metrics_ix2)
    comparer.print_comparison_results()