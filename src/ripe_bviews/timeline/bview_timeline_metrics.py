# ASes que foram removidos de uma data para a próxima
# ASes que foram adicionados de uma data para a próxima
# ASes que começaram oscilação nessa data (sair, voltar, sair) ou (voltar, sair, voltar)
# ASes que terminaram oscilação nessa data

from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from src.ripe_bviews.bview_labels import date_range_title, summarized_date_labels, time_delta_title
from src.ripe_bviews.download_and_parse.load_configs import load_configs
from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data_timeline, load_bview_data_timeline_from_configs
from src.ripe_bviews.timeline.bview_timeline import load_bview_data
from src.ripe_bviews.oscillations.bview_oscillation_logic import calculate_oscillation_metrics, get_comeback_times_count_from_oscillation_info

from src.utils.graphs import plot_list_as_bar_plot, plot_list_as_line_plot, plot_stacked_line_plot
import warnings

warnings.filterwarnings('ignore', category=UserWarning, message='.*Skipping download.*')
 
config = load_configs("ixbr.json")
#config = load_configs("de-cix-amsterdam.json")

ip_version = "v4"

asn_and_prefix = config["asn_and_prefix"].get("asn"), config["asn_and_prefix"].get("prefix")

rrc = config["rrc"]
start_date = datetime.strptime(config["start_date"], "%Y-%m-%d")
end_date = datetime.strptime(config["end_date"], "%Y-%m-%d")
day_delta = timedelta(days=config.get("day_delta", 7))
time_str = config.get("time_str", "0000")

#all_stats, labels = load_bview_data_timeline(start_date, end_date, asn_and_prefix, rrc, day_delta=day_delta, time_str=time_str, time_delta_hours=config.get("time_delta_hours", 0), ip_version=ip_version)
all_stats, labels = load_bview_data_timeline_from_configs(config, ip_version=ip_version)     

subfolder = rrc + "/" + ip_version + "/" + start_date.strftime("%Y%m%d") + "_" + end_date.strftime("%Y%m%d") + "_" + time_str + "/" + str(day_delta.days) + "days" + "/"
  
   
# Calculate oscillation metrics using the dedicated function
metrics = calculate_oscillation_metrics(all_stats)
oscillation_info = metrics.oscillation_info
total_oscillations = metrics.total_oscillations

metrics.load_oscillating_lists()
 
 
 
# Calculate net growth of non-oscillating ASes (stable membership)
net_non_oscillating_growth = []
for i in range(len(metrics.added_non_oscillating_asns_over_time)):
    net_growth = metrics.added_non_oscillating_asns_over_time[i] - metrics.removed_non_oscillating_asns_over_time[i]
    net_non_oscillating_growth.append(net_growth)

net_non_oscillating_growth_accumulated = []
cumulative_sum = 0
for change in net_non_oscillating_growth:
    cumulative_sum += change
    net_non_oscillating_growth_accumulated.append(cumulative_sum)



# Calculate average time ASes take to come back
all_comeback_times = []
for _, info in metrics.oscillation_info.items():
    all_comeback_times.extend(info["comeback_times"])

all_comeback_times_with_one_contribution_per_asn_in_a_time = []
for _, info in metrics.oscillation_info.items():
    if info["comeback_times"]:
        all_comeback_times_with_one_contribution_per_asn_in_a_time.extend(set(info["comeback_times"]))


average_time_ases_take_to_come_back = sum(all_comeback_times) / len(all_comeback_times) if all_comeback_times else 0

print(f"Oscillating ASes: {len(metrics.oscillation_info)}")

print(f"Average time to come back (in snapshots): {average_time_ases_take_to_come_back:.2f}")
time_to_comeback_in_days = average_time_ases_take_to_come_back * day_delta.days
print(f"Average time to come back (in days): {time_to_comeback_in_days:.2f}")


print(f"Total oscillations: {total_oscillations}")
 
print(f"Total unique ASes that did not come back after removal: {len(metrics.all_did_not_come_backs)}")

