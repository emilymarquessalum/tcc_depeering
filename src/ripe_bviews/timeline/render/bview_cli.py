import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))  



from src.ripe_bviews.timeline.bview_timeline_by_ip_version import bview_timeline_ip_version
from src.ripe_bviews.timeline.bview_timeline_prefixes import bview_prefixes, bview_prefixes_ranking
from src.utils.graphs import create_window_with_all_rendered_graphs_this_session
from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data
from src.ripe_bviews.timeline.bview_vars import get_ip_version   
from src.ripe_bviews.download_and_parse.load_configs import get_all_configs, load_configs
from src.ripe_bviews.timeline.bview_timeline import bview_ranking, bview_route_changes, bview_timeline
from src.ripe_bviews.timeline.render.bview_requirements import load_oscillations, load_timeline, load_timeline_weekly


requirement_functions = {
    "timeline": load_timeline,
    "timeline_weekly": load_timeline_weekly,
    "oscillations": load_oscillations
}
 
functionalities = [
    {
        "name": "load_data",
        "function": load_bview_data,
        "description": "Load data from API based on config",
        "requirements": []
    },
    {
        "name": "timeline",
        "function": bview_timeline,
        "description": "Members, reachables over time",
        "requirements": ["timeline", "oscillations", "timeline_weekly"]
    }, 
    {
         "name": "ip-version-timeline",
         "function": bview_timeline_ip_version,
         "description": "Timeline comparing by IP version",
         "requirements": []
    },
    {
         "name": "ranking",
         "function": bview_ranking,
            "description": "Rankings, like member reachability...",
            "requirements": ["timeline"]
    },
    {
        "name": "route-changes",
        "function": bview_route_changes,
        "description": "Route changes over time",
        "requirements": ["timeline" ]
    },
    {
        "name": "prefix-timeline",
        "function": bview_prefixes,
        "description": "Prefix changes over time",
        "requirements": ["timeline"]
    },
    {
         "name": "prefix-ranking",
         "function": bview_prefixes_ranking,
            "description": "Prefix rankings, like concentration of prefixes in a few ASes...",
            "requirements": ["timeline"]
    },
    {
        "name": "oscillations",
        "function": "oscillations",
        "description": "Oscillations over time"
    }
]

def list_available_functionalities():
    print("-" * 40)
    print("Available functionalities:")
    for func in functionalities:
        print(f"- {func['name']}: {func['description'] if 'description' in func else 'No description available'}")
    print("-" * 40)

all_required_data = {}

last_config_loaded = "NAPAfrica.json"
config = load_configs(last_config_loaded)
all_required_data["config"] = config


def run_functionality(func):
    if func is None:
            print("Invalid functionality. Please try again.")
            return
    
    try:
            # check if requirements are met
            requirements = func.get("requirements", [])
            for req in requirements:
                if req not in all_required_data:
                    print(f"Loading required data for '{req}'...")
                    all_required_data[req] = requirement_functions[req](config=config, ip_version=get_ip_version(config),
                                                                        all_stats=all_required_data.get("timeline")
                                                                        )  # you can modify this to pass actual config and ip_version
    except Exception as e:
            print(f"Error loading required data for functionality '{func['name']}': {e}")
            return


        # now you can call the function with the required data
    print(f"Running functionality '{func['name']}' with required data: {requirements}")
        
    function_to_call = func["function"] 
    function_to_call(all_required_data)

while True:

    print("Enter the functionality you want to run")
    input_str = input("(or 'list' to see available functionalities, 'all' to run all, 'exit' to quit, 'config x' to set config to x, 'configs' to check all available configs, 'window' to see a window with all graphs): ").strip()

    if input_str == "window":
         
        create_window_with_all_rendered_graphs_this_session()
        continue

    if input_str.startswith("configs"):
        config_files = get_all_configs()
        print("Available configs:")
        for cfg in config_files:
            print(f"- {cfg}")
        continue

    if input_str.startswith("config "):
        config_name = input_str.split(" ", 1)[1] 
        if config_name == last_config_loaded:
            print(f"Config is already set to '{config_name}'. No changes made.")
            continue
        try:
            config = load_configs(config_name)
            all_required_data = {}  # reset all required data when config changes
            all_required_data["config"] = config
            last_config_loaded = config_name
            print(f"Config set to '{config_name}', and all required data has been reset.")
        except Exception as e:
            print(f"Error loading config '{config_name}': {e}")
        continue

    if input_str == "exit":
        break

    elif input_str == "list":
        list_available_functionalities()

    elif input_str == "all":
        for func in functionalities:
            run_functionality(func)

    else:
        print("-" * 40)
        func = next((f for f in functionalities if f["name"] == input_str), None)
        run_functionality(func)
        print("-" * 40)
        continue