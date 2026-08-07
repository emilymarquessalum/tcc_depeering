



# New ASes: ideally we would check as much of the historical information we have for an IXP, to make sure the AS was never in the IXP,
# but this would cause a situation where we would use different timeframes for different IXPs depending on the data available for that IXP...
# instead of using all data, lets define a fixed timeframe that all IXPs will have to follow to count for this analysis.
# Since i want to make this work with IX.br São Paulo, that threshold will be 1 year (cant be more than that, because IX.br São Paulo started in 2025)




from src.utils.graphs import plot_list_as_line_plot


def bview_new_members(all_required_data):

    all_stats, labels_summarized, max_labels = all_required_data["timeline"]

    first_snapshot = all_stats[0]
    first_snapshot_date = first_snapshot.date_as_datetime() # all snapshots that are less than 365 days apart from this one will be caught in the first_year_snapshots 

    first_year_snapshots = []

    after_first_year_snapshots = []

    passed_first_year = False

    for snapshot in all_stats:

        if passed_first_year:
            after_first_year_snapshots.append(snapshot)
        else:
            snapshot_date = snapshot.date_as_datetime()
            days_difference = (snapshot_date - first_snapshot_date).days

            if days_difference <= 365:
                first_year_snapshots.append(snapshot)
            else:
                after_first_year_snapshots.append(snapshot)
                passed_first_year = True

    all_members_from_first_year = set()
    for snapshot in first_year_snapshots:
        all_members_from_first_year.update(snapshot.unique_members)

    new_members_added_over_time = []
    for snapshot in after_first_year_snapshots:
        new_members = set(snapshot.unique_members) - all_members_from_first_year
        new_members_added_over_time.append((snapshot.date_as_datetime(), new_members))
        all_members_from_first_year.update(new_members)

    print(f"Unique new members added over time: {len(set(new_members_added_over_time))}")

    plot_list_as_line_plot(new_members_added_over_time,  
                           title="New Members Added Over Time",  
                           ylabel="New Members Added"
                           )