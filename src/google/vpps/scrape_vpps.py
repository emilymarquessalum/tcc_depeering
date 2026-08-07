 
import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


def scrape_vpps(): 
    
    url = "https://peering.google.com/#/options/verified-peering-provider"
     
    options = webdriver.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(options=options)
    
    try:
        driver.get(url)
         
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "table")))
        
        time.sleep(2)   
          
        tables = driver.find_elements(By.TAG_NAME, "table")
        
        data = {
            "gold": [],
            "silver": []
        }
        
        # Process each table
        for table_idx, table in enumerate(tables):
            try:
                # Get table header to identify if it's gold or silver
                header_text = table.text.lower()
                
                # Determine if this is gold or silver table
                is_gold = False
                is_silver = False
                
                # Try to find table caption or section header
                try:
                    caption = table.find_element(By.TAG_NAME, "caption").text.lower()
                    is_gold = "gold" in caption
                    is_silver = "silver" in caption
                except NoSuchElementException:
                    pass
                
                # If no caption, infer from position (first table = gold, second = silver)
                if not is_gold and not is_silver:
                    is_gold = table_idx == 0
                    is_silver = table_idx == 1
                
                provider_type = "gold" if is_gold else "silver"
                
                # Extract rows from table body
                tbody = table.find_element(By.TAG_NAME, "tbody")
                rows = tbody.find_elements(By.TAG_NAME, "tr")
                
                for row in rows:
                    try:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        
                        if len(cells) < 3:
                            continue
                        
                        # Extract ISP/Link (first column)
                        isp_cell = cells[0]
                        isp_text = isp_cell.text.strip()
                        
                        # Try to find link in ISP cell
                        isp_link = None
                        try:
                            link_elem = isp_cell.find_element(By.TAG_NAME, "a")
                            isp_link = link_elem.get_attribute("href")
                        except NoSuchElementException:
                            pass
                        
                        # Extract Sales Region (second column - skip Logo which should be first visual element)
                        # The columns are: ISP/Link, Logo, Sales Region, Metros
                        # We skip Logo (index 1) and get Sales Region (index 2)
                        sales_region = cells[2].text.strip() if len(cells) > 2 else ""
                        
                        # Extract Metros with multiple PNIs (fourth column)
                        metros = cells[3].text.strip() if len(cells) > 3 else ""
                        
                        provider_info = {
                            "isp_name": isp_text,
                            "isp_link": isp_link,
                            "sales_region": sales_region,
                            "metros_with_multiple_pnis": metros
                        }
                        
                        data[provider_type].append(provider_info)
                        
                    except Exception as e:
                        print(f"Error processing row: {e}")
                        continue
                
                print(f"Extracted {len(data[provider_type])} {provider_type} providers")
                
            except Exception as e:
                print(f"Error processing table {table_idx}: {e}")
                continue
        
        return data
        
    finally:
        driver.quit()


def save_vpps_to_json(data, output_file="google_vpps.json"):
    """Save scraped VPPs data to JSON file"""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Data saved to {output_file}")


if __name__ == "__main__":
    print("Starting VPPs scraper...")
    vpps_data = scrape_vpps()
    
    print(f"\nGold providers: {len(vpps_data['gold'])}")
    print(f"Silver providers: {len(vpps_data['silver'])}")
     
    import os
    output_path = os.path.join(os.path.dirname(__file__), "google_vpps.json")
    save_vpps_to_json(vpps_data, output_path)
    
    print("\nSample data:")
    if vpps_data['gold']:
        print("Gold sample:", json.dumps(vpps_data['gold'][0], indent=2))
    if vpps_data['silver']:
        print("Silver sample:", json.dumps(vpps_data['silver'][0], indent=2))
