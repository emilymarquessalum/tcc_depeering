import sqlite3
import os
from typing import Tuple, Optional, Dict, Set, List
from collections import defaultdict
from pathlib import Path
import sys

from matplotlib import pyplot as plt
import os
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


# Preserving your setup
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))
from src.google.vpps.google_vpps_list import get_google_vpp_asns
from src.utils.graphs import DEFAULT_FIGSIZE, save_plot
from src.ripe_bviews.timeline.render.bview_functionalities import _get_most_recent_caida_data
from src.ripe_bviews.timeline.bview_hegemony import _apply_alpha_trimming, get_sorted_asns_from_scores, plot_top5_transit 
from definitions import ROOT_DIR

def calculate_as_hegemony_from_db(
    conn: sqlite3.Connection,
    target_asn: Optional[int] = None,
    alpha: float = 0.34,
    filter_full_feed: bool = True,
    ip_version: str = "v4",
    v4_threshold: int = 1,
    v6_threshold: int = 50_000,
    allowed_viewpoints: Optional[Set[str]] = None
) -> Tuple[Dict[int, float], Set[str]]:
    """
    Core Hegemony math operating on an open SQLite connection.
    Can be reused by BGP snapshot databases or RIPE Atlas traceroute databases.
    """
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
        if vp not in vp_total_weights:
            dropped_viewpoints += 1
            continue

        actual_table_size = vp_table_sizes.get(vp, 0)
        
        if filter_full_feed and actual_table_size < chosen_threshold:
            dropped_viewpoints += 1
            continue  
            
        vp_active_weights[vp] = vp_total_weights[vp]
        
    all_active_peers = set(vp_active_weights.keys())
    n_viewpoints = len(all_active_peers)
    
    if filter_full_feed:
        print(f"[HEGEMONY] Filter/Baseline alignment ENABLED (Threshold: {chosen_threshold} prefixes).")
        print(f"[HEGEMONY] Retained {n_viewpoints} viewpoints. Dropped/Filtered {dropped_viewpoints} views.")

    if n_viewpoints == 0:
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
        
    return hegemony_scores, all_active_peers


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
    Refactored wrapper to keep existing script execution completely unchanged.
    """
    conn = sqlite3.connect(db_path)
    scores, vps = calculate_as_hegemony_from_db(
        conn=conn,
        target_asn=target_asn,
        alpha=alpha,
        filter_full_feed=filter_full_feed,
        ip_version=ip_version,
        v4_threshold=v4_threshold,
        v6_threshold=v6_threshold,
        allowed_viewpoints=allowed_viewpoints
    )
    conn.close()
    return scores, vps


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
    suffix = f"0000.{ip_version}.origin_as.{asn}.txt"
    relevant_files = [f for f in files if f.startswith("output_bview.") and f.endswith(suffix)]

    if not relevant_files:
        return None, None

    dates = [f.split(".")[1] for f in relevant_files]
    return min(dates), max(dates)

def get_all_dates_available_for_asn_data(asn, rrc_used, ip_version, start_date=None):
    path = f"{ROOT_DIR}/{rrc_used}/"
    files = os.listdir(path)
    suffix = f"0000.{ip_version}.origin_as.{asn}.txt"
    relevant_files = [f for f in files if f.startswith("output_bview.") and f.endswith(suffix)]

    if not relevant_files:
        return []

    dates = [f.split(".")[1] for f in relevant_files]

    if start_date:
        dates = [d for d in dates if d >= start_date]

    return sorted(dates)


def get_interval_dates_for_asn_data(
    asn, rrc_used, ip_version, month_interval, start_date=None, time_interval_acceptance=10
):
    path = f"{ROOT_DIR}/{rrc_used}/"
    files = os.listdir(path)
    suffix = f"0000.{ip_version}.origin_as.{asn}.txt"
    relevant_files = [f for f in files if f.startswith("output_bview.") and f.endswith(suffix)]

    if not relevant_files:
        return []

    dates = [f.split(".")[1] for f in relevant_files]

    if start_date:
        dates = [d for d in dates if d >= start_date]
        
    if not dates:
        return []

    sorted_dates = sorted(dates)
    
    # Convert string dates to datetime objects for easy distance math
    available_dts = [datetime.strptime(d, "%Y%m%d") for d in sorted_dates]
    
    final_dates = []
    
    # 1. Always append the first available valid date
    final_dates.append(available_dts[0].strftime("%Y%m%d"))
    
    # 2. Set the first ideal target (e.g., exactly +6 months from the first date)
    current_target = available_dts[0] + relativedelta(months=month_interval)
    max_date = available_dts[-1]
    
    # Keep generating targets until we exceed our available dataset
    while current_target <= max_date + timedelta(days=time_interval_acceptance):
        
        # Find the single closest available date to our ideal current_target
        closest_dt = min(available_dts, key=lambda d: abs((d - current_target).days))
        
        # Check if the closest date falls within our acceptance window
        if abs((closest_dt - current_target).days) <= time_interval_acceptance:
            closest_str = closest_dt.strftime("%Y%m%d")
            
            # Prevent adding duplicates or going backwards (can happen if intervals/windows overlap)
            last_added_dt = datetime.strptime(final_dates[-1], "%Y%m%d")
            if closest_dt > last_added_dt:
                final_dates.append(closest_str)
                
        # Advance the ideal target perfectly to the next interval (prevents drifting)
        current_target += relativedelta(months=month_interval)

    return final_dates


def load_hegemony_for_date(asn, alpha, rrc_used, date, ip_version, allowed_viewpoints=None):
    db_path = f"huge_bgp_cache_{rrc_used}_{date}_{ip_version}_{asn}.db"
    path = f"{ROOT_DIR}/{rrc_used}/output_bview.{date}.0000.{ip_version}.origin_as.{asn}.txt"
    
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
    db_path = f"huge_bgp_cache_{rrc_used}_{date}_{ip_version}_{asn}.db"
    path = f"{ROOT_DIR}/{rrc_used}/output_bview.{date}.0000.{ip_version}.origin_as.{asn}.txt"
    
    if not os.path.exists(db_path):
        parser = LargeBViewParser(db_path=db_path, ip_version=ip_version)
        parser.parse_to_disk(path)
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Total prefixes seen per viewpoint in this snapshot (unfiltered by reachable_as)
    cursor.execute("""
        SELECT viewpoint_peer, COUNT(DISTINCT prefix) 
        FROM bgp_mappings 
        GROUP BY viewpoint_peer
    """)
    vp_table_sizes = {vp: size for vp, size in cursor.fetchall()}

    # 2. Query ALL viewpoints present in the snapshot
    cursor.execute("SELECT DISTINCT viewpoint_peer FROM bgp_mappings")
    all_vps = {row[0] for row in cursor.fetchall()}
    conn.close()

    if not filter_full_feed:
        return all_vps

    # If parsing origin-filtered files, lower thresholds or check presence
    chosen_threshold = v4_threshold if ip_version == "v4" else 1  # Adjusted for single-origin files
    
    active_vps = {
        vp for vp, size in vp_table_sizes.items() 
        if size >= chosen_threshold
    }

    return active_vps


def select_best_date_in_window(
    asn: int,
    rrc_used: str,
    ip_version: str,
    current_idx: int,
    all_dates: List[str],
    window_size: int,
    filter_full_feed: bool = True
) -> str: 
    if window_size <= 0:
        return all_dates[current_idx]

    # Look ahead up to `window_size` available entries in all_dates
    candidate_dates = all_dates[current_idx : current_idx + window_size + 1]

    best_date = candidate_dates[0]
    max_monitors = -1

    for d in candidate_dates:
        # Verify raw text file exists before trying to parse/count viewpoints
        raw_path = f"{ROOT_DIR}/{rrc_used}/output_bview.{d}.0000.{ip_version}.origin_as.{asn}.txt"
        if not os.path.exists(raw_path):
            continue

        try:
            vps = get_active_viewpoints_for_date(
                asn, rrc_used, d, ip_version, filter_full_feed=filter_full_feed
            )
            monitor_count = len(vps)
            if monitor_count > max_monitors:
                max_monitors = monitor_count
                best_date = d
        except Exception as e:
            print(f"[WARNING] Could not count monitors for date {d}: {e}")
            continue

    return best_date


def compare_hegemony_for_two_dates(
    asn, alpha, rrc_used, ip_version, date_before, date_after, use_strict_viewpoint_filtering: bool = False,
    use_free_viewpoint_filtering: bool = False,
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
        if use_free_viewpoint_filtering:
            print("[VIEWPOINTS] Free viewpoint filtering enabled: Using all active viewpoints for each date independently.")
            hegemony_scores_before, _ = load_hegemony_for_date(
                        asn, alpha, rrc_used, date_before, ip_version
                    )
                    
            hegemony_scores_after, _ = load_hegemony_for_date(
                        asn, alpha, rrc_used, date_after, ip_version
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


def get_hegemony_scores(
    asn, 
    rrc_used, 
    ip_version, 
    date_list, 
    alpha, 
    use_strict_viewpoint_filtering, 
    use_free_viewpoint_filtering=False,
    use_best_next_days: int = 0
):
    hegemony_scores_dict = {} 
    viewpoint_counts_dict = {}
     
    selected_dates = []
    if use_best_next_days > 0:
        print(f"[BEST DAYS] Evaluating next {use_best_next_days} days to select snapshot with max monitors...")
        for i, current_date in enumerate(date_list):
            best_d = select_best_date_in_window(
                asn, rrc_used, ip_version, i, date_list, use_best_next_days
            )
            selected_dates.append(best_d)
            print(f"[BEST DAYS] Date {current_date} -> Selected {best_d}")
    else:
        selected_dates = list(date_list)

    # Track valid dates
    valid_date_list = selected_dates
    allowed_viewpoints_baseline = None
    
    if use_strict_viewpoint_filtering:
        print(f"[VIEWPOINTS] Computing strict viewpoint intersection across all {len(valid_date_list)} dates...")
        
        date_to_vps = {
            snapshot: get_active_viewpoints_for_date(asn, rrc_used, snapshot, ip_version)
            for snapshot in valid_date_list
        }
        
        valid_date_list = [
            date for date in valid_date_list 
            if len(date_to_vps[date]) > 3
        ]
        
        dropped_count = len(selected_dates) - len(valid_date_list)
        if dropped_count > 0:
            print(f"[VIEWPOINTS] Strict mode dropped {dropped_count} snapshot(s) with 3 or fewer monitors.")
            
        if not valid_date_list:
            print("[VIEWPOINTS] All snapshots were dropped under strict mode filtering.")
            return {}, {}, []

        active_sets = [date_to_vps[date] for date in valid_date_list]
        allowed_viewpoints_baseline = set.intersection(*active_sets)
        print(f"[VIEWPOINTS] Strict viewpoint filtering retained {len(allowed_viewpoints_baseline)} viewpoints across {len(valid_date_list)} snapshots.")

    for date in valid_date_list:
        if allowed_viewpoints_baseline is not None:
            scores, active_vps = load_hegemony_for_date(
                asn, alpha, rrc_used, date, ip_version,
                allowed_viewpoints=allowed_viewpoints_baseline
            )
        elif use_free_viewpoint_filtering:
            scores, active_vps = load_hegemony_for_date(
                asn, alpha, rrc_used, date, ip_version
            )
        else:
            if 'first_vps' not in locals():
                scores, active_vps = load_hegemony_for_date(asn, alpha, rrc_used, date, ip_version)
                first_vps = active_vps
            else:
                scores, active_vps = load_hegemony_for_date(
                    asn, alpha, rrc_used, date, ip_version, allowed_viewpoints=first_vps
                )

        hegemony_scores_dict[date] = scores
        viewpoint_counts_dict[date] = len(active_vps)

    return hegemony_scores_dict, viewpoint_counts_dict, valid_date_list


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
    asn, alpha, rrc_used, ip_version, date_list, use_strict_viewpoint_filtering: bool = False,
    use_free_viewpoint_filtering=False,
    show_collector_count_over_time: bool = False,
    use_best_next_days: int = 0,
    show_as_percentage: bool = False
):
    # 1. Unpack valid_date_list alongside scores and counts
    hegemony_scores_dict, viewpoint_counts_dict, valid_date_list = get_hegemony_scores(
        asn, rrc_used, ip_version, date_list, alpha, use_strict_viewpoint_filtering,
        use_free_viewpoint_filtering=use_free_viewpoint_filtering,
        use_best_next_days=use_best_next_days
    )

    if not valid_date_list:
        print("[WARNING] No valid snapshots available to process.")
        return

    # 2. Pass valid_date_list (not date_list) to compute top ASNs over time
    top_fives_over_time, unique_asns_list = get_top_five_asns_over_time(
        hegemony_scores_dict, valid_date_list
    )

    # Calculate total hegemony for each snapshot date
    total_hegemony_per_date = [
        sum(hegemony_scores_dict[date].values()) for date in valid_date_list
    ]

    # 3. Use valid_date_list to build monitor counts
    monitor_counts = [viewpoint_counts_dict[date] for date in valid_date_list]

    # Check if monitor count is strictly constant across all dates
    is_monitor_constant = len(set(monitor_counts)) == 1 if monitor_counts else False
    constant_monitor_val = monitor_counts[0] if is_monitor_constant else None

    # Create figure and primary y-axis
    fig, ax1 = plt.subplots(figsize=DEFAULT_FIGSIZE)

    # --- Secondary Y-Axis for AS Monitors (Bar Plot) ---
    bars = None
    # Only draw bars if enabled AND the count actually varies over time
    if show_collector_count_over_time and not is_monitor_constant:
        ax2 = ax1.twinx()
        bars = ax2.bar(
            valid_date_list,
            monitor_counts,
            color="tab:gray",
            alpha=0.3,
            width=0.4,
            label="AS Monitors Count",
        )
        ax2.set_ylabel("Number of AS Monitors", fontsize=12, color="tab:gray")
        ax2.tick_params(axis="y", labelcolor="tab:gray")
        ax2.grid(False)

    # --- Line Plot for Top AS Hegemony Scores ---
    line_styles = ["-", "--", ":", "-."]
    markers = ["o", "s", "^", "v", "D", "X", "P"]

    base_linewidth = 6.0
    width_step = 0.8
    lines = []

    for i, target_asn in enumerate(unique_asns_list):
        scores_for_asn = []
        for d_idx in range(len(valid_date_list)):
            val = top_fives_over_time[d_idx][i]
            if show_as_percentage:
                tot = total_hegemony_per_date[d_idx]
                val = (val / tot * 100.0) if tot > 0 else 0.0
            scores_for_asn.append(val)

        lw = max(1.5, base_linewidth - (i * width_step))
        ls = line_styles[i % len(line_styles)]
        mk = markers[i % len(markers)]
        alpha_val = 0.75 if lw > 3.0 else 1.0

        (line,) = ax1.plot(
            valid_date_list,
            scores_for_asn,
            marker=mk,
            markersize=7 - (i * 0.4),
            linewidth=lw,
            linestyle=ls,
            alpha=alpha_val,
            label=f"ASN {target_asn}",
        )
        lines.append(line)

    # Axis Labels & Aesthetics
    ax1.set_xlabel("Date", fontsize=12)
    y_label = "Hegemony (%)" if show_as_percentage else "Hegemony Score"
    ax1.set_ylabel(y_label, fontsize=12)
    
    title_metric = "Hegemony Percentage" if show_as_percentage else "Hegemony Scores"
    
    # Adapt title depending on whether monitor count is static or dynamic
    if is_monitor_constant:
        title_str = (
            f"{title_metric} Over Time for Top ASNs [Monitors Constant: {constant_monitor_val}]\n"
            f"(Target ASN: {asn}, RRC: {rrc_used}, IP: {ip_version}, α={alpha})"
        )
    else:
        title_str = (
            f"{title_metric} Over Time for Top ASNs & Monitor Count\n"
            f"(Target ASN: {asn}, RRC: {rrc_used}, IP: {ip_version}, α={alpha})"
        )

    ax1.set_title(title_str, fontsize=14)
    ax1.tick_params(axis="x", rotation=45)
    ax1.grid(True, linestyle="--", alpha=0.5)

    # Combine legends
    all_handles = list(lines)
    if bars is not None:
        all_handles.append(bars)
        
    all_labels = [h.get_label() for h in all_handles]
    ax1.legend(
        all_handles,
        all_labels,
        bbox_to_anchor=(1.15, 1),
        loc="upper left",
        title="Metrics",
    )

    plt.tight_layout()
    plt.show()

    save_plot(
        fig=fig, title=f"hegemony_over_time_{asn}_{rrc_used}_{ip_version}.png"
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
    use_strict_viewpoint_filtering = True # only viewpoints that existed in all snapshots
    use_free_viewpoint_filtering = False # all viewpoints available for each snapshot independently
    show_collector_count_over_time = False 
    show_as_percentage = True

    for config in configs:
        rrc_used = config["rrc_used"]
        ip_version = config["ip_version"]
        asn = config["asn"]
        start_date = config["start_date"]
        use_best_next_days = config["use_best_next_days"]

        print(f"\n[INFO] Processing ASN {asn} for RRC {rrc_used} ({ip_version.upper()}) with start date {start_date} and best next days {use_best_next_days}...")

        date_before, date_after = get_first_and_last_date_available_for_asn_data(asn, rrc_used, ip_version)

        compare_hegemony_for_two_dates(
            asn, alpha, rrc_used, ip_version, date_before, date_after, 
            use_strict_viewpoint_filtering=use_strict_viewpoint_filtering,
            use_free_viewpoint_filtering=use_free_viewpoint_filtering,
        )

        
        # dates =  get_all_dates_available_for_asn_data(asn, rrc_used, ip_version, start_date=start_date)
        dates = get_interval_dates_for_asn_data(asn, rrc_used, ip_version, month_interval=6, start_date=start_date)

        compare_hegemony_for_several_dates(
            asn, alpha, rrc_used, ip_version, dates,
            use_strict_viewpoint_filtering=use_strict_viewpoint_filtering,
            use_free_viewpoint_filtering=use_free_viewpoint_filtering,
            use_best_next_days=use_best_next_days,
            show_collector_count_over_time=show_collector_count_over_time,
            show_as_percentage=show_as_percentage,
        )

        compare_vpp_and_non_vpp_hegemony_over_time(
            asn, alpha, rrc_used, ip_version, dates,
            use_strict_viewpoint_filtering=use_strict_viewpoint_filtering,
            #use_free_viewpoint_filtering=use_free_viewpoint_filtering,
            use_best_next_days=use_best_next_days,
            show_as_percentage=show_as_percentage,
        )