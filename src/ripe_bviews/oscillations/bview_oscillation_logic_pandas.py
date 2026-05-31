import pandas as pd
import numpy as np
from src.ripe_bviews.read_bgpdump import BGPDumpSnapshotStats
from src.utils.graphs import plot_list_as_line_plot
from progress.bar import Bar


class OscillationMetricsPandas:
    def __init__(self, oscillation_info: pd.DataFrame, total_oscillations: int, all_stats, route_oscillation_info: list = None):
        self.oscillation_info: pd.DataFrame = oscillation_info
        self.total_oscillations = total_oscillations
        self.all_stats: list[BGPDumpSnapshotStats] = all_stats
        self.route_oscillation_info: list = route_oscillation_info if route_oscillation_info is not None else []

        # Time series tracking
        self.oscillating_start_over_time = []
        self.oscillating_end_over_time = []
        self.removed_asns_over_time = []
        self.added_asns_over_time = []
        self.added_oscillating_asns_over_time = []
        self.added_non_oscillating_asns_over_time = []
        self.removed_oscillating_asns_over_time: list[int] = []
        self.removed_non_oscillating_asns_over_time: list[int] = []

        # Actual ASN sets over time
        self.all_removed_asns_over_time: list[set[int]] = []
        self.all_added_asns_over_time: list[set[int]] = []
        self.all_did_not_come_backs = set()

        self.oscillating_routes_over_time = []
        self.unique_oscillating_asns = None

    def get_unique_oscillating_asns(self):
        if self.unique_oscillating_asns is None:
            self.unique_oscillating_asns = set(self.oscillation_info.index.tolist())
        return self.unique_oscillating_asns

    def get_as_oscillation_count(self, asn):
        asn = int(asn)
        return int(self.oscillation_info.loc[asn, "oscillations"]) if asn in self.oscillation_info.index else 0

    def get_oscillating_variance_over_time(self):
        total_variance = []
        for i in range(len(self.added_oscillating_asns_over_time)):
            variance = self.added_oscillating_asns_over_time[i] + self.removed_oscillating_asns_over_time[i]
            total_variance.append(variance)
        return total_variance

    def load_route_oscillating_info(self):
        if len(self.oscillating_routes_over_time) > 0:
            return

        for i in range(1, len(self.all_stats)):
            prev_routes = self.all_stats[i - 1].get_unique_routes()
            curr_routes = self.all_stats[i].get_unique_routes()
            removed = prev_routes - curr_routes
            added = curr_routes - prev_routes

            self.oscillating_routes_over_time.append({
                "removed_count": len(removed),
                "added_count": len(added),
                "removed_routes": removed,
                "added_routes": added
            })

    def load_oscillating_lists(self, use_reachables=False):
        attr = "unique_reachables" if use_reachables else "unique_members"
        oscillating_asns_set = set(self.oscillation_info.index)
        
        # Build presence matrix (rows=ASNs, cols=snapshots)
        all_asns = set()
        for stat in self.all_stats:
            all_asns.update(getattr(stat, attr))
        
        presence_data = []
        for i, stat in enumerate(self.all_stats):
            current_asns = getattr(stat, attr)
            presence_data.append({asn: (1 if asn in current_asns else 0) for asn in all_asns})
        
        presence_df = pd.DataFrame(presence_data).T
        
        for i in range(1, len(self.all_stats)):
            prev_col = presence_df.iloc[:, i - 1]
            curr_col = presence_df.iloc[:, i]
            
            removed_asns = set(presence_df.index[prev_col == 1]) - set(presence_df.index[curr_col == 1])
            added_asns = set(presence_df.index[curr_col == 1]) - set(presence_df.index[prev_col == 1])
            
            self.removed_asns_over_time.append(len(removed_asns))
            self.added_asns_over_time.append(len(added_asns))
            self.all_removed_asns_over_time.append(removed_asns)
            self.all_added_asns_over_time.append(added_asns)

            # Count oscillations starting/ending using vectorized mask
            start_count = sum(1 for idx_list in self.oscillation_info["start_idxs"] if i in idx_list)
            end_count = sum(1 for idx_list in self.oscillation_info["end_idxs"] if i in idx_list)
            self.oscillating_start_over_time.append(start_count)
            self.oscillating_end_over_time.append(end_count)

            # Vectorized classification using masks
            added_osc = len(added_asns & oscillating_asns_set)
            self.added_oscillating_asns_over_time.append(added_osc)
            self.added_non_oscillating_asns_over_time.append(len(added_asns) - added_osc)

        # Vectorized "did not come back" detection using presence matrix
        self._compute_did_not_come_back(presence_df, oscillating_asns_set)

    def _compute_did_not_come_back(self, presence_df, oscillating_asns_set):
        """Compute ASNs that never came back using vectorized operations."""
        for i in range(len(self.all_removed_asns_over_time)):
            asns_removed = self.all_removed_asns_over_time[i]
            
            # Check future presence for each removed ASN
            for asn in asns_removed:
                if asn in presence_df.index:
                    if presence_df.loc[asn, i + 1:].sum() == 0:
                        self.all_did_not_come_backs.add(asn)

            # Vectorized classification for removed ASNs
            removed_osc = len(asns_removed & oscillating_asns_set)
            self.removed_oscillating_asns_over_time.append(removed_osc)
            self.removed_non_oscillating_asns_over_time.append(len(asns_removed) - removed_osc)


