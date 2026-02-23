
import os
import subprocess
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

import warnings

from definitions import ROOT_DIR, append_root


ripe_data_cache = {}
def download_ripe_data(rrc, date_str, time_str):

    year = date_str[:4]
    month = date_str[4:6]
    ripe_month_dir = f"{year}.{month}"
    
    base_url = f"https://data.ris.ripe.net/{rrc}/{ripe_month_dir}/"
    
    print(f"Accessing URL: {base_url}")

    local_dir = append_root(os.path.join("data", rrc)) 
    if not os.path.exists(local_dir):
        os.makedirs(local_dir)
 
    if os.path.exists(get_rib_file_name(rrc, date_str, time_str)):
        print(f"File bview.{date_str}.{time_str}.gz already exists. Skipping download.")
        return
    response_text = ripe_data_cache.get(base_url)
    if response_text is None:
        try:
            response = requests.get(base_url)
            response.raise_for_status()
            
            response_text = response.text
            ripe_data_cache[base_url] = response_text
        except requests.exceptions.HTTPError as e:
            print(f"Error: Could not access the directory. Check if the RRC and Date are correct. ({e})")
            return
    soup = BeautifulSoup(response_text, 'html.parser')
     
    target_pattern = f"bview.{date_str}.{time_str}"
    links = [a['href'] for a in soup.find_all('a', href=True) 
             if target_pattern in a['href'] and a['href'].endswith('.gz')]

    if not links:
        print(f"No files found matching {date_str} at {time_str}.")
        return
    print(len(links))
    if links:
        link = links[0]  # Take the first/only match
        file_url = urljoin(base_url, link)
        file_path = get_rib_file_name(rrc, date_str, time_str)
        
        print(f"Downloading: {link}")

        with requests.get(file_url, stream=True) as r:
            r.raise_for_status()
            print(f"Saving to: {file_path}")
            with open(file_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=16384):
                    f.write(chunk)
        print(f"Saved to: {file_path}")

def get_rib_file_name(rrc, date_str, time_str):
    file_name = f"data/{rrc}/bview.{date_str}.{time_str}.gz" 
    return append_root(file_name)

def get_rib_output_file_name(rrc, date_str, time_str, asn):
    file_name = f"data/{rrc}/bview.{date_str}.{time_str}.{asn}.txt" 
    file_name = f"{rrc}/output_bview.{date_str}.{time_str}.txt"
    return append_root(file_name)


def parsing_ripe_file(bgpcanner_or_bgpdump, rrc, date_str, time_str, asn, prefix, output_file_name):
    if bgpcanner_or_bgpdump == "bgpdump":
        path_of_file = get_rib_file_name(rrc, date_str, time_str)
        command = f'bgpdump -m "{path_of_file}" | grep "|{prefix}|{asn}|" > {output_file_name}'
        print(command)
        subprocess.run(command, shell=True,capture_output=True)
    else:    
        command = f'bgpscanner -i "{prefix}" {get_rib_file_name(rrc, date_str, time_str)} > {output_file_name}' 
        print(command)
        subprocess.run(command, shell=True,capture_output=True)

def download_and_save_file(rrc, date_str, time_str, asn, prefix, bgpcanner_or_bgpdump="bgpscanner"):
 
    output_file_name = get_rib_output_file_name(rrc, date_str, time_str, asn)
    if os.path.exists(output_file_name):
        warnings.warn(f"File {output_file_name} already exists. Skipping download.")
        return
    download_ripe_data(rrc, date_str, time_str)
    print(f"Run {bgpcanner_or_bgpdump}")
    start_time = os.times()
    if not os.path.exists(output_file_name):
        parsing_ripe_file(bgpcanner_or_bgpdump, rrc, date_str, time_str, asn, prefix, output_file_name)
    else:
        print(f"File {output_file_name} already exists. Skipping parsing.")
    end_time = os.times()
    print(f"{bgpcanner_or_bgpdump} completed in {end_time.elapsed - start_time.elapsed} seconds.")  


if __name__ == "__main__": 
    rrc = "rrc15"
    date_str = "20260122"
    time_str = "0000"
    asn = "26162" 
    prefix = "187.16.216.253"
    
    parsing_ripe_file("bgpdump", rrc, date_str, time_str, asn, prefix, get_rib_output_file_name(rrc, date_str, time_str, asn))
    #download_and_save_file(rrc, date_str, time_str, asn, prefix)