import sys 
from pathlib import Path
import inquirer
import os
import threading
import time
from colorama import init, Fore, Style
import requests


# Initialize colorama
init(autoreset=True)

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))  

#from src.ripe_bviews.timeline.render.bview_calendar_viz import DataAvailabilityCalendar
#from src.utils.graphs import create_window_with_all_rendered_graphs_this_session 
from src.ripe_bviews.timeline.bview_vars import get_ip_version   
from src.ripe_bviews.download_and_parse.load_configs import get_all_configs, load_configs
from src.ripe_bviews.timeline.render.bview_functionalities import functionalities, requirement_functions

from inquirer.render.console._list import List as ListRender

# use this only if you want to see all options for demonstration purposes, like
# printing the full list of options. This code will BREAK the menu and command selection as a whole.
'''
set_unrestrained_options()

'''

# --- File-Based Config Cache Logic ---
CONFIG_CACHE_FILE = Path(__file__).parent / ".config_cache"

def load_cached_config(default_config="ixbr.json"):
    """Loads the last saved config name from the cache file, or returns the default."""
    if CONFIG_CACHE_FILE.exists():
        with open(CONFIG_CACHE_FILE, "r", encoding="utf-8") as f:
            cached_name = f.read().strip()
            if cached_name:
                return cached_name
    return default_config

def save_cached_config(config_name):
    """Saves the current config name to the cache file."""
    with open(CONFIG_CACHE_FILE, "w", encoding="utf-8") as f:
        f.write(config_name)


all_required_data = {}
# Dynamically load the last active config instead of always hardcoding "ixbr.json"
last_config_loaded = load_cached_config("ixbr.json")
config = load_configs(last_config_loaded)
all_required_data["config"] = config
 
config_lock = threading.Lock()  # Protects variables shared with the background thread
stop_watcher = False

def get_config_file_path(config_name):
    return Path(__file__).parent.parent.parent / "configs" / config_name

try:
    last_config_mtime = os.path.getmtime(get_config_file_path(last_config_loaded))
except Exception:
    last_config_mtime = 0.0

def background_config_watcher():
    """Thread function that continuously polls the config file for modifications."""
    global config, all_required_data, last_config_mtime
    
    while not stop_watcher:
        time.sleep(1.0)  # Check every 1 second
        
        with config_lock:
            path = get_config_file_path(last_config_loaded)
            if path.exists():
                try:
                    current_mtime = os.path.getmtime(path)
                    if current_mtime > last_config_mtime:
                        config = load_configs(last_config_loaded)
                        all_required_data = {"config": config}
                        last_config_mtime = current_mtime
                        
                        # Use carriage return and ansi clear-line sequence to cleanly break 
                        # into the terminal space without completely ruining inquirer's format.
                        sys.stdout.write("\r\033[K")
                        print(f"{Fore.GREEN}[LIVE SYNC] Synced with new changes to config {last_config_loaded}{Style.RESET_ALL}")
                        sys.stdout.flush()
                except Exception:
                    pass

# Start the background daemon thread
watcher_thread = threading.Thread(target=background_config_watcher, daemon=True)
watcher_thread.start()


# --- File-Based History Cache Logic ---
HISTORY_FILE = Path(__file__).parent / ".history_cache"

def load_history():
    """Loads previously run functions from the history file."""
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_to_history(func_name):
    """Appends a newly run function name to the history file if not already present."""
    if func_name not in history_cache:
        history_cache.add(func_name)
        with open(HISTORY_FILE, "a", encoding="utf-8") as f:
            f.write(f"{func_name}\n")

# Initialize the history cache from the file
history_cache = load_history()


def run_functionality(func):
    if func is None:
        print("Invalid functionality. Please try again.")
        return False
    
    with config_lock:  # Secure current thread frame snapshots
        current_config = config
        current_data = all_required_data.copy()

    try:
        requirements = func.get("requirements", [])
        for req in requirements:
            if req not in current_data:
                print(f"Loading required data for '{req}'...")
                current_data[req] = requirement_functions[req](
                    config=current_config, 
                    ip_version=get_ip_version(current_config),
                    all_stats=current_data.get("timeline")
                )
                # Keep global storage updated
                with config_lock:
                    all_required_data[req] = current_data[req]
    except Exception as e:
        print(f"Error loading required data for functionality '{func['name']}': {e}")
        return False

    print(f"\nRunning functionality '{func['name']}' with required data: {requirements}")
    function_to_call = func["function"] 
    
    if callable(function_to_call):
        function_to_call(current_data)
    else:
        print(f"Placeholder executed for: {function_to_call}")
         
    save_to_history(func["name"])
    return True


