"""Plotting functions for individual ASN analysis."""
from src.caidapeeringdb.ixp_size import plot_ixp_connections_by_continent, plot_ixp_connections_ratio_from_total_ixps_in_that_region
from src.utils.graphs import (
    plot_list_as_bar_plot,
    plot_list_as_line_plot,
    plot_list_as_win_loss_bar_plot,
    plot_stacked_line_plot,
    plot_stacked_win_loss_bar_plot_by_continent,
)
from src.caidapeeringdb.continent_logic import (
    continent_colors,
    organize_connections_by_continent,
    get_continent_for_ixp,
    build_continent_connections,
)
from src.caidapeeringdb.caidapeeringdb_load import (
    get_data,
    get_ixp_id_to_ixp_name_mapping,
    get_unique_ixps_from_data_list,
    ixp_name_short_format,
    get_connections_for_ixp,
    load_connections_over_time_for_asns,
)


def plot_connections_for_asns_over_time(connections_over_time_by_asn_peered, connections_over_time_by_asn_not_peered, asns_to_search, all_files, ixp_by_continent_count=None):
    """Plot detailed analysis for individual ASNs."""
    data = get_data(all_files[-1])
    ixp_id_to_name = get_ixp_id_to_ixp_name_mapping(data)
    ixps = get_unique_ixps_from_data_list([get_data(file) for file in all_files])

    plot_transitions = False

    for asn, connections_over_time in connections_over_time_by_asn_peered.items():
        subfolder = "peeringdb_connections/" + str(asn)

        asn_to_search = None
        for asn_tuple in asns_to_search:
            if asn_tuple[0] == asn:
                asn_to_search = asn_tuple
                break

        connections_peered = [len(connections) for _, connections in connections_over_time]
        connections_not_peered = [len(connections) for _, connections in connections_over_time_by_asn_not_peered[asn]]
        transitions_from_one_type_to_another_over_time = []

        if plot_transitions:
            for i in range(1, len(connections_over_time)):
                prev_peered_ids = [conn["id"] for conn in connections_over_time[i-1][1]]
                prev_not_peered_ids = [conn["id"] for conn in connections_over_time_by_asn_not_peered[asn][i-1][1]]
                curr_peered_ids = [conn["id"] for conn in connections_over_time[i][1]]
                curr_not_peered_ids = [conn["id"] for conn in connections_over_time_by_asn_not_peered[asn][i][1]]

                transitions_from_peered_to_not_peered = []
                transitions_from_not_peered_to_peered = []
                for conn in prev_peered_ids:
                    if conn not in curr_peered_ids and conn in curr_not_peered_ids:
                        transitions_from_peered_to_not_peered.append(conn)
                for conn in prev_not_peered_ids:
                    if conn not in curr_not_peered_ids and conn in curr_peered_ids:
                        transitions_from_not_peered_to_peered.append(conn)

                transitions = len(transitions_from_peered_to_not_peered) + len(transitions_from_not_peered_to_peered)
                transitions_from_one_type_to_another_over_time.append(transitions)

            plot_list_as_line_plot(
                transitions_from_one_type_to_another_over_time,
                y=[file_date for file_date, _ in connections_over_time[1:]],
                subfolder=subfolder,
                title=f"Transitions in Connections for ASN {asn_to_search[0]} ({asn_to_search[1]}) over time",
                xlabel="Date",
                ylabel="Type of Transition and Number of Connections",
            )

        dates_y = [file_date for file_date, _ in connections_over_time]
        plot_list_as_line_plot(
            [len(connections) for _, connections in connections_over_time],
            y=dates_y,
            subfolder=subfolder,
            title=f"IXP Connections in Route Server for ASN {asn_to_search[0]} ({asn_to_search[1]}) over time",
            xlabel="Date",
            max_labels=12,
            ylabel="Number of Connections"
        )

        # Plot connections by continent for peered connections
        continent_data_series_peered, dates_for_plot, sorted_continents = organize_connections_by_continent(connections_over_time, ixps)

        plot_stacked_line_plot(
            [continent_data_series_peered[continent] for continent in sorted_continents],
            [f"Connections in {continent}" for continent in sorted_continents],
            x_labels=dates_for_plot,
            title=f"In Route Server Connections by Continent for ASN {asn_to_search[0]} ({asn_to_search[1]}) over time",
            xlabel="Date",
            ylabel="Number of Connections",
            subfolder=subfolder
        )

        # Plot connections by continent for not-peered connections
        continent_data_series_not_peered, dates_for_plot, sorted_continents = organize_connections_by_continent(connections_over_time_by_asn_not_peered[asn], ixps)

        plot_stacked_line_plot(
            [continent_data_series_not_peered[continent] if continent in continent_data_series_not_peered else [0] * len(dates_for_plot) for continent in sorted_continents],
            [f"Connections in {continent}" for continent in sorted_continents],
            x_labels=dates_for_plot,
            title=f"Not In Route Server Connections by Continent for ASN {asn_to_search[0]} ({asn_to_search[1]}) over time",
            xlabel="Date",
            ylabel="Number of Connections",
            subfolder=subfolder
        )

        ixps_over_time = [[ixp_id_to_name.get(net.get("ix_id"), net.get("ix_id")) for net in connections] for _, connections in connections_over_time]
 


        plot_win_loss = False

        if plot_win_loss:
            plot_list_as_win_loss_bar_plot(
                ixps_over_time,
                f"In Route Server IXP Connections in Route Server for ASN {asn_to_search[0]} over time - Win vs Loss",
                create_text_report=True,
                y=dates_y[1:],
                xlabel='Date',
                ylabel='Gain/Loss',
                subfolder=subfolder
            )

            ixps_over_time_not_peered = [[ixp_id_to_name.get(net.get("ix_id"), net.get("ix_id")) for net in connections] for _, connections in connections_over_time_by_asn_not_peered[asn]]

            plot_list_as_win_loss_bar_plot(
                ixps_over_time_not_peered,
                f"Not In Route Server IXP Connections for ASN {asn_to_search[0]} over time - Win vs Loss",
                y=dates_y[1:],
                xlabel='Date',
                ylabel='Gain/Loss',
                subfolder=subfolder
            )

        # Build continent data for win-loss plot (peered connections)
        continent_connections_over_time_peered = build_continent_connections(connections_over_time, ixps)

        plot_stacked_win_loss_bar_plot_by_continent(
            continent_connections_over_time_peered,
            title=f"Region-wise IXP Connection Gains vs Losses Over Time for ASN {asn_to_search[0]} ({asn_to_search[1]}) - In Route Server",
            y=dates_y[1:],
            subfolder=subfolder,
            create_text_report=True
        )

        plot_ixp_sizes = False

        if plot_ixp_sizes:
            ixps_peered_info_at_first_date = connections_over_time[0][1]
            ixps_peered_region_distribution = {}

            for conn in ixps_peered_info_at_first_date:
                ixp_id = conn.get("ix_id")
                ixp_info = next((ixp for ixp in ixps if str(ixp["id"]) == str(ixp_id)), None)
                continent = get_continent_for_ixp(ixp_id, ixp_info)
                if continent not in ixps_peered_region_distribution:
                    ixps_peered_region_distribution[continent] = 0
                ixps_peered_region_distribution[continent] += 1

            # Plot IXP sizes for all IXPs connected to this ASN
            plot_ixp_sizes_for_asn(
                ixps_peered_info_at_first_date,
                ixp_id_to_name,
                ixps,
                asn_to_search,
                dates_y[0],
                subfolder,
                data
            )

            colors = [continent_colors.get(continent, "#333333") for continent in ixps_peered_region_distribution.keys()]

            plot_ixp_connections_by_continent(
                ixps_peered_region_distribution,
                asn_to_search,
                dates_y,
                colors,
                subfolder=subfolder
            )

        if ixp_by_continent_count:
            ixps_peered_region_distribution_count_by_total_ixps_in_that_region = {}
            for continent, count in ixps_peered_region_distribution.items():
                total_ixps_in_region = ixp_by_continent_count.get(continent, 0)  
                if total_ixps_in_region > 0:
                    ixps_peered_region_distribution_count_by_total_ixps_in_that_region[continent] = count / total_ixps_in_region
                else:
                    ixps_peered_region_distribution_count_by_total_ixps_in_that_region[continent] = 0

            
            plot_ixp_connections_ratio_from_total_ixps_in_that_region(
                ixps_peered_region_distribution_count_by_total_ixps_in_that_region,
                asn_to_search,
                dates_y,
                colors,
                subfolder=subfolder
            )


        if plot_win_loss:
            # Build continent data for win-loss plot (not peered connections)
            continent_connections_over_time_not_peered = build_continent_connections(connections_over_time_by_asn_not_peered[asn], ixps)

            plot_stacked_win_loss_bar_plot_by_continent(
                continent_connections_over_time_not_peered,
                title=f"Region-wise IXP Connection Gains vs Losses Over Time for ASN {asn_to_search[0]} ({asn_to_search[1]}) - Not In Route Server",
                y=dates_y[1:],
                subfolder=subfolder,
            
                create_text_report=True
            ) 

        plot_ixps_lost = False

        if plot_ixps_lost:
            # IXPs that were lost, chronologically ordered
            ixps_not_peered_lost = []
            for i in range(1, len(connections_over_time_by_asn_not_peered[asn])):
                prev_ixps = {net.get("ix_id") for net in connections_over_time_by_asn_not_peered[asn][i-1][1]}
                curr_ixps = {net.get("ix_id") for net in connections_over_time_by_asn_not_peered[asn][i][1]}
                lost_ixps = prev_ixps - curr_ixps
                ixps_not_peered_lost.append(lost_ixps)

            ixps_not_peered_lost_connections = []
            for ixp_list in ixps_not_peered_lost:
                connection_count = []
                for ixp_id in ixp_list:
                    ixp_connections = get_connections_for_ixp(ixp_id, data, key="netixlan", connections_should_be="peered")
                    connection_count.append(len(ixp_connections))
                ixps_not_peered_lost_connections.append(connection_count)

            number_of_lost_ixps_per_continent = {}
            for ixp_list in ixps_not_peered_lost:
                for ixp_id in ixp_list:
                    ixp_info = next((ixp for ixp in ixps if str(ixp["id"]) == str(ixp_id)), None)
                    continent = get_continent_for_ixp(ixp_id, ixp_info)
                    if continent not in number_of_lost_ixps_per_continent:
                        number_of_lost_ixps_per_continent[continent] = 0
                    number_of_lost_ixps_per_continent[continent] += 1

            all_loss = sum(number_of_lost_ixps_per_continent.values())
            plot_list_as_bar_plot(
                list(number_of_lost_ixps_per_continent.keys()),
                y=[v / all_loss for v in number_of_lost_ixps_per_continent.values()],
                subfolder=subfolder,
                is_percentage=True,
                colors=[continent_colors.get(continent, "#333333") for continent in number_of_lost_ixps_per_continent.keys()],
                title=f"Number of IXPs Lost by Continent for ASN {asn_to_search[0]} ({asn_to_search[1]}) over time",
                xlabel="Continent",
                ylabel="Number of IXPs Lost"
            )

            plot_ixp_sizes_of_ixps_lost(ixps_not_peered_lost, ixps_not_peered_lost_connections, ixp_id_to_name, ixps, asn_to_search, dates_y, subfolder) 

        plot_list_as_line_plot(
            [len(connections) for _, connections in connections_over_time_by_asn_not_peered[asn]],
            y=[file_date for file_date, _ in connections_over_time_by_asn_not_peered[asn]],
            subfolder=subfolder,
            title=f"IXP Connections that were not in Route Server for ASN {asn_to_search[0]} ({asn_to_search[1]}) over time",
            xlabel="Date",
            ylabel="Number of Not Peered Connections"
        )

        plot_stacked_line_plot(
            [connections_peered, connections_not_peered],
            ["In Route Server Connections", "Not-In-Route-Server Connections"],
            x_labels=[file_date for file_date, _ in connections_over_time],
            subfolder=subfolder,
            title=f"In Route Server x Not In Route Server IXP Connections for ASN {asn_to_search[0]} ({asn_to_search[1]}) over time",
            xlabel="Date",
            ylabel="Number of Connections",
            max_labels=12,
            sort_by_size=False
        )

        #_debug(connections_over_time, asn_to_search)


