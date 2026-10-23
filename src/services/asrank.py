import requests

def get_as_rank_info(asn: str) -> dict | None:
    """Fetch rank and ASN details for a specific AS using GraphQL."""
    url = "https://api.asrank.caida.org/v2/graphql"
    query = """
    query ($asn: String!) {
      asn(asn: $asn) {
        asn
        asnName
        rank
      }
    }
    """
    response = requests.post(url, json={'query': query, 'variables': {'asn': asn}})
    if response.status_code == 200:
        data = response.json()
        return data.get('data', {}).get('asn')
    return None

def get_as_by_rank(rank: int) -> dict | None:
    """Fetch AS details for a specific rank position."""
    if rank < 1:
        return None
    url = "https://api.asrank.caida.org/v2/graphql"
    query = """
    query ($rank: Int!) {
      asns(first: 1, offset: %d) {
        edges {
          node {
            asn
            asnName
            rank
          }
        }
      }
    }
    """ % (rank - 1)  # offset is 0-indexed
    
    response = requests.post(url, json={'query': query})
    if response.status_code == 200:
        edges = response.json().get('data', {}).get('asns', {}).get('edges', [])
        if edges:
            return edges[0]['node']
    return None

def find_closest_similar_ases(asn_list: list[str]) -> dict[str, dict]:
    """
    For each ASN in input, finds the closest CAIDA ASRank AS 
    that is NOT present in the input list.
    """
    input_set = set(str(asn) for asn in asn_list)
    results = {}

    for asn in asn_list:
        target_info = get_as_rank_info(str(asn))
        if not target_info or target_info.get('rank') is None:
            results[str(asn)] = None
            continue
        
        target_rank = target_info['rank']
        
        # Search outward by rank distance offset (1, 2, 3...)
        offset = 1
        found_match = None
        
        while True:
            # Check higher rank (numerically smaller) and lower rank (numerically larger)
            candidates = []
            
            cand_above = get_as_by_rank(target_rank - offset)
            if cand_above and cand_above['asn'] not in input_set:
                candidates.append(cand_above)
                
            cand_below = get_as_by_rank(target_rank + offset)
            if cand_below and cand_below['asn'] not in input_set:
                candidates.append(cand_below)

            if candidates:
                # If both are available at the same distance, pick the first (above)
                found_match = candidates[0]
                break
            
            # If both adjacent ranks are in input_set, expand search radius
            offset += 1
            if target_rank - offset < 1 and cand_below is None:
                break # Reached ends of rank dataset
                
        results[str(asn)] = {
            'target_rank': target_rank,
            'closest_asn': found_match['asn'] if found_match else None,
            'closest_asn_name': found_match['asnName'] if found_match else None,
            'closest_rank': found_match['rank'] if found_match else None,
            'rank_distance': offset if found_match else None
        }

    return results

# Example Usage:
if __name__ == "__main__":
    my_ases = ["15169", "3356", "2914"] # Google, Lumen, NTT
    similar_ases = find_closest_similar_ases(my_ases)
    
    for orig_asn, match in similar_ases.items():
        if match:
            print(f"AS{orig_asn} (Rank {match['target_rank']}) -> Closest External: AS{match['closest_asn']} ({match['closest_asn_name']}) at Rank {match['closest_rank']}")