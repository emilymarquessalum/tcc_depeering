import json
import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


def fetch_bimonthly_wayback_snapshots(target_url, start_year=2021):
    """
    Query the Wayback Machine CDX API to fetch available snapshots,
    filtering roughly one snapshot every ~60 days.
    """
    cdx_url = "https://web.archive.org/cdx/search/cdx"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    params = {
        "url": target_url,
        "output": "json",
        "fl": "timestamp,original,statuscode",
        "filter": "statuscode:200",
        "collapse": "timestamp:6"  # Collapse to roughly 1 snapshot per month at the CDX level (YYYYMM)
    }
    
    print("Fetching snapshot index from Internet Archive CDX API...")
    try:
        response = requests.get(cdx_url, headers=headers, params=params, timeout=60)
        response.raise_for_status()
        records = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch Wayback CDX records: {e}")
        return []
    except json.JSONDecodeError as e:
        print(f"Failed to parse CDX response as JSON: {e}")
        print(f"Raw response preview: {response.text[:200]}")
        return []

    if len(records) <= 1:
        print("No snapshots found.")
        return []

    # Skip header row ['timestamp', 'original', 'statuscode']
    rows = records[1:]
    
    sampled_snapshots = []
    last_timestamp = 0
    min_interval_seconds = 50 * 24 * 3600  # ~50 days minimum to space out roughly bimonthly

    for row in rows:
        ts_str = row[0]  # Format: YYYYMMDDhhmmss
        year = int(ts_str[:4])
        if year < start_year:
            continue
            
        try:
            struct_time = time.strptime(ts_str, "%Y%m%d%H%M%S")
            epoch = time.mktime(struct_time)
        except ValueError:
            continue

        if epoch - last_timestamp >= min_interval_seconds:
            wayback_url = f"https://web.archive.org/web/{ts_str}/{target_url}"
            date_formatted = f"{ts_str[:4]}-{ts_str[4:6]}-{ts_str[6:8]}"
            sampled_snapshots.append({
                "timestamp": ts_str,
                "date": date_formatted,
                "url": wayback_url
            })
            last_timestamp = epoch

    return sampled_snapshots


def scrape_vpps_from_url(driver, url):
    """Scrape VPP table data from a specific URL using Selenium."""
    driver.get(url)
     
    wait = WebDriverWait(driver, 60)
    try:
        wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "table")))
    except TimeoutException:
        print(f"  [Timeout] Tables did not render for {url}")
        return None
    
    time.sleep(3)  # Allow JS/Angular components to finish rendering
      
    tables = driver.find_elements(By.TAG_NAME, "table")
    
    data = {
        "gold": [],
        "silver": []
    }
    
    for table_idx, table in enumerate(tables):
        try:
            is_gold = False
            is_silver = False
            
            try:
                caption = table.find_element(By.TAG_NAME, "caption").text.lower()
                is_gold = "gold" in caption
                is_silver = "silver" in caption
            except NoSuchElementException:
                pass
            
            if not is_gold and not is_silver:
                is_gold = table_idx == 0
                is_silver = table_idx == 1
            
            provider_type = "gold" if is_gold else "silver"
            
            try:
                tbody = table.find_element(By.TAG_NAME, "tbody")
                rows = tbody.find_elements(By.TAG_NAME, "tr")
            except NoSuchElementException:
                continue
            
            for row in rows:
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) < 3:
                        continue
                    
                    isp_cell = cells[0]
                    isp_text = isp_cell.text.strip()
                    
                    isp_link = None
                    try:
                        link_elem = isp_cell.find_element(By.TAG_NAME, "a")
                        isp_link = link_elem.get_attribute("href")
                    except NoSuchElementException:
                        pass
                    
                    sales_region = cells[2].text.strip() if len(cells) > 2 else ""
                    metros = cells[3].text.strip() if len(cells) > 3 else ""
                    
                    provider_info = {
                        "isp_name": isp_text,
                        "isp_link": isp_link,
                        "sales_region": sales_region,
                        "metros_with_multiple_pnis": metros
                    }
                    
                    data[provider_type].append(provider_info)
                    
                except Exception:
                    continue
            
        except Exception as e:
            print(f"  Error processing table {table_idx}: {e}")
            continue

    return data


def save_vpps_to_json(data, output_file):
    """Save scraped VPPs data to JSON file."""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Saved to {output_file}")


def main():
    target_url = "https://peering.google.com/#/options/verified-peering-provider"
    
    snapshots = fetch_bimonthly_wayback_snapshots(target_url, start_year=2024)
    print(f"\nFound {len(snapshots)} snapshots to process.\n")

    if not snapshots:
        return

    output_dir = os.path.join(os.path.dirname(__file__), "vpp_historical_data")
    os.makedirs(output_dir, exist_ok=True)

    options = webdriver.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = None

    try:
        for idx, snap in enumerate(snapshots, start=1):
            date_str = snap["date"]
            archive_url = snap["url"]
            filename = f"google_vpps_{date_str}.json"
            output_path = os.path.join(output_dir, filename)

            # Check if file already exists
            if os.path.exists(output_path):
                print(f"[{idx}/{len(snapshots)}] Skipping {date_str} (file already exists: {filename})")
                continue

            # Initialize driver lazily only when we need to scrape
            if driver is None:
                driver = webdriver.Chrome(options=options)
                driver.set_page_load_timeout(180)
                driver.set_script_timeout(180)

                driver.implicitly_wait(60)

            print(f"[{idx}/{len(snapshots)}] Processing snapshot for {date_str}...")
            
            vpps_data = scrape_vpps_from_url(driver, archive_url)
            
            if vpps_data and (vpps_data["gold"] or vpps_data["silver"]):
                save_vpps_to_json(vpps_data, output_path)
                print(f"  Captured {len(vpps_data['gold'])} Gold, {len(vpps_data['silver'])} Silver providers.")
            else:
                print(f"  No provider data extracted from snapshot {date_str}.")

    finally:
        if driver is not None:
            driver.quit()


if __name__ == "__main__":
    main()