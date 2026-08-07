import tarfile
import os
import datetime
from pathlib import Path


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
