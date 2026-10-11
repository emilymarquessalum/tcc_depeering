from collections import defaultdict
from datetime import datetime
import math
import os
from pathlib import Path
import sqlite3
import sys
from typing import Dict, List, Optional, Set, Tuple, Union

from matplotlib import pyplot as plt
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
) -> Tuple[Dict[str, List[int]], Dict[int, float]]:
    """
    Computes AS hegemony scores and collects all BGP AS path lengths mapped per transit ASN,
    with AS path prepending stripped out.
    
    Returns:
        - transit_path_lengths: Dict[transit_asn_str, List[path_length]]
        - hegemony_scores: Dict[transit_asn_int, hegemony_score]
    """
    hegemony_scores, _ = calculate_as_hegemony_disk(
        db_path=db_path,
        target_asn=target_asn,
        alpha=alpha,
        ip_version=ip_version,
    )

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    query = "SELECT as_path FROM bgp_mappings"
    if target_asn is not None:
        query += " WHERE reachable_as = ?"
        cursor.execute(query, (target_asn,))
    else:
        cursor.execute(query)

    transit_path_lengths = defaultdict(list)

    while True:
        rows = cursor.fetchmany(50_000)
        if not rows:
            break

        for (path_str,) in rows:
            if not path_str:
                continue
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

            # Path length after prepending is removed
            path_len = len(dedup_as_path)

            unique_transits = set(dedup_as_path)
            if target_asn is not None and target_asn in unique_transits:
                unique_transits.remove(target_asn)

            for transit_node in unique_transits:
                transit_path_lengths[str(transit_node)].append(path_len)

    conn.close()
    return transit_path_lengths, hegemony_scores


