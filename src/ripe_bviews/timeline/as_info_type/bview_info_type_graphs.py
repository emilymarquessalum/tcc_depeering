

from src.utils.graphs import plot_list_as_bar_plot


def plot_categories_from_ipverse_data(results_matched, label, labels,ip_version="--"):
    categories_count_from_ipverse = {}
    for res in results_matched:
        category = res["category"]
        categories_count_from_ipverse[category] = categories_count_from_ipverse.get(category, 0) + 1
     
  
    plot_list_as_bar_plot( 
        [(v.capitalize().replace("_", " ") if v is not None else "Unknown") for v in list(categories_count_from_ipverse.keys())],
        list(categories_count_from_ipverse.values()),
         title=f"{label} ASes, by IPVerse AS Category and PeeringDB info_type - for {labels[0].replace('/', '_')} {ip_version}",
          xlabel=f"Number of ASes {label}",
          ylabel="IPVerse AS Category",
          sort_by_size=True,
          sort_by_size_cut=5 
    ) 