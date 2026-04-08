
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
import warnings

warnings.filterwarnings('ignore', category=UserWarning, message='.*Skipping download.*')
from src.ripe_bviews.download_and_parse.load_configs import load_configs, print_config
from src.ripe_bviews.timeline.bview_timeline import get_ases_that_did_not_come_back

from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data_timeline_from_configs
from src.ripe_bviews.oscillations.bview_oscillation_logic import OscillationMetrics, calculate_oscillation_metrics

from src.ripe_bviews.timeline.bview_vars import get_subfolder
from src.utils.graphs import plot_list_as_line_plot
# Static features (we are not very interested in those): ASes in common (memberXreachable)
# Timeline features: Which ASes that left the IXP1 also left IXP2 at that timeframe or in a different one
class RIBCompare:

    def __init__(self):
        
        self.ases_that_left_at_the_same_time = set()
        self.ases_that_left = set()
        self.ases_that_left_only_ixp1 = set()
        self.ases_that_left_only_ixp2 = set()

        self.ases_that_entered_at_the_same_time = set()
        self.ases_that_entered = set() # ASes that entered both IXPs but not at the same time
        self.ases_that_entered_only_ixp1 = set()
        self.ases_that_entered_only_ixp2 = set()

    def load_data(self, oscillation_metrics_1: OscillationMetrics, oscillation_metrics_2: OscillationMetrics):
        
        total_range_added = min(len(oscillation_metrics_1.all_added_asns_over_time), len(oscillation_metrics_2.all_added_asns_over_time))
        ases_that_entered_ixp1 = set()
        ases_that_entered_ixp2 = set()

        total_range_removed = min(len(oscillation_metrics_1.all_removed_asns_over_time), len(oscillation_metrics_2.all_removed_asns_over_time))
        ases_that_left_ixp1 = set()
        ases_that_left_ixp2 = set()

        for i in range(total_range_added):
            ases_added_1 = oscillation_metrics_1.all_added_asns_over_time[i]
            ases_added_2 = oscillation_metrics_2.all_added_asns_over_time[i] 
            ases_entered_at_the_same_time = ases_added_1.intersection(ases_added_2)
            self.ases_that_entered_at_the_same_time.update(ases_entered_at_the_same_time)
            ases_that_entered_ixp1.update(ases_added_1) 
            ases_that_entered_ixp2.update(ases_added_2)
            self.ases_that_entered_only_ixp1.update(ases_added_1 - ases_added_2)
            self.ases_that_entered_only_ixp2.update(ases_added_2 - ases_added_1)
        
        self.ases_that_entered = ases_that_entered_ixp1.intersection(ases_that_entered_ixp2)

        for i in range(total_range_removed):
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
        
        print("---")
        
        print(f"ASes that entered at the same time: {len(self.ases_that_entered_at_the_same_time)}")
        print(f"ASes that entered in different times: {len(self.ases_that_entered)}")
        print(f"ASes that entered only IXP1: {len(self.ases_that_entered_only_ixp1)}")
        print(f"ASes that entered only IXP2: {len(self.ases_that_entered_only_ixp2)}")

        print("---")
        
        print(f"ASes that left at the same time: {len(self.ases_that_left_at_the_same_time)}")
        print(f"ASes that left in different times: {len(self.ases_that_left)}")
        print(f"ASes that left only IXP1: {len(self.ases_that_left_only_ixp1)}")
        print(f"ASes that left only IXP2: {len(self.ases_that_left_only_ixp2)}")


if __name__ == "__main__":

    configs_ix1 = load_configs("ixbr.json")
    configs_ix2 = load_configs("de-cix-amsterdam.json")

    subfolder = get_subfolder(configs_ix1, ip_version="v4") + "_vs_" + configs_ix2.get("name", "Unknown") 

    ignored_dates = ["20251205.0000"]
    all_stats_ix1, labels_ix1 = load_bview_data_timeline_from_configs(configs_ix1, ignored_dates=ignored_dates)
    all_stats_ix2, labels_ix2 = load_bview_data_timeline_from_configs(configs_ix2, ignored_dates=ignored_dates)

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

    members_in_common_over_time = []
    reachables_in_common_over_time = []
    for stat_ix1, stat_ix2 in zip(all_stats_ix1, all_stats_ix2):
        members_in_common_over_time.append(len(set(stat_ix1.unique_members).intersection(set(stat_ix2.unique_members))))
        reachables_in_common_over_time.append(len(set(stat_ix1.unique_reachables).intersection(set(stat_ix2.unique_reachables))))
    plot_list_as_line_plot(members_in_common_over_time, y=labels_ix1, title="Members in Common Over Time", subfolder=subfolder)
    plot_list_as_line_plot(reachables_in_common_over_time, y=labels_ix1, title="Reachables in Common Over Time", subfolder=subfolder)

    
    retroactive = max(int(0.1 * len(all_stats_ix1)), 1)
    
    
    print(f"ASes that were present in the first {retroactive} snapshots (from total of {len(all_stats_ix1)}, ({(retroactive/len(all_stats_ix1))*100:.2f}%).")
    ases_removed_that_did_not_come_back_ixp1 = get_ases_that_did_not_come_back([stat.unique_members for stat in all_stats_ix1],
                                                                          retrospective=retroactive)
    
    print_config(configs_ix1, ip_version="v4")
    
    print(f"ASes that existed in the first {retroactive} snapshots, but were removed and did not come back: {len(ases_removed_that_did_not_come_back_ixp1)}")

    ases_removed_that_did_not_come_back_ixp2 = get_ases_that_did_not_come_back([stat.unique_members for stat in all_stats_ix2],
                                                                          retrospective=retroactive)
    print_config(configs_ix2, ip_version="v4")
    
    print(f"ASes that existed in the first {retroactive} snapshots, but were removed and did not come back: {len(ases_removed_that_did_not_come_back_ixp2)}")

    ases_removed_from_both = ases_removed_that_did_not_come_back_ixp1.intersection(ases_removed_that_did_not_come_back_ixp2)
    print(f"ASes that existed in the first {retroactive} snapshots, but were removed and did not come back in both IXPs: {len(ases_removed_from_both)}")

    