def plot_ixp_sizes_for_asn(connections, ixp_id_to_name, ixps, asn_to_search, date, subfolder, data):
    """Plot the size of every IXP that an ASN is connected to."""
    ixp_ids = [conn.get("ix_id") for conn in connections]
    ixp_names = [ixp_name_short_format(ixp_id_to_name.get(ixp_id, str(ixp_id))) for ixp_id in ixp_ids]
    
    ixp_connections = []
    for ixp_id in ixp_ids:
        ixp_conns = get_connections_for_ixp(ixp_id, data, key="netixlan", connections_should_be="peered")
        ixp_connections.append(len(ixp_conns))
    
    colors = [continent_colors.get(get_continent_for_ixp(ixp_id, next((ixp for ixp in ixps if str(ixp["id"]) == str(ixp_id)), None)), "#333333") for ixp_id in ixp_ids]
    
    plot_list_as_bar_plot(
        ixp_names,
        y=ixp_connections,
        sort_by_size=True,
        colors=colors,
        subfolder=subfolder,
        xlabel="IXP",
        ylabel="Number of Peered Connections",
        title=f"IXP Size for All IXPs Connected to ASN {asn_to_search[0]} ({asn_to_search[1]}) at {date}"
    )


def plot_ixp_sizes_of_ixps_lost(ixps_not_peered_lost, ixps_not_peered_lost_connections, 
                           ixp_id_to_name, ixps, asn_to_search, dates_y, subfolder):
        aggregated_ixp_names = []
        aggregated_ixp_connections = []
        for i in range(len(ixps_not_peered_lost)):
            ixp_names = [ixp_name_short_format(ixp_id_to_name.get(ixp_id, str(ixp_id))) for ixp_id in ixps_not_peered_lost[i]]
            ixp_connections = ixps_not_peered_lost_connections[i]
            aggregated_ixp_names.extend(ixp_names)
            aggregated_ixp_connections.extend(ixp_connections)
            colors = [continent_colors.get(get_continent_for_ixp(ixp_id, next((ixp for ixp in ixps if str(ixp["id"]) == str(ixp_id)), None)), "#333333") for ixp_id in ixps_not_peered_lost[i]]
            plot_list_as_bar_plot(
                ixp_names,
                y=ixp_connections,
                sort_by_size=True,
                colors=colors,
                subfolder=subfolder,
                xlabel="IXP",
                ylabel="Number of Peered Connections",
                title=f"IXP Size of all IXPs that lost connection with ASN {asn_to_search[0]} at {dates_y[i]}"
            )

        indices_where_connections_are_less_than_ten = [i for i, conn in enumerate(aggregated_ixp_connections) if conn < 10]
        aggregated_ixp_connections = [conn for i, conn in enumerate(aggregated_ixp_connections) if i not in indices_where_connections_are_less_than_ten]
        aggregated_ixp_names = [ixp_name_short_format(name) for i, name in enumerate(aggregated_ixp_names) if i not in indices_where_connections_are_less_than_ten]
        plot_list_as_bar_plot(
            aggregated_ixp_names,
            y=aggregated_ixp_connections,
            subfolder=subfolder,
            title=f"IXP Size of All IXPs that Lost connection with ASN {asn_to_search[0]} ({asn_to_search[1]}) over time - From {dates_y[0]} to {dates_y[-1]}",
            xlabel="IXP",
            ylabel="Number of Peered Connections"
        )


