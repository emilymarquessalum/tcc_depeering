
from time import sleep
from src.utils.graphs import plot_as_path_length_distribution
from ixpert import search_prefix
from src.ripe_bviews.read_update import read_update, UpdateFileStats
from src.ripe_bviews.compare_bviews.compare_bviews import compare_bviews
from ripeatlas import get_atlas_measurement_data





date = "20250302"
scheduled_time = "1600"
date_2 = "20250303"

#stats = UpdateFileStats()
#stats.load(f"data/stats_{date}_{scheduled_time}.txt")
#stats = read_update(date, scheduled_time)#, focus_asn_in_as_path='262907')
#stats.save(f"data/stats_{date}_{scheduled_time}.txt")
#stats.print_summary()
# plot_as_path_length_distribution(stats.as_path_count, title=f'AS Path Length Distribution {date}_{scheduled_time}')
# plot_as_path_length_distribution(stats.depeer_replacement_count, title=f'AS Path Length Distribution After Depeering Repair {date}_{scheduled_time}')

'''
for asn in stats.asn_originators_of_depeered_repared_prefixes:
    print(f"data for ASN: {asn}")
    result = get_atlas_measurement_data(f"{asn}")
    if result:
        print(f"ASN: {asn}, Data: {result}")
    sleep(1)  # To avoid overwhelming the API with requests
'''

stats = compare_bviews(f"data/bview.{date}.{scheduled_time}.txt", f"data/bview.{date_2}.{scheduled_time}.txt")
stats.print_summary()




'''
for prefix in stats.unique_depeered_prefixes:
    result = search_prefix(prefix)
    if result:
        print(f"Prefix: {prefix}, Data: {result}")
    sleep(1)  # To avoid overwhelming the API with requests
'''    