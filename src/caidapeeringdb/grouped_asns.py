 
from collections import defaultdict

from src.utils.graphs import (
    plot_list_as_bar_plot,
    plot_list_as_line_plot,
    plot_map_as_bar_plot,
    plot_stacked_line_plot,
    plot_stacked_win_loss_bar_plot_by_continent,
)
from src.caidapeeringdb.continent_logic import (
    continent_colors,
    get_continent_for_ixp,
)
from src.caidapeeringdb.caidapeeringdb_load import (
    get_data,
    get_unique_ixps_from_data_list,
    get_all_ixps,
    load_connections_over_time_for_asns,
    get_asns_of_info_type,
)


def plot_ixps_distribution_by_continent(ixp_by_continent_count_percentage):
    """Plot the distribution of IXPs by continent."""
    plot_map_as_bar_plot(
        ixp_by_continent_count_percentage,
        title="Number of IXPs by Continent in PeeringDB",
        colors=continent_colors,
        is_percentage=True,
        sort_by_size=True,
        xlabel="Continent",
        ylabel="Number of IXPs",
        subfolder="peeringdb_connections"
    )


def get_ixps_by_continent_count(all_files):
    # 1. Use a generator instead of a list comprehension to save memory 
    # (Assuming get_unique_ixps_from_data_list accepts iterables)
    ixps_gen = (get_data(file) for file in all_files)
    ixps = get_unique_ixps_from_data_list(ixps_gen)

    # 2. Use defaultdict to eliminate the 'if continent not in' check
    ixps_by_continent = defaultdict(list)
    
    for ixp in ixps: 
        continent = get_continent_for_ixp(ixp["id"], ixp)
        ixps_by_continent[continent].append(ixp)

    # 3. Calculate counts and percentages efficiently in a single loop
    total_ixp_count = len(ixps)  # No need to sum dict values, we already have the total count!
    
    ixp_by_continent_count = {}
    ixp_by_continent_count_percentage = {}
 
    if total_ixp_count > 0:
        for continent, continent_ixps in ixps_by_continent.items():
            count = len(continent_ixps)
            ixp_by_continent_count[continent] = count
            ixp_by_continent_count_percentage[continent] = count / total_ixp_count
 
    return ixp_by_continent_count, ixp_by_continent_count_percentage, dict(ixps_by_continent)


def plot_grouped_connections_over_time_for_asns_of_info_type(all_files, info_type):
    """Plot aggregated connections for ASNs of a specific info type."""
    last_date_data = get_data(all_files[-1])
    asns_to_search = get_asns_of_info_type(last_date_data, info_type)

    if not asns_to_search:
        print(f"No ASNs found for info type: {info_type}")
        return

    # Extract IDs and Names
    asns_ids, asn_names, _ = zip(*asns_to_search)

    # Batch load data
    peered_data = load_connections_over_time_for_asns(all_files, asns_to_search, connections_should_be='peered')
    not_peered_data = load_connections_over_time_for_asns(all_files, asns_to_search, connections_should_be="not_peered")

    sample_asn = asns_ids[0]
    num_time_steps = len(peered_data[sample_asn])

    connections_for_group_peered = [0] * num_time_steps
    connections_for_group_not_peered = [0] * num_time_steps

    for asn in asns_ids:
        for i, ((_, p_conns), (_, np_conns)) in enumerate(zip(peered_data[asn], not_peered_data[asn])):
            connections_for_group_peered[i] += len(p_conns)
            connections_for_group_not_peered[i] += len(np_conns)

    # Formatting names for the note
    sorted_names = sorted(asn_names)
    display_names = sorted_names[:5]
    if len(sorted_names) > 5:
        display_names.append(f"... and {len(sorted_names) - 5} others")

    plot_stacked_line_plot(
        [connections_for_group_peered, connections_for_group_not_peered],
        ["In Route Server Connections", "Not In Route Server Connections"],
        x_labels=[date for date, _ in peered_data[sample_asn]],
        subfolder="peeringdb_connections",
        title=f"Connections for ASes with info type {info_type} over time",
        xlabel="Date",
        ylabel="Number of Connections",
        notes=f"This group includes ASNs like: {', '.join(display_names)}"
    )


