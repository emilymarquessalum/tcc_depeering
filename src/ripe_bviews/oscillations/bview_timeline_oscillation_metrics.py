



import sys
from pathlib import Path 

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Calculate oscillation metrics using the dedicated function
from datetime import datetime, timedelta
 

from src.ripe_bviews.bview_labels import get_date_range_title, summarized_date_labels, time_delta_title
from src.ripe_bviews.download_and_parse.load_configs import load_configs
from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data_timeline_from_configs
from src.ripe_bviews.oscillations.bview_oscillation_logic import calculate_oscillation_metrics, OscillationMetrics, get_comeback_times_count_from_oscillation_info
from src.ripe_bviews.timeline.bview_vars import get_annotations, get_ip_version, get_labels_info, get_subfolder, get_title_start
from src.utils.graphs import create_window_with_all_rendered_graphs_this_session, plot_list_as_bar_plot, plot_list_as_line_plot, plot_map_as_bar_plot, plot_stacked_line_plot



# growth if we were to ignore oscillations 
def calculate_non_oscillating_growth_metrics(metrics: OscillationMetrics):
    net_non_oscillating_growth = []
    for i in range(len(metrics.added_non_oscillating_asns_over_time)):
        net_growth = metrics.added_non_oscillating_asns_over_time[i] - metrics.removed_non_oscillating_asns_over_time[i]
        net_non_oscillating_growth.append(net_growth)

    net_non_oscillating_growth_accumulated = []
    cumulative_sum = 0
    for change in net_non_oscillating_growth:
        cumulative_sum += change
        net_non_oscillating_growth_accumulated.append(cumulative_sum)
    
    return net_non_oscillating_growth, net_non_oscillating_growth_accumulated



def calculate_comeback_time_metrics(metrics: OscillationMetrics):
    all_comeback_times = []
    print(f"debug: number of oscillation info {len(metrics.oscillation_info)}")
    for _, info in metrics.oscillation_info.items():
        if info["comeback_times"]:
            all_comeback_times.extend(info["comeback_times"])

    all_comeback_times_with_one_contribution_per_asn_in_a_time = []
    for _, info in metrics.oscillation_info.items():
        if info["comeback_times"]:
            all_comeback_times_with_one_contribution_per_asn_in_a_time.extend(set(info["comeback_times"]))

    average_time_ases_take_to_come_back = sum(all_comeback_times) / len(all_comeback_times) if all_comeback_times else 0
    
    return all_comeback_times, all_comeback_times_with_one_contribution_per_asn_in_a_time, average_time_ases_take_to_come_back

def plot_member_oscillation_statistics(comeback_times_count: dict, config, title_start, date_range_title_str, time_delta_title_str, subfolder):
    
    print(f"Number of different comeback times: {len(set(comeback_times_count.keys()))}")
    
    come_back_set = set(comeback_times_count.keys())
    ordered_comeback_times_count = sorted(comeback_times_count.items())
    ordered_comeback_values = [count for _, count in ordered_comeback_times_count]

    number_of_ases_label = "Number of ASes"
    time_to_come_back_label = "Time to Come Back (in snapshots)"

    plot_list_as_bar_plot(sorted(come_back_set), 
                        y=ordered_comeback_values,
                        max_x_value=20,
                        title=f"{title_start}Member Count of ASes by Time to Come Back {date_range_title_str} - {time_delta_title_str}",
                            xlabel=time_to_come_back_label, 
                            ylabel=number_of_ases_label,
                            subfolder=subfolder)


def plot_reachable_oscillation_statistics(reachable_oscillation_metrics, title_start, date_range_title_str, time_delta_title_str, subfolder):
    comeback_times_count_reachables, _ = get_comeback_times_count_from_oscillation_info(reachable_oscillation_metrics.oscillation_info)
    ordered_comeback_times_count_reachables = sorted(comeback_times_count_reachables.items()) 
    ordered_comeback_values_reachables = [count for _, count in ordered_comeback_times_count_reachables]

    number_of_ases_label = "Number of ASes"
    time_to_come_back_label = "Time to Come Back (in snapshots)"

    print(f"Oscillating Reachable ASes: {len(reachable_oscillation_metrics.oscillation_info)}")
    print("---")

    plot_list_as_bar_plot([time for time, _ in ordered_comeback_times_count_reachables],
                        y=ordered_comeback_values_reachables,
                        title=title_start + f"Reachable Count of ASes by Time to Come Back {date_range_title_str} - {time_delta_title_str}",
                            xlabel=time_to_come_back_label, 
                            ylabel=number_of_ases_label,
                        max_x_value=20,
                            subfolder=subfolder)

