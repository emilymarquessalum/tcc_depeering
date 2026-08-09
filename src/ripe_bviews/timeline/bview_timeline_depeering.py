


from src.ripe_bviews.oscillations.bview_oscillation_logic import calculate_oscillation_metrics
from src.utils.graphs import plot_stacked_line_plot


def bview_timeline_depeering(all_required_data):
    all_stats, labels, _ = all_required_data["timeline"]

    # Calculate metrics to ensure asn_states is populated
    metrics = calculate_oscillation_metrics(all_stats, labels)
    asn_states = metrics.asn_states

    num_snapshots = len(all_stats)
    last_idx = num_snapshots - 1

    # Define snapshot thresholds based on your dump interval
    # (Assuming 1 snapshot per day here; adjust these multipliers if your snapshots are hourly/etc.)
    ONE_WEEK = 7
    ONE_MONTH = 30

    # 1. Initialize timeline lists (one inner list per snapshot)
    potential_depeerings_over_time = [[] for _ in range(num_snapshots)]
    soft_depeerings_over_time = [[] for _ in range(num_snapshots)]
    hard_depeerings_over_time = [[] for _ in range(num_snapshots)]

    # 2. Reconstruct contiguous absence periods for each AS
    for asn, state in asn_states.items():
        presence = state["presence_historic"]

        # Track historical contiguous offline durations per snapshot
        absence_duration = 0
        for i in range(num_snapshots):
            if presence[i] == 0:
                absence_duration += 1
                
                # Classify duration at snapshot i
                if absence_duration < ONE_WEEK:
                    potential_depeerings_over_time[i].append(asn)
                elif ONE_WEEK <= absence_duration < ONE_MONTH:
                    soft_depeerings_over_time[i].append(asn)
                else:  # absence_duration >= ONE_MONTH
                    hard_depeerings_over_time[i].append(asn)
            else:
                absence_duration = 0  # Reset counter when AS is present

    # 3. Extract current status (the state at the final snapshot)
    potential_depeerings_currently = potential_depeerings_over_time[last_idx]
    soft_depeerings_currently = soft_depeerings_over_time[last_idx]
    hard_depeerings_currently = hard_depeerings_over_time[last_idx]

    # --- Print Outputs ---
    print(f"Number of potential de-peerings currently: {len(potential_depeerings_currently)}")
    print(f"Number of soft de-peerings currently: {len(soft_depeerings_currently)}")
    print(f"Number of hard de-peerings currently: {len(hard_depeerings_currently)}")

    potential_depeerings_over_time_in_numbers = [len(depeerings) for depeerings in potential_depeerings_over_time]
    soft_depeerings_over_time_in_numbers = [len(depeerings) for depeerings in soft_depeerings_over_time]
    hard_depeerings_over_time_in_numbers = [len(depeerings) for depeerings in hard_depeerings_over_time]

    plot_stacked_line_plot(
        [
            potential_depeerings_over_time_in_numbers,
            soft_depeerings_over_time_in_numbers,
            hard_depeerings_over_time_in_numbers
        ],
        [
            "Potential De-peerings (less than 7 days)",
            "Soft De-peerings (7 days to 1 month)",
            "Hard De-peerings (more than 1 month)"
        ],
        title="De-peering Timeline",
    )