def plot_connections_for_group(connections_over_time, group, connection_type, asns_to_search, all_files):
    """Plot connections for a group of ASNs over time."""
    asns_of_that_group = [asn_tuple[0] for asn_tuple in asns_to_search if group in asn_tuple[2]]
    asn_names_of_that_group = [asn_tuple[1] for asn_tuple in asns_to_search if group in asn_tuple[2]]
    connections_for_group = []

    for i in range(len(connections_over_time[asns_of_that_group[0]])):
        total_connections_for_group_at_time_i = 0
        for asn in asns_of_that_group:
            connections_for_asn = connections_over_time[asn]
            total_connections_for_group_at_time_i += len(connections_for_asn[i][1])
        connections_for_group.append(total_connections_for_group_at_time_i)

    plot_list_as_line_plot(
        connections_for_group,
        y=[file_date for file_date, _ in connections_over_time[asns_of_that_group[0]]],
        subfolder="peeringdb_connections",
        title=f"Connections for {group} over time - {'In Route Server' if connection_type == 'peered' else 'Not In Route Server'}",
        xlabel="Date",
        ylabel="Number of Connections",
        notes=f"This group includes ASNs: {', '.join([f'{asn_names_of_that_group[i]}' for i, asn in enumerate(asn_names_of_that_group)])}"
    )

    # Build continent data for the group
    data = get_data(all_files[-1])
    ixps = get_all_ixps(data)

    continent_connections_over_time = []
    dates_y = [file_date for file_date, _ in connections_over_time[asns_of_that_group[0]]]

    # Iterate through each time period
    for time_idx in range(len(dates_y)):
        continent_to_connections = {}

        # Aggregate connections for all ASNs in the group at this time period
        for asn in asns_of_that_group:
            if time_idx < len(connections_over_time[asn]):
                _, connections_at_time = connections_over_time[asn][time_idx]

                for conn in connections_at_time:
                    ixp_id = conn.get("ix_id")
                    ixp_info = next((ixp for ixp in ixps if ixp["id"] == ixp_id), None)
                    continent = get_continent_for_ixp(ixp_id, ixp_info)

                    if continent not in continent_to_connections:
                        continent_to_connections[continent] = []
                    continent_to_connections[continent].append(conn)

        continent_connections_over_time.append((dates_y[time_idx], continent_to_connections))

    # Plot stacked win-loss by continent for the group
    connection_type_label = "In Route Server" if connection_type == 'peered' else "Not In Route Server"
    plot_stacked_win_loss_bar_plot_by_continent(
        continent_connections_over_time,
        title=f"Region-wise IXP Connection Gains vs Losses Over Time for {group} - {connection_type_label}",
        y=dates_y[1:],
        subfolder="peeringdb_connections",
        create_text_report=True
    )


def plot_stacked_connections_for_all_asns(connections_over_time_by_asn_peered, connections_over_time_by_asn_not_peered):
    """Plot stacked connections for all ASNs."""
    over_time_peered = []
    over_time_not_peered = []

    for i in range(len(connections_over_time_by_asn_peered[next(iter(connections_over_time_by_asn_peered))])):
        total_peered_at_time_i = 0
        total_not_peered_at_time_i = 0
        for asn in connections_over_time_by_asn_peered.keys():
            connections_for_asn_peered = connections_over_time_by_asn_peered[asn]
            connections_for_asn_not_peered = connections_over_time_by_asn_not_peered[asn]
            total_peered_at_time_i += len(connections_for_asn_peered[i][1])
            total_not_peered_at_time_i += len(connections_for_asn_not_peered[i][1])
        over_time_peered.append(total_peered_at_time_i)
        over_time_not_peered.append(total_not_peered_at_time_i)

    plot_stacked_line_plot(
        [over_time_peered, over_time_not_peered],
        ["In Route Server Connections", "Not In Route Server Connections"],
        x_labels=[file_date for file_date, _ in connections_over_time_by_asn_peered[next(iter(connections_over_time_by_asn_peered))]],
        subfolder="peeringdb_connections",
        title="In Route Server x Not In Route Server Connections for All ASNs over time",
        xlabel="Date",
        ylabel="Number of Connections",
    )


def plot_stacked_connections_for_group(connections_peered, connections_not_peered, group, asns_to_search):
    """Plot stacked connections for a group of ASNs."""
    asns_of_that_group = [asn_tuple[0] for asn_tuple in asns_to_search if group in asn_tuple[2]]
    asn_names_of_that_group = [asn_tuple[1] for asn_tuple in asns_to_search if group in asn_tuple[2]]

    connections_for_group_peered = []
    connections_for_group_not_peered = []

    for i in range(len(connections_peered[asns_of_that_group[0]])):
        total_peered_connections_for_group_at_time_i = 0
        total_not_peered_connections_for_group_at_time_i = 0
        for asn in asns_of_that_group:
            connections_for_asn_peered = connections_peered[asn]
            connections_for_asn_not_peered = connections_not_peered[asn]
            total_peered_connections_for_group_at_time_i += len(connections_for_asn_peered[i][1])
            total_not_peered_connections_for_group_at_time_i += len(connections_for_asn_not_peered[i][1])
        connections_for_group_peered.append(total_peered_connections_for_group_at_time_i)
        connections_for_group_not_peered.append(total_not_peered_connections_for_group_at_time_i)

    plot_stacked_line_plot(
        [connections_for_group_peered, connections_for_group_not_peered],
        ["In Route Server Connections", "Not In Route Server Connections"],
        x_labels=[file_date for file_date, _ in connections_peered[asns_of_that_group[0]]],
        subfolder="peeringdb_connections",
        title=f"In Route Server x Not In Route Server Connections for {group} over time",
        xlabel="Date",
        ylabel="Number of Connections",
        notes=f"This group includes ASNs: {', '.join([f'{asn_names_of_that_group[i]}' for i, asn in enumerate(asn_names_of_that_group)])}"
    )


