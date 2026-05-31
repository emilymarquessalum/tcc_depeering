

import sys
from pathlib import Path
import warnings


sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent)) 
 




import datetime 


from src.services.maxmind import load_ip_block_to_country_mapping

from src.ripe_bviews.read_bgpdump import BGPDumpSnapshotStats
from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data_timeline_from_configs
from src.utils.graphs import create_window_with_all_rendered_graphs_this_session, plot_list_as_bar_plot, plot_list_as_line_plot, plot_map_as_bar_plot, plot_stacked_line_plot, plot_stacked_bar_plot

from src.ripe_bviews.download_and_parse.load_configs import load_configs, print_config
from src.ripe_bviews.timeline.bview_vars import get_ip_version

import ipaddress



warnings.filterwarnings('ignore', category=UserWarning, message='.*')

def calculate_total_addresses(prefix_list):
    total_addresses = 0
    
    for prefix in prefix_list:
        try:
            # Create an interface or network object
            network = ipaddress.ip_network(prefix, strict=False)
            # .num_addresses returns the total count (2^(32-n))
            total_addresses += network.num_addresses
        except ValueError as e:
            print(f"Skipping invalid prefix '{prefix}': {e}")
            
    return total_addresses


def calculate_unique_addresses(prefix_list):
    # 1. Convert strings to network objects
    # We use set() to immediately discard exact duplicates
    networks = [ipaddress.ip_network(p, strict=False) for p in set(prefix_list)]
    
    # 2. Collapse overlapping prefixes
    # This merges /24s into their parent /23s if both exist
    unique_networks = list(ipaddress.collapse_addresses(networks))
    
    # 3. Sum the unique addresses
    total_unique = sum(net.num_addresses for net in unique_networks)
    
    return total_unique, unique_networks

def view_prefix_changes(prefix_mappings, stat_before: BGPDumpSnapshotStats, first_stat: BGPDumpSnapshotStats, ip_version: str):
    prefixes_that_changed_without_asn_depeering = set()
    prefixes_that_changed_because_of_asn_depeering = set()
    prefixes_that_only_changed_in_length = set()
    prefixes_that_got_more_specific = set()
    prefixes_that_got_less_specific = set()
    stat_before_prefixes = set(stat_before.prefix_mappings.keys())
    for member_as, prefix_list in prefix_mappings.items():
        for prefix_info in prefix_list:
            if member_as not in stat_before_prefixes:
                prefixes_that_changed_because_of_asn_depeering.add(prefix_info)
                continue
                
            if prefix_info not in stat_before.prefix_mappings.get(member_as, []):
                prefixes_that_changed_without_asn_depeering.add(prefix_info)
                if prefix_info.split("/")[0] in [p.split("/")[0] for p in stat_before.prefix_mappings.get(member_as, [])]:
                    prefixes_that_only_changed_in_length.add(prefix_info)
                    old_length = int([p.split("/")[1] for p in stat_before.prefix_mappings.get(member_as, []) if p.split("/")[0] == prefix_info.split("/")[0]][0])
                    new_length = int(prefix_info.split("/")[1])
                    if new_length > old_length:
                        prefixes_that_got_more_specific.add(prefix_info)
                    elif new_length < old_length:
                        prefixes_that_got_less_specific.add(prefix_info)

    print(f"Prefix changes from {stat_before.datetime_str()} to {first_stat.datetime_str()} in {ip_version}:")
    print(f"Prefixes that changed (not because of ASN depeering): {len(prefixes_that_changed_without_asn_depeering)}")
    print(f"Prefixes that changed because of ASN depeering: {len(prefixes_that_changed_because_of_asn_depeering)}")
    print(f"Prefixes that only changed in length: {len(prefixes_that_only_changed_in_length)}")
    print(f"Prefixes that got more specific: {len(prefixes_that_got_more_specific)}")
    print(f"Prefixes that got less specific: {len(prefixes_that_got_less_specific)}")


def view_prefixes_grouped_by_length(prefix_mappings, name, ip_version):
    prefixes = set()
    prefix_grouped = {}
    for member_as, prefix_list in prefix_mappings.items():
        for prefix_info in prefix_list:
            prefixes.add(prefix_info)
            group = prefix_info.split("/")[1]  
            if group not in prefix_grouped:
                prefix_grouped[group] = []
            prefix_grouped[group].append(prefix_info)
    print(f"Unique prefixes: {len(prefixes)}")

    prefix_lengths_key = list(prefix_grouped.keys())
    prefix_lengths_key.sort(key=lambda x: int(x), reverse=True)
    
    prefix_lengths_values = []
    for key in prefix_lengths_key:
        prefix_lengths_values.append(prefix_grouped[key])
    plot_list_as_bar_plot(prefix_lengths_key, y=[len(v) for v in prefix_lengths_values],
                         title=f"{name} - Prefixes grouped by length - {ip_version}", xlabel="Prefix Length", ylabel="Number of Prefixes")


