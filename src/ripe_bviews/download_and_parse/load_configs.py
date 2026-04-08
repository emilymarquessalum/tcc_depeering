

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

def load_configs(config_file_path):
    
    path = Path(__file__).parent.parent / "configs" / config_file_path
    with open(path, 'r') as f:
        config = json.load(f)
    return config

def print_config(config, ip_version=None):
    start_date = config.get("start_date", "N/A")
    end_date = config.get("end_date", "N/A")
    rrc = config.get("rrc", "N/A")
    time_delta_hours = config.get("time_delta_hours", "N/A")
    print(f"Loaded config: RRC={rrc}, Start Date={start_date}, End Date={end_date}, IP Version={ip_version}, Time Delta Hours={time_delta_hours}")
if __name__ == "__main__":
    config = load_configs("ixbr.json")
    print_config(config)