def plot_one_contribution_per_asn_comeback_times(all_comeback_times_with_one_contribution_per_asn_in_a_time, title_start, date_range_title_str, time_delta_title_str, subfolder):
    comeback_times_count_one_per_asn = {}
    for time in all_comeback_times_with_one_contribution_per_asn_in_a_time:
        if time not in comeback_times_count_one_per_asn:
            comeback_times_count_one_per_asn[time] = 0
        comeback_times_count_one_per_asn[time] += 1

    ordered_comeback_times_count_per_asn = sorted(comeback_times_count_one_per_asn.items())
    ordered_comeback_values = [count for time, count in ordered_comeback_times_count_per_asn]

    number_of_ases_label = "Number of ASes"
    time_to_come_back_label = "Time to Come Back (in snapshots)"

    plot_list_as_bar_plot([time for time, count in ordered_comeback_times_count_per_asn], 
                        y=ordered_comeback_values,
                        title=title_start + f"One-Contribution-Per-ASN-in-A-Time Count of ASes by Time to Come Back {date_range_title_str} - {time_delta_title_str}",
                            xlabel=time_to_come_back_label, 
                            ylabel=number_of_ases_label,
                            subfolder=subfolder)


def plot_oscillation_variance_over_time(metrics, labels_summarized, max_labels, title_start, ip_version, date_range_title_str, subfolder):
    total_oscillation_variance = metrics.get_oscillating_variance_over_time()

    plot_list_as_line_plot(total_oscillation_variance, summarized_date_labels(labels_summarized[1:]), title=title_start + f"Variance Oscillation Over Time - {ip_version} - {date_range_title_str}", xlabel="Date", ylabel="Oscillation Variance", subfolder=subfolder,
                        max_labels=max_labels)
    
    return total_oscillation_variance

def plot_added_asnes_oscillating_vs_non_oscillating(metrics, labels_summarized, max_labels, title_start, ip_version, date_range_title_str, subfolder):
    
    
    percentage_of_ases_added_that_are_oscillating_in_terms_of_the_total = 0
    sum_of_total_oscillating_added = sum(metrics.added_oscillating_asns_over_time)
    sum_of_total = sum(metrics.added_non_oscillating_asns_over_time) + sum_of_total_oscillating_added
    if sum_of_total > 0:
        percentage_of_ases_added_that_are_oscillating_in_terms_of_the_total = (sum_of_total_oscillating_added / sum_of_total) * 100
    
    print(f"Percentage of ASes added that are oscillating in terms of the total added: {percentage_of_ases_added_that_are_oscillating_in_terms_of_the_total:.2f}%")
    plot_stacked_line_plot([metrics.added_oscillating_asns_over_time, metrics.added_non_oscillating_asns_over_time], 
                        ["Oscillating ASes", "Non-Oscillating ASes"],
                        x_labels=labels_summarized[1:],
                        max_labels=max_labels, 
                        annotations=get_annotations(),
                        title=title_start + f"Added ASes - Oscillating vs Non-Oscillating Over Time - {ip_version} - {date_range_title_str}", 
                        xlabel="Date", 
                        ylabel="Number of Added ASes", subfolder=subfolder)

def analyze_added_asnes_proportions(metrics):
    average_added_oscillating_compared_to_total_added = []
    sum_of_total_added = 0
    sum_of_added_oscillating = 0
    for i in range(len(metrics.added_asns_over_time)):
        total_added = metrics.added_asns_over_time[i]
        added_oscillating = metrics.added_oscillating_asns_over_time[i]
        sum_of_total_added += total_added
        sum_of_added_oscillating += added_oscillating
        average_added_oscillating_compared_to_total_added.append(added_oscillating / total_added if total_added > 0 else 0)
    
    final_average = sum(average_added_oscillating_compared_to_total_added) / len(average_added_oscillating_compared_to_total_added) if average_added_oscillating_compared_to_total_added else 0
    proportion_added_oscillating_compared_to_total_added = sum_of_added_oscillating / sum_of_total_added if sum_of_total_added > 0 else 0
    
    print(f"Average proportion of added ASes that are oscillating: {final_average*100:.2f}%")
    print(f"Overall proportion of added ASes that are oscillating: {proportion_added_oscillating_compared_to_total_added*100:.2f}%")