comeback_times_count = {}
for time in all_comeback_times:
    if time not in comeback_times_count:
        comeback_times_count[time] = 0
    comeback_times_count[time] += 1

come_back_set = set(all_comeback_times)
print(f"Unique comeback times (in snapshots): {sorted(come_back_set)}")

ordered_comeback_times_count = sorted(comeback_times_count.items())
ordered_comeback_values = [count for _, count in ordered_comeback_times_count]

time_to_come_back_label = "Time to Come Back (in snapshots)"
title_start = f"{config.get('name')} - "
number_of_ases_label = "Number of ASes"


labels_summarized = summarized_date_labels(labels)
max_labels=len(labels)//6


# x axis will be  time to come back in snapshots, y axis will be number of ASes that came back in that time
plot_list_as_bar_plot(come_back_set , 
                     y=ordered_comeback_values,
                     max_x_value=20,
                     title=f"{title_start}Member Count of ASes by Time to Come Back {date_range_title(start_date, end_date)} - {time_delta_title(day_delta.days, config.get('time_delta_hours', 0))}",
                        xlabel=time_to_come_back_label, 
                        ylabel=number_of_ases_label,
                        subfolder=subfolder)

reachable_oscillation_metrics = calculate_oscillation_metrics(all_stats, use_reachables=True)
comeback_times_count_reachables, come_back_set_reachables = get_comeback_times_count_from_oscillation_info(reachable_oscillation_metrics.oscillation_info)

ordered_comeback_times_count_reachables = sorted(comeback_times_count_reachables.items()) 
ordered_comeback_values_reachables = [count for _, count in ordered_comeback_times_count_reachables]

 
plot_list_as_bar_plot( [time for time, _ in ordered_comeback_times_count_reachables]
                        ,
                     y=ordered_comeback_values_reachables,
                     title=title_start + f"Reachable Count of ASes by Time to Come Back {date_range_title(start_date, end_date)} - {time_delta_title(day_delta.days, config.get('time_delta_hours', 0))}",
                        xlabel=time_to_come_back_label, 
                        ylabel=number_of_ases_label,
                     max_x_value=20,
                        subfolder=subfolder)



comeback_times_count_one_per_asn = {}
for time in all_comeback_times_with_one_contribution_per_asn_in_a_time:
    if time not in comeback_times_count_one_per_asn:
        comeback_times_count_one_per_asn[time] = 0
    comeback_times_count_one_per_asn[time] += 1

come_back_set = set(all_comeback_times_with_one_contribution_per_asn_in_a_time)
print(f"Unique comeback times (in snapshots): {sorted(come_back_set)}")

ordered_comeback_times_count_per_asn = sorted(comeback_times_count_one_per_asn.items())
ordered_comeback_values = [count for time, count in ordered_comeback_times_count_per_asn]
plot_list_as_bar_plot([time for time, count in ordered_comeback_times_count_per_asn] , 
                     y=ordered_comeback_values,
                     title=title_start + f"One-Contribution-Per-ASN-in-A-Time Count of ASes by Time to Come Back {date_range_title(start_date, end_date)} - {time_delta_title(day_delta.days, config.get('time_delta_hours', 0))}",
                        xlabel=time_to_come_back_label, 
                        ylabel=number_of_ases_label,
                        subfolder=subfolder)
 
plot_list_as_line_plot(metrics.removed_asns_over_time, labels_summarized[1:], 
                       max_labels=max_labels,
                       title="Removed ASes Over Time", xlabel="Date", ylabel="Number of Removed ASes", subfolder=subfolder)
plot_list_as_line_plot(metrics.added_asns_over_time, labels_summarized[1:], 
                       max_labels=max_labels,
                       title="Added ASes Over Time", xlabel="Date", ylabel="Number of Added ASes", subfolder=subfolder)


total_oscillation_variance = metrics.get_oscillating_variance_over_time()