def view_prefixes_member_concentration_by_length(prefix_mappings, name, ip_version, from_self_or_others="Owned by the Member", subfolder=None, top_n=10, group_n_by_n=None):


    
    # Calculate address counts by ASN and prefix length
    asn_prefix_length_addresses = {}  # {asn: {prefix_length: address_count}}
    
    for asn, prefix_list in prefix_mappings.items():
        asn_prefix_length_addresses[asn] = {}
 
        for prefix in prefix_list:
            try:
                prefix_length = int(prefix.split("/")[1])
                network = ipaddress.ip_network(prefix, strict=False)
                address_count = network.num_addresses
                
                if prefix_length not in asn_prefix_length_addresses[asn]:
                    asn_prefix_length_addresses[asn][prefix_length] = 0
                asn_prefix_length_addresses[asn][prefix_length] += address_count
            except (ValueError, IndexError):
                continue
    
    # Get all unique prefix lengths across all ASNs
    all_prefix_lengths = set()
    for length_dict in asn_prefix_length_addresses.values():
        all_prefix_lengths.update(length_dict.keys())
    
    all_prefix_lengths = sorted(list(all_prefix_lengths))
    
    # Group prefix lengths if requested
    if group_n_by_n and group_n_by_n > 1:
        grouped_lengths = {}  # {group_label: [list of prefix lengths in group]}
        group_labels = []  # Ordered list of group labels
        
        for i, length in enumerate(all_prefix_lengths):
            group_idx = i // group_n_by_n
            group_start_idx = group_idx * group_n_by_n
            group_end_idx = min(group_start_idx + group_n_by_n - 1, len(all_prefix_lengths) - 1)
            
            group_label = f"/{all_prefix_lengths[group_start_idx]}-/{all_prefix_lengths[group_end_idx]}"
            
            if group_label not in grouped_lengths:
                grouped_lengths[group_label] = []
                group_labels.append(group_label)
            
            grouped_lengths[group_label].append(length)
        
        # Aggregate addresses by group
        grouped_asn_addresses = {}  # {asn: {group_label: total_addresses}}
        for asn, length_dict in asn_prefix_length_addresses.items():
            grouped_asn_addresses[asn] = {}
            for group_label, lengths in grouped_lengths.items():
                grouped_asn_addresses[asn][group_label] = sum(length_dict.get(l, 0) for l in lengths)
        
        # Replace the working data with grouped data
        asn_prefix_length_addresses = grouped_asn_addresses
        all_prefix_lengths = group_labels
    
    # Calculate total addresses per ASN
    asn_total_addresses = {}
    if group_n_by_n and group_n_by_n > 1:
        asn_total_addresses = {asn: sum(length_dict.values()) 
                               for asn, length_dict in asn_prefix_length_addresses.items()}
    else:
        # Original calculation for ungrouped lengths
        for asn, length_dict in asn_prefix_length_addresses.items():
            asn_total_addresses[asn] = sum(length_dict.values())
    
    # Get top N ASNs by total addresses
    top_asns = sorted(asn_total_addresses.keys(), 
                      key=lambda asn: asn_total_addresses[asn], 
                      reverse=True)[:top_n]
    
    # Build data lists for each prefix length (or group)
    data_lists = []
    for prefix_length in all_prefix_lengths:
        address_counts = []
        for asn in top_asns:
            address_counts.append(asn_prefix_length_addresses[asn].get(prefix_length, 0))
        data_lists.append(address_counts)
    
    # Create stacked bar plot
    plot_stacked_bar_plot(
        data_lists=data_lists,
        labels=all_prefix_lengths,
        x_labels=[str(asn) for asn in top_asns],
        title=f"{name} - Top {top_n} ASes by Address Count (by Prefix Length) - {ip_version} - {from_self_or_others}",
        xlabel="ASN",
        ylabel="Addresses",
        subfolder=subfolder,
        sort_by_size=False,
        use_rotated_labels=True
    )
    

