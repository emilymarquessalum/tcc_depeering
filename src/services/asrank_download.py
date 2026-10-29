
import json
import requests

URL = "https://api.asrank.caida.org/v2/graphql"
QUERY = """
query ($first: Int!, $offset: Int!) {
  asns(first: $first, offset: $offset) {
    edges {
      node {
        asn
        asnName
        rank
      }
    }
  }
}
"""

def download_asrank():
    first = 5000
    offset = 0
    
    print("Starting ASRank dataset download...")
    with open("asns.jsonl", "w", encoding="utf-8") as f:
        while True:
            payload = {"query": QUERY, "variables": {"first": first, "offset": offset}}
            response = requests.post(URL, json=payload)
            
            if response.status_code != 200:
                print(f"Error: Received HTTP {response.status_code}")
                break
                
            data = response.json()
            edges = data.get("data", {}).get("asns", {}).get("edges", [])
            
            if not edges:
                break
                
            for edge in edges:
                f.write(json.dumps(edge["node"]) + "\n")
                
            offset += len(edges)
            print(f"Downloaded {offset} ASes...")

    print("Download complete! Saved to asns.jsonl")

if __name__ == "__main__":
    download_asrank()