def change_config_menu():
    global config, all_required_data, last_config_loaded, last_config_mtime
    config_files = get_all_configs()
    
    if not config_files:
        print("No configuration files found.")
        return

    config_question = [
        inquirer.List(
            'config_file',
            message="Select a configuration file",
            choices=config_files,
            carousel=True
        )
    ]
    answers = inquirer.prompt(config_question)
    if not answers:
        return

    config_name = answers['config_file']
    if config_name == last_config_loaded:
        print(f"Config is already set to '{config_name}'. No changes made.")
        return

    try:
        with config_lock:
            config = load_configs(config_name)
            all_required_data = {"config": config}  # Reset data
            last_config_loaded = config_name
            try:
                last_config_mtime = os.path.getmtime(get_config_file_path(last_config_loaded))
            except Exception:
                last_config_mtime = 0.0
        
        # Save the updated config selection to the cache file
        save_cached_config(config_name)
                
        print(f"Config successfully set to '{config_name}', and required data has been reset.")
    except Exception as e:
        print(f"Error loading config '{config_name}': {e}")


def get_menu_prefix(item):
    """Helper to generate colorized status tags for menu choices."""
    if item.get("status") == "broken":
        return f"{Fore.RED}[BROKEN]{Style.RESET_ALL} "
    elif "submenu" in item:
        return f"{Fore.CYAN}[MENU]{Style.RESET_ALL} "
    elif item['name'] not in history_cache:
        return f"{Fore.YELLOW}[NEW]{Style.RESET_ALL} "
   
    return ""


def handle_submenu(submenu_items, menu_title):
    """Recursively processes submenus when an item contains nested routes."""
    while True:
        choices = []
        for item in submenu_items:
            prefix = get_menu_prefix(item)
            desc = item.get('description', 'No description')
            choices.append((f"{prefix}{item['name']} ({desc})", item['name']))
        
        choices.append((f"{Fore.LIGHTBLACK_EX}<-- Back{Style.RESET_ALL}", "back"))

     
        question = [
            inquirer.List(
                'action',
                message=f"Submenu: {menu_title}",
                choices=choices,
                carousel=True
            )
        ]
        answers = inquirer.prompt(question)
        if not answers or answers['action'] == "back":
            break

        selected_action = answers['action']
        matched_item = next((i for i in submenu_items if i["name"] == selected_action), None)

        if matched_item:
            if "submenu" in matched_item:
                handle_submenu(matched_item["submenu"], matched_item["name"])
            else:
                print("-" * 40)
                run_functionality(matched_item)
                print("-" * 40)


# Main Interface Loop

last_action_taken = None

try:
    while True:
        with config_lock:
            current_config_name = last_config_loaded
            current_ip_version = get_ip_version(config)

        print(f"\n[ Current Config: {current_config_name}, IP Version: {current_ip_version} ]")
        
        menu_choices = []
        for func in functionalities:
            prefix = get_menu_prefix(func)
            desc = func.get('description', 'No description')
            menu_choices.append((f"{prefix}{func['name']} ({desc})", func['name']))
            
        menu_choices.extend([
            ("--- Calendar View ---", "calendar"),
            ("--- Run All Functionalities ---", "all"),
            ("--- View Session Graphs Window ---", "window"),
            ("--- Delete Invalid-Date Cache ---", "clear_invalid_cache"),
            ("--- Change Active Config ---", "config"),
            ("--- Exit ---", "exit")
        ])

        if last_action_taken:
            menu_choices.insert(0, (f"{Fore.GREEN}[LAST RAN] {last_action_taken} {Style.RESET_ALL}", last_action_taken))

            
            


        main_question = [
            inquirer.List(
                'action',
                message="Use Arrow Keys to select an option and press Enter",
                choices=menu_choices,
                default=menu_choices[0] if last_action_taken is None else menu_choices[1],
                carousel=True,
            )
        ]

        answers = inquirer.prompt(main_question)
        if not answers:
            break

        action = answers['action']
        last_action_taken = action

        if action == "exit":
            print("Exiting...")
            break

        elif action == "calendar":
            pass#app = DataAvailabilityCalendar(config_name=current_config_name)
            #app.run()
            
        elif action == "window":
            create_window_with_all_rendered_graphs_this_session()
        
        elif action == "clear_invalid_cache":

            URL_ELIXIR = os.getenv("URL_ELIXIR", "http://localhost:4000")
            try:
                response = requests.post(f"{URL_ELIXIR}/bview/erase-invalid-dates-bviews")
                if response.status_code == 200:
                    print("Successfully cleared invalid-date cache.")
                else: 
                    print(f"Failed to clear cache. Status code: {response.status_code}")
            except Exception as e:
                print(f"Error while clearing cache: {e}")

        elif action == "config":
            change_config_menu()
            
        elif action == "all":
            def execute_all_recursive(items):
                for item in items:
                    if "submenu" in item:
                        execute_all_recursive(item["submenu"])
                    elif item.get("status") != "broken":
                        run_functionality(item)
            execute_all_recursive(functionalities)
                
        else:
            func = next((f for f in functionalities if f["name"] == action), None)
            if func:
                if "submenu" in func:
                    handle_submenu(func["submenu"], func["name"])
                else:
                    print("-" * 40)
                    run_functionality(func)
                    print("-" * 40)
finally:
    stop_watcher = True