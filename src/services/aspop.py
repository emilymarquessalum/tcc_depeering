


import os


aspop_url = "https://stats.labs.apnic.net/aspop"

def get_aspop():
    import requests
    from bs4 import BeautifulSoup
    import re
    import json
    
    if True:
    #if not os.path.exists('aspop.html'):
        response = requests.get(aspop_url)
        
        soup = BeautifulSoup(response.text, 'html.parser')

        with open('aspop.html', 'w', encoding='utf-8') as f:
            f.write(soup.prettify())
        
    aspop_data = []
    
    # Extract the JavaScript array from the page
    script_tags = soup.find_all('script')
    for script in script_tags:
        script_content = script.string
        if script_content and 'arrayToDataTable' in script_content:
            # Find arrayToDataTable call and extract data more carefully
            try:
                # Find the start of arrayToDataTable([
                start_idx = script_content.find('arrayToDataTable([')
                if start_idx == -1:
                    continue
                    
                start_idx += len('arrayToDataTable([')
                
                # Find the matching closing bracket
                bracket_count = 1
                idx = start_idx
                while idx < len(script_content) and bracket_count > 0:
                    if script_content[idx] == '[':
                        bracket_count += 1
                    elif script_content[idx] == ']':
                        bracket_count -= 1
                    idx += 1
                
                # Extract array content
                array_str = '[' + script_content[start_idx:idx-1] + ']'
                
                # Clean up HTML tags and entities
                array_str = re.sub(r'<a href="[^"]*">([^<]*)</a>', r'\1', array_str)
                array_str = array_str.replace('&quot;', '"')
                # Remove comments like /* ... */
                array_str = re.sub(r'/\*.*?\*/', '', array_str, flags=re.DOTALL)
                
                # Parse using json5 if available, otherwise use ast.literal_eval
                try:
                    import json5
                    data_array = json5.loads(array_str)
                except ImportError:
                    # Fallback: use Python's literal_eval
                    import ast
                    data_array = ast.literal_eval(array_str)
                
                # Skip the header row and process data
                for row in data_array[1:]:
                    if isinstance(row, list) and len(row) >= 4:
                        aspop_data.append({
                            'rank': row[0],
                            'asn': row[1].replace('AS', '') if isinstance(row[1], str) else row[1],
                            'name': row[2],
                            'country': row[3],
                            'users': row[4],
                            'percent_country': row[5],
                            'percent_internet': row[6],
                            'samples': row[7] if len(row) > 7 else None
                        })
                print(f"Successfully extracted {len(aspop_data)} rows from ASPOP data.")
                break
                
            except Exception as e:
                print(f"Error parsing data: {e}")
    
    if not aspop_data:
        print("No data found in the ASPOP page.")
    
    return aspop_data

 
if __name__ == "__main__":
    print(get_aspop()) 