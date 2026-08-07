import gzip
import io
import os
import requests

class CAIDAAS2Org:
    def __init__(self, cache_filename="caida_as2org_cache.txt.gz"):
        self.url = "https://publicdata.caida.org/datasets/as-organizations/20260601.as-org2info.txt.gz"
        self.cache_filename = cache_filename
        
        self.asn_to_org = {}  
        self.org_to_asns = {} 
        self.org_names = {}   
        
        self._load_dataset()
        print(f"Dataset ready. (Orgs indexed: {len(self.org_names)} | ASNs indexed: {len(self.asn_to_org)})")

    def _load_dataset(self):
        # 1. Local caching logic
        if os.path.exists(self.cache_filename):
            print(f"Found cached dataset locally at '{self.cache_filename}'. Loading...")
            with open(self.cache_filename, 'rb') as f:
                file_content = f.read()
        else:
            print(f"Cache not found. Downloading dataset from CAIDA...")
            response = requests.get(self.url, timeout=30)
            if response.status_code != 200:
                raise Exception(f"Failed to download dataset. Status code: {response.status_code}")
            
            file_content = response.content
            with open(self.cache_filename, 'wb') as f:
                f.write(file_content)
            print(f"Dataset downloaded and cached locally as '{self.cache_filename}'.")

        # 2. Dual-Format Parser (Handles both top and bottom halves)
        with gzip.GzipFile(fileobj=io.BytesIO(file_content)) as gzip_file:
            for line_bytes in gzip_file:
                line = line_bytes.decode('utf-8').strip()
                
                # Ignore metadata lines and format headers
                if not line or line.startswith("#") or line.startswith("format:"):
                    continue
                
                parts = line.split("|")
                
                # TOP HALF: Parse Organization Line
                # Format (5 fields): org_id | changed | org_name | country | source
                if len(parts) == 5 and not parts[0].isdigit():
                    org_id = parts[0]
                    org_name = parts[2]
                    self.org_names[org_id] = org_name
                
                # BOTTOM HALF: Parse ASN Line
                # Format (6 fields): aut | changed | aut_name | org_id | opaque_id | source
                elif len(parts) == 6 and parts[0].isdigit():
                    asn = int(parts[0])
                    org_id = parts[3] # Index 3 maps to the org_id field in this section
                    
                    self.asn_to_org[asn] = org_id
                    if org_id not in self.org_to_asns:
                        self.org_to_asns[org_id] = []
                    self.org_to_asns[org_id].append(asn)

    def get_org_asn_from_sub_asn(self, sub_asn: int):
        sub_asn = int(sub_asn)
        org_id = self.asn_to_org.get(sub_asn)
        if not org_id:
            return {"error": f"ASN {sub_asn} not found in AS2Org dataset."}
        
        all_sibling_asns = self.org_to_asns.get(org_id, [])
        org_name = self.org_names.get(org_id, "Unknown Org Name")
        primary_asn = min(all_sibling_asns) if all_sibling_asns else sub_asn
        
        return {
            "queried_asn": sub_asn,
            "parent_org_id": org_id,
            "parent_org_name": org_name,
            "primary_asn": primary_asn,
            "all_associated_asns": sorted(all_sibling_asns)
        }

# --- Execution Example ---
if __name__ == "__main__":
    as2org = CAIDAAS2Org()
    print("-" * 50)
    
    # Testing your AT&T target ASN
    test_asn = 23764
    result = as2org.get_org_asn_from_sub_asn(test_asn)
    
    if "error" not in result:
        print(f"Queried ASN:   AS{result['queried_asn']}")
        print(f"Org Name:      {result['parent_org_name']} ({result['parent_org_id']})")
        print(f"Primary ASN:   AS{result['primary_asn']}")
        print(f"Total ASNs owned by this Org: {len(result['all_associated_asns'])}")
        print(f"All ASNs owned by this Org: {result['all_associated_asns']}")
    else:
        print(result["error"])