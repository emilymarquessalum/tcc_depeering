from collections import defaultdict
from datetime import datetime
from dateutil.relativedelta import relativedelta
import math
import os
from pathlib import Path
import sqlite3
import sys
from typing import Dict, List, Optional, Set, Tuple, Union

from matplotlib import pyplot as plt
from matplotlib.patches import Patch
import numpy as np

# Preserving repository structure / imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from definitions import ROOT_DIR
from src.ripe_bviews.timeline.bview_load import get_all_rrcs
from src.google.vpps.google_vpps_list import get_google_vpp_asns
from src.ripe_bviews.timeline.large_files.bview_sqlite_parser import (
    LargeBViewParser,
    calculate_as_hegemony_disk,
    get_all_dates_available_for_asn_data,
    get_interval_dates_for_asn_data,
    _resolve_rrc_dir,
)
from src.ripe_bviews.timeline.large_files.global_hegemony import _parse_ip_versions
from src.utils.graphs import DEFAULT_FIGSIZE, save_plot, format_labels_if_they_are_dates


def _get_clean_vpp_set() -> Set[str]:
    """Retrieves and normalizes Google VPP ASNs into pure numeric string format."""
    raw_vpps = get_google_vpp_asns(include_alternatives=True)
    return {str(asn).upper().replace("AS", "").strip() for asn in raw_vpps}


def extract_path_lengths_and_hegemony(
    db_path: str,
    target_asn: int,
    alpha: float = 0.34,
    ip_version: str = "v4",
    considers_duplicated_paths: bool = False,
    only_penultimate_as: bool = False,
) -> Tuple[Dict[str, List[int]], Dict[int, float]]:
    """
    Computes AS hegemony scores and collects all BGP AS path lengths mapped per transit ASN,
    with AS path prepending stripped out.
    """
    hegemony_scores, _ = calculate_as_hegemony_disk(
        db_path=db_path,
        target_asn=target_asn,
        alpha=alpha,
        ip_version=ip_version,
    )

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    select_clause = "SELECT as_path FROM bgp_mappings" if considers_duplicated_paths else "SELECT DISTINCT as_path FROM bgp_mappings"
    
    if target_asn is not None:
        query = f"{select_clause} WHERE reachable_as = ?"
        cursor.execute(query, (target_asn,))
    else:
        query = select_clause
        cursor.execute(query)

    transit_path_lengths = defaultdict(list)
    seen_paths: Set[str] = set()

    while True:
        rows = cursor.fetchmany(50_000)
        if not rows:
            break

        for (path_str,) in rows:
            if not path_str:
                continue

            if not considers_duplicated_paths:
                if path_str in seen_paths:
                    continue
                seen_paths.add(path_str)

            try:
                raw_as_path = [int(x) for x in path_str.split(",") if x]
            except ValueError:
                continue

            if not raw_as_path:
                continue

            # Strip AS path prepending by collapsing consecutive duplicate ASNs
            dedup_as_path = []
            for asn in raw_as_path:
                if not dedup_as_path or dedup_as_path[-1] != asn:
                    dedup_as_path.append(asn)

            path_len = len(dedup_as_path)

            unique_transits = set(dedup_as_path)
            if target_asn is not None and target_asn in unique_transits:
                unique_transits.remove(target_asn)

            if only_penultimate_as and target_asn is not None:
                new_unique_transits = set()
                for idx, asn in enumerate(dedup_as_path):
                    if asn == target_asn and idx > 0:
                        penultimate_as = dedup_as_path[idx - 1]
                        if penultimate_as != target_asn:
                            new_unique_transits.add(penultimate_as)
                unique_transits = new_unique_transits

            for transit_node in unique_transits:
                transit_path_lengths[str(transit_node)].append(path_len)

    conn.close()
    return transit_path_lengths, hegemony_scores