def view_prefixes_member_concentration(stat: BGPDumpSnapshotStats, name, ip_version, from_self_or_others="Owned by the Member", subfolder=None, prefix_mappings=None):
    """
    View prefix concentration statistics for members. If prefix_mappings is provided (for backward compatibility),
    it will be used instead of deriving from stat.
    """
    if prefix_mappings is None:
        prefix_mappings_member_has, prefix_mappings_member_reaches, prefix_mappings_asn_has = stat.get_prefix_mappings()
        if from_self_or_others == "Owned by the Member":
            prefix_mappings = prefix_mappings_member_has
        elif from_self_or_others == "Reached by the Member":
            prefix_mappings = prefix_mappings_member_reaches
        else:
            prefix_mappings = prefix_mappings_asn_has

    if prefix_mappings is None or len(prefix_mappings) == 0: 
        print(f"No prefix mapping data available for {name} - {ip_version} - {from_self_or_others}.")
        return
    
    top_n = 10
    
    # Get top by prefix count
    top_by_prefix_count = stat.get_top_members_by_prefix_count(
        prefix_mappings,
        top_n=top_n)
    top_member_ases = [asn for asn, _ in top_by_prefix_count]
    
    # Calculate total unique prefixes
    unique_prefixes = set()
    for prefixes in prefix_mappings.values():
        unique_prefixes.update(prefixes)
    total_prefix_count = len(unique_prefixes)
    
    top_prefix_percentage_counts = [count / total_prefix_count * 100 for _, count in top_by_prefix_count]

    plot_list_as_bar_plot(
        top_member_ases,
        y=top_prefix_percentage_counts,
        title=f"{name} - Top {top_n} ASes by Prefix Count - {ip_version} - {from_self_or_others}",
        xlabel="ASN",
        ylabel="Prefixes %",
        subfolder=subfolder
    )

    # Get top by address count
    top_by_address_count = stat.get_top_members_by_address_count(prefix_mappings, top_n=top_n)
    top_member_ases_by_addresses = [asn for asn, _ in top_by_address_count]
    
    total_address_count = sum(count for _, count in top_by_address_count)
    top_address_percentage_counts = [count / total_address_count * 100 for _, count in top_by_address_count]

    plot_list_as_bar_plot(
        top_member_ases_by_addresses,
        y=top_address_percentage_counts,
        title=f"{name} - Top {top_n} ASes by Address Count - {ip_version} - {from_self_or_others}",
        xlabel="ASN",
        ylabel="Addresses (Aggregated) %",
        subfolder=subfolder
    )

    view_prefixes_member_concentration_by_length(prefix_mappings, name, ip_version, from_self_or_others=from_self_or_others, subfolder=subfolder, group_n_by_n=3)


from collections import Counter

def view_unique_prefixes_member_concentration(stat: BGPDumpSnapshotStats, name, ip_version, subfolder=None, prefix_mappings=None):
    """
    View unique prefix concentration statistics. If prefix_mappings is provided (for backward compatibility),
    it will be used instead of deriving from stat.
    """
    if prefix_mappings is None:
        _, prefix_mappings_member_reaches, _ = stat.get_prefix_mappings()
        prefix_mappings = prefix_mappings_member_reaches  # Default to "Reached by Member"
    
    top_n = 10
    
    # Get top by unique prefix count
    top_by_unique_prefix_count = stat.get_top_members_by_unique_prefix_count(top_n=top_n)
    top_member_ases = [asn for asn, _ in top_by_unique_prefix_count]
    
    # Calculate total unique prefixes
    from collections import Counter
    all_prefixes_iter = (prefix for prefixes in prefix_mappings.values() for prefix in prefixes)
    prefix_counts = Counter(all_prefixes_iter)
    total_unique_prefix_count = sum(1 for count in prefix_counts.values() if count == 1)

    if total_unique_prefix_count == 0:
        print(f"No unique prefixes found for {name} - {ip_version}")
        return

    top_prefix_percentages = [count / total_unique_prefix_count * 100 for _, count in top_by_unique_prefix_count]

    # Plot Prefix Concentration
    plot_list_as_bar_plot(
        top_member_ases,
        y=top_prefix_percentages,
        title=f"{name} - Top {top_n} ASes by UNIQUE Prefix Count - {ip_version}",
        xlabel="ASN",
        ylabel="Unique Prefixes %",
        subfolder=subfolder
    )

    # Get top by unique address count
    top_by_unique_address_count = stat.get_top_members_by_unique_address_count(top_n=top_n)
    top_ases_by_addr = [asn for asn, _ in top_by_unique_address_count]
    
    total_unique_address_count = sum(count for _, count in top_by_unique_address_count)

    if total_unique_address_count > 0:
        top_addr_percentages = [count / total_unique_address_count * 100 for _, count in top_by_unique_address_count]

        plot_list_as_bar_plot(
            top_ases_by_addr,
            y=top_addr_percentages,
            title=f"{name} - Top {top_n} ASes by UNIQUE Address Count - {ip_version}",
            xlabel="ASN",
            ylabel="Unique Addresses %",
            subfolder=subfolder
        )