plot_list_as_line_plot(total_oscillation_variance, summarized_date_labels(labels_summarized[1:]), title=title_start + "Variance Oscillation Over Time", xlabel="Date", ylabel="Oscillation Variance", subfolder=subfolder,
                       max_labels=max_labels
                       )

plot_stacked_line_plot([metrics.added_oscillating_asns_over_time, metrics.added_non_oscillating_asns_over_time], 
                       ["Oscillating ASes", "Non-Oscillating ASes"],
                       x_labels=labels_summarized[1:],
                       max_labels=max_labels, 
                       title=title_start + "Added ASes - Oscillating vs Non-Oscillating Over Time", 
                       xlabel="Date", 
                       ylabel="Number of Added ASes", subfolder=subfolder)

average_added_oscillating_compared_to_total_added = []
for i in range(len(metrics.added_asns_over_time)):
    total_added = metrics.added_asns_over_time[i]
    added_oscillating = metrics.added_oscillating_asns_over_time[i]
    average_added_oscillating_compared_to_total_added.append(added_oscillating / total_added if total_added > 0 else 0)
final_average = sum(average_added_oscillating_compared_to_total_added) / len(average_added_oscillating_compared_to_total_added) if average_added_oscillating_compared_to_total_added else 0
print(f"Average proportion of added ASes that are oscillating: {final_average*100:.2f}%")

average_removed_oscillating_compared_to_total_removed = [] 
for i in range(len(metrics.all_removed_asns_over_time)):
    total_removed = len(metrics.all_removed_asns_over_time[i])
    removed_oscillating = metrics.removed_oscillating_asns_over_time[i]
    average_removed_oscillating_compared_to_total_removed.append(removed_oscillating / total_removed if total_removed > 0 else 0)
final_average_removed = sum(average_removed_oscillating_compared_to_total_removed) / len(average_removed_oscillating_compared_to_total_removed) if average_removed_oscillating_compared_to_total_removed else 0
print(f"Average proportion of removed ASes that are oscillating: {final_average_removed*100:.2f}%")

average_variance_oscillation_compared_to_total_variance = []
for i in range(len(total_oscillation_variance)):
    total_added = metrics.added_asns_over_time[i]
    total_removed = len(metrics.all_removed_asns_over_time[i])
    variance = total_oscillation_variance[i]
    total_variance = total_added + total_removed
    average_variance_oscillation_compared_to_total_variance.append(variance / total_variance if total_variance > 0 else 0)
final_average_variance = sum(average_variance_oscillation_compared_to_total_variance) / len(average_variance_oscillation_compared_to_total_variance) if average_variance_oscillation_compared_to_total_variance else 0
print(f"Average proportion of oscillation variance compared to total added ASes: {final_average_variance*100:.2f}%")

plot_stacked_line_plot([metrics.removed_oscillating_asns_over_time, metrics.removed_non_oscillating_asns_over_time], 
                       ["Came Back (Oscillating)", "Did Not Come Back"],
                       x_labels=labels_summarized[1:],
                       max_labels=max_labels,
                       title=title_start + "Removed ASes - Oscillating vs Non-Oscillating Over Time", 
                       xlabel="Date", 
                       ylabel="Number of Removed ASes", subfolder=subfolder)

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

plot_list_as_line_plot(metrics.oscillating_start_over_time, labels_summarized[1:], title=title_start + "ASes Starting Oscillation Over Time", xlabel="Date", ylabel="Number of ASes Starting Oscillation", subfolder=subfolder, max_labels=max_labels)
plot_list_as_line_plot(metrics.oscillating_end_over_time, labels_summarized[1:], title=title_start + "ASes Ending Oscillation Over Time", xlabel="Date", ylabel="Number of ASes Ending Oscillation", subfolder=subfolder, max_labels=max_labels)

oscillations_accumulated_by_time_str = {}

for label in labels[1:]:
    time_str_in_label = label.split(" ")[1] 
    if time_str_in_label not in oscillations_accumulated_by_time_str:
        oscillations_accumulated_by_time_str[time_str_in_label] = 0
    index = labels.index(label)
    oscillations_accumulated_by_time_str[time_str_in_label] += metrics.oscillating_start_over_time[index - 1]
