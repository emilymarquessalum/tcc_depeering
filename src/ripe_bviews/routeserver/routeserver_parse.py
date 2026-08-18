import tarfile
import os
import datetime
from pathlib import Path



ROUTESERVER_PATH = "/home/jfpereira/routeservers_json/"

# routes_received: routes neighbour is trying to announce to the route server
# routes_filtered: not accepted
# routes_accepted: accepted routes 
# routes_exported: routes it has access to because of the RouteServer.


# loads all route server data from a single date (different hours of that date),
# stores the latest information of an AS (if the AS was visible at any time of that day that our snapshots acquired, it will be in the resulting data, even if it 
# de-peered that day, to avoid cases where the AS simply left the IXP for a few hours due to outtages and etc)
def load_all_routeserver_data_from_date(date, ixp, routeserver_name) -> dict[str, list[dict]]:


    path = ROUTESERVER_PATH + date + "/" + ixp + "/neighbors"

    try:

        available_dates = os.listdir(path)

        if len(available_dates) == 0:
            return None
        
        asn_to_data_mapping = {}

        for available_date_file in available_dates:
            with open(path + "/" + available_date_file) as f:
                file_data = json.load(f)
                asns_data = file_data[routeserver_name]["neighbors"]

                for asn_specific_data in asns_data:

                    asn = asn_specific_data["asn"]
                    asn_to_data_mapping[asn] = asn_specific_data # asn, routes_received, routes_filtered, routes_accepted, routes_exported

        return asn_to_data_mapping
    except:
        return None

def get_empty_asn_data(asn):
    return {
        "asn": asn,
        "routes_received": -1, # -1 means didnt exist
        "routes_filtered": -1,
        'routes_accepted': -1,
        "routes_exported": -1
    }

def load_routeserver_data_from_range(ixp, routeserver, start_time, end_time, interval):

    current_time = start_time

    asn_to_routes_over_time_map = {}



    while current_time <= end_time:

        date_str = current_time.strftime("%Y%m%d")
        print(f"Processing data for date: {date_str}")
        route_server_data = load_all_routeserver_data_from_date(date_str, ixp, routeserver)

        if route_server_data is None:
            print(f"  No data found for {date_str}")
            current_time += interval
            #for asn in asn_to_routes_over_time_map.keys():
            #    asn_to_routes_over_time_map[asn].append(get_empty_asn_data(asn))
                
            continue
        
        for asn in route_server_data.keys(): 
            if asn not in asn_to_routes_over_time_map:
                asn_to_routes_over_time_map[asn] = [
                    get_empty_asn_data(asn) for _ in range((current_time - start_time).days)
                ]

            asn_to_routes_over_time_map[asn].append(route_server_data[asn]) 

        asns_missing = set(asn_to_routes_over_time_map.keys()) - set(route_server_data.keys())

        for asn in asns_missing:
            asn_to_routes_over_time_map[asn].append(
                get_empty_asn_data(asn)
            )

        current_time += interval

    return asn_to_routes_over_time_map




def extract_routeserver_data_from_tar_gz(tar_gz_file_path, start_date, end_date, routeserver_name="ix-br"):
    
    # Target base path where routeserver.py expects to find data
    target_base_path = "/home/emily/Desktop/projects/furg/tcc_depeering_elixir/data/routeservers/{routeserver_name}".format(
        routeserver_name=routeserver_name
    )
    
    # Ensure base directory exists
    os.makedirs(target_base_path, exist_ok=True)
    
    # Open the tar.gz file
    with tarfile.open(tar_gz_file_path, 'r:gz') as tar_ref:
        # Get all members in the tar
        all_members = tar_ref.getnames()
        
        # Iterate through date range
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime("%Y%m%d")
            target_dir = os.path.join(target_base_path, date_str, "neighbors")
            
            # Check if data already exists for this date
            if os.path.exists(target_dir) and os.listdir(target_dir):
                print(f"Skipping {date_str}: already extracted")
                current_date += datetime.timedelta(days=1)
                continue
             
            target_prefix = f"routeservers_json/{date_str}/{routeserver_name}/neighbors/"
             
            matching_files = [f for f in all_members if f.startswith(target_prefix) and f != target_prefix]
            
            if matching_files:
                # Take the first file
                file_to_extract = matching_files[0]
                file_name = os.path.basename(file_to_extract)
                 
                os.makedirs(target_dir, exist_ok=True)
                 
                extract_path = os.path.join(target_dir, file_name)
                 
                # Extract file from tar
                member = tar_ref.getmember(file_to_extract)
                with tar_ref.extractfile(member) as source:
                    with open(extract_path, 'wb') as target:
                        target.write(source.read())
                
                print(f"Extracted {date_str}: {file_name} -> {extract_path}")
            else:
                print(f"No data found for {date_str}")
            
            current_date += datetime.timedelta(days=1)
    
    print(f"Extraction complete. Data saved to {target_base_path}")


if __name__ == "__main__": 
    
    tar_gz_file_path = "/home/emily/Desktop/projects/furg/tcc_depeering_elixir/data/routeservers/routeservers_json.tar.gz" 
     
    start_date = datetime.datetime(2025, 8, 16)
    end_date = datetime.datetime(2025, 11, 6)
     
    extract_routeserver_data_from_tar_gz(tar_gz_file_path, start_date, end_date, routeserver_name="ix-br")
