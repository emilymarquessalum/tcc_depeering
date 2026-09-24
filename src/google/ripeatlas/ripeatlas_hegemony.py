






import datetime
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional

import matplotlib.pyplot as plt


# Ensure root import path matching ripeatlas_google.py and bview_sqlite_parser.py
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.ripe_bviews.timeline.large_files.bview_sqlite_parser import calculate_as_hegemony_from_db
from data_loader import load_measurement_data 
from src.ripe_bviews.timeline.bview_hegemony import get_sorted_asns_from_scores
from src.utils.graphs import DEFAULT_FIGSIZE, save_plot


def build_sqlite_db_from_atlas_data(
    measurement_data: List[dict], 
    target_asn: int, 
    db_path: str = ":memory:"
) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
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
    
    records = []
    
    # Flatten measurement list if nested
    flat_data = []
    for item in measurement_data:
        if isinstance(item, list):
            flat_data.extend(item)
        else:
            flat_data.append(item)
    
    for meas in flat_data:
        # Extract Probe ID / Viewpoint
        probe_id = meas.get("probe_id") or meas.get("prb_id") or meas.get("msm_id")
        if not probe_id:
            continue
        viewpoint_peer = str(probe_id)
        
        # Extract AS Path
        as_path = meas.get("as_path") or meas.get("asn_path")
        if not as_path:
            # Fallback check inside hops if present
            hops = meas.get("result", [])
            as_path = []
            for h in hops:
                asn = h.get("asn")
                if asn and (not as_path or as_path[-1] != asn):
                    as_path.append(int(asn))
                    
        if not as_path:
            continue
            
        # Ensure path items are integers
        try:
            as_path = [int(x) for x in as_path]
        except (ValueError, TypeError):
            continue

        # Extract Target / Reachable ASN
        reachable_as = target_asn if target_asn in as_path else as_path[-1]
        
        # Extract target prefix or default to dummy prefix per measurement
        dst_addr = meas.get("dst_addr") or meas.get("dst_name") or "0.0.0.0/32"
        prefix = meas.get("prefix", dst_addr)
        
        prefix_weight = 1.0  # Equal path weight for individual traceroute runs
        as_path_encoded = ",".join(map(str, as_path))
        
        records.append((
            viewpoint_peer,
            reachable_as,
            prefix,
            prefix_weight,
            as_path_encoded,
            ""
        ))
        
    cursor.executemany(
        "INSERT INTO bgp_mappings VALUES (?, ?, ?, ?, ?, ?);", 
        records
    )
    conn.commit()
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_vp ON bgp_mappings(viewpoint_peer);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reachable ON bgp_mappings(reachable_as);")
    conn.commit()
    
    return conn


def calculate_ripeatlas_hegemony(
    measurement_data: List[dict], 
    target_asn: int, 
    alpha: float = 0.34
) -> Tuple[Dict[int, float], Set[str]]:
    """
    Computes Hegemony score based on RIPE Atlas measurements.
    """
    conn = build_sqlite_db_from_atlas_data(measurement_data, target_asn, db_path=":memory:")
    
    # Calculate hegemony via SQLite engine
    scores, active_vps = calculate_as_hegemony_from_db(
        conn=conn,
        target_asn=target_asn,
        alpha=alpha,
        filter_full_feed=False,  # Atlas probe endpoints don't require full BGP table thresholds
        ip_version="v4",
        v4_threshold=1
    )
    
    conn.close()
    return scores, active_vps


def plot_ripeatlas_hegemony(
    hegemony_scores: Dict[int, float], 
    target_asn: int, 
    top_n: int = 10
):
    """
    Plots the top N transit ASNs calculated by RIPE Atlas Hegemony.
    """
    sorted_asns = get_sorted_asns_from_scores(hegemony_scores)[:top_n]
    if not sorted_asns:
        print("No hegemony scores calculated.")
        return

    scores = [hegemony_scores[asn] for asn in sorted_asns]
    asn_labels = [f"ASN {asn}" for asn in sorted_asns]

    fig, ax = plt.subplots(figsize=DEFAULT_FIGSIZE)
    ax.bar(asn_labels, scores, color="skyblue", edgecolor="navy")
    ax.set_ylabel("Hegemony Score")
    ax.set_xlabel("Transit ASNs")
    ax.set_title(f"Top {top_n} Transit AS Hegemony Scores for Target ASN {target_asn} (RIPE Atlas)")
    ax.grid(True, linestyle="--", alpha=0.5)
    
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    google_ases_for_search = [15169]
    probe_ids = [10515, 10704]

    start_date = datetime.datetime(2024, 1, 1)
    end_date = datetime.datetime(2024, 6, 1)
    type_exclusion_filter = "dns"
    SAMPLE_SEED_OFFSET = 10
    day_delta = datetime.timedelta(days=31)
    alpha = 0.34

    for asn in google_ases_for_search:
        print(f"\nLoading RIPE Atlas measurement data for ASN {asn}...")
        measurement_counts, dates_in_plot, measurement_data = load_measurement_data(
            start_date, 
            end_date, 
            asn, 
            type_exclusion_filter, 
            day_delta, 
            seed_offset=SAMPLE_SEED_OFFSET,
            sample_size=300
            #probe_ids=probe_ids
        )
        
        print(f"Loaded {len(measurement_data)} measurements across probes.")
        
        hegemony_scores, active_vps = calculate_ripeatlas_hegemony(
            measurement_data, 
            target_asn=asn, 
            alpha=alpha
        )
        
        print(f"\nActive Probes/Viewpoints count: {len(active_vps)}")
        print("\nTop 10 Hegemony Transit ASNs:")
        sorted_transits = get_sorted_asns_from_scores(hegemony_scores)[:10]
        for t_asn in sorted_transits:
            print(f"  ASN {t_asn}: {hegemony_scores[t_asn]:.4f}")

        plot_ripeatlas_hegemony(hegemony_scores, target_asn=asn, top_n=10)
