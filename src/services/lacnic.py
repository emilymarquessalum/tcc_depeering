


import ipaddress

from matplotlib import pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path
import sys

from src.ripe_bviews.read_bgpdump import BGPDumpSnapshotStats
from src.ripe_bviews.timeline.as_info_type.bview_timeline_by_as_info_type import create_asn_to_astype_map
from src.utils.prefixes import get_prefixes_announced_in_ixp_that_are_delegated, sum_unique_48_proportions


sys.path.insert(0, str(Path(__file__).parent.parent.parent))  
from src.services.nicbr import get_prefix_to_asn_mapping_data
from src.utils.file_parsing import download_google_drive_json, download_txt_from_path


url_lacnic = "https://ftp.lacnic.net/pub/stats/lacnic/delegated-lacnic-latest"


def get_lacnic_data():
  columns_to_keep_lacnic = [1, 2, 3, 4]
  header = ["country_code", "resource_type", "resource_number", "resource_size"]

  cache_path_name_lacnic = download_txt_from_path(url_lacnic)

  df = pd.read_csv(
      cache_path_name_lacnic,
      sep="|",
      skiprows=4,
      usecols=columns_to_keep_lacnic,
      names=header,
      header=None,
      engine="python",
  )

  return df


def get_prefixes_delegated_to_br_df():
   
    lacnic_delegations_df = get_lacnic_data()

    lacnic_delegations_df = lacnic_delegations_df[
        (lacnic_delegations_df["resource_type"] == "ipv6")
    ]

    def map_prefix_by_row(row): 
        row_str = f"{row['resource_number']}/{int(row['resource_size'])}"
        return ipaddress.IPv6Network(row_str)

    prefixes_delegated_to_br_df = lacnic_delegations_df[
        (lacnic_delegations_df["country_code"] == "BR")
    ]
    

    prefixes_delegated_to_br_df["network"] = prefixes_delegated_to_br_df.apply(
    map_prefix_by_row,
    axis=1
    )

    prefixes_delegated_to_br_df = prefixes_delegated_to_br_df.drop(["country_code"], axis=1)


    prefix_to_asn_nic_mapping_df = get_prefix_to_asn_mapping_data()

    prefixes_delegated_to_br_df["network_str"] = prefixes_delegated_to_br_df["network"].astype(str)


    exploded = prefix_to_asn_nic_mapping_df.explode("prefixes")

    prefix_to_asns_nic = (exploded.groupby("prefixes")["ASN"].agg(list)).reset_index()
    prefix_to_asns_nic.rename(columns={"prefixes": "prefix_delegated"}, inplace=True)

    prefixes_delegated_to_br_df  = prefixes_delegated_to_br_df.merge(
      prefix_to_asns_nic[["prefix_delegated", "ASN"]],
      left_on="network_str",
      right_on="prefix_delegated",
      how="left"
    )


    prefixes_delegated_to_br_df = prefixes_delegated_to_br_df.rename(columns={"ASN": "asns"})

    prefixes_delegated_to_br_df = prefixes_delegated_to_br_df.drop(columns=["prefix_delegated" ])
    return prefixes_delegated_to_br_df