def analyze_removed_asnes_proportions(metrics):
    average_removed_oscillating_compared_to_total_removed = [] 
    sum_of_total_removed = 0
    sum_of_removed_oscillating = 0
    for i in range(len(metrics.all_removed_asns_over_time)):
        total_removed = len(metrics.all_removed_asns_over_time[i])
        removed_oscillating = metrics.removed_oscillating_asns_over_time[i]
        sum_of_total_removed += total_removed
        sum_of_removed_oscillating += removed_oscillating   
        average_removed_oscillating_compared_to_total_removed.append(removed_oscillating / total_removed if total_removed > 0 else 0)
    
    final_average_removed = sum(average_removed_oscillating_compared_to_total_removed) / len(average_removed_oscillating_compared_to_total_removed) if average_removed_oscillating_compared_to_total_removed else 0
    proportion_removed_oscillating_compared_to_total_removed = sum_of_removed_oscillating / sum_of_total_removed if sum_of_total_removed > 0 else 0
    
    print(f"Average proportion of removed ASes that are oscillating: {final_average_removed*100:.2f}%")
    print(f"Overall proportion of removed ASes that are oscillating: {proportion_removed_oscillating_compared_to_total_removed*100:.2f}%")

def analyze_oscillation_variance_proportions(metrics, total_oscillation_variance):
    average_variance_oscillation_compared_to_total_variance = []
    sum_of_total_variance = 0
    sum_of_oscillation_variance = 0
    for i in range(len(total_oscillation_variance)):
        total_added = metrics.added_asns_over_time[i]
        total_removed = len(metrics.all_removed_asns_over_time[i])
        oscillation_variance = total_oscillation_variance[i]
        total_variance = total_added + total_removed
        sum_of_total_variance += total_variance
        sum_of_oscillation_variance += oscillation_variance
        average_variance_oscillation_compared_to_total_variance.append(oscillation_variance / total_variance if total_variance > 0 else 0)
    
    final_average_variance = sum(average_variance_oscillation_compared_to_total_variance) / len(average_variance_oscillation_compared_to_total_variance) if average_variance_oscillation_compared_to_total_variance else 0
    print(f"Average proportion of oscillation variance compared to total added ASes: {final_average_variance*100:.2f}%")
    print(f"Overall proportion of oscillation variance compared to total added ASes: {sum_of_oscillation_variance / sum_of_total_variance * 100:.2f}%")

def plot_removed_asnes_oscillating_vs_non_oscillating(metrics, labels_summarized, max_labels, title_start, ip_version, date_range_title_str, subfolder):
    
    
    percentage_of_removed_oscillating_ases_from_total = 0
    total_of_oscillatings_removed = sum(metrics.removed_oscillating_asns_over_time)
    total_removed = total_of_oscillatings_removed + sum(metrics.removed_non_oscillating_asns_over_time)

    if total_removed > 0:
        percentage_of_removed_oscillating_ases_from_total = (total_of_oscillatings_removed / total_removed) * 100
    print(f"Percentage of removed ASes that are oscillating in terms of the total removed: {percentage_of_removed_oscillating_ases_from_total:.2f}%")
    
    plot_stacked_line_plot([metrics.removed_oscillating_asns_over_time, metrics.removed_non_oscillating_asns_over_time], 
                        ["Came Back (Oscillating)", "Did Not Come Back"],
                        x_labels=labels_summarized[1:],
                        max_labels=max_labels,
                        title=title_start + "Removed ASes - Oscillating vs Non-Oscillating Over Time - " + ip_version + " - " + date_range_title_str,
                        xlabel="Date", 
                        ylabel="Number of Removed ASes", subfolder=subfolder)

