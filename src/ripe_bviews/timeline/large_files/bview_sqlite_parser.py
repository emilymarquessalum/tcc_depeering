import sqlite3
import os
from typing import Tuple, Optional, Dict, Set, List
from collections import defaultdict
from pathlib import Path
import sys

from matplotlib import pyplot as plt


# Preserving your setup
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))
from src.google.vpps.google_vpps_list import get_google_vpp_asns
from src.utils.graphs import DEFAULT_FIGSIZE, save_plot
from src.ripe_bviews.timeline.render.bview_functionalities import _get_most_recent_caida_data
from src.ripe_bviews.timeline.bview_hegemony import _apply_alpha_trimming, get_sorted_asns_from_scores, plot_top5_transit 
from definitions import ROOT_DIR

def calculate_as_hegemony_disk(
    db_path: str, 
    target_asn: Optional[int] = None, 
    alpha: float = 0.34,
    filter_full_feed: bool = True,
    ip_version: str = "v4",
    v4_threshold: int = 1,
    v6_threshold: int = 50_000,
    allowed_viewpoints: Optional[Set[str]] = None
) -> Tuple[Dict[int, float], Set[str]]:
    """
    Computes AS Hegemony over huge disk-cached datasets using indexed queries.
    Handles both IPv4 (Path-Weighted) and IPv6 (Unweighted/Classical) protocols dynamically.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # --- STEP 1: Determine Active Viewpoints & Apply Thresholds ---
    print(f"[HEGEMONY] Aggregating baseline metrics per Viewpoint ({ip_version.upper()})...")
    
    # Track distinct prefix counts for full-feed vetting
    cursor.execute("""
        SELECT viewpoint_peer, COUNT(DISTINCT prefix) 
        FROM bgp_mappings 
        GROUP BY viewpoint_peer
    """)
    vp_table_sizes = {vp: size for vp, size in cursor.fetchall()}

    # Select total paths or total path-weights depending on IP version
    query_baseline = "SELECT viewpoint_peer, prefix_weight FROM bgp_mappings"
    if target_asn is not None:
        query_baseline += " WHERE reachable_as = ?"
        cursor.execute(query_baseline, (target_asn,))
    else:
        cursor.execute(query_baseline)

    vp_total_weights = defaultdict(float)
    for vp, weight in cursor.fetchall():
        vp_total_weights[vp] += weight

    vp_active_weights = {}
    dropped_viewpoints = 0
    chosen_threshold = v4_threshold if ip_version == "v4" else v6_threshold

    candidate_vps = set(vp_total_weights.keys())
    if allowed_viewpoints is not None:
        candidate_vps.intersection_update(allowed_viewpoints)

    for vp in candidate_vps:
        # Check if peer is present
        if vp not in vp_total_weights:
            dropped_viewpoints += 1
            continue

        actual_table_size = vp_table_sizes.get(vp, 0)
        
        # Apply full feed threshold filter
        if filter_full_feed and actual_table_size < chosen_threshold:
            dropped_viewpoints += 1
            continue  
            
        vp_active_weights[vp] = vp_total_weights[vp]
        
    all_active_peers = set(vp_active_weights.keys())
    n_viewpoints = len(all_active_peers)
    
    if filter_full_feed:
        print(f"[HEGEMONY] Full-feed filter/Baseline alignment ENABLED (Threshold: {chosen_threshold} prefixes).")
        print(f"[HEGEMONY] Retained {n_viewpoints} viewpoints. Dropped/Filtered {dropped_viewpoints} views.")

    if n_viewpoints == 0:
        conn.close()
        return {}, set()

    # --- STEP 2: Discover Transit Intersections ---
    print("[HEGEMONY] Processing unique Transit AS nodes...")
    
    transit_vp_weights = defaultdict(lambda: defaultdict(float))
    all_transit_asns = set()
    allowed_vps = all_active_peers
    
    query = "SELECT viewpoint_peer, as_path, prefix_weight FROM bgp_mappings"
    if target_asn is not None:
        query += " WHERE reachable_as = ?"
        cursor.execute(query, (target_asn,))
    else:
        cursor.execute(query)
        
    while True:
        rows = cursor.fetchmany(size=50_000)
        if not rows:
            break
            
        for vp, path_str, weight in rows:
            if vp not in allowed_vps:
                continue
                
            try:
                as_path = [int(x) for x in path_str.split(",") if x]
            except ValueError:
                continue
            
            unique_transits = set(as_path)
            if target_asn is not None and target_asn in unique_transits:
                unique_transits.remove(target_asn)

            for transit_node in unique_transits:
                transit_vp_weights[transit_node][vp] += weight
                all_transit_asns.add(transit_node)

    # --- STEP 3: Apply Alpha-Trimming Mechanics ---
    print("[HEGEMONY] Finalizing distribution trimming mechanics...")
    hegemony_scores = {}
    
    active_peers_list = list(all_active_peers)
    for asn in all_transit_asns:
        scores = []
        for vp_key in active_peers_list:
            vp_transit_weight = transit_vp_weights[asn].get(vp_key, 0.0) 
            fraction = vp_transit_weight / vp_active_weights[vp_key] if vp_active_weights[vp_key] > 0 else 0.0
            scores.append(fraction)
            
        hegemony_scores[asn] = _apply_alpha_trimming(scores, alpha)
        
    conn.close()
    return hegemony_scores, all_active_peers 


class LargeBViewParser:
    def __init__(self, db_path: str = "bview_staging.db", ip_version: str = "v4"):
        self.db_path = db_path
        self.ip_version = ip_version.lower()
        
    def init_database(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=OFF;")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bgp_mappings (
                viewpoint_peer TEXT,
                reachable_as INTEGER,
                prefix TEXT,
                prefix_weight REAL,
                as_path TEXT,
                communities TEXT
            );
        """)
        cursor.execute("CREATE INDEX idx_vp ON bgp_mappings(viewpoint_peer);")
        cursor.execute("CREATE INDEX idx_reachable ON bgp_mappings(reachable_as);")
        conn.commit()
        conn.close()

    def _parse_asn(self, asn_str: str) -> Optional[int]:
        try:
            return int(asn_str.strip())
        except ValueError:
            return None

    def _calculate_prefix_weight(self, prefix: str) -> float:
        if self.ip_version == "v6":
            return 1.0
            
        try:
            mask = int(prefix.split("/")[-1])
            return float(1 << (32 - mask))
        except (ValueError, IndexError):
            return 1.0

    def _process_line(self, line: str) -> Optional[Tuple[str, int, str, float, str, str]]:
        trimmed = line.strip()
        if not trimmed:
            return None
            
        fields = trimmed.split("|")
        if len(fields) < 9:
            return None
            
        raw_viewpoint_peer = fields[3].strip() 
        if not raw_viewpoint_peer:
            return None
            
        prefix = fields[5]
        as_path_str = fields[6]
        communities = fields[8]
        
        if self.ip_version == "v4":
            if "." not in prefix or "/" not in prefix:
                return None
        elif self.ip_version == "v6":
            if ":" not in prefix or "/" not in prefix:
                return None
        else:
            return None
        
        raw_as_path = as_path_str.split()
        if not raw_as_path:
            return None
            
        as_path = []
        last_valid = None
        for raw_asn in raw_as_path:
            asn = self._parse_asn(raw_asn)
            if asn is not None:
                as_path.append(asn)
                last_valid = asn
                
        if not as_path:
            return None
            
        reachable = last_valid
        prefix_weight = self._calculate_prefix_weight(prefix)
        as_path_encoded = ",".join(map(str, as_path))
        
        return (raw_viewpoint_peer, reachable, prefix, prefix_weight, as_path_encoded, communities)

    def parse_to_disk(self, file_path: str, chunk_size: int = 100_000, limit: Optional[int] = None):
        self.init_database()
        conn = sqlite3.connect(self.db_path)    
        cursor = conn.cursor()
        
        batch = []
        lines_processed = 0
        
        print(f"[PARSER] Commencing out-of-core file streaming ({self.ip_version.upper()}) for {file_path}...")
        
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if limit and lines_processed >= limit:
                    break
                    
                record = self._process_line(line)
                if record:
                    batch.append(record)
                    
                lines_processed += 1
                
                if len(batch) >= chunk_size:
                    cursor.executemany(
                        "INSERT INTO bgp_mappings VALUES (?, ?, ?, ?, ?, ?);", batch
                    )
                    conn.commit()
                    batch.clear()
                    
            if batch:
                cursor.executemany(
                    "INSERT INTO bgp_mappings VALUES (?, ?, ?, ?, ?, ?);", batch
                )
                conn.commit()
                
        conn.close()
        print(f"[PARSER] Parsing completed. Records offloaded to {self.db_path}.")