def lacnic_delegation_analysis(all_required_data):
    
    all_stats, _, _ = all_required_data["timeline"]
    caida_data = all_required_data["caida_data"] 

    last_stats: BGPDumpSnapshotStats = all_stats[-1]

    last_stats_all_reachable_info = last_stats.mappings.values()
   
    def flatten(xss):
        return [x for xs in xss for x in xs]
    last_stats_all_reachable_info = flatten(last_stats_all_reachable_info)
    ixbr_fortaleza_df = pd.DataFrame(
        {
            "prefix": [v["prefix"] for v in last_stats_all_reachable_info],
            "as_path": [v["as_path"] for v in last_stats_all_reachable_info]
        }
    )
    
    prefixes_delegated_to_br_df = get_prefixes_delegated_to_br_df()
 

    df_delegated = prefixes_delegated_to_br_df.copy()
    df_delegated["asns"] = df_delegated["asns"].dropna() 

      
    df_delegated_exploded = df_delegated.explode("asns")
    


    fortaleza_announced_df = get_prefixes_announced_in_ixp_that_are_delegated(prefixes_delegated_to_br_df, ixbr_fortaleza_df)

    df_announced = fortaleza_announced_df.copy()


    df_announced_exploded = df_announced.explode("origin_ases")


    unique_ases_delegated = df_delegated["asns"].dropna().explode().astype(int).unique()

    unique_ases_announced = df_announced["origin_ases"].dropna().explode().astype(int).unique()
    
    unique_ases = list(set(unique_ases_delegated).union(set(unique_ases_announced)))

    cnpj_mapping_dict = {}
    as_to_category_map = create_asn_to_astype_map(unique_ases, caida_data, cnpj_mapping_dict=cnpj_mapping_dict)

    print(cnpj_mapping_dict)
   
    df_delegated_exploded["categories"] = (
    df_delegated_exploded["asns"]
    .fillna(0).astype(int)  
    .map(as_to_category_map)
    .fillna("unknown")
    )
    df_delegated_exploded["categories"] = df_delegated_exploded["categories"].fillna("unknown")
 
    use_48_proportion = False

    if use_48_proportion:
        delegated_stats = (
            df_delegated_exploded.groupby("categories")["network"]
            .apply(sum_unique_48_proportions)
            .reset_index(name="delegated_48s")
        )
    else:
        delegated_stats = (
            df_delegated_exploded.groupby("categories")["network"]
            .count()
            .reset_index(name="delegated_48s")
        )

    df_announced_exploded["categories"] = (
    df_announced_exploded["origin_ases"]
    .fillna(0).astype(int) # temporarily fillna to cast to int safely
    .map(as_to_category_map)
    .fillna("unknown")
    )
    df_announced_exploded["categories"] = df_announced_exploded["categories"].fillna("unknown")

    if use_48_proportion:
        announced_stats = (
            df_announced_exploded.groupby("categories")["original_prefix_announcement"]
            .apply(lambda series: sum_unique_48_proportions(
                [
                    prefix 
                    for item in series 
                    for prefix in (item if isinstance(item, list) else [item]) 
                    if pd.notna(prefix)
                ]
            ))
            .reset_index(name="announced_48s")
        )
    else:
        announced_stats = (
            df_announced_exploded.groupby("categories")["original_prefix_announcement"] 
            .count()
            .reset_index(name="announced_48s")
        )

    category_stats = delegated_stats.merge(announced_stats, on="categories", how="outer").fillna(0)
    
    # ADDED: Calculate percentage (handling Division by Zero safely)
    category_stats["percentage"] = np.where(
        category_stats["delegated_48s"] > 0,
        (category_stats["announced_48s"] / category_stats["delegated_48s"]) * 100,
        0.0
    )

    category_stats = category_stats.sort_values(by="delegated_48s", ascending=False)

    categories = category_stats["categories"].tolist()
    delegated_vals = category_stats["delegated_48s"].tolist()
    announced_vals = category_stats["announced_48s"].tolist()
    percentage_vals = category_stats["percentage"].tolist()  # ADDED

    x = np.arange(len(categories))

    def format_with_suffix(x):
        if x <= 0: return '0'
        elif x >= 1_000_000_000: return f'{x / 1_000_000_000:.1f}B'.replace('.0B', 'B')
        elif x >= 1_000_000: return f'{x / 1_000_000:.1f}M'.replace('.0M', 'M')
        elif x >= 1_000: return f'{x / 1_000:.1f}K'.replace('.0K', 'K')
        return f'{int(x)}'

    fig, ax = plt.subplots(figsize=(12, 6))
    n_top = 6
    width = 0.3
    rect_pad = 0.05

    x_subset = x[:n_top]
    categories_subset = categories[:n_top]

    # Dynamic Legend Labels
    label_delegated = 'Delegated /48 Equivalents' if use_48_proportion else 'Total Delegated Prefixes'
    label_announced = 'Announced /48 Equivalents (Fortaleza)' if use_48_proportion else 'Total Announced Prefixes (Fortaleza)'

    rects1 = ax.bar(x_subset - width/2, delegated_vals[:n_top], width, label=label_delegated, color='#1f77b4')
    rects2 = ax.bar(rect_pad + x_subset + width/2, announced_vals[:n_top], width, label=label_announced, color='#ff7f0e')

    ax.set_ylabel('Total /48 Equivalent Prefixes' if use_48_proportion else "Total Prefixes", fontsize=12)
    ax.set_xlabel('Category', fontsize=12)
    ax.set_title('IPv6 Allocation Space vs. Visibility in Fortaleza by Category'
                  + (" (/48 Units)" if use_48_proportion else ""), fontsize=14, fontweight='bold')

    ax.set_xticks(x_subset)
    ax.set_xticklabels(categories_subset, rotation=0, ha='center', fontsize=11)
    
    # Raised the top limit slightly (1.3) to make room for the percentage text above the bars
    ax.set_ylim(top=max(delegated_vals[:n_top]) * 1.3)
    ax.legend(fontsize=11)
    ax.grid(axis='y', linestyle='--', alpha=0.7)

    # Base counts/proportions on bars
    ax.bar_label(rects1, padding=5, fmt=format_with_suffix, fontsize=9)
    ax.bar_label(rects2, padding=5, fmt=format_with_suffix, fontsize=9)

    # ADDED: Loop to add percentage labels centered above each category's bar cluster
    for i in range(len(x_subset)):
        highest_bar_y = max(delegated_vals[i], announced_vals[i])
        pct_text = f"{percentage_vals[i]:.1f}%"
        
        ax.text(
            x=x_subset[i] + (rect_pad / 2),           # Center between the two bars
            y=highest_bar_y + (max(delegated_vals[:n_top]) * 0.08),  # Position safely above the taller bar
            s=pct_text,
            ha='center',
            va='bottom',
            fontsize=10,
            fontweight='bold',
            color='#2c3e50',
            bbox=dict(facecolor='white', alpha=0.6, edgecolor='none', boxstyle='round,pad=0.2') # Cleaner visibility
        )

    file_name = 'prefixes_by_category_48_proportions.png' if use_48_proportion else "prefixes_by_category.png"
    plt.savefig(file_name, dpi=300, bbox_inches='tight')

    print(f"Saved {file_name}") 

    df_delegated_as_counts = (
        df_delegated_exploded.groupby("categories")["asns"]
        .nunique()
        .reset_index(name="delegated_as_count")
    )

    # 2. Count unique ASes per category for ANNOUNCED space
    # (Grouping by category and counting unique elements in the 'origin_ases' column)
    df_announced_as_counts = (
        df_announced_exploded.groupby("categories")["origin_ases"]
        .nunique()
        .reset_index(name="announced_as_count")
    )

    # 3. Merge the two counts together cleanly
    as_counts_stats = pd.merge(
        df_delegated_as_counts, 
        df_announced_as_counts, 
        on="categories", 
        how="outer"
    ).fillna(0)

    # Convert counts to integers since nunique can be filled with 0
    as_counts_stats["delegated_as_count"] = as_counts_stats["delegated_as_count"].astype(int)
    as_counts_stats["announced_as_count"] = as_counts_stats["announced_as_count"].astype(int)

    # Print out a clean summary to the console
    print("\n=== Unique AS Count by Category ===")
    for _, row in as_counts_stats.iterrows():
        print(f"Category: {row['categories']}")
        print(f"  -> {row['delegated_as_count']} ASes are delegating")
        print(f"  -> {row['announced_as_count']} ASes are announcing")
        print("-" * 40)

    # 4. Plotting the AS Count comparison
    fig2, ax2 = plt.subplots(figsize=(12, 6))
    
    # Sorting by delegated AS count for a consistent visual hierarchy
    as_counts_stats = as_counts_stats.sort_values(by="delegated_as_count", ascending=False)
    
    cat_labels = as_counts_stats["categories"].tolist()
    del_as_vals = as_counts_stats["delegated_as_count"].tolist()
    ann_as_vals = as_counts_stats["announced_as_count"].tolist()
    
    x_indices = np.arange(len(cat_labels))
    
    rects_del = ax2.bar(x_indices - width/2, del_as_vals, width, label='Delegated ASes', color='#2ca02c')
    rects_ann = ax2.bar(rect_pad + x_indices + width/2, ann_as_vals, width, label='Announced ASes (Fortaleza)', color='#9467bd')
    
    ax2.set_ylabel('Number of Unique ASes', fontsize=12)
    ax2.set_xlabel('Category', fontsize=12)
    ax2.set_title('Unique Autonomous Systems (ASes) by Category', fontsize=14, fontweight='bold')
    
    ax2.set_xticks(x_indices)
    ax2.set_xticklabels(cat_labels, rotation=0, ha='center', fontsize=11)
    ax2.set_ylim(top=max(del_as_vals) * 1.2)
    ax2.legend(fontsize=11)
    ax2.grid(axis='y', linestyle='--', alpha=0.7)
    
    # Attach numeric labels directly above the bars
    ax2.bar_label(rects_del, padding=3, fontsize=9)
    ax2.bar_label(rects_ann, padding=3, fontsize=9)
    
    as_fig_name = 'as_counts_by_category.png'
    plt.savefig(as_fig_name, dpi=300, bbox_inches='tight')
    print(f"Saved {as_fig_name}") 