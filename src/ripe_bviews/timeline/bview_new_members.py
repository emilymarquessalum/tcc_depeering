



# New ASes: ideally we would check as much of the historical information we have for an IXP, to make sure the AS was never in the IXP,
# but this would cause a situation where we would use different timeframes for different IXPs depending on the data available for that IXP...
# instead of using all data, lets define a fixed timeframe that all IXPs will have to follow to count for this analysis.
# Since i want to make this work with IX.br São Paulo, that threshold will be 1 year (cant be more than that, because IX.br São Paulo started in 2025)




from datetime import timedelta

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

    last_first_year_snapshot = first_year_snapshots[-1]
    last_first_year_snapshot_date = last_first_year_snapshot.date_as_datetime()
    if last_first_year_snapshot_date < first_snapshot_date + timedelta(days=365):
        print(f"Warning: The last snapshot in the first year ({last_first_year_snapshot_date}) is less than 365 days after the first snapshot ({first_snapshot_date}).")   

        answer = input("Continue anyway? (y/n): ")
        if answer.lower() != "y":
            return   
        print("Continuing, but separating snapshots into first year and after first year, by halfing the snapshots list.")
        first_year_snapshots = first_year_snapshots[:len(first_year_snapshots)//2]
        after_first_year_snapshots = first_year_snapshots[len(first_year_snapshots)//2:]

    
    if len(after_first_year_snapshots) < 11:
        print(f"Warning: There are only {len(after_first_year_snapshots)} snapshots after the first year. This may not be enough data to analyze new members over time.")
        answer = input("Continue anyway? (y/n): ")
        if answer.lower() != "y":
            return

    all_members_from_first_year = set()
    for snapshot in first_year_snapshots:
        all_members_from_first_year.update(snapshot.unique_members)

    new_members_added_over_time = []
    for snapshot in after_first_year_snapshots:
        new_members = set(snapshot.unique_members) - all_members_from_first_year
        new_members_added_over_time.append((snapshot.date_as_datetime(), new_members))
        all_members_from_first_year.update(new_members)

    def flatten(lol):
        for item in lol:
            yield from item
    print(f"Unique new members added over time: {len(set(flatten([m[1] for m in new_members_added_over_time])))}")

    plot_list_as_line_plot(new_members_added_over_time,  
                           title="New Members Added Over Time",  
                           ylabel="New Members Added"
                           )