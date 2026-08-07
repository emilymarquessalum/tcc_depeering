

from pathlib import Path 
import json
 

class ConfigLoader:
    def __init__(self, config_file_path):
        self.config_file_path = config_file_path
        self.config = None

    def load(self):
        path = Path(__file__).parent.parent / "configs" / self.config_file_path
        with open(path, 'r') as f:
            self.config = json.load(f)
        return self.config

def get_all_configs():
    configs_path = Path(__file__).parent.parent / "configs"
    config_files = [f.name for f in configs_path.glob("*.json")]
    
    return config_files

def get_all_routeviews_configs():
    configs_path = Path(__file__).parent.parent / "configs" #/ "routeviews_specific"
    config_files = [f.name for f in configs_path.glob("*.json")]
    config_files_that_are_route_views = []
    for config_file in config_files:
        with open(configs_path / config_file, 'r') as f:
            config = json.load(f)
            if config.get("routeserver-folder-name"):
                config_files_that_are_route_views.append(config_file)
    return config_files

def load_configs(config_file_path):
    
    path = Path(__file__).parent.parent / "configs" / config_file_path
    with open(path, 'r') as f:
        config = json.load(f)
    return config

def save_configs(config, config_file_path):
    path = Path(__file__).parent.parent / "configs" / config_file_path
    json_str = json.dumps(config, indent=4)
    
    # 2. Split it into individual lines
    lines = json_str.splitlines()
    
    formatted_lines = []
    field_count = 0
    
    for line in lines:
        formatted_lines.append(line)
         
        stripped = line.strip()
        if stripped and stripped not in ('{', '}', '[', ']'):
            if "start_date" in stripped:
                formatted_lines.insert(len(formatted_lines) - 1, "") 
            if "day_delta" in stripped:
                formatted_lines.insert(len(formatted_lines), "")
                
    # 3. Join the lines back together and write to the file
    with open(path, 'w') as f:
        f.write("\n".join(formatted_lines))

def print_config(config, ip_version=None):
    start_date = config.get("start_date", "N/A")
    end_date = config.get("end_date", "N/A")
    rrc = config.get("rrc", "N/A")
    time_delta_hours = config.get("time_delta_hours", "N/A")
    print(f"Loaded config: Name={config.get('name', 'N/A')}, RRC={rrc}, Start Date={start_date}, End Date={end_date}, IP Version={ip_version}, Time Delta Hours={time_delta_hours}")

def simple_print_debug(config):
    print(f"IXP={config.get('name', 'N/A')}, Start Date={config.get('start_date', 'N/A')}, End Date={config.get('end_date', 'N/A')}")
if __name__ == "__main__":
    config = load_configs("ixbr.json")
    print_config(config)