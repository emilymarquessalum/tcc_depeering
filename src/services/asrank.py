import requests
from bisect import bisect_left
import random


def fetch_all_asrank(limit: int = 10000) -> list[dict]:
    """
    Fetches the top N ranked ASes in bulk pages from CAIDA ASRank.
    Returns a sorted list of dicts ordered by rank.
    """
    url = "https://api.asrank.caida.org/v2/graphql"
    asns = []
    first = 1000  # CAIDA handles pages of 1,000 cleanly
    offset = 0
    
    query = """
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
    
    while offset < limit:
        res = requests.post(
            url, 
            json={'query': query, 'variables': {'first': first, 'offset': offset}}
        )
        if res.status_code != 200:
            break
            
        edges = res.json().get('data', {}).get('asns', {}).get('edges', [])
        if not edges:
            break
            
        for edge in edges:
            asns.append(edge['node'])
            
        offset += len(edges)
        if len(edges) < first:
            break
            
    return asns

def find_closest_similar_ases(
    input_asns: list[str], 
    max_rank_depth: int = 10000, 
    all_asns=None, 
    asn_to_idx=None,
    prioritize_higher: bool | None = None,
    minimum_distance: int = 1
) -> dict[str, dict | None]:
    input_set = set(str(asn) for asn in input_asns)

    if asn_to_idx is None:
        all_asns = fetch_all_asrank(limit=max_rank_depth) 
        asn_to_idx = {item['asn']: idx for idx, item in enumerate(all_asns)}

    results = {}
    missing_counts = {
        'target_not_in_rank_list': 0,
        'no_candidates_within_minimum_distance': 0,
        'all_valid_candidates_in_input_set': 0
    }

    for target_asn in input_asns:
        target_str = str(target_asn)
        if target_str not in asn_to_idx:
            results[target_str] = None
            missing_counts['target_not_in_rank_list'] += 1
            continue
            
        target_idx = asn_to_idx[target_str]
        target_info = all_asns[target_idx]
        found_match = None

        if target_idx - minimum_distance < 0 and target_idx + minimum_distance >= len(all_asns):
            missing_counts['no_candidates_within_minimum_distance'] += 1
        else:
            if prioritize_higher is not None:
                search_orders = [
                    range(target_idx - minimum_distance, -1, -1),
                    range(target_idx + minimum_distance, len(all_asns))
                ]
                if prioritize_higher is False:
                    search_orders.reverse()

                for idx_range in search_orders:
                    for idx in idx_range:
                        cand = all_asns[idx]
                        if cand['asn'] not in input_set:
                            found_match = cand
                            break
                    if found_match:
                        break
            else:
                offset = minimum_distance
                while target_idx - offset >= 0 or target_idx + offset < len(all_asns):
                    candidates = []
                    if target_idx - offset >= 0:
                        cand = all_asns[target_idx - offset]
                        if cand['asn'] not in input_set:
                            candidates.append(cand)
                    if target_idx + offset < len(all_asns):
                        cand = all_asns[target_idx + offset]
                        if cand['asn'] not in input_set:
                            candidates.append(cand)
                    if candidates:
                        found_match = random.choice(candidates)
                        break
                    offset += 1

            if found_match is None:
                missing_counts['all_valid_candidates_in_input_set'] += 1
                
        results[target_str] = {
            'target_rank': target_info['rank'],
            'closest_asn': found_match['asn'] if found_match else None,
            'closest_asn_name': found_match['asnName'] if found_match else None,
            'closest_rank': found_match['rank'] if found_match else None,
            'rank_distance': abs(found_match['rank'] - target_info['rank']) if found_match else None
        }


    print(missing_counts)

    return results


if __name__ == "__main__":
    my_ases = ["15169", "3356", "2914"]
    matches = find_closest_similar_ases(my_ases)
    
    for orig_asn, match in matches.items():
        if match:
            print(f"AS{orig_asn} (Rank {match['target_rank']}) -> Closest External: AS{match['closest_asn']} ({match['closest_asn_name']}) at Rank {match['closest_rank']}")