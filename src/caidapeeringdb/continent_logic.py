 
from pathlib import Path
import json


import json
import sys
from pathlib import Path




sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.regions_and_locations import REGION_TO_COLOR_MAP
from src.caidapeeringdb.ixp_size import get_largest_ixps_from_ixp_list
 
from src.caidapeeringdb.caidapeeringdb_load import get_all_files, get_data, get_unique_ixps_from_data_list


# Load configuration from JSON file
config_path = Path(__file__).parent / "config.json"
with open(config_path, 'r') as f:
    config = json.load(f)

manual_ixp_to_continent_mapping = config.get("manual_ixp_to_continent_mapping", {})
continent_colors = config.get("continent_colors", REGION_TO_COLOR_MAP)


def get_continent_for_ixp(ixp_id, ixp_info):
    """Extract continent from IXP info with fallback to manual mapping."""
    continent = ixp_info.get("region_continent", "Unknown") if ixp_info else "Unknown"

    if continent == "Unknown":
        continent = manual_ixp_to_continent_mapping.get(str(ixp_id), "Unknown")

    return continent


def build_continent_connections(connections_over_time, ixps):
    """Build a list of (date, continent_to_connections_dict) tuples from connections over time."""
    continent_connections = []

    for file_date, connections in connections_over_time:
        continent_to_connections = {}

        for conn in connections:
            ixp_id = conn.get("ix_id")
            ixp_info = next((ixp for ixp in ixps if str(ixp["id"]) == str(ixp_id)), None)

            conn_plus_ixp_info = {**conn, **ixp_info} if ixp_info else conn
            continent = get_continent_for_ixp(ixp_id, conn_plus_ixp_info)

            if continent not in continent_to_connections:
                continent_to_connections[continent] = []
            continent_to_connections[continent].append(conn)

        continent_connections.append((file_date, continent_to_connections))

    return continent_connections


def organize_connections_by_continent(connections_over_time, ixps):
    """Organize connections by continent and prepare for plotting."""
    connections_over_time_by_continent = []

    continent_connections = build_continent_connections(connections_over_time, ixps)
    connections_over_time_by_continent = continent_connections

    all_existing_continents = set()
    for _, continent_connections_dict in connections_over_time_by_continent:
        all_existing_continents.update(continent_connections_dict.keys())

    for file_date, continent_connections_dict in connections_over_time_by_continent:
        for continent in all_existing_continents:
            if continent not in continent_connections_dict:
                continent_connections_dict[continent] = []

    # Reorganize data by continent (each continent is a separate series)
    continent_data_series = {continent: [] for continent in all_existing_continents}
    dates_for_plot = [file_date for file_date, _ in connections_over_time_by_continent]

    for file_date, continent_connections_dict in connections_over_time_by_continent:
        for continent in all_existing_continents:
            continent_data_series[continent].append(len(continent_connections_dict[continent]))

    sorted_continents = sorted(all_existing_continents)

    return continent_data_series, dates_for_plot, sorted_continents


def get_data_structures_excluding_continent(data_structures, continent_to_exclude, all_ixps):
    
    continent_to_ixps_map = {str(ixp["id"]): get_continent_for_ixp(ixp["id"], ixp) for ixp in all_ixps}

    filtered_data_structures = {}
    for key, ixp_ids in data_structures.items():
        if ixp_ids is None:
            filtered_data_structures[key] = None
            continue
        if not isinstance(ixp_ids, set):
            filtered_data_structures[key] = ixp_ids
            continue
        filtered_ixp_ids = {ixp_id for ixp_id in ixp_ids if continent_to_ixps_map.get(str(ixp_id), "Unknown") != continent_to_exclude}
        filtered_data_structures[key] = filtered_ixp_ids

    return filtered_data_structures


def get_unique_ixps_of_region_from_data_list(data_list, region):

    ixps = get_unique_ixps_from_data_list(data_list)

    return [ixp for ixp in ixps if ixp.get("region_continent") == region]


if __name__ == "__main__":

    all_files = get_all_files()
    
    data = get_data(all_files[-1])
    print([ix["name"] + f" (id {ix['id']}, {ix['connections']} connections)" for ix in get_largest_ixps_from_ixp_list(get_unique_ixps_of_region_from_data_list([data], "Africa"), data, 
                                         top_n=10)])