def get_ases_that_did_not_come_back(all_stats, use_reachables=False, index=0) -> set:
    attr = "unique_reachables" if use_reachables else "unique_members"
    result = getattr(all_stats[index], attr).copy()
    for stat in all_stats[index + 1:]:
        result -= getattr(stat, attr)
    return result


def plot_as_presences_over_time(all_asn_presences, group=None, subfolder=None):
    presences_df = pd.DataFrame(all_asn_presences)
    aggregations = presences_df.sum(axis=0).tolist()
    title = f"Number of Oscillating ASes Present Over Time - Group {group}" if group else "Number of Oscillating ASes Present Over Time"
    plot_list_as_line_plot(aggregations, title=title, xlabel="Time Snapshots", ylabel="Number of Oscillating ASes", subfolder=subfolder)


def _init_state(num_snapshots: int, i: int) -> dict:
    """Initialize a state dictionary for an ASN or route."""
    return {
        "presence": np.zeros(num_snapshots, dtype=int),
        "oscillations": 0,
        "start_idxs": [],
        "end_idxs": [],
        "comeback_times": [],
        "disappeared": False,
        "first_absence": None,
        "last_seen": i
    }


def _handle_presence(state: dict, i: int) -> None:
    """Update state when an entity is present."""
    state["presence"][i] = 1
    if state["disappeared"]:
        state["oscillations"] += 1
        if state["first_absence"] is not None:
            state["comeback_times"].append(i - state["first_absence"])
        state["disappeared"] = False
        state["end_idxs"].append(i)
    state["last_seen"] = i


def _handle_disappearance(state: dict, i: int) -> None:
    """Update state when an entity disappears."""
    if not state["disappeared"]:
        state["disappeared"] = True
        state["first_absence"] = i
        state["start_idxs"].append(i)


def _build_asn_states(all_stats: list, attr_name: str, num_snapshots: int) -> dict:
    """Build ASN state tracking dictionary for all snapshots."""
    asn_states = {}
    
    for i, stat in enumerate(all_stats):
        current_asns = getattr(stat, attr_name)
        
        for asn in current_asns:
            if asn not in asn_states:
                asn_states[asn] = _init_state(num_snapshots, i)
            _handle_presence(asn_states[asn], i)

        for asn, state in asn_states.items():
            if state["last_seen"] < i:
                _handle_disappearance(state, i)
    
    return asn_states


def _build_oscillation_dataframe(asn_states: dict) -> tuple:
    """Build DataFrame from oscillating ASN states."""
    oscillating = {asn: state for asn, state in asn_states.items() if state["oscillations"] > 0}
    
    if not oscillating:
        return pd.DataFrame(index=pd.Index([], name="asn")), 0
    
    df = pd.DataFrame({
        "start_idxs": [state["start_idxs"] for state in oscillating.values()],
        "end_idxs": [state["end_idxs"] for state in oscillating.values()],
        "comeback_times": [state["comeback_times"] for state in oscillating.values()],
        "presence_historic": [state["presence"] for state in oscillating.values()],
        "oscillations": [state["oscillations"] for state in oscillating.values()]
    }, index=pd.Index(oscillating.keys(), name="asn"))
    
    return df, int(df["oscillations"].sum())


def _build_route_states(all_stats: list, num_snapshots: int) -> dict:
    """Build route state tracking dictionary for all snapshots."""
    route_states = {}
    bar = Bar(max=len(all_stats) - 1)
    
    for i, stat in enumerate(all_stats):
        bar.next()
        _, current_routes_list = stat.get_unique_routes()
        current_routes = {tuple(r) for r in current_routes_list}

        for r_tuple in current_routes:
            if r_tuple not in route_states:
                route_states[r_tuple] = _init_state(num_snapshots, i)
            _handle_presence(route_states[r_tuple], i)

        for r_tuple, state in route_states.items():
            if state["last_seen"] < i:
                _handle_disappearance(state, i)
    
    bar.finish()
    return route_states


def calculate_oscillation_metrics(all_stats: list[BGPDumpSnapshotStats], use_reachables=False, calculate_routes=False) -> OscillationMetricsPandas:
    """Calculate oscillation metrics using pandas DataFrames for vectorized operations."""
    attr_name = "unique_reachables" if use_reachables else "unique_members"
    num_snapshots = len(all_stats)
    
    # Build ASN states
    asn_states = _build_asn_states(all_stats, attr_name, num_snapshots)
    oscillation_df, total_oscillations = _build_oscillation_dataframe(asn_states)

    # Build route states (optional)
    route_data = []
    if calculate_routes:
        route_states = _build_route_states(all_stats, num_snapshots)
        oscillating_routes = {r: state for r, state in route_states.items() if state["oscillations"] > 0}
        route_data = [{
            "path": list(r),
            "start_idxs": state["start_idxs"],
            "end_idxs": state["end_idxs"],
            "comeback_times": state["comeback_times"],
            "presence_historic": state["presence"],
            "oscillations": state["oscillations"]
        } for r, state in oscillating_routes.items()]

    return OscillationMetricsPandas(oscillation_df, int(total_oscillations), all_stats, route_data)


def get_comeback_times_count_from_oscillation_info(oscillation_info: pd.DataFrame):
    """Get comeback times count from oscillation DataFrame."""
    all_comeback_times = pd.Series([t for times in oscillation_info["comeback_times"] for t in times])
    return all_comeback_times.value_counts().to_dict(), set(all_comeback_times.unique())