plot_list_as_bar_plot(list(oscillations_accumulated_by_time_str.keys()), 
                     y=list(oscillations_accumulated_by_time_str.values()),
                     subfolder=subfolder,
                     title=title_start + f"Accumulated ASes Starting Oscillation by Time String (UTC) {date_range_title(start_date, end_date)}")

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
                     title=title_start + f"Accumulated ASes Ending Oscillation by Time String (UTC) {date_range_title(start_date, end_date)}"
                     )

check_reachable_two_depeering_categories = True
if check_reachable_two_depeering_categories:
    reachable_depeered_from_members = [] # members are still present but reachable depeered from them
    reachable_peers_to_members_that_depeered = [] # members are not present anymore, therefore making their reachable exit
    count_of_member_connections = []

    all_counts_of_reachable_depeered_from_members = []
    all_counts_of_reachable_peers_to_members_that_depeered = []
    for i, stat in enumerate(all_stats[1:], 1):
        previous_stat = all_stats[i - 1]
        lost_reachables = previous_stat.unique_reachables - stat.unique_reachables
        lost_members = previous_stat.unique_members - stat.unique_members
        reachable_depeered_from_members_count = 0
        reachable_peers_to_members_that_depeered_count = 0
        for asn in lost_reachables:
            # asn reachable is the value, not the key
        
            related_members = {int(m) for m, reachables in previous_stat.mappings.items() if asn in reachables}
            count_of_member_connections.append(len(related_members))
        
            if related_members:
                still_present_members = related_members - lost_members
                
                if len(still_present_members) == 0:
                    reachable_peers_to_members_that_depeered.append(asn)
                    reachable_peers_to_members_that_depeered_count += 1
                else:
                    reachable_depeered_from_members_count += 1
                    reachable_depeered_from_members.append(asn)
        all_counts_of_reachable_depeered_from_members.append(reachable_depeered_from_members_count)
        all_counts_of_reachable_peers_to_members_that_depeered.append(reachable_peers_to_members_that_depeered_count)

    #plot_list_as_line_plot(all_counts_of_reachable_depeered_from_members, labels[1:], subfolder=subfolder, title=title_start + "Count of Reachable ASes that Depeered from Members but Still Have Other Members Peered In Over Time", xlabel="Date", ylabel="Count of Reachable ASes" )
    #plot_list_as_line_plot(all_counts_of_reachable_peers_to_members_that_depeered, labels[1:], subfolder=subfolder, title=title_start + "Count of Reachable ASes that Lost All Member Connections Over Time", xlabel="Date", ylabel="Count of Reachable ASes" )
    plot_stacked_line_plot([all_counts_of_reachable_depeered_from_members, all_counts_of_reachable_peers_to_members_that_depeered],
                           ["Depeered from Members but Still Have Other Members Peered In", "Lost All Member Connections"],
                           x_labels=labels[1:],
                           title=title_start + "Count of Reachable ASes that Depeered from Members - Comparison Over Time", 
                           xlabel="Date", 
                           ylabel="Count of Reachable ASes", subfolder=subfolder)
    print(f"Reachable ASes that left but still has its previous members peered into the IXP: {len(reachable_depeered_from_members)}")
    print(f"Reachable ASes that left and no longer have any members peered into the IXP: {len(reachable_peers_to_members_that_depeered)}")
    average_member_connections = sum(count_of_member_connections) / len(count_of_member_connections) if count_of_member_connections else 0
    print(f"Average number of member connections for lost reachables: {average_member_connections:.2f}")
    unique_member_connections = set(count_of_member_connections)
    print(f"Unique number of member connections for lost reachables: {sorted(unique_member_connections)}")

