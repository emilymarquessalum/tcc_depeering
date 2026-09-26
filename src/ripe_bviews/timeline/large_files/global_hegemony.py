


from collections.abc import Set
from datetime import datetime

import os
import sqlite3
from typing import Dict, List, Tuple, Tuple
from typing import List

from matplotlib import pyplot as plt
from matplotlib.dates import relativedelta
from pyparsing import Dict, Optional
from definitions import ROOT_DIR

from src.ripe_bviews.timeline.large_files.bview_sqlite_parser import LargeBViewParser, calculate_as_hegemony_disk, get_active_viewpoints_for_date, get_all_dates_available_for_asn_data, get_top_five_asns_over_time

from src.ripe_bviews.timeline.large_files.bview_sqlite_parser import LargeBViewParser
from src.utils.graphs import DEFAULT_FIGSIZE, save_plot


def load_global_hegemony_for_date(
    asn: int, 
    alpha: float, 
    date: str, 
    ip_version: str, 
    rrc_list: List[str],
    allowed_viewpoints: Optional[Set[str]] = None
) -> Tuple[Dict[int, float], Set[str]]:
    """
    Parses and aggregates BGP data from ALL listed RRCs for a given date,
    then executes Hegemony math on the global dataset.
    """
    global_db_path = f"huge_bgp_cache_GLOBAL_{date}_{ip_version}_{asn}.db"
    
    # If the combined global DB doesn't exist, build it by importing tables from all RRCs
    if not os.path.exists(global_db_path):
        print(f"\n[GLOBAL] Initializing unified database for date {date} across {len(rrc_list)} RRCs...")
        
        # Initialize primary database schema
        parser = LargeBViewParser(db_path=global_db_path, ip_version=ip_version)
        parser.init_database()
        
        global_conn = sqlite3.connect(global_db_path)
        global_cursor = global_conn.cursor()
        
        for rrc in rrc_list:
            raw_path = f"{ROOT_DIR}/{rrc}/output_bview.{date}.0000.{ip_version}.origin_as.{asn}.txt"
            if not os.path.exists(raw_path):
                continue
                
            rrc_db_path = f"huge_bgp_cache_{rrc}_{date}_{ip_version}_{asn}.db"
            if not os.path.exists(rrc_db_path):
                rrc_parser = LargeBViewParser(db_path=rrc_db_path, ip_version=ip_version)
                rrc_parser.parse_to_disk(raw_path)
            
            # Attach individual RRC database and insert records into global DB
            global_cursor.execute("ATTACH DATABASE ? AS source_db;", (rrc_db_path,))
            global_cursor.execute("""
                INSERT INTO bgp_mappings 
                SELECT * FROM source_db.bgp_mappings;
            """)
            global_conn.commit()
            global_cursor.execute("DETACH DATABASE source_db;")
            
        global_conn.close()

    # Perform Hegemony calculation on the unified database
    return calculate_as_hegemony_disk(
        global_db_path, 
        target_asn=asn, 
        alpha=alpha, 
        ip_version=ip_version, 
        allowed_viewpoints=allowed_viewpoints
    )


def get_global_hegemony_scores(
    asn: int, 
    ip_version: str, 
    date_list: List[str], 
    alpha: float, 
    rrc_list: List[str],
    use_strict_viewpoint_filtering: bool = False, 
    use_free_viewpoint_filtering: bool = False
) -> Tuple[Dict[str, Dict[int, float]], Dict[str, int], List[str]]:
    """
    Computes global hegemony scores across all specified RRCs over time.
    """
    hegemony_scores_dict = {} 
    viewpoint_counts_dict = {}
    valid_date_list = list(date_list)
    allowed_viewpoints_baseline = None
    
    if use_strict_viewpoint_filtering:
        print(f"[GLOBAL VIEWPOINTS] Finding strict viewpoint intersection across all {len(valid_date_list)} dates...")
        date_to_vps = {}
        for d in valid_date_list:
            # Union of active viewpoints across all RRCs for date d
            d_vps = set()
            for rrc in rrc_list:
                raw_path = f"{ROOT_DIR}/{rrc}/output_bview.{d}.0000.{ip_version}.origin_as.{asn}.txt"
                if os.path.exists(raw_path):
                    d_vps.update(get_active_viewpoints_for_date(asn, rrc, d, ip_version))
            date_to_vps[d] = d_vps
            
        valid_date_list = [d for d in valid_date_list if len(date_to_vps[d]) > 3]
        if not valid_date_list:
            return {}, {}, []

        allowed_viewpoints_baseline = set.intersection(*[date_to_vps[d] for d in valid_date_list])

    for d in valid_date_list:
        scores, active_vps = load_global_hegemony_for_date(
            asn, alpha, d, ip_version, rrc_list,
            allowed_viewpoints=allowed_viewpoints_baseline
        )
        hegemony_scores_dict[d] = scores
        viewpoint_counts_dict[d] = len(active_vps)

    return hegemony_scores_dict, viewpoint_counts_dict, valid_date_list


