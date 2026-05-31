






import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data_timeline_from_configs
from src.ripe_bviews.download_and_parse.load_configs import load_configs
from src.ripe_bviews.oscillations.bview_oscillation_logic import calculate_oscillation_metrics
from src.ripe_bviews.timeline.bview_vars import get_ip_version, get_labels_info, get_labels_info, get_subfolder, get_title_start
from src.utils.graphs import create_window_with_all_rendered_graphs_this_session, plot_list_as_bar_plot, plot_list_as_line_plot, plot_stacked_line_plot




if __name__ == "__main__":
    config = load_configs("AMS-IX.json")

    config = load_configs("ixbr.json")
    title_start = get_title_start(config) 
    ip_version = get_ip_version(config)
    subfolder = get_subfolder(config, ip_version) + "/oscillation_metrics/"

    all_stats, labels = load_bview_data_timeline_from_configs(config, ip_version=ip_version)     

    labels_summarized, max_labels = get_labels_info(labels)

    metrics = calculate_oscillation_metrics(all_stats, calculate_routes=True) 
    metrics.load_oscillating_lists()
    metrics.load_route_oscillating_info()
    


    route_oscillation_info = metrics.route_oscillation_info

    unique_oscillating_asns = metrics.get_unique_oscillating_asns()
    oscillating_start_routes_over_time = metrics.oscillating_start_routes_over_time
    oscillating_end_routes_over_time = metrics.oscillating_end_routes_over_time


    plot_list_as_line_plot(oscillating_start_routes_over_time, labels_summarized[1:], title=title_start + "Routes Starting Oscillation Over Time", xlabel="Date", ylabel="Number of Routes Starting Oscillation", subfolder=subfolder, max_labels=max_labels)
    plot_list_as_line_plot(oscillating_end_routes_over_time, labels_summarized[1:], title=title_start + "Routes Ending Oscillation Over Time", xlabel="Date", ylabel="Number of Routes Ending Oscillation", subfolder=subfolder, max_labels=max_labels)

    
    
    oscillating_routes_from_non_oscillating_ases_over_time = []

    oscillating_routes_from_oscillating_ases = []

    for i in range(len(labels_summarized)-1):
        count_oscillating = 0
        count_non_oscillating = 0
        for route_info in route_oscillation_info:
            if route_info["start_idx"] == i:
                if route_info["member"] in unique_oscillating_asns:
                    count_oscillating += 1
                else:
                    count_non_oscillating += 1
        oscillating_routes_from_oscillating_ases.append(count_oscillating)
        oscillating_routes_from_non_oscillating_ases_over_time.append(count_non_oscillating)

    plot_stacked_line_plot(
        [
            oscillating_routes_from_oscillating_ases,
            oscillating_routes_from_non_oscillating_ases_over_time
        ],
        ["From Oscillating ASes", "From Non-Oscillating ASes"],
        x_labels=labels_summarized[1:],
        title=title_start + "Routes Starting Oscillation Over Time, Separated by Whether They Come From Oscillating ASes or Not",
        ylabel="Number of Routes Starting Oscillation", subfolder=subfolder, max_labels=max_labels
    )


    route_count_by_path_length_for_oscillating_routes = {}
    route_count_by_path_length_for_oscillating_routes_without_prepend = {}
    
    for route_info in route_oscillation_info:
        path_length = len(route_info["path"]) 
        path_length_without_prepend = len([asn for idx, asn in enumerate(route_info["path"]) if idx == 0 or asn != route_info["path"][idx - 1]])
        if path_length not in route_count_by_path_length_for_oscillating_routes:
            route_count_by_path_length_for_oscillating_routes[path_length] = 0
        route_count_by_path_length_for_oscillating_routes[path_length] += 1

        if path_length_without_prepend not in route_count_by_path_length_for_oscillating_routes_without_prepend:
            route_count_by_path_length_for_oscillating_routes_without_prepend[path_length_without_prepend] = 0
        route_count_by_path_length_for_oscillating_routes_without_prepend[path_length_without_prepend] += 1


    plot_list_as_bar_plot(
        [i for i in sorted(list(route_count_by_path_length_for_oscillating_routes.keys()))],
        list(route_count_by_path_length_for_oscillating_routes.values()),
                        max_x_value=10,
                          title=title_start + "Distribution of Path Lengths for Oscillating Routes", xlabel="Path Length", ylabel="Number of Oscillating Routes", subfolder=subfolder)
 
    plot_list_as_bar_plot(
        [i for i in sorted(list(route_count_by_path_length_for_oscillating_routes_without_prepend.keys()))],
        list(route_count_by_path_length_for_oscillating_routes_without_prepend.values()),
                        max_x_value=10,
                          title=title_start + "Distribution of Path Lengths for Oscillating Routes (Without Prepend)", xlabel="Path Length", ylabel="Number of Oscillating Routes", subfolder=subfolder)

    create_window_with_all_rendered_graphs_this_session()
