


from annotationlib import get_annotations

from src.ripe_bviews.oscillations.bview_oscillation_logic import calculate_oscillation_metrics
from src.utils.graphs import plot_list_as_line_plot, plot_stacked_line_plot

def plot_depeering_over_time_by_type(all_stats, labels_summarized, subfolder, max_labels, config=None, title_start=''):
    """
    Plots all de-peering events over time classified into three tiers:
      1. Potential De-peering: Disappeared < 7 days
      2. Soft De-peering: Disappeared >= 7 days and < 30 days
      3. Hard De-peering: Disappeared >= 30 days (or never returned)
    """
    if config is None:
        config = {}

    # 1. Determine snapshot step size in days
    days_per_snapshot = config.get("day_delta", 7) + (config.get("time_delta_hours", 0) / 24.0)
    if days_per_snapshot <= 0:
        days_per_snapshot = 7.0

    snapshots_7_days = max(1, int(round(7.0 / days_per_snapshot)))
    snapshots_30_days = max(snapshots_7_days + 1, int(round(30.0 / days_per_snapshot)))

    # Set threshold high enough to cover up to the hard de-peering boundary
    metrics = calculate_oscillation_metrics(all_stats, snapshots_for_real_depeering=snapshots_30_days)
    metrics.load_oscillating_lists()

    total_steps = len(metrics.all_removed_asns_over_time)
    
    potential_depeerings = [0] * total_steps  # < 7 days
    soft_depeerings = [0] * total_steps       # 7 to < 30 days
    hard_depeerings = [0] * total_steps       # >= 30 days

    # Track index pointers to consume comeback_times sequentially per ASN
    asn_event_pointers = {}

    # 2. Iterate through every removal event across all snapshots
    for t_idx, removed_asns in enumerate(metrics.all_removed_asns_over_time):
        for asn in removed_asns:
            info = metrics.oscillation_info.get(asn)
            
            # Default to infinity (never came back / hard depeering)
            duration = float('inf')

            if info and "comeback_times" in info and info["comeback_times"]:
                comeback_list = info["comeback_times"]
                current_event_idx = asn_event_pointers.get(asn, 0)
                
                # Fetch the corresponding comeback duration for this specific removal event
                if current_event_idx < len(comeback_list):
                    duration = comeback_list[current_event_idx]
                    asn_event_pointers[asn] = current_event_idx + 1

            # 3. Categorize de-peering event
            if duration < snapshots_7_days:
                potential_depeerings[t_idx] += 1
            elif duration < snapshots_30_days:
                soft_depeerings[t_idx] += 1
            else:
                hard_depeerings[t_idx] += 1

    # 4. Prepare stacked data & labels
    data_lists = [
        potential_depeerings,
        soft_depeerings,
        hard_depeerings
    ]
    
    labels = [
        "Potential De-peering (< 7d)",
        "Soft De-peering (7d - 30d)",
        "Hard De-peering (>= 30d)"
    ]

    colors = ["#f1c40f", "#e67e22", "#e74c3c"]

    # 5. Render Stacked Line Plot
    plot_stacked_line_plot(
        data_lists=data_lists,
        labels=labels,
        x_labels=labels_summarized[1:],
        title=f"{title_start}Depeerings Over Time by Type",
        xlabel="Date",
        ylabel="Number of Depeerings",
        colors=colors,
        subfolder=subfolder,
        max_labels=max_labels,
        annotations=get_annotations(),
        sort_by_size=False
    )


def plot_depeerings_over_time(all_stats, labels_summarized, subfolder, max_labels, title_start=''):
    metrics = calculate_oscillation_metrics(all_stats, snapshots_for_real_depeering=7)
    metrics.load_oscillating_lists()
    plot_list_as_line_plot([len(asns) for asns in metrics.all_removed_asns_over_time], labels_summarized[1:], 

                           title=f"{title_start}Depeerings Over Time", xlabel="Time", ylabel="Number of Depeerings", subfolder=subfolder, max_labels=max_labels, annotations=get_annotations())
