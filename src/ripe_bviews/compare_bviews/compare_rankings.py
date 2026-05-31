def compare_top_asn_rankings(all_stats_ix1, all_stats_ix2, top_n=10,
                             compare_by="address_count", type_of_mapping="Owned by the Member"):
 
    # Map comparison types to methods
    method_map = {
        "reachables": "get_top_members_by_reachables",
        "prefix_count": "get_top_members_by_prefix_count",
        "address_count": "get_top_members_by_address_count",
        "unique_prefix_count": "get_top_members_by_unique_prefix_count",
        "unique_address_count": "get_top_members_by_unique_address_count",
    }
    
    if compare_by not in method_map:
        raise ValueError(f"Invalid compare_by value: {compare_by}. Must be one of {list(method_map.keys())}")
    
    method_name = method_map[compare_by]
    
    # Get top ASes from both IXPs using the specified method
    method_ix1 = getattr(all_stats_ix1[-1], method_name)
    method_ix2 = getattr(all_stats_ix2[-1], method_name)

    prefix_mappings_ix1 = all_stats_ix1[-1].get_prefix_mappings_for(type_of_mapping)
    prefix_mappings_ix2 = all_stats_ix2[-1].get_prefix_mappings_for(type_of_mapping)

    top_ases_from_ixp1 = [asn[0] for asn in method_ix1(prefix_mappings_ix1, top_n=top_n)]
    top_ases_from_ixp2 = [asn[0] for asn in method_ix2(prefix_mappings_ix2, top_n=top_n)]

    # Find common ASes
    top_ases_in_common = set(top_ases_from_ixp1).intersection(set(top_ases_from_ixp2))
    
    # Find ASes with same rank placement
    top_ases_in_common_that_appeared_in_same_rank = set()
    for asn in top_ases_in_common:
        index_in_ixp1 = top_ases_from_ixp1.index(asn)
        index_in_ixp2 = top_ases_from_ixp2.index(asn)
        if index_in_ixp1 == index_in_ixp2:
            top_ases_in_common_that_appeared_in_same_rank.add(asn)

    # Format comparison type label 
    compare_by_labels = {
        "reachables": "Reachable ASes",
        "prefix_count": "Prefix Count",
        "address_count": "Address Count",
        "unique_prefix_count": "Unique Prefix Count",
        "unique_address_count": "Unique Address Count",
    }
    label = compare_by_labels.get(compare_by, compare_by)

    # Create a mapping of common ASes to superscript numbers
    superscript_map = {
        '0': '*⁰', '1': '*¹', '2': '*²', '3': '*³', '4': '*⁴', 
        '5': '*⁵', '6': '*⁶', '7': '*⁷', '8': '*⁸', '9': '*⁹'
    }
    
    asn_to_number = {}
    for idx, asn in enumerate(sorted(top_ases_in_common), 1):
        asn_to_number[asn] = idx

    # Print summary
    print(f"\nConsidering {label} and comparing by {type_of_mapping}:")
    print(f"From the Top {top_n} ASes in each IXP (sorted by {label}):")
    print(f"  Number of ASes in common: {len(top_ases_in_common)}")
    print(f"  Number of ASes with matching rank placement: {len(top_ases_in_common_that_appeared_in_same_rank)}")
    print(f"  Common ASes list: {top_ases_in_common}\n")

    # Print side-by-side rankings
    print(f"{'Rank':<6} {'IXP1':<20} {'IXP2':<20}")
    print("-" * 50)
    
    for rank in range(top_n):
        asn1 = top_ases_from_ixp1[rank] if rank < len(top_ases_from_ixp1) else None
        asn2 = top_ases_from_ixp2[rank] if rank < len(top_ases_from_ixp2) else None
        
        # Format ASN with superscript marker if in common
        if asn1:
            num1 = asn_to_number.get(asn1, "")
            num_str1 = ''.join(superscript_map[d] for d in str(num1)) if num1 else ""
            asn1_str = f"AS{asn1}{num_str1}"
        else:
            asn1_str = "---"
        
        if asn2:
            num2 = asn_to_number.get(asn2, "")
            num_str2 = ''.join(superscript_map[d] for d in str(num2)) if num2 else ""
            asn2_str = f"AS{asn2}{num_str2}"
        else:
            asn2_str = "---"
        
        print(f"{rank+1:<6} {asn1_str:<20} {asn2_str:<20}")
    
    # Print legend
    if asn_to_number:
        print("\nCommon ASes Legend:")
        for asn in sorted(top_ases_in_common):
            num = asn_to_number[asn]
            num_str = ''.join(superscript_map[d] for d in str(num))
            marker = " (same rank)" if asn in top_ases_in_common_that_appeared_in_same_rank else ""
            print(f"  {num_str} = AS{asn}{marker}")
    print()

    return {
        "top_ases_from_ixp1": top_ases_from_ixp1,
        "top_ases_from_ixp2": top_ases_from_ixp2,
        "top_ases_in_common": top_ases_in_common,
        "top_ases_in_common_that_appeared_in_same_rank": top_ases_in_common_that_appeared_in_same_rank,
        "compare_by": compare_by
    }
