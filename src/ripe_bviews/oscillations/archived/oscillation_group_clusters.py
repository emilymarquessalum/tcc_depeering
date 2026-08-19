from datetime import datetime, timedelta
from pathlib import Path
import sys
import warnings 
import numpy as np
import matplotlib.pyplot as plt
from sklearn.cluster import AgglomerativeClustering
from sklearn.decomposition import PCA

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data_timeline
from src.utils.graphs import plot_list_as_bar_plot

from src.ripe_bviews.timeline.bview_timeline import load_bview_data
from src.ripe_bviews.oscillations.bview_oscillation_logic import calculate_oscillation_metrics, plot_as_presences_over_time



warnings.filterwarnings('ignore', category=UserWarning, message='.*Skipping download.*')
start_date = datetime(2025, 10, 20)
end_date = datetime(2026, 1, 1)#datetime.datetime(202
day_delta = timedelta(days=3)


subfolder = start_date.strftime("%Y%m%d") + "_" + end_date.strftime("%Y%m%d") + "_" + str(day_delta.days) + "days/"
all_stats, labels = load_bview_data_timeline(start_date, end_date, ("26162", "187.16.216.253"), "rrc15", day_delta=day_delta, relative_path="../")
metrics = calculate_oscillation_metrics(all_stats)

oscillation_info = metrics.oscillation_info
total_oscillations = metrics.total_oscillations

all_data_points = []
asn_list = []
for oscillation_asn, info in oscillation_info.items():
    data_points = info['presence_historic']
    all_data_points.append(data_points)
    asn_list.append(oscillation_asn)

plot_as_presences_over_time(all_data_points)
all_data_points = np.array([np.array(dp) if isinstance(dp, list) else dp for dp in all_data_points])


if all_data_points.ndim > 2:
    all_data_points = all_data_points.reshape(all_data_points.shape[0], -1)

pca = PCA(n_components=2)
data_2d = pca.fit_transform(all_data_points)

x = data_2d[:, 0]
y = data_2d[:, 1]

print(f"PCA explained variance ratio: {pca.explained_variance_ratio_}")
print(f"Total variance explained: {pca.explained_variance_ratio_.sum():.2%}")

data = list(zip(x, y))

number_of_clusters = 2
hierarchical_cluster = AgglomerativeClustering(n_clusters=number_of_clusters, linkage='ward')
labels = hierarchical_cluster.fit_predict(data)

# Map clusters to ASNs
cluster_groups = {i: [] for i in range(number_of_clusters)}
for idx, cluster_label in enumerate(labels):
    cluster_groups[cluster_label].append(asn_list[idx])

# Print cluster groups
print("\n" + "="*50)
print("Oscillation Groups by Cluster")
print("="*50)
for cluster_id in sorted(cluster_groups.keys()):
    asns = cluster_groups[cluster_id]
    print(f"\nCluster {cluster_id} ({len(asns)} ASes):")
    print(f"  {asns}")
print("="*50 + "\n")
plt.clf()
plt.scatter(x, y, c=labels)
plt.xlabel(f'PC1 ({pca.explained_variance_ratio_[0]:.1%})')
plt.ylabel(f'PC2 ({pca.explained_variance_ratio_[1]:.1%})')
plt.title('Oscillation Groups - Hierarchical Clustering')
plt.show()
plt.savefig(f'oscillation_clusters_{number_of_clusters}_clusters.png')

for group_id, asns in cluster_groups.items():
    print(f"\nCluster {group_id} ASNs: {asns}")
    all_comeback_times = []
    all_group_presences = []
    for asn, info in oscillation_info.items():
        if asn in asns:
            all_comeback_times.extend(info["comeback_times"])
            all_group_presences.append(info["presence_historic"])
    if all_comeback_times:

        plot_as_presences_over_time(all_group_presences, group=group_id, subfolder=subfolder)
        comeback_times_count = {}
        for time in all_comeback_times:
            if time not in comeback_times_count:
                comeback_times_count[time] = 0
            comeback_times_count[time] += 1

        come_back_set = set(all_comeback_times)
        print(f"Unique comeback times (in snapshots): {sorted(come_back_set)}")

        ordered_comeback_times_count = sorted(comeback_times_count.items())
        ordered_comeback_values = [count for time, count in ordered_comeback_times_count]
        plot_list_as_bar_plot(ordered_comeback_values, 
                            y=[time for time, count in ordered_comeback_times_count],
                            title=f"Cluster {group_id} Count of ASes by Time to Come Back from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} - {day_delta.days} interval",
                                xlabel="Time to Come Back (in snapshots)", 
                                ylabel="Number of ASes",
                                subfolder=subfolder)




### filtrado, tem muito código copiado e depois tenho que refatorar
oscillation_info = metrics.oscillation_info
total_oscillations = metrics.total_oscillations

all_data_points = []
asn_list = []
for oscillation_asn, info in oscillation_info.items():
    data_points = info['presence_historic']
    if oscillation_asn not in cluster_groups[1]:
        continue  
    all_data_points.append(data_points)
    asn_list.append(oscillation_asn)


all_data_points = np.array([np.array(dp) if isinstance(dp, list) else dp for dp in all_data_points])


if all_data_points.ndim > 2:
    all_data_points = all_data_points.reshape(all_data_points.shape[0], -1)

pca = PCA(n_components=2)
data_2d = pca.fit_transform(all_data_points)
  
number_of_clusters = 2
hierarchical_cluster = AgglomerativeClustering(n_clusters=number_of_clusters, linkage='ward')


x = data_2d[:, 0]
y = data_2d[:, 1]
 
 
data = list(zip(x, y))

labels = hierarchical_cluster.fit_predict(data) 

print(f"PCA explained variance ratio: {pca.explained_variance_ratio_}")
print(f"Total variance explained: {pca.explained_variance_ratio_.sum():.2%}")

plt.clf()

plt.scatter(x, y, c=labels)
plt.xlabel(f'PC1 ({pca.explained_variance_ratio_[0]:.1%})')
plt.ylabel(f'PC2 ({pca.explained_variance_ratio_[1]:.1%})')
plt.title('Oscillation Groups - Hierarchical Clustering') 
plt.show()
plt.savefig(f'filtered_oscillation_clusters_{number_of_clusters}_clusters.png')


data = list(zip(x, y))

cluster_groups = {i: [] for i in range(number_of_clusters)}
for idx, cluster_label in enumerate(labels):
    cluster_groups[cluster_label].append(asn_list[idx])

if True:
   
    
    for group_id, asns in cluster_groups.items():
        
        all_comeback_times = []
        for asn, info in oscillation_info.items():
            if asn in asns: 
                all_comeback_times.extend(info["comeback_times"])

        if all_comeback_times:
                comeback_times_count = {}
                for time in all_comeback_times:
                    if time not in comeback_times_count:
                        comeback_times_count[time] = 0
                    comeback_times_count[time] += 1

                come_back_set = set(all_comeback_times)
                print(f"Unique comeback times (in snapshots): {sorted(come_back_set)}")

                ordered_comeback_times_count = sorted(comeback_times_count.items())
                ordered_comeback_values = [count for time, count in ordered_comeback_times_count]
                plot_list_as_bar_plot(ordered_comeback_values, 
                                    y=[time for time, count in ordered_comeback_times_count], 
                                    title=f"Filtered Cluster {group_id} Count of ASes by Time to Come Back from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} - {day_delta.days} interval",
                                        xlabel="Time to Come Back (in snapshots)", 
                                        ylabel="Number of ASes",
                                        subfolder=subfolder)