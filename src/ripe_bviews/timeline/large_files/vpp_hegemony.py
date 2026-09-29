

import sqlite3
import os
from typing import Tuple, Optional, Dict, Set, List
from collections import defaultdict
from pathlib import Path
import sys

from matplotlib import pyplot as plt
from datetime import datetime
from dateutil.relativedelta import relativedelta


# Preserving your setup
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))
from src.google.vpps.google_vpps_list import get_google_vpp_asns
from src.utils.graphs import DEFAULT_FIGSIZE, save_plot
from src.ripe_bviews.timeline.bview_hegemony import get_sorted_asns_from_scores 
from definitions import ROOT_DIR

# Import database parsing and core score computations from the base bview_sqlite_parser
from bview_sqlite_parser import (
    get_hegemony_scores,
    get_top_five_asns_over_time,
    get_interval_dates_for_asn_data,
)


def compare_vpp_and_non_vpp_hegemony_over_time(
    asn, alpha, rrc_used, ip_version, date_list, 
    use_strict_viewpoint_filtering: bool = False,
    use_best_next_days: int = 0,
    show_as_percentage: bool = False
):
    google_vpps_asns = get_google_vpp_asns(include_alternatives=True)
     
    hegemony_scores_dict, viewpoint_counts_dict, valid_date_list = get_hegemony_scores(
        asn, rrc_used, ip_version, date_list, alpha, use_strict_viewpoint_filtering,
        use_best_next_days=use_best_next_days
    )

    if not valid_date_list:
        print("[WARNING] No valid snapshots available to process.")
        return

    top_fives_over_time, unique_asns_list = get_top_five_asns_over_time(hegemony_scores_dict, valid_date_list)

    hegemony_over_time_vpp_or_not_vpp: list[tuple[float, float]] = []

    for date_idx, date in enumerate(valid_date_list):
        hegemony_vpp = 0.0
        hegemony_not_vpp = 0.0

        for i, asn_for_hegemony in enumerate(unique_asns_list):
            asn_score = top_fives_over_time[date_idx][i]
            if str(asn_for_hegemony) in google_vpps_asns:
                hegemony_vpp += asn_score
            else:
                hegemony_not_vpp += asn_score

        if show_as_percentage:
            tot = sum(hegemony_scores_dict[date].values())
            if tot > 0:
                hegemony_vpp = (hegemony_vpp / tot) * 100.0
                hegemony_not_vpp = (hegemony_not_vpp / tot) * 100.0
            else:
                hegemony_vpp, hegemony_not_vpp = 0.0, 0.0

        hegemony_over_time_vpp_or_not_vpp.append((hegemony_vpp, hegemony_not_vpp))

    plt.figure(figsize=DEFAULT_FIGSIZE)

    plt.plot(
        valid_date_list,
        [hegemony[0] for hegemony in hegemony_over_time_vpp_or_not_vpp],
        label="VPP Hegemony", 
    )

    plt.plot(
        valid_date_list,
        [hegemony[1] for hegemony in hegemony_over_time_vpp_or_not_vpp],
        label="Non-VPP Hegemony", 
    )

    y_label = "Hegemony Percentage (%)" if show_as_percentage else "Hegemony"
    plt.ylabel(y_label)
    plt.xlabel("Date")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(bbox_to_anchor=(1.02, 1), loc="upper left", title="Is-VPP")
    plt.show()
    save_plot(fig=plt.gcf(), title=f"hegemony_over_time_by_vpp_feature_{asn}_{rrc_used}_{ip_version}.png")


if __name__ == "__main__":
    asn = 15169
    start_date = None 
    
    configs = [ 
        {"rrc_used": rrc, "ip_version": "v6", "asn": 15169, "start_date": None, "use_best_next_days": 0} for rrc in [
            "rrc03", "rrc04", "rrc05", "rrc06", "rrc07", "rrc08", "rrc09", "rrc10",
            "rrc11", "rrc12", "rrc13", "rrc14", "rrc15", "rrc16", "rrc17", "rrc18",
            "rrc19", "rrc20", "rrc21", "rrc22",
        ]
    ]
    asn_input = input(f"Enter ASN to analyze (default {asn}): ")
    if asn_input:
        asn = int(asn_input)
        
    alpha = 0.34 
    use_strict_viewpoint_filtering = True
    show_as_percentage = True

    for config in configs:
        rrc_used = config["rrc_used"]
        ip_version = config["ip_version"]
        asn = config["asn"]
        start_date = config["start_date"]
        use_best_next_days = config["use_best_next_days"]

        print(f"\n[INFO] Running VPP Analysis for ASN {asn} on RRC {rrc_used} ({ip_version.upper()})...")

        try:
            dates = get_interval_dates_for_asn_data(asn, rrc_used, ip_version, month_interval=6, start_date=start_date)

            compare_vpp_and_non_vpp_hegemony_over_time(
                asn, alpha, rrc_used, ip_version, dates,
                use_strict_viewpoint_filtering=use_strict_viewpoint_filtering,
                use_best_next_days=use_best_next_days,
                show_as_percentage=show_as_percentage,
            )
        except Exception as e:
            print(f"[ERROR] An error occurred during VPP analysis for RRC {rrc_used}: {e}")
            continue