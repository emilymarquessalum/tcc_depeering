import sys 
from pathlib import Path

from src.ripe_bviews.routeserver.bview_timeline_lookingglass import bview_looking_glass
from src.ripe_bviews.timeline.bview_new_members import bview_new_members 


sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))  


from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_asn_data_timeline_from_configs
from src.ripe_bviews.timeline.as_info_type.bview_timeline_by_as_info_type import analyze_bview_by_as_info_type

from src.ripe_bviews.timeline.bview_load import bview_load_data, bview_load_data_routeviews, load_asn_collector_rrc_data
from src.ripe_bviews.timeline.bview_timeline_prefixes import bview_prefix_check, bview_prefixes, bview_prefixes_ranking   
from src.ripe_bviews.timeline.bview_timeline_by_ip_version import bview_timeline_ip_version 
from src.ripe_bviews.timeline.bview_timeline_as import check_asn_connection, check_asn_connection_for_relevant_ases
from src.ripe_bviews.timeline.bview_timeline_reachable_metrics import bview_reachable_metrics
from src.ripe_bviews.oscillations.bview_timeline_oscillation_metrics import bview_oscillations
from src.caidapeeringdb.caidapeeringdb_load import get_most_recent_data
from src.ripe_bviews.timeline.bview_hegemony import bview_as_hegemony_analysis, bview_hegemony_of_current_ixp
from src.ripe_bviews.timeline.bview_as_depeer_relevance import bview_depeering 
from src.ripe_bviews.timeline.bview_timeline_routes import bview_timeline_routes
from src.ripe_bviews.timeline.bview_timeline_vpps_compare import bview_check_for_vpps
from src.ripe_bviews.timeline.variability import print_variability_metrics


from src.ripe_bviews.timeline.bview_timeline import bview_ranking, bview_timeline
from src.ripe_bviews.timeline.render.bview_requirements import load_all_routeviews_timelines_first_date, load_all_routeviews_timelines_first_date_function, load_oscillations, load_timeline, load_timeline_weekly

def _get_most_recent_caida_data(config, ip_version, all_stats=None):
    return get_most_recent_data()



 
requirement_functions = {
    "timeline": load_timeline,
    "timeline_weekly": load_timeline_weekly,
    "all_routeviews_timelines_first_date": load_all_routeviews_timelines_first_date,
    "oscillations": load_oscillations,
    "caida_data": _get_most_recent_caida_data,
    "load_bview_asn_data_timeline_from_configs": load_bview_asn_data_timeline_from_configs,
}
 
functionalities = [
    {
        "name": "load",
        "description": "Data loading options...",
        "submenu": [
            {"name": "load_data", "function": bview_load_data, "description": "Load data from API based on config", "requirements": []},
            {"name": "load_routeviews_data", "function": bview_load_data_routeviews, "description": "Load and analyze RouteViews data over time", "requirements": []},
            {"name": "load-first-date-of-routeviews-timelines", "function": load_all_routeviews_timelines_first_date_function, "description": "Load first date of all RouteViews timelines (used for AS Hegemony analysis)", "requirements": []},

            {"name": "load_asn_collector_rrc_data", "function": load_asn_collector_rrc_data, "description": "Load data from current collector, filtered by ASN", "requirements": []},
        ]
    },
   # {"name": "temp-LACNICtest",     "function": lacnic_delegation_analysis,       "requirements": ["timeline", "caida_data"]},
    {"name": "timeline", "function": bview_timeline, "description": "Members, reachables over time...", "requirements": ["timeline", "timeline_weekly"]}, 
    {"name": "new-members", "function": bview_new_members, "description": "New members over time", "requirements": ["timeline"]},
    {"name": "ranking", "function": bview_ranking, "description": "Rankings, like member reachability...", "requirements": ["timeline", "caida_data"]},
    {"name": "reachability_metrics", "function": bview_reachable_metrics, "description": "Reachability metrics over time", "requirements": ["timeline"]},
    {"name": "route-analysis", "function": bview_timeline_routes, "description": "Routes over time and other analysis", "requirements": ["timeline"]},

    {"name": "Looking Glass", "function": bview_looking_glass, "description": "Access Looking Glass data"},
    
    {"name": "ip-version-timeline", "function": bview_timeline_ip_version, "description": "Timeline comparing by IP version", "requirements": ["caida_data"]},
    {"name": "as-info-type-timeline", "function": analyze_bview_by_as_info_type, "description": "Timeline comparing AS info types (like PeeringDB categories)", "requirements": ["timeline", "caida_data"]},
    {"name": "prefix-timeline", "function": bview_prefixes, "description": "Prefix changes over time", "requirements": ["timeline"]},
    {"name": "prefix-ranking", "function": bview_prefixes_ranking, "description": "Prefix rankings, like concentration of prefixes in a few ASes...", "requirements": ["timeline"]},
    {"name": "prefix-check", "function": bview_prefix_check, "description": "Check which ASes announce a specific prefix over time", "requirements": ["timeline"]},
    {"name": "as-hegemony", "function": bview_as_hegemony_analysis, "description": "AS Hegemony (Centrality) for Routeview IXPs", "requirements": ["all_routeviews_timelines_first_date", "caida_data"]},
    {"name": "as_hegemony_for_ixp",
     "function": bview_hegemony_of_current_ixp, 
     "description": "Hegemony for specified config",
     "requirements": ["timeline", "caida_data", ]
     },
    { 
        "name": "AS-connection",
        "function": check_asn_connection,
        "description": "Check connectivity metrics for a specific ASN",
        "requirements": ["timeline"]
    },
    {
        "name": "AS-connection-relevant-ICPs",
        "function": check_asn_connection_for_relevant_ases,
        "description": "Check connectivity metrics for relevant ICP ASes (Google, Netflix, Meta...)",
        "requirements": ["timeline"]
    },
    {"name": "identify-vpps", "function": bview_check_for_vpps, "description": "Check for presence of Google VPP ASNs over time", "requirements": ["timeline"]},
    
    
    {
        "name": "WIP", 
        "submenu": [
 {"name": "depeering", "function": bview_depeering, "status": "broken", "description": "Depeering events over time"},
    {"name": "oscillations", "function": bview_oscillations, "description": "Oscillations over time", "status": "broken",
        "requirements": ["oscillations", "timeline"]
     },
        ]
    },
    # low relevance analysis
    {"name": "variability", "function": print_variability_metrics, "description": "Calculate and plot variability metrics over time", "requirements": ["timeline", "oscillations"]},
]
