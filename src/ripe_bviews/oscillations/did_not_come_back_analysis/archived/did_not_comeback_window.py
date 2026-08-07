import sys
from pathlib import Path

# Fix path to match your project structure
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data_timeline_from_configs
from src.ripe_bviews.download_and_parse.load_configs import load_configs
from src.ripe_bviews.timeline.bview_vars import get_ip_version
from src.utils.graphs import plot_list_as_bar_plot

def get_dncb_asns_in_window(all_stats, start_idx, end_idx, use_reachables=False):
    """
    Finds ASes that were present at the start of a window 
    but disappeared and never returned within that specific window.
    """
    attr_name = "unique_reachables" if use_reachables else "unique_members"
    
    # Get the baseline set of ASes alive at the start snapshot of the window
    starting_asns = getattr(all_stats[start_idx], attr_name).copy()
    
    # Remove any ASes that are seen in any subsequent snapshot within this window
    for idx in range(start_idx + 1, end_idx + 1):
        active_asns = getattr(all_stats[idx], attr_name)
        starting_asns -= active_asns
        
    return starting_asns

if __name__ == "__main__":
    # 1. Load Configurations and Timeline Data
    config = load_configs("ixbr.json")
    ip_version = get_ip_version(config) 
    all_stats, labels = load_bview_data_timeline_from_configs(config, ip_version=ip_version)     
    
    # 2. Window Configuration
    safe_snapshots = 3  # Step size (n) for the evaluation window
    use_reachables = False  # Set to True if analyzing unique_reachables
    
    num_snapshots = len(all_stats)
    
    window_labels = []
    dncb_counts_per_window = []
    
    print(f"--- Running Windowed DNCB Analysis (n = {safe_snapshots}) ---")
    
    # 3. Slide through the timeline n-by-n
    for start_idx in range(0, num_snapshots - 1, safe_snapshots):
        # Ensure the window does not overshoot the total snapshots available
        end_idx = min(start_idx + safe_snapshots, num_snapshots - 1)
        
        # Avoid processing final dangling indexes that can't form a meaningful window
        if start_idx == end_idx:
            break
            
        # Get ASes that left and didn't come back within this range
        dncb_asns = get_dncb_asns_in_window(all_stats, start_idx, end_idx, use_reachables=use_reachables)
        
        # Create a clean label representing the snapshot window boundaries
        window_range_str = f"S{start_idx}→S{end_idx}"
        window_labels.append(window_range_str)
        dncb_counts_per_window.append(len(dncb_asns))
        
        print(f"Window [{window_range_str}]: {len(dncb_asns)} ASes permanently left this window interval.")

    # 4. Visualize the Windowed Dropouts
    plot_list_as_bar_plot(
        window_labels,
        y=dncb_counts_per_window,
        title=f"{config.get('name', 'IXP')} - ASes that Permanently Left (Did Not Come Back) within {safe_snapshots}-Snapshot Windows",
        xlabel="Snapshot Windows",
        ylabel="Number of Permanent Drops within Window",
        subfolder="oscillations"
    )