# This is very heavy (but reasonable with less or 1 samples), keep it turned off unless you really need it
need_to_calculate_average_mappings_count__per_reachable = False
if need_to_calculate_average_mappings_count__per_reachable:
    count_of_mappings_per_reachable = []
    number_of_needed_samples = min(2, len(all_stats) - 1)
    for stat in all_stats[:number_of_needed_samples]:
        reachables = stat.unique_reachables
        for reachable in reachables:
            related_members = {int(m) for m, reachables in stat.mappings.items() if reachable in reachables}
            count = len(related_members)
            count_of_mappings_per_reachable.append(count)
    average_mappings_per_reachable = sum(count_of_mappings_per_reachable) / len(count_of_mappings_per_reachable) if count_of_mappings_per_reachable else 0
    print(f"(samples used: {number_of_needed_samples})")
    print(f"Average number of member connections per reachable AS: {average_mappings_per_reachable:.2f}")
    print(f"Unique number of member connections per reachable AS: {sorted(set(count_of_mappings_per_reachable))}")
print("Finished all plotting for dates from {} to {} with interval of {} days.".format(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), day_delta.days))

need_to_calculate_other_members_of_reachable_from_reachables_whose_member_left = False
if need_to_calculate_other_members_of_reachable_from_reachables_whose_member_left:
    count_of_other_members_of_reachable_from_reachables_whose_member_left = {}
    count_of_total_reachables_that_left_with_the_member = 0
    number_of_samples = min(2, len(all_stats) - 1)
    for i in range(1, number_of_samples + 1):
        stat = all_stats[i]
        previous_stat = all_stats[i - 1]
        lost_members = previous_stat.unique_members - stat.unique_members
        for member in lost_members:
            related_reachables = previous_stat.mappings.get(str(member), set())
            for reachable in related_reachables:
                
                if reachable not in stat.unique_reachables:  
                    count_of_total_reachables_that_left_with_the_member += 1
                    continue
                # Only consider if the reachable was NOT lost
                for other_member, other_reachables in previous_stat.mappings.items():
                    if str(other_member) != str(member) and reachable in other_reachables:
                        if reachable not in count_of_other_members_of_reachable_from_reachables_whose_member_left:
                            count_of_other_members_of_reachable_from_reachables_whose_member_left[reachable] = 0
                        count_of_other_members_of_reachable_from_reachables_whose_member_left[reachable] += 1

    average_other_members_per_reachable = sum(count_of_other_members_of_reachable_from_reachables_whose_member_left.values()) / len(count_of_other_members_of_reachable_from_reachables_whose_member_left) if count_of_other_members_of_reachable_from_reachables_whose_member_left else 0
    print(f"(samples used: {number_of_samples})")
    print(f"Average number of other members connected to a reachable AS whose member left: {average_other_members_per_reachable:.2f}")
    print(f"Total count of reachables that left with the member: {count_of_total_reachables_that_left_with_the_member}")


need_to_calculate_average_number_of_reachables_a_member_gives_access_to = False

if need_to_calculate_average_number_of_reachables_a_member_gives_access_to:
    count_of_reachables_per_member = []
    number_of_samples = min(2, len(all_stats))
    for stat in all_stats[:number_of_samples]:
        members = stat.unique_members
        for member in members:
            related_reachables = stat.mappings.get(str(member), set())
            count = len(related_reachables)
            count_of_reachables_per_member.append(count)
    average_reachables_per_member = sum(count_of_reachables_per_member) / len(count_of_reachables_per_member) if count_of_reachables_per_member else 0
    print(f"(samples used: {number_of_samples})")
    print(f"Average number of reachable ASes per member AS: {average_reachables_per_member:.2f}")
    print(f"Unique number of reachable ASes per member AS: {sorted(set(count_of_reachables_per_member))}")

import numpy as np
from scipy.stats import pearsonr
removed_array = np.array(metrics.removed_asns_over_time)
added_array = np.array(metrics.added_asns_over_time) 
if len(removed_array) > 1 and len(added_array) > 1 and len(removed_array) == len(added_array):
    corr_removed_added, _ = pearsonr(removed_array, added_array) 
#print(f"Correlation between removing and adding ASes: {corr_removed_added:.2f}") 