def get_db_for_date(
    asn: int,
    rrc_used: Union[str, List[str]],
    date: str,
    ip_version: str,
) -> str:
    """
    Ensures SQLite staging DB exists for the given ASN, Date, and IP Version.
    If rrc_used is a list of RRCs or 'global', it merges all RRC datasets into a single GLOBAL database.
    """
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
            global_cursor.execute("INSERT INTO bgp_mappings SELECT * FROM source_db.bgp_mappings;")
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
):
    """
    Executes Path Length Analysis across 8 separate figures:
      1. Overall Path Length over time
      2. Mean Path Length: VPPs vs. Non-VPPs
      3. Mean Path Length Delta (VPP - Non-VPP)
      4. Q25 Path Length: VPPs vs. Non-VPPs
      5. Q25 Path Length Delta (VPP Q25 - Non-VPP Q25)
      6. Q75 Path Length: VPPs vs. Non-VPPs
      7. Q75 Path Length Delta (VPP Q75 - Non-VPP Q75)
      8. Path Length for Top X Hegemony ASNs over time
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
                dates = get_all_dates_available_for_asn_data(asn, rrc, ip_ver, start_date=start_date)
                all_available_dates.update(dates)

            if not all_available_dates:
                print(f"[WARNING] No dates available across RRCs for ASN {asn} ({ip_ver.upper()}).")
                continue

            sorted_dates = sorted(list(all_available_dates))
            available_dts = [datetime.strptime(d, "%Y%m%d") for d in sorted_dates]
            dates = [available_dts[0].strftime("%Y%m%d")]
            current_dt = available_dts[0]

            while True:
                future_dts = [d for d in available_dts if d > current_dt]
                if not future_dts:
                    break
                ideal_target = current_dt + relativedelta(months=month_interval)
                closest_dt = min(future_dts, key=lambda d: abs((d - ideal_target).days))
                dates.append(closest_dt.strftime("%Y%m%d"))
                current_dt = closest_dt
                if current_dt >= available_dts[-1]:
                    break
        else:
            dates = get_interval_dates_for_asn_data(
                asn, rrc_used, ip_ver, month_interval=month_interval, start_date=start_date
            )

        if not dates:
            print(f"[WARNING] No dates available for ASN {asn}, RRC {rrc_tag}, IP {ip_ver.upper()}.")
            continue

        valid_dates = []
        avg_path_len_overall = []
        
        # Means
        avg_path_len_vpp = []
        avg_path_len_non_vpp = []
        avg_path_len_vpp_delta = []

        # Q25 (25th Percentile)
        q25_path_len_vpp = []
        q25_path_len_non_vpp = []
        q25_path_len_vpp_delta = []

        # Q75 (75th Percentile)
        q75_path_len_vpp = []
        q75_path_len_non_vpp = []
        q75_path_len_vpp_delta = []

        avg_path_len_topx = []

        for d in dates:
            try:
                db_path = get_db_for_date(asn, active_rrc_target, d, ip_ver)
                transit_path_lengths, hegemony_scores = extract_path_lengths_and_hegemony(
                    db_path=db_path, target_asn=asn, alpha=alpha, ip_version=ip_ver
                )
            except Exception as e:
                print(f"[ERROR] Could not process date {d} for {ip_ver.upper()}: {e}")
                continue

            if not transit_path_lengths:
                continue

            valid_dates.append(d)

            # Overall
            all_lengths = [l for lens in transit_path_lengths.values() for l in lens]
            avg_overall = sum(all_lengths) / len(all_lengths) if all_lengths else 0.0
            avg_path_len_overall.append(avg_overall)

            # VPP vs Non-VPP lengths collections
            vpp_lengths = [l for asn_str, lens in transit_path_lengths.items() if asn_str in clean_vpp_set for l in lens]
            non_vpp_lengths = [l for asn_str, lens in transit_path_lengths.items() if asn_str not in clean_vpp_set for l in lens]

            # Means & Delta
            avg_vpp = sum(vpp_lengths) / len(vpp_lengths) if vpp_lengths else 0.0
            avg_non_vpp = sum(non_vpp_lengths) / len(non_vpp_lengths) if non_vpp_lengths else 0.0
            avg_path_len_vpp.append(avg_vpp)
            avg_path_len_non_vpp.append(avg_non_vpp)
            avg_path_len_vpp_delta.append(avg_vpp - avg_non_vpp)

            # Q25 Percentile Calculations & Delta
            vpp_q25 = float(np.percentile(vpp_lengths, 25)) if vpp_lengths else 0.0
            non_vpp_q25 = float(np.percentile(non_vpp_lengths, 25)) if non_vpp_lengths else 0.0
            q25_path_len_vpp.append(vpp_q25)
            q25_path_len_non_vpp.append(non_vpp_q25)
            q25_path_len_vpp_delta.append(vpp_q25 - non_vpp_q25)

            # Q75 Percentile Calculations & Delta
            vpp_q75 = float(np.percentile(vpp_lengths, 75)) if vpp_lengths else 0.0
            non_vpp_q75 = float(np.percentile(non_vpp_lengths, 75)) if non_vpp_lengths else 0.0
            q75_path_len_vpp.append(vpp_q75)
            q75_path_len_non_vpp.append(non_vpp_q75)
            q75_path_len_vpp_delta.append(vpp_q75 - non_vpp_q75)

            # Top X Hegemony Path Length
            sorted_hegemony = sorted(hegemony_scores.items(), key=lambda x: x[1], reverse=True)
            total_transits = len(sorted_hegemony)

            if is_percentage_top_x and top_x is not None:
                cutoff_count = max(1, math.ceil(total_transits * (top_x / 100.0)))
            else:
                cutoff_count = int(top_x) if top_x else 5

            top_x_asns = {str(item[0]) for item in sorted_hegemony[:cutoff_count]}
            top_x_lengths = [l for asn_str, lens in transit_path_lengths.items() if asn_str in top_x_asns for l in lens]

            avg_topx = sum(top_x_lengths) / len(top_x_lengths) if top_x_lengths else 0.0
            avg_path_len_topx.append(avg_topx)

        processed_data[ip_ver] = {
            "dates": format_labels_if_they_are_dates(valid_dates),
            "overall": avg_path_len_overall,
            "vpp": avg_path_len_vpp,
            "non_vpp": avg_path_len_non_vpp,
            "delta": avg_path_len_vpp_delta,
            "vpp_q25": q25_path_len_vpp,
            "non_vpp_q25": q25_path_len_non_vpp,
            "q25_delta": q25_path_len_vpp_delta,
            "vpp_q75": q75_path_len_vpp,
            "non_vpp_q75": q75_path_len_non_vpp,
            "q75_delta": q75_path_len_vpp_delta,
            "topx": avg_path_len_topx,
        }

    if not processed_data:
        print("[WARNING] No data available to plot.")
        return

    ip_tag = "both" if len(ip_versions) > 1 else ip_versions[0]
    top_tag = f"top{int(top_x)}pct" if is_percentage_top_x else f"top{top_x}"
    top_label_desc = f"Top {top_x}%" if is_percentage_top_x else f"Top {top_x}"

    # ==========================================
    # FIGURE 1: Overall Path Length Over Time
    # ==========================================
    fig1, ax1 = plt.subplots(figsize=DEFAULT_FIGSIZE)
    for ip_ver, data in processed_data.items():
        ls = "-" if ip_ver == "v4" else "--"
        mk = "o" if ip_ver == "v4" else "^"
        lbl_suffix = f" ({ip_ver.upper()})" if len(ip_versions) > 1 else ""
        ax1.plot(data["dates"], data["overall"], marker=mk, linestyle=ls, linewidth=2.5, label=f"Overall Path Length{lbl_suffix}")

    ax1.set_ylabel("Avg Path Length (Hops)")
    ax1.set_xlabel("Date")
    ax1.set_title(f"AS Path Length \n(ASN: {asn}, {rrc_tag})")
    ax1.tick_params(axis="x", rotation=45)
    ax1.grid(True, linestyle="--", alpha=0.5)
    ax1.legend(loc="upper right")
    plt.tight_layout()
    plt.show()
    save_plot(fig=fig1, title=f"path_length_overall_{asn}_{rrc_tag.lower()}_{ip_tag}.png")

    # ==========================================
    # FIGURE 2: VPP vs. Non-VPP Path Length (Mean)
    # ==========================================
    fig2, ax2 = plt.subplots(figsize=DEFAULT_FIGSIZE)
    for ip_ver, data in processed_data.items():
        ls = "-" if ip_ver == "v4" else "--"
        lbl_suffix = f" ({ip_ver.upper()})" if len(ip_versions) > 1 else ""
        ax2.plot(data["dates"], data["vpp"], marker="o" if ip_ver == "v4" else "^", linestyle=ls, linewidth=2.5, color="tab:blue", label=f"VPP Path Length{lbl_suffix}")
        ax2.plot(data["dates"], data["non_vpp"], marker="s" if ip_ver == "v4" else "D", linestyle=ls, linewidth=2.5, color="tab:orange", label=f"Non-VPP Path Length{lbl_suffix}")

    ax2.set_ylabel("Avg Path Length (Hops)")
    ax2.set_xlabel("Date")
    ax2.set_title(f"AS Path Length (Mean): VPPs vs. Non-VPPs \n(AS{asn}, Scope: {rrc_tag})")
    ax2.tick_params(axis="x", rotation=45)
    ax2.grid(True, linestyle="--", alpha=0.5)
    ax2.legend(loc="upper right")
    plt.tight_layout()
    plt.show()
    save_plot(fig=fig2, title=f"path_length_vpp_vs_non_vpp_mean_{asn}_{rrc_tag.lower()}_{ip_tag}.png")

    # ==========================================
    # FIGURE 3: Mean Delta (VPP - Non-VPP)
    # ==========================================
    fig3, ax3 = plt.subplots(figsize=DEFAULT_FIGSIZE)
    for ip_ver, data in processed_data.items():
        ls = "-" if ip_ver == "v4" else "--"
        mk = "o" if ip_ver == "v4" else "^"
        lbl_suffix = f" ({ip_ver.upper()})" if len(ip_versions) > 1 else ""
        color = "tab:purple" if ip_ver == "v4" else "tab:red"
        ax3.plot(data["dates"], data["delta"], marker=mk, linestyle=ls, linewidth=2.5, color=color, label=f"VPP Extra Path Length{lbl_suffix}")

    ax3.axhline(0, color="gray", linestyle=":", linewidth=1.5, label="Equal Path Length (0 Hops)")
    ax3.set_ylabel("Difference in Avg Path Length (Hops)")
    ax3.set_xlabel("Date")
    ax3.set_title(f"Mean Path Length Delta: VPP vs Non-VPP (VPP - Non-VPP)\n(AS{asn}, {rrc_tag})")
    ax3.tick_params(axis="x", rotation=45)
    ax3.grid(True, linestyle="--", alpha=0.5)
    ax3.legend(loc="upper right")
    plt.tight_layout()
    plt.show()
    save_plot(fig=fig3, title=f"path_length_vpp_delta_mean_{asn}_{rrc_tag.lower()}_{ip_tag}.png")

    # ==========================================
    # FIGURE 4: Q25 Path Length (VPP vs Non-VPP)
    # ==========================================
    fig4, ax4 = plt.subplots(figsize=DEFAULT_FIGSIZE)
    for ip_ver, data in processed_data.items():
        ls = "-" if ip_ver == "v4" else "--"
        lbl_suffix = f" ({ip_ver.upper()})" if len(ip_versions) > 1 else ""
        ax4.plot(data["dates"], data["vpp_q25"], marker="o" if ip_ver == "v4" else "^", linestyle=ls, linewidth=2.5, color="tab:blue", label=f"VPP Q25 Path Length{lbl_suffix}")
        ax4.plot(data["dates"], data["non_vpp_q25"], marker="s" if ip_ver == "v4" else "D", linestyle=ls, linewidth=2.5, color="tab:orange", label=f"Non-VPP Q25 Path Length{lbl_suffix}")

    ax4.set_ylabel("Q25 Path Length (Hops)")
    ax4.set_xlabel("Date")
    ax4.set_title(f"25th Percentile (Q25) Path Length: VPPs vs Non-VPPs\n(AS{asn}, Scope: {rrc_tag})")
    ax4.tick_params(axis="x", rotation=45)
    ax4.grid(True, linestyle="--", alpha=0.5)
    ax4.legend(loc="upper right")
    plt.tight_layout()
    plt.show()
    save_plot(fig=fig4, title=f"path_length_vpp_vs_non_vpp_q25_{asn}_{rrc_tag.lower()}_{ip_tag}.png")

    # ==========================================
    # FIGURE 5: Q25 Delta (VPP Q25 - Non-VPP Q25)
    # ==========================================
    fig5, ax5 = plt.subplots(figsize=DEFAULT_FIGSIZE)
    for ip_ver, data in processed_data.items():
        ls = "-" if ip_ver == "v4" else "--"
        mk = "o" if ip_ver == "v4" else "^"
        lbl_suffix = f" ({ip_ver.upper()})" if len(ip_versions) > 1 else ""
        color = "tab:purple" if ip_ver == "v4" else "tab:red"
        ax5.plot(data["dates"], data["q25_delta"], marker=mk, linestyle=ls, linewidth=2.5, color=color, label=f"VPP Extra Q25 Path Length{lbl_suffix}")

    ax5.axhline(0, color="gray", linestyle=":", linewidth=1.5, label="Equal Path Length (0 Hops)")
    ax5.set_ylabel("Difference in Q25 Path Length (Hops)")
    ax5.set_xlabel("Date")
    ax5.set_title(f"Q25 Path Length Delta: VPP vs Non-VPP (VPP Q25 - Non-VPP Q25)\n(AS{asn}, {rrc_tag})")
    ax5.tick_params(axis="x", rotation=45)
    ax5.grid(True, linestyle="--", alpha=0.5)
    ax5.legend(loc="upper right")
    plt.tight_layout()
    plt.show()
    save_plot(fig=fig5, title=f"path_length_vpp_delta_q25_{asn}_{rrc_tag.lower()}_{ip_tag}.png")

    # ==========================================
    # FIGURE 6: Q75 Path Length (VPP vs Non-VPP)
    # ==========================================
    fig6, ax6 = plt.subplots(figsize=DEFAULT_FIGSIZE)
    for ip_ver, data in processed_data.items():
        ls = "-" if ip_ver == "v4" else "--"
        lbl_suffix = f" ({ip_ver.upper()})" if len(ip_versions) > 1 else ""
        ax6.plot(data["dates"], data["vpp_q75"], marker="o" if ip_ver == "v4" else "^", linestyle=ls, linewidth=2.5, color="tab:blue", label=f"VPP Q75 Path Length{lbl_suffix}")
        ax6.plot(data["dates"], data["non_vpp_q75"], marker="s" if ip_ver == "v4" else "D", linestyle=ls, linewidth=2.5, color="tab:orange", label=f"Non-VPP Q75 Path Length{lbl_suffix}")

    ax6.set_ylabel("Q75 Path Length (Hops)")
    ax6.set_xlabel("Date")
    ax6.set_title(f"75th Percentile (Q75) Path Length: VPPs vs Non-VPPs\n(AS{asn}, Scope: {rrc_tag})")
    ax6.tick_params(axis="x", rotation=45)
    ax6.grid(True, linestyle="--", alpha=0.5)
    ax6.legend(loc="upper right")
    plt.tight_layout()
    plt.show()
    save_plot(fig=fig6, title=f"path_length_vpp_vs_non_vpp_q75_{asn}_{rrc_tag.lower()}_{ip_tag}.png")

    # ==========================================
    # FIGURE 7: Q75 Delta (VPP Q75 - Non-VPP Q75)
    # ==========================================
    fig7, ax7 = plt.subplots(figsize=DEFAULT_FIGSIZE)
    for ip_ver, data in processed_data.items():
        ls = "-" if ip_ver == "v4" else "--"
        mk = "o" if ip_ver == "v4" else "^"
        lbl_suffix = f" ({ip_ver.upper()})" if len(ip_versions) > 1 else ""
        color = "tab:purple" if ip_ver == "v4" else "tab:red"
        ax7.plot(data["dates"], data["q75_delta"], marker=mk, linestyle=ls, linewidth=2.5, color=color, label=f"VPP Extra Q75 Path Length{lbl_suffix}")

    ax7.axhline(0, color="gray", linestyle=":", linewidth=1.5, label="Equal Path Length (0 Hops)")
    ax7.set_ylabel("Difference in Q75 Path Length (Hops)")
    ax7.set_xlabel("Date")
    ax7.set_title(f"Q75 Path Length Delta: VPP vs Non-VPP (VPP Q75 - Non-VPP Q75)\n(AS{asn}, {rrc_tag})")
    ax7.tick_params(axis="x", rotation=45)
    ax7.grid(True, linestyle="--", alpha=0.5)
    ax7.legend(loc="upper right")
    plt.tight_layout()
    plt.show()
    save_plot(fig=fig7, title=f"path_length_vpp_delta_q75_{asn}_{rrc_tag.lower()}_{ip_tag}.png")

    # ==========================================
    # FIGURE 8: Top X Hegemony Path Length
    # ==========================================
    fig8, ax8 = plt.subplots(figsize=DEFAULT_FIGSIZE)
    for ip_ver, data in processed_data.items():
        ls = "-" if ip_ver == "v4" else "--"
        mk = "o" if ip_ver == "v4" else "^"
        lbl_suffix = f" ({ip_ver.upper()})" if len(ip_versions) > 1 else ""
        ax8.plot(data["dates"], data["topx"], marker=mk, linestyle=ls, linewidth=2.5, color="tab:green", label=f"{top_label_desc} Hegemony Path Length{lbl_suffix}")

    ax8.set_ylabel("Avg Path Length (Hops)")
    ax8.set_xlabel("Date")
    ax8.set_title(f"AS Path Length for {top_label_desc} Hegemony Transits Over Time\n(Target ASN: {asn}, Scope: {rrc_tag})")
    ax8.tick_params(axis="x", rotation=45)
    ax8.grid(True, linestyle="--", alpha=0.5)
    ax8.legend(loc="upper right")
    plt.tight_layout()
    plt.show()
    save_plot(fig=fig8, title=f"path_length_hegemony_{top_tag}_{asn}_{rrc_tag.lower()}_{ip_tag}.png")


if __name__ == "__main__":
    from dateutil.relativedelta import relativedelta

    asn = 15169
    alpha = 0.34
    all_rrcs = [rrc["rrc"] for rrc in get_all_rrcs()]

    mode = input("Run mode ('global' or 'single') [default 'global']: ").strip().lower() or "global"
    ip_version = input("Enter IP version ('v4', 'v6', or 'both') [default 'both']: ").strip() or "both"
    top_x_input = input("Enter Top X hegemony cut-off (e.g. '5' for Top 5, '10%' for Top 10%) [default '5']: ").strip() or "5"

    if top_x_input.endswith("%"):
        is_percentage_top_x = True
        top_x = float(top_x_input.replace("%", "").strip())
    else:
        is_percentage_top_x = False
        top_x = int(top_x_input)

    if mode == "global":
        print(f"\n[INFO] Running GLOBAL Path Length Hegemony analysis for ASN {asn} across {len(all_rrcs)} RRCs...")
        analyze_path_length_hegemony(
            asn=asn,
            alpha=alpha,
            rrc_list=all_rrcs,
            ip_version=ip_version,
            top_x=top_x,
            is_percentage_top_x=is_percentage_top_x,
            month_interval=6,
            text_scale=1.0,
        )
    else:
        rrc_used = input("Enter single RRC to analyze (e.g. 'rrc03') [default 'rrc03']: ").strip() or "rrc03"
        print(f"\n[INFO] Running Single RRC Path Length Hegemony analysis for ASN {asn} on {rrc_used}...")
        analyze_path_length_hegemony(
            asn=asn,
            alpha=alpha,
            rrc_used=rrc_used,
            ip_version=ip_version,
            top_x=top_x,
            is_percentage_top_x=is_percentage_top_x,
            month_interval=6,
            text_scale=1.0,
        )