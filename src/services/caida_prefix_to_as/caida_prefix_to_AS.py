


from pathlib import Path


file_name =  "routeviews-rv6-20240315-1000.pfx2as"

def load_caida_prefix_to_as_mapping(file_name):
    prefix_to_as = {}

    current_path = Path(__file__).parent
    file_path = current_path / file_name
    with open(file_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 2:
                prefix = parts[0]
                as_number = parts[1]
                prefix_to_as[prefix] = as_number
    return prefix_to_as

prefix_to_as_mapping = load_caida_prefix_to_as_mapping(file_name)

def caida_prefix_to_AS(prefix):
    return prefix_to_as_mapping.get(prefix) 