def plot_non_oscillating_growth_over_time(net_non_oscillating_growth, net_non_oscillating_growth_accumulated, labels_summarized, max_labels, title_start, subfolder):
    plot_list_as_line_plot(net_non_oscillating_growth, labels_summarized[1:], 
                        title=title_start + "Net Growth of Non-Oscillating (Stable) ASes Over Time", 
                        xlabel="Date", 
                        ylabel="Net Change in Stable ASes",
                        max_labels=max_labels,
                        subfolder=subfolder)
    plot_list_as_line_plot(net_non_oscillating_growth_accumulated, labels_summarized[1:], 
                        title=title_start + "Net Growth Accumulated of Non-Oscillating (Stable) ASes Over Time", 
                        xlabel="Date", 
                        ylabel="Accumulated Stable ASes Change",
                        max_labels=max_labels,
                        subfolder=subfolder)

def plot_oscillating_start_end_over_time(metrics, labels_summarized, max_labels, title_start, subfolder):
    plot_list_as_line_plot(metrics.oscillating_start_over_time, labels_summarized[1:], title=title_start + "ASes Starting Oscillation Over Time", xlabel="Date", ylabel="Number of ASes Starting Oscillation", subfolder=subfolder, max_labels=max_labels)
    plot_list_as_line_plot(metrics.oscillating_end_over_time, labels_summarized[1:], title=title_start + "ASes Ending Oscillation Over Time", xlabel="Date", ylabel="Number of ASes Ending Oscillation", subfolder=subfolder, max_labels=max_labels)

def plot_oscillations_by_time_of_day(metrics, labels, config, title_start, ip_version, date_range_title_str, subfolder):
    oscillations_accumulated_by_time_str = {}

    for label in labels[1:]:
        time_str_in_label = label.split(" ")[1] 
        if time_str_in_label not in oscillations_accumulated_by_time_str:
            oscillations_accumulated_by_time_str[time_str_in_label] = 0
        index = labels.index(label)
        oscillations_accumulated_by_time_str[time_str_in_label] += metrics.oscillating_start_over_time[index - 1]
    
    time_str_label = []
    for time_str in oscillations_accumulated_by_time_str.keys():
        time_str_label.append(time_str)
    oscillations_y_time_str = [oscillations_accumulated_by_time_str[time_str] for time_str in time_str_label]
    
    utc_conversion = -3
    for i in range(len(time_str_label)):
        time_str_label[i] = (time_str_label[i][:2] + "h") + " (" + str((int(time_str_label[i][:2]) + utc_conversion) % 24) + "h)"
    
    plot_list_as_bar_plot(time_str_label, 
                        y=oscillations_y_time_str,
                        subfolder=subfolder,
                        title=title_start + f"Accumulated ASes Starting Oscillation by Time - {ip_version} - {date_range_title_str}")

    ended_oscillations_accumulated_by_time_str = {}
    for label in labels[1:]:
        time_str_in_label = label.split(" ")[1] 
        if time_str_in_label not in ended_oscillations_accumulated_by_time_str:
            ended_oscillations_accumulated_by_time_str[time_str_in_label] = 0
        index = labels.index(label)
        ended_oscillations_accumulated_by_time_str[time_str_in_label] += metrics.oscillating_end_over_time[index - 1]
    
    plot_list_as_bar_plot(list(ended_oscillations_accumulated_by_time_str.keys()), 
                        y=list(ended_oscillations_accumulated_by_time_str.values()),
                        subfolder=subfolder,
                        title=title_start + f"Accumulated ASes Ending Oscillation by Time String (UTC) {date_range_title_str}")