def get_db_for_date(
    asn: int,
    rrc_used: Union[str, List[str]],
    date: str,
    ip_version: str,
    considers_duplicated_paths: bool = False,
) -> str:
    """Ensures SQLite staging DB exists for the given ASN, Date, and IP Version."""
    is_global = isinstance(rrc_used, list) or (isinstance(rrc_used, str) and rrc_used.lower() == "global")
    
    if is_global:
        rrc_list = rrc_used if isinstance(rrc_used, list) else ["rrc03"]
        global_db_path = f"huge_bgp_cache_GLOBAL_{date}_{ip_version}_{asn}.db"
        
        if os.path.exists(global_db_path):
            return global_db_path

        print(f"[GLOBAL] Building unified path database for date {date} across {len(rrc_list)} RRCs...")
        parser = LargeBViewParser(db_path=global_db_path, ip_version=ip_version)
        parser.init_database()

        global_conn = sqlite3.connect(global_db_path)
        global_cursor = global_conn.cursor()

        for rrc in rrc_list:
            rrc_dir = _resolve_rrc_dir(rrc)
            raw_path = os.path.join(rrc_dir, f"output_bview.{date}.0000.{ip_version}.origin_as.{asn}.txt")
            if not os.path.exists(raw_path):
                raw_path = os.path.join(rrc_dir, f"output_bview.{date}.0000.origin_as.{asn}.txt")
                if not os.path.exists(raw_path):
                    continue

            rrc_db_path = f"huge_bgp_cache_{rrc}_{date}_{ip_version}_{asn}.db"
            if not os.path.exists(rrc_db_path):
                rrc_parser = LargeBViewParser(db_path=rrc_db_path, ip_version=ip_version)
                rrc_parser.parse_to_disk(raw_path)

            global_cursor.execute("ATTACH DATABASE ? AS source_db;", (rrc_db_path,))
            
            if considers_duplicated_paths:
                global_cursor.execute("INSERT INTO bgp_mappings SELECT * FROM source_db.bgp_mappings;")
            else:
                global_cursor.execute(
                    "INSERT OR IGNORE INTO bgp_mappings SELECT * FROM source_db.bgp_mappings;"
                )
                
            global_conn.commit()
            global_cursor.execute("DETACH DATABASE source_db;")

        global_conn.close()
        return global_db_path

    else:
        db_path = f"huge_bgp_cache_{rrc_used}_{date}_{ip_version}_{asn}.db"
        if os.path.exists(db_path):
            return db_path

        rrc_dir = _resolve_rrc_dir(rrc_used)
        path = os.path.join(rrc_dir, f"output_bview.{date}.0000.{ip_version}.origin_as.{asn}.txt")
        if not os.path.exists(path):
            path = os.path.join(rrc_dir, f"output_bview.{date}.0000.origin_as.{asn}.txt")

        if not os.path.exists(path):
            raise FileNotFoundError(f"Source bview file not found: {path}")

        parser = LargeBViewParser(db_path=db_path, ip_version=ip_version)
        parser.parse_to_disk(path)
        return db_path


