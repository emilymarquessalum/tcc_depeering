



import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
# step 1: get ASes that are oscillating, and the period of time they oscillated for.
# step 2: also get ASes that left and did not come back.
# step 3: for each AS, call a function that will look in 
#         CAIDA PeeringDB to check if at any point that de-peering was registered. Since most 
#         oscillations are very short, its likely not registered. What is interesting is that 
#         we can look at the "outliers" (ASes that oscillated for a longer period of time) and 
#         show that "most ASes that oscillate longer do leave the Route Server in a relevant way, 
#         enough to be registered in CAIDA PeeringDB". 
#         But what if the distribution is like "most ASes that oscillate for a medium ammount of time dont 
#         show up in CAIDA PeeringDB, but most ASes that oscillate for a long time do show up in CAIDA PeeringDB"? 



# it would beinteresting to have an answer for "when an AS stops announcing routes, 
# how long does it take for CAIDA PeeringDB to be updated to reflect that de-peering?" -> 
# when at all

# lets say we find that the ASes that take the longest to come back are 
# small ASes. We can confirm better what that coming-back means by looking at CAIDA PeeringDB. 
# Did this AS even get aknoledged as having de-peered? If not, then really what we showed 
# is that small ASes can almost be completely "ignored". It doesnt really matter if a small 
# AS is not announcing routes for a while, to the number of ASes in the IXP. Also peering news about
# Small ASes is mostly irrelevant either way.

# what about big ASes? we can focus on those... and if they take longer, we bring up this metric
# to basically say "in 80% of the times a big AS stops announcing, PeeringDB is eventually 
# updated to say it de-peered from the IXP". This gives us confidence that 
# seeing a big AS stop announcing is actually big news, and can be shown with more urgency in 
# peering news.



from src.utils.graphs import plot_stacked_bar_plot

from src.caidapeeringdb.caidapeeringdb_load import get_data, get_file_from_date, is_asn_in_ixp
from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data_timeline_from_configs
from src.ripe_bviews.download_and_parse.load_configs import load_configs 
from src.ripe_bviews.oscillations.bview_oscillation_logic import calculate_oscillation_metrics
from src.ripe_bviews.timeline.bview_vars import get_ip_version


if __name__ == "__main__":

    config = load_configs("ixbr.json")
    config = load_configs("AMS-IX.json")
    ip_version = get_ip_version(config)

    time_between_snapshots_hours = config.get("time_delta_hours", 0)
    time_between_day_delta = config.get("day_delta", 0)
    all_stats, labels = load_bview_data_timeline_from_configs(config, ip_version=ip_version)

    last_date_str = labels[-1]
    last_date_formatted = "20"+last_date_str[:8].replace("/", "_") 
    print(f"Last date in BView data: {last_date_formatted}")
    last_date_peeringdb_data = get_data(get_file_from_date(last_date_formatted)) 

    metrics = calculate_oscillation_metrics(all_stats) 
    metrics.load_oscillating_lists()

    ases_that_did_not_come_back_announcing_routes = metrics.all_did_not_come_back_events

    asn_in_ixp_data = []
    for asn, last_index in ases_that_did_not_come_back_announcing_routes:
        last_date_asn_was_seen = labels[last_index]

        is_in_ixp = is_asn_in_ixp(asn, config["peeringdb_ixp_id"], last_date_peeringdb_data)
        asn_in_ixp_data.append((asn, is_in_ixp, last_index))
 
    
    total_ases_that_did_not_come_back = len(ases_that_did_not_come_back_announcing_routes)
    ases_that_did_not_come_back_and_are_in_ixp = sum(1 for asn, in_ixp, idx in asn_in_ixp_data if in_ixp)

    print(f"Total ASes that did not come back announcing routes: {total_ases_that_did_not_come_back}")
    print(f"ASes that did not come back announcing routes and are in the IXP according to PeeringDB: {ases_that_did_not_come_back_and_are_in_ixp}")
    
    # Group ASes by time since they stopped announcing routes
    time_buckets = {}
    for asn, is_in_ixp, last_index in asn_in_ixp_data:
        time_since_stop = len(labels) - 1 - last_index
        if time_since_stop not in time_buckets:
            time_buckets[time_since_stop] = {"in_ixp": 0, "not_in_ixp": 0}
        
        if is_in_ixp:
            time_buckets[time_since_stop]["in_ixp"] += 1
        else:
            time_buckets[time_since_stop]["not_in_ixp"] += 1
    
    # Sort by time since stop and prepare data for plotting
    sorted_times = sorted(time_buckets.keys())
    x_labels = [f"{t} snapshots" for t in sorted_times]
    in_ixp_counts = [time_buckets[t]["in_ixp"] for t in sorted_times]
    not_in_ixp_counts = [time_buckets[t]["not_in_ixp"] for t in sorted_times]
    
    plot_stacked_bar_plot(
        data_lists=[in_ixp_counts, not_in_ixp_counts],
        labels=["Still Registered in IXP", "Not in IXP"],
        x_labels=x_labels,
        title="ASes - Status in PeeringDB, " \
        "Grouped by Time Since They Stopped Announcing Routes - AMS-IX from " + labels[0][:8].replace("/", "_") + " to " + labels[-1][:8].replace("/", "_") + ", " + str(time_between_day_delta) + " days at a time",
        xlabel="Time since AS stopped announcing routes",
        ylabel="Number of ASes",
        subfolder="oscillations",
        sort_by_size=False
    )