def bview_oscillation_metrics():

    config = load_configs("ixbr.json")
    config = load_configs("AMS-IX.json")

    title_start = get_title_start(config) 
    ip_version = get_ip_version(config)
    subfolder = get_subfolder(config, ip_version) + "/oscillation_metrics/"

    all_stats, labels = load_bview_data_timeline_from_configs(config, ip_version=ip_version)     

    labels_summarized, max_labels = get_labels_info(labels)

    snapshots_for_real_depeering = config.get("snapshots_for_real_depeering", 7)
    metrics = calculate_oscillation_metrics(all_stats, snapshots_for_real_depeering=snapshots_for_real_depeering) 
    total_oscillations = metrics.total_oscillations

    metrics.load_oscillating_lists()
    
    start_date = datetime.strptime(config["start_date"], "%Y-%m-%d")
    end_date = datetime.strptime(config["end_date"], "%Y-%m-%d")
    day_delta = timedelta(days=config.get("day_delta", 7))
    
    date_range_title_str = get_date_range_title(start_date, end_date)
    time_delta_title_str = time_delta_title(day_delta.days, config.get('time_delta_hours', 0))

    #net_non_oscillating_growth, net_non_oscillating_growth_accumulated = calculate_non_oscillating_growth_metrics(metrics)

    all_comeback_times, all_comeback_times_with_one_contribution_per_asn_in_a_time, average_time_ases_take_to_come_back = calculate_comeback_time_metrics(metrics)

    print(f"Oscillating ASes: {len(metrics.oscillation_info)}")
    print(f"Average time to come back (in snapshots): {average_time_ases_take_to_come_back:.2f}")
    time_to_comeback_in_days = average_time_ases_take_to_come_back * day_delta.days
    print(f"Average time to come back (in days): {time_to_comeback_in_days:.2f}")
    print(f"Total oscillations: {total_oscillations}")
    print(f"Total unique ASes that did not come back after removal: {len(metrics.all_did_not_come_backs)}")
    print(f"Potential depeerings below {snapshots_for_real_depeering} snapshots: {len(metrics.all_potential_depeerings)}")

    total_added_oscillations = 0
    total_removed_oscillations = 0

    for i in range(len(metrics.added_oscillating_asns_over_time)):
        added_oscillating = metrics.added_oscillating_asns_over_time[i]
        removed_oscillating = metrics.removed_oscillating_asns_over_time[i]
        total_added_oscillations += added_oscillating
        total_removed_oscillations += removed_oscillating
    
    # if there are double added ASNs than removed, 
    # the printed value should be 2
    if total_removed_oscillations > 0:
        percentage_difference =  (total_added_oscillations / total_removed_oscillations) * 100
        print(f"Percentage difference between added and removed oscillating ASNs: {percentage_difference:.2f}%")
    else:
        print("No removed oscillating ASNs to calculate percentage difference.")



    comeback_times_count = {}
    for time in all_comeback_times:
        if time not in comeback_times_count:
            comeback_times_count[time] = 0
        comeback_times_count[time] += 1

    plot_member_oscillation_statistics(comeback_times_count, config, title_start, date_range_title_str, time_delta_title_str, subfolder)
    
    sys.exit(0)
    reachable_oscillation_metrics = calculate_oscillation_metrics(all_stats, use_reachables=True, snapshots_for_real_depeering=snapshots_for_real_depeering)
    plot_reachable_oscillation_statistics(reachable_oscillation_metrics, title_start, date_range_title_str, time_delta_title_str, subfolder)

    plot_one_contribution_per_asn_comeback_times(all_comeback_times_with_one_contribution_per_asn_in_a_time, title_start, date_range_title_str, time_delta_title_str, subfolder)
    
    #plot_added_removed_asnes_over_time(metrics, labels_summarized, max_labels, title_start, subfolder)

    total_oscillation_variance = plot_oscillation_variance_over_time(metrics, labels_summarized, max_labels, title_start, ip_version, date_range_title_str, subfolder)

    plot_added_asnes_oscillating_vs_non_oscillating(metrics, labels_summarized, max_labels, title_start, ip_version, date_range_title_str, subfolder)

    analyze_added_asnes_proportions(metrics)
    
    analyze_removed_asnes_proportions(metrics)
    
    analyze_oscillation_variance_proportions(metrics, total_oscillation_variance)

    plot_removed_asnes_oscillating_vs_non_oscillating(metrics, labels_summarized, max_labels, title_start, ip_version, date_range_title_str, subfolder)

    oscillating_frequency = {}
    for asn, info in metrics.oscillation_info.items():
        num_oscillations = info["oscillations"]
        if num_oscillations not in oscillating_frequency:
            oscillating_frequency[num_oscillations] = 0
        oscillating_frequency[num_oscillations] += 1 
    
    sorted_keys = sorted(oscillating_frequency.keys())
    plot_list_as_bar_plot(sorted_keys, [oscillating_frequency[k] for k in sorted_keys],
                            title=f"{title_start} Frequency of Oscillations for ASes - {config.get('name', 'Unknown')} - {date_range_title_str} - {ip_version}",
                            xlabel="Number of Oscillations",
                            ylabel="Number of ASes",    
                            subfolder=subfolder)
    #plot_non_oscillating_growth_over_time(net_non_oscillating_growth, net_non_oscillating_growth_accumulated, labels_summarized, max_labels, title_start, subfolder)

    #plot_oscillating_start_end_over_time(metrics, labels_summarized, max_labels, title_start, subfolder)

    #plot_oscillations_by_time_of_day(metrics, labels, config, title_start, ip_version, date_range_title_str, subfolder)
 