def _debug(connections_over_time, asn_to_search):
        if len(connections_over_time[-1][1]) < 10:
            print(f"ASN {asn_to_search[0]} ({asn_to_search[1]})")
            last_connections = connections_over_time[-1][1]
            for conn in last_connections:
                print(f"IX: {conn['name']}")

        if len(connections_over_time[-1][1]) > 100:
            first_connections = connections_over_time[0][1]
            last_connections = connections_over_time[-1][1]
            growth_percentage = ((len(last_connections) - len(first_connections)) / len(first_connections)) * 100 if len(first_connections) > 0 else 0
            print(f"ASN {asn_to_search[0]} ({asn_to_search[1]}) had a growth of {growth_percentage:.2f}% in connections from {connections_over_time[0][0]} to {connections_over_time[-1][0]}")
            print(f"from {len(first_connections)} connections to {len(last_connections)} connections")


def plot_asns_analysis(all_files, asns_to_search_list, ixp_by_continent_count):
    """
    Plot analysis for individual ASNs.

    Args:
        all_files: List of files to load
        asns_to_search_list: List of ASN tuples to analyze
        ixp_by_continent_count: Dictionary of IXP counts by continent
    """
    connections_over_time_by_asn_peered = load_connections_over_time_for_asns(
        all_files, asns_to_search_list, connections_should_be="peered"
    )
    connections_over_time_by_asn_not_peered = load_connections_over_time_for_asns(
        all_files, asns_to_search_list, connections_should_be="not_peered"
    )

    plot_connections_for_asns_over_time(
        connections_over_time_by_asn_peered,
        connections_over_time_by_asn_not_peered,
        asns_to_search_list,
        all_files,
        ixp_by_continent_count=ixp_by_continent_count
    )