def analyze_global_hegemony_over_time(
    asn: int,
    alpha: float,
    ip_version: str,
    rrc_list: List[str],
    start_date: Optional[str] = None,
    month_interval: int = 6,
    use_strict_viewpoint_filtering: bool = True,
    use_free_viewpoint_filtering: bool = False,
    show_as_percentage: bool = True
):
    """
    Discovers all available dates across ALL RRCs, aggregates the dataset for each date,
    and produces a global Hegemony analysis over time.
    """
    # 1. Gather union of all available dates across all specified RRCs
    all_available_dates = set()
    for rrc in rrc_list:
        dates = get_all_dates_available_for_asn_data(asn, rrc, ip_version, start_date=start_date)
        all_available_dates.update(dates)

    if not all_available_dates:
        print("[ERROR] No data available for the specified parameters.")
        return

    sorted_dates = sorted(list(all_available_dates))
    
    # Filter dates based on monthly intervals
    available_dts = [datetime.strptime(d, "%Y%m%d") for d in sorted_dates]
    interval_dates = [available_dts[0].strftime("%Y%m%d")]
    current_dt = available_dts[0]
    
    while True:
        ideal_target = current_dt + relativedelta(months=month_interval)
        future_dts = [d for d in available_dts if d > current_dt]
        if not future_dts:
            break
        closest_dt = min(future_dts, key=lambda d: abs((d - ideal_target).days))
        interval_dates.append(closest_dt.strftime("%Y%m%d"))
        current_dt = closest_dt
        if current_dt >= available_dts[-1]:
            break

    print(f"\n[GLOBAL HEGEMONY] Processing {len(interval_dates)} date snapshots across {len(rrc_list)} RRCs...")

    # 2. Compute Global Hegemony
    hegemony_scores_dict, viewpoint_counts_dict, valid_date_list = get_global_hegemony_scores(
        asn, ip_version, interval_dates, alpha, rrc_list,
        use_strict_viewpoint_filtering=use_strict_viewpoint_filtering,
        use_free_viewpoint_filtering=use_free_viewpoint_filtering
    )

    if not valid_date_list:
        print("[WARNING] No valid global snapshots available.")
        return

    # 3. Plot Top ASNs over time (Global)
    top_fives_over_time, unique_asns_list = get_top_five_asns_over_time(
        hegemony_scores_dict, valid_date_list
    )
    total_hegemony_per_date = [
        sum(hegemony_scores_dict[d].values()) for d in valid_date_list
    ]

    fig, ax1 = plt.subplots(figsize=DEFAULT_FIGSIZE)
    line_styles = ["-", "--", ":", "-."]
    markers = ["o", "s", "^", "v", "D", "X", "P"]

    for i, target_asn in enumerate(unique_asns_list):
        scores_for_asn = []
        for d_idx in range(len(valid_date_list)):
            val = top_fives_over_time[d_idx][i]
            if show_as_percentage:
                tot = total_hegemony_per_date[d_idx]
                val = (val / tot * 100.0) if tot > 0 else 0.0
            scores_for_asn.append(val)

        ax1.plot(
            valid_date_list,
            scores_for_asn,
            marker=markers[i % len(markers)],
            linestyle=line_styles[i % len(line_styles)],
            linewidth=2.5,
            label=f"ASN {target_asn}",
        )

    ax1.set_xlabel("Date", fontsize=12)
    ax1.set_ylabel("Hegemony (%)" if show_as_percentage else "Hegemony Score", fontsize=12)
    ax1.set_title(
        f"GLOBAL Hegemony Over Time (All RRCs Combined)\n(Target ASN: {asn}, IP: {ip_version.upper()}, α={alpha})",
        fontsize=14
    )
    ax1.tick_params(axis="x", rotation=45)
    ax1.grid(True, linestyle="--", alpha=0.5)
    ax1.legend(bbox_to_anchor=(1.05, 1), loc="upper left", title="Top Transits")

    plt.tight_layout()
    plt.show()
    save_plot(fig=fig, title=f"global_hegemony_over_time_{asn}_{ip_version}.png")


if __name__ == "__main__":
    asn = 15169
    alpha = 0.34
    ip_version = "v6"
    
    # All target RRC collectors[cite: 1]
    all_rrcs = [
        "rrc00", "rrc01", "rrc03", "rrc04", "rrc05", "rrc06", "rrc07", "rrc08", 
        "rrc09", "rrc10", "rrc11", "rrc12", "rrc13", "rrc14", "rrc15", "rrc16", 
        "rrc17", "rrc18", "rrc19", "rrc20", "rrc21", "rrc22"
    ]

    # Run Global Hegemony over all RRCs
    analyze_global_hegemony_over_time(
        asn=asn,
        alpha=alpha,
        ip_version=ip_version,
        rrc_list=all_rrcs,
        start_date=None,
        month_interval=6,
        use_strict_viewpoint_filtering=True,
        show_as_percentage=True
    )