def bview_oscillations(all_required_data):

    oscillation_data = all_required_data["oscillations"]
    all_stats, labels_summarized, max_labels = all_required_data["timeline"]

    config = all_required_data["config"]
    title_start = get_title_start(config)
    ip_version = get_ip_version(config)
    subfolder = get_subfolder(config, ip_version) + "/oscillation_metrics/"
    snapshots_for_real_depeering = config.get("snapshots_for_real_depeering", 0)
    date_range_title_str = get_date_range_title(datetime.strptime(config["start_date"], "%Y-%m-%d"), datetime.strptime(config["end_date"], "%Y-%m-%d"))
    time_delta_title_str = time_delta_title(config.get("day_delta", 7), config.get('time_delta_hours', 0))

    all_comeback_times, all_comeback_times_with_one_contribution_per_asn_in_a_time, average_time_ases_take_to_come_back = calculate_comeback_time_metrics(oscillation_data)

    comeback_times_count = {}
    for time in all_comeback_times:
        if time not in comeback_times_count:
            comeback_times_count[time] = 0
        comeback_times_count[time] += 1 

    plot_member_oscillation_statistics(comeback_times_count, config, title_start, date_range_title_str, time_delta_title_str, subfolder)
    plot_added_asnes_oscillating_vs_non_oscillating(oscillation_data, labels_summarized, max_labels, title_start, ip_version, date_range_title_str, subfolder)
    plot_removed_asnes_oscillating_vs_non_oscillating(oscillation_data, labels_summarized, max_labels, title_start, ip_version, date_range_title_str, subfolder)
    print(f"Potential depeerings below {snapshots_for_real_depeering} snapshots: {len(getattr(oscillation_data, 'all_potential_depeerings', []))}")

    return
    reachable_oscillation_metrics = calculate_oscillation_metrics(all_stats, use_reachables=True)
    plot_reachable_oscillation_statistics(reachable_oscillation_metrics, title_start, date_range_title_str, time_delta_title_str, subfolder)

    plot_one_contribution_per_asn_comeback_times(all_comeback_times_with_one_contribution_per_asn_in_a_time, title_start, date_range_title_str, time_delta_title_str, subfolder)
    
    #plot_added_removed_asnes_over_time(metrics, labels_summarized, max_labels, title_start, subfolder)

    total_oscillation_variance = plot_oscillation_variance_over_time(metrics, labels_summarized, max_labels, title_start, ip_version, date_range_title_str, subfolder)

    
    analyze_added_asnes_proportions(metrics)
    
    analyze_removed_asnes_proportions(metrics)
    
    analyze_oscillation_variance_proportions(metrics, total_oscillation_variance)

    
    oscillating_frequency = {}
    for asn, info in metrics.oscillation_info.items():
        num_oscillations = info["oscillations"]
        if num_oscillations not in oscillating_frequency:
            oscillating_frequency[num_oscillations] = 0
        oscillating_frequency[num_oscillations] += 1 
    
    sorted_keys = sorted(oscillating_frequency.keys())
    plot_list_as_bar_plot(sorted_keys, [oscillating_frequency[k] for k in sorted_keys],
                            title=f"{title_start} Frequency of Oscillations for ASes - {config.get('name', 'Unknown')} - {date_range_title_str} - {ip_version}",
                            xlabel="Number of Oscillations",
                            ylabel="Number of ASes",    
                            subfolder=subfolder)
    

if __name__ == "__main__":
    bview_oscillation_metrics()

    create_window_with_all_rendered_graphs_this_session()