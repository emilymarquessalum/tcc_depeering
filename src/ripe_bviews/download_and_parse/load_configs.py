

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


if __name__ == "__main__":
    config = load_configs("ixbr.json")
    print(config)