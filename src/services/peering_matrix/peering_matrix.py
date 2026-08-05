import datetime
import os
import re
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import pandas as pd
from urllib.parse import urlparse, parse_qs


URL = "https://ix.nap.africa/peering-matrix?proto=6&vlan=1"
# TODO: opens different settings, save with proper name (IXP+setting+current_date)

def fetch_page(url, proto, vlan):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    url = f"{url}?proto={proto}&vlan={vlan}"
    print(f"Fetching data from {url}...")
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"Failed to fetch webpage. Status code: {response.status_code}")
        return None

    return BeautifulSoup(response.text, "html.parser")


def get_vlan_options(soup):
    dropdown_links = soup.select(".dropdown-menu .dropdown-item[href]")
    vlan_values = []

    for link in dropdown_links:
        href = link.get("href", "")
        parsed_href = urlparse(href)
        vlan_value = parse_qs(parsed_href.query).get("vlan", [None])[0]

        if vlan_value is not None:
            vlan_values.append(vlan_value.strip())

    return list(dict.fromkeys(vlan_values))


def scrape_peering_matrix(url, proto, vlan):
    soup = fetch_page(url, proto, vlan)

    if soup is None:
        return []


    th_elements = soup.find_all("th", class_="th-as")
    column_asns = []
    for th in th_elements:
        asn = th.get("data-id")
        if asn:
            column_asns.append(asn.strip())

    print(f"Found {len(column_asns)} ASNs in the table header.")
 
    rows = soup.find_all("tr")

    matrix_results = []

    for row in rows: 
        asn_cell = row.find("td", class_="asn")
        if not asn_cell:
            continue
 
        source_asn = asn_cell.text.strip()
 
        status_cells = row.find_all("td", class_=re.compile(r"col-yasn-"))
 
        if len(status_cells) != len(column_asns): 
            pass

        for cell in status_cells:
            cell_id = cell.get("id", "")   
  
            id_parts = cell_id.split("-")
            if len(id_parts) >= 3:
                target_asn = id_parts[2]
            else: 
                class_attr = " ".join(cell.get("class", []))
                match = re.search(r"col-yasn-(\d+)", class_attr)
                target_asn = match.group(1) if match else None

            if not target_asn:
                continue
 
            if source_asn == target_asn:
                continue
 
            class_list = cell.get("class", [])
            class_str = " ".join(class_list).replace("\n", " ") 
            class_str = " ".join(class_str.split())
 
            if "not-peered" in class_str:
                status = "not-peered"
            elif "peered" in class_str:
                status = "peered"
            else:
                status = "unknown/blank"

            matrix_results.append(
                {
                    "source_as": source_asn,
                    "target_as": target_asn,
                    "status": status,
                    "proto": proto,
                    "vlan": vlan,
                }
            )

    return matrix_results

# parquet, turns out, was not necessary here. Will leave it as such for practice. 
def save_as_parquet(peering_data, filename="peering_matrix.parquet"):
    print("Converting data to Parquet columnar format...")
 
    df = pd.DataFrame(peering_data)
 
    df["source_as"] = df["source_as"].astype("category")
    df["target_as"] = df["target_as"].astype("category")
    df["status"] = df["status"].astype("category")
    df["proto"] = df["proto"].astype("category")
    df["vlan"] = df["vlan"].astype("category")


    df.to_parquet(filename, compression="snappy", index=False)
    print(f"Success! Columnar data saved to: {filename}")


def build_output_filename(ixp, proto, vlan, output_dir="."):
    current_data = datetime.date.today().strftime("%Y_%m_%d")
    return Path(output_dir) / f"{ixp}/{current_data}_proto{proto}_vlan{vlan}.parquet"


def fetch_and_save_peering_matrix(url, outputs=None):

    folder = url.replace("https://", "").replace("/peering-matrix", "").replace("/ixp", "")

    if not outputs:
        outputs = ["."]

    for output in outputs:
        if not os.path.exists(Path(output)):
            os.mkdir(Path(output)) 
        if not os.path.exists(Path(output) / folder):
            os.mkdir(Path(output) / folder)

    initial_soup = fetch_page(url, proto=4, vlan=1)

    if initial_soup is None:
        raise SystemExit(1)

    vlan_options = get_vlan_options(initial_soup)
    print(f"Found {len(vlan_options)} VLAN options in the dropdown.")

    for proto in (4, 6):
        for vlan in vlan_options:
            peering_data = scrape_peering_matrix(url, proto, vlan)

            if not peering_data:
                continue

            print("\n--- Scraping Sample Results ---")
            for connection in peering_data[:15]:
                print(
                    f"proto {connection['proto']} vlan {connection['vlan']} | AS {connection['source_as']} -> AS {connection['target_as']}: {connection['status']}"
                )

            print(f"\nTotal connection states parsed for proto {proto}, vlan {vlan}: {len(peering_data)}")
            
            for output in outputs:
                output_filename = build_output_filename(folder, proto, vlan, output_dir=output)
                save_as_parquet(peering_data, filename=str(output_filename))
 
if __name__ == "__main__":
    fetch_and_save_peering_matrix("https://ix.nap.africa/peering-matrix")
