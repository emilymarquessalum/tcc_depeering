



import ipaddress

import numpy as np
import pandas as pd


def count_48_prefixes(network: ipaddress.IPv6Network) -> float:

    if network.prefixlen <= 48:
        return 2 ** (48 - network.prefixlen)

    return 1 / (2 ** (network.prefixlen - 48))

def sum_unique_48_proportions(network_series) -> float:

    networks = list(network_series.dropna()) if not isinstance(network_series, list) else network_series

    if isinstance(networks[0], str):
      networks = [ipaddress.IPv6Network(ip) for ip in networks]


    collapsed_networks = ipaddress.collapse_addresses(networks)

    total_48s = 0.0
    for net in collapsed_networks:
      total_48s += count_48_prefixes(net)

    return total_48s



def get_network_ranges(address_objects):
  return np.array([int(n.network_address) for n in address_objects]), np.array([int(n.broadcast_address) for n in address_objects])




def get_prefixes_announced_in_ixp_that_are_delegated(prefixes_delegated, ixbr_fortaleza_df):

    delegated_addresses = [
            ipaddress.IPv6Network(f"{num}/{int(size)}")
            for num, size in zip(prefixes_delegated['resource_number'], prefixes_delegated['resource_size'])
    ]

    delegated_start, delegated_end = get_network_ranges(delegated_addresses)
    delegated_networks = np.array([str(n) for n in delegated_addresses])


    ix_addresses = [ipaddress.IPv6Network(p) for p in ixbr_fortaleza_df["prefix"]]
    ix_start, ix_end = get_network_ranges(ix_addresses)
    ix_prefixes = ixbr_fortaleza_df["prefix"].values

    quantity_of_sets = 0

    def extract_origin_asns(path):
        nonlocal quantity_of_sets

        return [path[-1]]
       
        if pd.isna(path):
            return []
        path_str = str(path).strip()

        if '{' in path_str and '}' in path_str:
            quantity_of_sets += 1
            start_idx = path_str.find('{') + 1
            end_idx = path_str.find('}')
            set_content = path_str[start_idx:end_idx]

            set_content = set_content.replace(',', ' ')
            return set_content.split()

        parts = path_str.split()
        return [parts[-1]] if parts else []

    ix_ases = ixbr_fortaleza_df["as_path"].apply(extract_origin_asns).values

    sort_idx = np.argsort(ix_start)
    ix_start = ix_start[sort_idx]
    ix_end = ix_end[sort_idx]
    ix_ases = ix_ases[sort_idx]
    ix_prefixes = ix_prefixes[sort_idx]

    matched_records = []


    lower_bounds = np.searchsorted(ix_start, delegated_start, side="left")
    upper_bounds = np.searchsorted(ix_start, delegated_end, side="right")

    for idx, upper_bound in enumerate(upper_bounds):
        lower_bound = lower_bounds[idx]

        if lower_bound >= upper_bound:
            continue

        d_end = delegated_end[idx]
        ix_end_window = ix_end[lower_bound:upper_bound]

        valid_mask = ix_end_window <= d_end

        if np.any(valid_mask):
            window_ases = ix_ases[lower_bound:upper_bound][valid_mask] # list of list
            window_prefixes = ix_prefixes[lower_bound:upper_bound][valid_mask]

            matching_ases = list({
                asn for sub_list in window_ases for asn in sub_list if asn is not None
            })
            matching_prefixes = list(window_prefixes)

            matched_records.append({
                "resource_number_delegated": delegated_networks[idx],
                "original_prefix_announcement": matching_prefixes,
                "origin_ases": matching_ases
            })

    print(quantity_of_sets)
    return pd.DataFrame(matched_records)