def plot_prefix_by_country(name, ip_version, prefix_mappings):
    ip_block_to_country_name_mapping = load_ip_block_to_country_mapping()
    
    ip_blocks_not_found = 0
    country_name_to_prefix_count = {}
    
    # Get all unique prefixes from the mappings
    unique_prefixes = set()
    for prefixes in prefix_mappings.values():
        unique_prefixes.update(prefixes)

    for prefix in unique_prefixes:
        country_name = ip_block_to_country_name_mapping.get(prefix)
        if not country_name:
            ip_blocks_not_found += 1
            continue
        if country_name not in country_name_to_prefix_count:
            country_name_to_prefix_count[country_name] = 0
        country_name_to_prefix_count[country_name] += 1

    print(f"Unique prefixes: {len(unique_prefixes)}")
    print(f"IP blocks not found in mapping: {ip_blocks_not_found}")
    

    countries = list(country_name_to_prefix_count.keys())
    counts = [country_name_to_prefix_count[country] for country in countries]
    
    
    print(f'Unique countries: {len(set(countries))}')

    plot_list_as_bar_plot(
        countries,
        counts,
        title=f"{name} - Prefixes by Country - {ip_version}",
        xlabel="Country",
        ylabel="Number of Prefixes",
        do_top_n=10, 
    )

if __name__ == "__main__":
    
    config = load_configs("ixbr.json")
    config = load_configs("MIX-IT.json")
    config = load_configs("AMS-IX.json")
    
    ip_version = get_ip_version(config)
    print_config(config, ip_version)

    name = config.get("name", "Unknown") 
  
    rrc = config["rrc"]
    start_date = datetime.datetime.strptime(config["start_date"], "%Y-%m-%d")
    end_date = datetime.datetime.strptime(config["end_date"], "%Y-%m-%d")
    day_delta = datetime.timedelta(days=config.get("day_delta", 7))
    time_str = config.get("time_str", "0000")   

    all_stats, labels = load_bview_data_timeline_from_configs(config, ip_version=ip_version,
                                                              skip_if_missing=3)    


    stat_before: BGPDumpSnapshotStats = all_stats[0]
    #first_stat = all_stats[1]

    #stat_before.sanity_check_on_mappings()
    #stat_before.sanity_check_on_prefix_mappings()

    if stat_before.prefix_mappings is None:
        print(f"No prefix mapping data available for {name} at {stat_before.datetime_str()}.")
        sys.exit(0)
        
    #prefix_mappings_member_has, prefix_mappings_member_reaches = first_stat.prefix_mappings
    prefix_mappings_member_has, prefix_mappings_member_reaches, prefix_mappings_asn_has = stat_before.get_prefix_mappings()
    #unique_prefixes = stat_before.get_unique_prefixes()

    if not prefix_mappings_member_has or not prefix_mappings_member_reaches or not prefix_mappings_asn_has:
        print(f"No prefix mapping data available for {name} at {stat_before.datetime_str()}.")
        sys.exit(0)

    #view_prefixes_grouped_by_length(prefix_mappings, name, ip_version)
    subfolder = f"{name}_{ip_version}_member_concentration"
    

    view_prefixes_member_concentration(stat_before, name, ip_version, from_self_or_others="Owned by the Member", subfolder=subfolder)
    #view_prefixes_member_concentration(stat_before, name, ip_version, from_self_or_others="Reached by the Member", subfolder=subfolder)
    #view_prefixes_member_concentration(stat_before, name, ip_version, from_self_or_others="Owned by ASN (member or reachable)", subfolder=subfolder)

    #view_unique_prefixes_member_concentration(prefix_mappings_member_reaches, name, ip_version, from_self_or_others="Reached by the Member", subfolder=subfolder)

    # plot_prefix_by_country()

    #view_prefix_changes(prefix_mappings, stat_before, first_stat, ip_version)

    '''
    prefixes_over_time = []
    for stat in all_stats:
        unique_prefixes = set()
        for prefixes in stat.prefix_mappings.values():
            unique_prefixes.update(prefixes)
        prefixes_over_time.append(len(unique_prefixes))
    
    address_spaces_over_time = []
    for stat in all_stats:
        unique_prefixes = set()
        for prefixes in stat.prefix_mappings.values():
            unique_prefixes.update(prefixes)
        address_count, _ = calculate_unique_addresses(unique_prefixes)
        address_spaces_over_time.append(address_count)
    
    plot_list_as_line_plot(
        address_spaces_over_time,
        y=labels,
        title=f"{name} - Total Address Space Over Time - {ip_version}",
        xlabel="Date",
        ylabel="Total Address Space (aggregated)",
    )

    plot_list_as_line_plot(
        prefixes_over_time,
        y=labels,
        title=f"{name} - Unique Prefixes Over Time - {ip_version}",
        xlabel="Date",
        ylabel="Unique Prefixes",
    )
    '''
    create_window_with_all_rendered_graphs_this_session()   