def analyze_path_length_hegemony(
    asn: int,
    alpha: float = 0.34,
    rrc_list: Optional[List[str]] = None,
    rrc_used: Optional[str] = "rrc03",
    ip_version: Union[str, List[str]] = "v4",
    start_date: Optional[str] = None,
    month_interval: int = 6,
    top_x: Optional[Union[int, float]] = 5,
    is_percentage_top_x: bool = False,
    text_scale: float = 1.0,
    considers_duplicated_paths: bool = False,
    only_penultimate_as: bool = False,
    showfliers: bool = False,
):
    """
    Executes Path Length Boxplot Analysis over time:
      1. Overall Path Length Boxplots
      2. VPP vs. Non-VPP Side-by-Side Boxplots
      3. Top X Hegemony Path Length Boxplots
    """
    clean_vpp_set = _get_clean_vpp_set()
    ip_versions = _parse_ip_versions(ip_version)

    is_global = bool(rrc_list)
    active_rrc_target = rrc_list if is_global else rrc_used
    rrc_tag = "GLOBAL" if is_global else str(rrc_used).upper()

    plt.rcParams.update({
        "font.size": 10 * text_scale,
        "axes.titlesize": 14 * text_scale,
        "axes.labelsize": 12 * text_scale,
        "xtick.labelsize": 10 * text_scale,
        "ytick.labelsize": 10 * text_scale,
        "legend.fontsize": 10 * text_scale,
        "figure.titlesize": 16 * text_scale,
    })

    processed_data = {}

    for ip_ver in ip_versions:
        if is_global:
            all_available_dates = set()
            for rrc in rrc_list:
                d_avail = get_all_dates_available_for_asn_data(asn, rrc, ip_ver, start_date=start_date)
                all_available_dates.update(d_avail)

            if not all_available_dates:
                print(f"[WARNING] No dates available across RRCs for ASN {asn} ({ip_ver.upper()}).")
                continue

            sorted_dates = sorted(list(all_available_dates))
            available_dts = [datetime.strptime(d, "%Y%m%d") for d in sorted_dates]
            interval_dates = [available_dts[0].strftime("%Y%m%d")]
            current_dt = available_dts[0]

            while True:
                future_dts = [d for d in available_dts if d > current_dt]
                if not future_dts:
                    break
                ideal_target = current_dt + relativedelta(months=month_interval)
                closest_dt = min(future_dts, key=lambda d: abs((d - ideal_target).days))
                
                if closest_dt <= current_dt:
                    break

                interval_dates.append(closest_dt.strftime("%Y%m%d"))
                current_dt = closest_dt
                if current_dt >= available_dts[-1]:
                    break
            dates = interval_dates
        else:
            dates = get_interval_dates_for_asn_data(
                asn, rrc_used, ip_ver, month_interval=month_interval, start_date=start_date
            )

        if not dates:
            print(f"[WARNING] No dates available for ASN {asn}, RRC {rrc_tag}, IP {ip_ver.upper()}.")
            continue

        valid_dates = []
        overall_distributions = []
        vpp_distributions = []
        non_vpp_distributions = []
        topx_distributions = []

        for d in dates:
            try:
                db_path = get_db_for_date(
                    asn, active_rrc_target, d, ip_ver, considers_duplicated_paths=considers_duplicated_paths
                )
                transit_path_lengths, hegemony_scores = extract_path_lengths_and_hegemony(
                    db_path=db_path,
                    target_asn=asn,
                    alpha=alpha,
                    ip_version=ip_ver,
                    considers_duplicated_paths=considers_duplicated_paths,
                    only_penultimate_as=only_penultimate_as,
                )
            except Exception as e:
                print(f"[ERROR] Could not process date {d} for {ip_ver.upper()}: {e}")
                continue

            if not transit_path_lengths:
                continue

            valid_dates.append(d)

            # Collect full path length arrays per group
            all_lengths = [l for lens in transit_path_lengths.values() for l in lens]
            vpp_lengths = [l for asn_str, lens in transit_path_lengths.items() if asn_str in clean_vpp_set for l in lens]
            non_vpp_lengths = [l for asn_str, lens in transit_path_lengths.items() if asn_str not in clean_vpp_set for l in lens]

            # Top X Hegemony Path Lengths
            sorted_hegemony = sorted(hegemony_scores.items(), key=lambda x: x[1], reverse=True)
            non_zero_hegemony = [item for item in sorted_hegemony if item[1] > 0.0]
            total_transits = len(non_zero_hegemony) if non_zero_hegemony else len(sorted_hegemony)

            if is_percentage_top_x and top_x is not None:
                cutoff_count = max(1, math.ceil(total_transits * (top_x / 100.0)))
            else:
                cutoff_count = int(top_x) if top_x else 5

            top_x_asns = {str(item[0]).replace("AS", "").strip() for item in sorted_hegemony[:cutoff_count]}
            top_x_lengths = [l for asn_str, lens in transit_path_lengths.items() if asn_str in top_x_asns for l in lens]

            overall_distributions.append(all_lengths if all_lengths else [0])
            vpp_distributions.append(vpp_lengths if vpp_lengths else [0])
            non_vpp_distributions.append(non_vpp_lengths if non_vpp_lengths else [0])
            topx_distributions.append(top_x_lengths if top_x_lengths else [0])

        processed_data[ip_ver] = {
            "dates": format_labels_if_they_are_dates(valid_dates),
            "overall": overall_distributions,
            "vpp": vpp_distributions,
            "non_vpp": non_vpp_distributions,
            "topx": topx_distributions,
        }

    if not processed_data:
        print("[WARNING] No data available to plot.")
        return

    top_tag = f"top{int(top_x)}pct" if is_percentage_top_x else f"top{top_x}"
    top_label_desc = f"Top {top_x}%" if is_percentage_top_x else f"Top {top_x}"

    for ip_ver, data in processed_data.items():
        dates = data["dates"]
        positions = np.arange(len(dates))

        # ==========================================
        # FIGURE 1: Overall Path Length Boxplots Over Time
        # ==========================================
        fig1, ax1 = plt.subplots(figsize=DEFAULT_FIGSIZE)
        ax1.boxplot(
            data["overall"],
            positions=positions,
            widths=0.4,
            patch_artist=True,
            showfliers=showfliers,
            boxprops=dict(facecolor="tab:blue", alpha=0.7),
            medianprops=dict(color="crimson", linewidth=2.0),
        )

        ax1.set_xticks(positions)
        ax1.set_xticklabels(dates, rotation=45)
        ax1.set_ylabel("AS Path Length (Hops)")
        ax1.set_xlabel("Date")
        ax1.set_title(f"AS Path Length Distribution Over Time ({ip_ver.upper()})\n(Target ASN: {asn}, Scope: {rrc_tag})")
        ax1.grid(True, linestyle="--", alpha=0.5)
        plt.tight_layout()
        plt.show()
        save_plot(fig=fig1, title=f"path_length_overall_boxplot_{asn}_{rrc_tag.lower()}_{ip_ver}.png")

        # ==========================================
        # FIGURE 2: VPP vs. Non-VPP Side-by-Side Boxplots
        # ==========================================
        fig2, ax2 = plt.subplots(figsize=DEFAULT_FIGSIZE)
        width = 0.35

        ax2.boxplot(
            data["vpp"],
            positions=positions - width / 2,
            widths=width * 0.8,
            patch_artist=True,
            showfliers=showfliers,
            boxprops=dict(facecolor="tab:blue", alpha=0.7),
            medianprops=dict(color="black", linewidth=1.5),
        )

        ax2.boxplot(
            data["non_vpp"],
            positions=positions + width / 2,
            widths=width * 0.8,
            patch_artist=True,
            showfliers=showfliers,
            boxprops=dict(facecolor="tab:orange", alpha=0.7),
            medianprops=dict(color="black", linewidth=1.5),
        )

        ax2.set_xticks(positions)
        ax2.set_xticklabels(dates, rotation=45)
        ax2.set_ylabel("AS Path Length (Hops)")
        ax2.set_xlabel("Date")
        ax2.set_title(f"AS Path Length Distribution: VPPs vs. Non-VPPs ({ip_ver.upper()})\n(AS{asn}, Scope: {rrc_tag})")
        ax2.grid(True, linestyle="--", alpha=0.5)

        legend_elements = [
            Patch(facecolor="tab:blue", alpha=0.7, label="VPP Transits"),
            Patch(facecolor="tab:orange", alpha=0.7, label="Non-VPP Transits"),
        ]
        ax2.legend(handles=legend_elements, loc="upper right")

        plt.tight_layout()
        plt.show()
        save_plot(fig=fig2, title=f"path_length_vpp_vs_non_vpp_boxplot_{asn}_{rrc_tag.lower()}_{ip_ver}.png")

        # ==========================================
        # FIGURE 3: Top X Hegemony Path Length Boxplots
        # ==========================================
        fig3, ax3 = plt.subplots(figsize=DEFAULT_FIGSIZE)
        ax3.boxplot(
            data["topx"],
            positions=positions,
            widths=0.4,
            patch_artist=True,
            showfliers=showfliers,
            boxprops=dict(facecolor="tab:green", alpha=0.7),
            medianprops=dict(color="crimson", linewidth=2.0),
        )

        ax3.set_xticks(positions)
        ax3.set_xticklabels(dates, rotation=45)
        ax3.set_ylabel("AS Path Length (Hops)")
        ax3.set_xlabel("Date")
        ax3.set_title(f"AS Path Length Distribution for {top_label_desc} Hegemony Transits ({ip_ver.upper()})\n(Target ASN: {asn}, Scope: {rrc_tag})")
        ax3.grid(True, linestyle="--", alpha=0.5)
        plt.tight_layout()
        plt.show()
        save_plot(fig=fig3, title=f"path_length_hegemony_{top_tag}_boxplot_{asn}_{rrc_tag.lower()}_{ip_ver}.png")