def get_first_and_last_date_available_for_asn_data(asn, rrc_used, ip_version):
    path = f"{ROOT_DIR}/{rrc_used}/"
    files = os.listdir(path)
    relevant_files = [f for f in files if f.startswith("output_bview.") and f.endswith(f"0000.origin_as.{asn}.txt")]

    if not relevant_files:
        return None, None

    dates = [f.split(".")[1] for f in relevant_files]
    return min(dates), max(dates)

def get_all_dates_available_for_asn_data(asn, rrc_used, ip_version):
    path = f"{ROOT_DIR}/{rrc_used}/"
    files = os.listdir(path)
    relevant_files = [f for f in files if f.startswith("output_bview.") and f.endswith(f"0000.origin_as.{asn}.txt")]

    if not relevant_files:
        return []

    dates = [f.split(".")[1] for f in relevant_files]
    return sorted(dates)

def load_hegemony_for_date(asn, alpha, rrc_used, date, ip_version, allowed_viewpoints=None):
    db_path = f"huge_bgp_cache_{rrc_used}_{date}_{ip_version}_{asn}.db"
    path = f"{ROOT_DIR}/{rrc_used}/output_bview.{date}.0000.origin_as.{asn}.txt"
    
    if not os.path.exists(db_path):
        parser = LargeBViewParser(db_path=db_path, ip_version=ip_version)
        parser.parse_to_disk(path) 
        
    return calculate_as_hegemony_disk(
        db_path, target_asn=asn, alpha=alpha, ip_version=ip_version, allowed_viewpoints=allowed_viewpoints
    ) 

