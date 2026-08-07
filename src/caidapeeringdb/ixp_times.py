
from datetime import datetime

from src.caidapeeringdb.utils import PEERINGDB_SUBFOLDER_PREFIX
from src.utils.graphs import plot_stacked_bar_plot



def get_ixp_connections_time_delta(connections, current_date=None, from_field="created"):
    
    if not connections:
        return []
    if current_date is None:
        current_date = datetime.now()

    times = {}
    for connection in connections:
        if from_field in connection:
            from_date = datetime.strptime(connection[from_field][:10], "%Y-%m-%d")

            diff = (current_date - from_date).days
            times[str(connection["ix_id"])] = diff
    
    return times


def plot_time_in_ixp_distribution(asn_to_analyze: int, time_deltas_for_connections: dict, from_field: str = "updated", title_suffix: str = ""):
        ranges = [30, 90, 180, 365, 365*2, 365*3, 365*4] 

        range_labels = [f"0-{ranges[0]} days"] + \
                       [f"{ranges[i-1]}-{ranges[i]} days" for i in range(1, len(ranges))] + \
                       [f"{ranges[-1]//365}+ years"]

        for i in range(len(ranges)):
            range_value = ranges[i]
            
            if range_value >= 365:
                years = range_value // 365
                if years == 1:
                    range_labels[i] = f"1 year"
                else:
                    range_labels[i] = f"{years-1}-{years} years"
 
        range_counts = {label: 0 for label in range_labels}

        count_of_not_found_range = 0
        for conn_id, delta in time_deltas_for_connections.items():
            if delta is None:
                count_of_not_found_range += 1
                continue
            for i, r in enumerate(ranges):
                if delta <= r:
                    range_counts[range_labels[i]] += 1
                    break
            else:
                range_counts[range_labels[-1]] += 1

        if count_of_not_found_range > 0:
            range_labels.append("Not Found")
            range_counts["Not Found"] = count_of_not_found_range

        plot_stacked_bar_plot(
            [list(range_counts.values())],
            ["Connections"],
            x_labels=list(range_counts.keys()),
            title=f"Time-in-IXP Distribution of Connections for ASN {asn_to_analyze} Before De-Peering - from field {from_field} {title_suffix}",
            xlabel="Connection Age Range",
            ylabel="Number of Connections",
            subfolder=PEERINGDB_SUBFOLDER_PREFIX + str(asn_to_analyze)
        )