if __name__ == "__main__":
    asn = 15169
    alpha = 0.34
    all_rrcs = [rrc["rrc"] for rrc in get_all_rrcs()]

    mode = input("Run mode ('global' or 'single') [default 'global']: ").strip().lower() or "global"
    ip_version = input("Enter IP version ('v4', 'v6', or 'both') [default 'both']: ").strip() or "both"
    top_x_input = input("Enter Top X hegemony cut-off (e.g. '5' for Top 5, '10%' for Top 10%) [default '5']: ").strip() or "5"
    dup_input = input("Consider duplicated paths? ('y/n') [default 'y']: ").strip().lower() or "y"
    fliers_input = input("Show outlier dots in boxplots? ('y/n') [default 'n']: ").strip().lower() or "n"

    considers_duplicated_paths = dup_input in ["y", "yes", "true", "1"]
    showfliers = fliers_input in ["y", "yes", "true", "1"]

    if top_x_input.endswith("%"):
        is_percentage_top_x = True
        top_x = float(top_x_input.replace("%", "").strip())
    else:
        is_percentage_top_x = False
        top_x = int(top_x_input)

    if mode == "global":
        print(f"\n[INFO] Running GLOBAL Path Length Hegemony Boxplot analysis for ASN {asn} across {len(all_rrcs)} RRCs...")
        analyze_path_length_hegemony(
            asn=asn,
            alpha=alpha,
            rrc_list=all_rrcs,
            ip_version=ip_version,
            top_x=top_x,
            is_percentage_top_x=is_percentage_top_x,
            month_interval=6,
            text_scale=1.0,
            considers_duplicated_paths=considers_duplicated_paths,
            showfliers=showfliers,
        )
    else:
        rrc_used = input("Enter single RRC to analyze (e.g. 'rrc03') [default 'rrc03']: ").strip() or "rrc03"
        print(f"\n[INFO] Running Single RRC Path Length Hegemony Boxplot analysis for ASN {asn} on {rrc_used}...")
        analyze_path_length_hegemony(
            asn=asn,
            alpha=alpha,
            rrc_used=rrc_used,
            ip_version=ip_version,
            top_x=top_x,
            is_percentage_top_x=is_percentage_top_x,
            month_interval=6,
            text_scale=1.0,
            considers_duplicated_paths=considers_duplicated_paths,
            showfliers=showfliers,
        )