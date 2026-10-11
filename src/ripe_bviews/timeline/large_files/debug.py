import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from definitions import ROOT_DIR
from bview_sqlite_parser import (
    _resolve_rrc_dir,
    get_all_dates_available_for_asn_data,
    get_active_viewpoints_for_date,
    load_hegemony_for_date,
    LargeBViewParser,
)


def run_debug_pipeline(asn: int = 15169, rrc_used: str = "rrc03", ip_version: str = "v4"):
    print("=" * 60)
    print(" BVIEW & HEGEMONY PIPELINE DEBUGGER")
    print("=" * 60)

    # --- STEP 1: PATH RESOLUTION ---
    print("\n[STEP 1] Checking Path Resolution...")
    print(f" - ROOT_DIR from definitions.py: {ROOT_DIR}")
    resolved_rrc_path = _resolve_rrc_dir(rrc_used)
    print(f" - Resolved path for {rrc_used}: {resolved_rrc_path}")
    
    if not os.path.exists(resolved_rrc_path):
        print(f" [FAIL] Directory {resolved_rrc_path} DOES NOT exist!")
        return
    print(f" [PASS] Directory {resolved_rrc_path} exists.")

    # --- STEP 2: DATE DISCOVERY ---
    print("\n[STEP 2] Testing Date Discovery...")
    found_dates = get_all_dates_available_for_asn_data(asn, rrc_used, ip_version)
    print(f" - Found {len(found_dates)} available date snapshot(s) for ASN {asn} ({ip_version.upper()}):")
    print(f"   {found_dates[:10]}")
    
    if not found_dates:
        print(f" [FAIL] No dates discovered in {resolved_rrc_path}. Listing sample directory files:")
        sample_files = os.listdir(resolved_rrc_path)[:10]
        for f in sample_files:
            print(f"   -> {f}")
        return
    print(" [PASS] Dates discovered successfully.")

    target_date = found_dates[0]
    print(f"\n---> Proceeding with testing using snapshot date: {target_date}")

    # --- STEP 3: FILE PARSING TO DISK ---
    print("\n[STEP 3] Testing File Parsing & SQLite Cache Creation...")
    expected_db = f"huge_bgp_cache_{rrc_used}_{target_date}_{ip_version}_{asn}.db"
    
    # Try finding the raw text file
    raw_path = os.path.join(resolved_rrc_path, f"output_bview.{target_date}.0000.{ip_version}.origin_as.{asn}.txt")
    if not os.path.exists(raw_path):
        raw_path = os.path.join(resolved_rrc_path, f"output_bview.{target_date}.0000.origin_as.{asn}.txt")
        
    print(f" - Target Raw File: {raw_path}")
    print(f" - Raw File Exists: {os.path.exists(raw_path)}")
    
    if not os.path.exists(raw_path):
        print(" [FAIL] Raw file not found at expected path.")
        return

    try:
        if os.path.exists(expected_db):
            print(f" - Removing existing test DB: {expected_db}")
            os.remove(expected_db)
            
        parser = LargeBViewParser(db_path=expected_db, ip_version=ip_version)
        parser.parse_to_disk(raw_path, limit=5000)  # Parse first 5000 lines for quick test
        print(f" [PASS] Successfully parsed lines into {expected_db}.")
    except Exception as e:
        print(f" [FAIL] Exception during file parsing: {e}")
        return

    # --- STEP 4: VIEWPOINTS & HEGEMONY COMPUTATION ---
    print("\n[STEP 4] Testing Viewpoint Extraction & Hegemony Score Calculation...")
    try:
        active_vps = get_active_viewpoints_for_date(asn, rrc_used, target_date, ip_version)
        print(f" - Extracted Active Viewpoints Count: {len(active_vps)}")
        print(f"   Sample Viewpoints: {list(active_vps)[:5]}")
        
        if len(active_vps) == 0:
            print(" [WARNING] Active viewpoints count is 0. Threshold/prefix table size filtering might be dropping all views.")

        scores, retained_vps = load_hegemony_for_date(asn, 0.34, rrc_used, target_date, ip_version)
        print(f" - Calculated Hegemony Scores for {len(scores)} transit ASNs.")
        
        sorted_transits = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]
        print(" - Top 5 Hegemony Scores:")
        for transit, score in sorted_transits:
            print(f"   * AS{transit}: {score:.4f}")
            
        print(" [PASS] Hegemony calculation completed successfully!")
    except Exception as e:
        print(f" [FAIL] Exception during Hegemony calculation: {e}")
        return

    #print("\n=" * 60)
    print(" DEBUGGER FINISHED: ALL PIPELINE STAGES FUNCTIONAL")
    print("=" * 60)


if __name__ == "__main__":
    run_debug_pipeline(asn=15169, rrc_used="rrc03", ip_version="v4")