def get_active_viewpoints_for_date(
    asn: int, 
    rrc_used: str, 
    date: str, 
    ip_version: str, 
    filter_full_feed: bool = True,
    v4_threshold: int = 1,
    v6_threshold: int = 50_000
) -> Set[str]:
    """Helper to retrieve active viewpoints for a given snapshot without computing full hegemony scores."""
    db_path = f"huge_bgp_cache_{rrc_used}_{date}_{ip_version}_{asn}.db"
    path = f"{ROOT_DIR}/{rrc_used}/output_bview.{date}.0000.origin_as.{asn}.txt"
    
    if not os.path.exists(db_path):
        parser = LargeBViewParser(db_path=db_path, ip_version=ip_version)
        parser.parse_to_disk(path)
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT viewpoint_peer, COUNT(DISTINCT prefix) 
        FROM bgp_mappings 
        GROUP BY viewpoint_peer
    """)
    vp_table_sizes = {vp: size for vp, size in cursor.fetchall()}

    query_baseline = "SELECT viewpoint_peer, prefix_weight FROM bgp_mappings WHERE reachable_as = ?"
    cursor.execute(query_baseline, (asn,))

    vp_total_weights = defaultdict(float)
    for vp, weight in cursor.fetchall():
        vp_total_weights[vp] += weight

    conn.close()

    chosen_threshold = v4_threshold if ip_version == "v4" else v6_threshold
    active_vps = set()

    for vp, total_weight in vp_total_weights.items():
        actual_table_size = vp_table_sizes.get(vp, 0)
        if filter_full_feed and actual_table_size < chosen_threshold:
            continue
        active_vps.add(vp)

    return active_vps


def compare_hegemony_for_two_dates(
    asn, alpha, rrc_used, ip_version, date_before, date_after, use_strict_viewpoint_filtering: bool = False
):
    if use_strict_viewpoint_filtering:
        print("[VIEWPOINTS] Finding strict intersection of active viewpoints across both dates...")
        vp_before = get_active_viewpoints_for_date(asn, rrc_used, date_before, ip_version)
        vp_after = get_active_viewpoints_for_date(asn, rrc_used, date_after, ip_version)
        strict_allowed_viewpoints = vp_before.intersection(vp_after)
        print(f"[VIEWPOINTS] Strict filtering retained {len(strict_allowed_viewpoints)} viewpoints present in both dates.")

        hegemony_scores_before, _ = load_hegemony_for_date(
            asn, alpha, rrc_used, date_before, ip_version, allowed_viewpoints=strict_allowed_viewpoints
        )
        hegemony_scores_after, _ = load_hegemony_for_date(
            asn, alpha, rrc_used, date_after, ip_version, allowed_viewpoints=strict_allowed_viewpoints
        )
    else:
        # 1. Load data for "Before" date and capture its active viewpoints
        hegemony_scores_before, viewpoints_before = load_hegemony_for_date(
            asn, alpha, rrc_used, date_before, ip_version
        )
        
        # 2. Load data for "After" date, restricting it to use ONLY the viewpoints from "Before"
        hegemony_scores_after, _ = load_hegemony_for_date(
            asn, alpha, rrc_used, date_after, ip_version, allowed_viewpoints=viewpoints_before
        )

    sorted_asns_before = get_sorted_asns_from_scores(hegemony_scores_before)
    sorted_asns_after = get_sorted_asns_from_scores(hegemony_scores_after)

    top_sorted_asns_before = sorted_asns_before[:5]
    top_sorted_asns_after = sorted_asns_after[:5]

    current_score_placement_for_past_top5 = [sorted_asns_after.index(asn) if asn in sorted_asns_after else -1 for asn in top_sorted_asns_before]
    previous_score_placement_for_current_top5 = [sorted_asns_before.index(asn) if asn in sorted_asns_before else -1 for asn in top_sorted_asns_after]

    print("Current placement for past top5:", current_score_placement_for_past_top5)
    print("Previous placement for current top5:", previous_score_placement_for_current_top5)

    caida_data = None
    try:
        caida_data = _get_most_recent_caida_data(None, None)
    except:
        pass

    plot_top5_transit(hegemony_scores_before, caida_data, asn,  
        ip_version, "", extra_label=f"{date_before} for {rrc_used} - α={alpha}") 
    
    plot_top5_transit(hegemony_scores_after, caida_data, asn,  
        ip_version, "", extra_label=f"{date_after} for {rrc_used} - α={alpha}") 



def get_hegemony_scores(asn, rrc_used, ip_version, date_list, alpha, use_strict_viewpoint_filtering):

    hegemony_scores_dict = {} 
    
    allowed_viewpoints_baseline = None
    
    if use_strict_viewpoint_filtering:
            print(f"[VIEWPOINTS] Computing strict viewpoint intersection across all {len(date_list)} dates...")
            active_sets = []
            for snapshot in date_list:
                viewpoints = get_active_viewpoints_for_date(asn, rrc_used, snapshot, ip_version)
                active_sets.append(viewpoints)
            
            allowed_viewpoints_baseline = set.intersection(*active_sets)
            print(f"[VIEWPOINTS] Strict viewpoint filtering retained {len(allowed_viewpoints_baseline)} viewpoints present across ALL snapshots.")
    
    if allowed_viewpoints_baseline is not None:
            # Use strict intersection for all dates
            for date in date_list:
                scores, viewpoints = load_hegemony_for_date(
                    asn, alpha, rrc_used, date, ip_version,
                    allowed_viewpoints=allowed_viewpoints_baseline
                )
                hegemony_scores_dict[date] = scores 
    else:
            # Legacy/Default mode: Use viewpoints active in first date as baseline
            first_date = date_list[0]
            first_score, first_viewpoints = load_hegemony_for_date(
                asn, alpha, rrc_used, first_date, ip_version
            )
    
            hegemony_scores_dict[first_date] = first_score 
    
            for date in date_list[1:]:
                scores, viewpoints = load_hegemony_for_date(
                    asn, alpha, rrc_used, date, ip_version,
                    allowed_viewpoints=first_viewpoints
                )
                hegemony_scores_dict[date] = scores 

    return hegemony_scores_dict


def get_top_five_asns_over_time(hegemony_scores_dict, date_list):
    all_unique_top_fives = set()
    for date in date_list:
            print(f"Hegemony scores for {date}:")
            sorted_asns = get_sorted_asns_from_scores(hegemony_scores_dict[date])
            all_unique_top_fives.update(sorted_asns[:3])
    
    unique_asns_list = sorted(list(all_unique_top_fives))
    
    top_fives_over_time: list[list[int]] = []
    
    for date in date_list:
            all_top_fives_but_in_current_date = []
            for target_asn in unique_asns_list:
                if target_asn in hegemony_scores_dict[date]:
                    all_top_fives_but_in_current_date.append(
                        hegemony_scores_dict[date][target_asn]
                    )
                else:
                    all_top_fives_but_in_current_date.append(0.0)
            top_fives_over_time.append(all_top_fives_but_in_current_date)

    return top_fives_over_time, unique_asns_list


def compare_hegemony_for_several_dates(
    asn, alpha, rrc_used, ip_version, date_list, use_strict_viewpoint_filtering: bool = False
):
    

    hegemony_scores_dict = get_hegemony_scores(asn, rrc_used, ip_version, date_list, alpha, use_strict_viewpoint_filtering)

    top_fives_over_time, unique_asns_list = get_top_five_asns_over_time(hegemony_scores_dict, date_list)

    # --- Line Plot Implementation with Anti-Occlusion Visual Tricks ---
    plt.figure(figsize=DEFAULT_FIGSIZE)

    line_styles = ["-", "--", ":", "-."]
    markers = ["o", "s", "^", "v", "D", "X", "P"]

    base_linewidth = 6.0
    width_step = 0.8

    for i, target_asn in enumerate(unique_asns_list):
        scores_for_asn = [
            top_fives_over_time[d_idx][i] for d_idx in range(len(date_list))
        ]

        lw = max(1.5, base_linewidth - (i * width_step))
        ls = line_styles[i % len(line_styles)]
        mk = markers[i % len(markers)]
        alpha_val = 0.75 if lw > 3.0 else 1.0

        plt.plot(
            date_list,
            scores_for_asn,
            marker=mk,
            markersize=7 - (i * 0.4),
            linewidth=lw,
            linestyle=ls,
            alpha=alpha_val,
            label=f"ASN {target_asn}",
        )

    plt.xlabel("Date", fontsize=12)
    plt.ylabel("Hegemony Score", fontsize=12)
    plt.title(
        f"Hegemony Scores Over Time for Top ASNs (Target ASN: {asn}, RRC: {rrc_used}, IP: {ip_version}, α={alpha})",
        fontsize=14,
    )
    plt.xticks(rotation=45)
    plt.grid(True, linestyle="--", alpha=0.5)

    plt.legend(bbox_to_anchor=(1.02, 1), loc="upper left", title="ASNs")
    plt.tight_layout()
    plt.show() 

    save_plot(fig=plt.gcf(), title=f"hegemony_over_time_{asn}_{rrc_used}_{ip_version}.png")



def compare_vpp_and_non_vpp_hegemony_over_time(asn, alpha, rrc_used, ip_version, date_list, use_strict_viewpoint_filtering: bool = False):

    google_vpps_asns = get_google_vpp_asns()
    
    hegemony_scores_dict = get_hegemony_scores(asn, rrc_used, ip_version, date_list, alpha, use_strict_viewpoint_filtering)

    top_fives_over_time, unique_asns_list = get_top_five_asns_over_time(hegemony_scores_dict, date_list)

    hegemony_over_time_vpp_or_not_vpp: list[tuple[int,int]] = []


    for date in range(len(date_list)):

        hegemony_vpp = 0
        hegemony_not_vpp = 0

        for i, asn in enumerate(unique_asns_list):

            asn_score = top_fives_over_time[date][i]
            if asn in google_vpps_asns:
                hegemony_vpp += asn_score
            else:
                hegemony_not_vpp += asn_score

        hegemony_over_time_vpp_or_not_vpp.append((hegemony_vpp, hegemony_not_vpp))

    plt.figure(figsize=DEFAULT_FIGSIZE)

    plt.plot(
        date_list,
        [hegemony[0] for hegemony in hegemony_over_time_vpp_or_not_vpp], # vpp
        label="VPP Hegemony", 
    )

    plt.plot(
        date_list,
        [hegemony[1] for hegemony in hegemony_over_time_vpp_or_not_vpp], # not vpp
        label="Non-VPP Hegemony", 
    )

    plt.ylabel("Hegemony")
    plt.xlabel("Date")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(bbox_to_anchor=(1.02, 1), loc="upper left", title="Is-VPP")
    plt.show()
    save_plot(fig=plt.gcf(), title=f"hegemony_over_time_by_vpp_feature_{asn}_{rrc_used}_{ip_version}.png")



if __name__ == "__main__":
    rrc_used = "rrc03"
    ip_version = "v4"
    asn = 15169

    asn_input = input(f"Enter ASN to analyze (default {asn}): ")
    if asn_input:
        asn = int(asn_input)
        
    alpha = 0.34 
    use_strict_viewpoint_filtering = True # only viewpoints that existed in all snapshots

    date_before, date_after = get_first_and_last_date_available_for_asn_data(asn, rrc_used, ip_version)

    compare_hegemony_for_two_dates(
        asn, alpha, rrc_used, ip_version, date_before, date_after, 
        use_strict_viewpoint_filtering=use_strict_viewpoint_filtering
    )

    compare_hegemony_for_several_dates(
        asn, alpha, rrc_used, ip_version, get_all_dates_available_for_asn_data(asn, rrc_used, ip_version),
        use_strict_viewpoint_filtering=use_strict_viewpoint_filtering
    )


    compare_vpp_and_non_vpp_hegemony_over_time(
        asn, alpha, rrc_used, ip_version, get_all_dates_available_for_asn_data(asn, rrc_used, ip_version),
        use_strict_viewpoint_filtering=use_strict_viewpoint_filtering
    )