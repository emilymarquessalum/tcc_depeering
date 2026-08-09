

from collections import Counter

from src.ripe_bviews.read_bgpdump import BGPDumpSnapshotStats
from src.utils.graphs import plot_list_as_line_plot

from progress.bar import Bar

class OscillationMetrics:
    def __init__(self, oscillation_info: dict, total_oscillations: int, all_stats, route_oscillation_info: list = None, snapshots_for_real_depeering: int = 0, asn_states: dict = None):
        
        # every key is an AS that oscillated at least once, and the value is a dict with info about the oscillation periods of that AS, comeback times, and presence historic
        self.oscillation_info: dict = oscillation_info

        self.total_oscillations = total_oscillations
        self.all_stats: list[BGPDumpSnapshotStats] = all_stats
        self.route_oscillation_info: list = route_oscillation_info if route_oscillation_info is not None else []
        self.snapshots_for_real_depeering = snapshots_for_real_depeering
        self.asn_states: dict = asn_states if asn_states is not None else {}

        self.oscillating_start_over_time = []
        self.oscillating_end_over_time = []

        self.removed_asns_over_time = []
        self.added_asns_over_time = []

        self.added_oscillating_asns_over_time = []
        self.added_non_oscillating_asns_over_time = []


        self.all_did_not_come_backs = set[int]()
        self.all_did_not_come_back_events = [] # list of tuples for ASes that did not come back (asn, last index seen)
        self.all_potential_depeerings = set[int]()
        self.all_potential_depeering_events = []
        self.removed_oscillating_asns_over_time: list[int] = []
        self.removed_non_oscillating_asns_over_time: list[int] = []
        self.all_removed_asns_over_time: list[set[int]] = []
        self.all_added_asns_over_time: list[set[int]] = []
        self.unique_oscillating_asns = None

        self.oscillating_routes_over_time = []
        self.oscillating_start_routes_over_time = []
        self.oscillating_end_routes_over_time = []


    def get_unique_oscillating_asns(self):
        if self.unique_oscillating_asns is None:
            self.unique_oscillating_asns = set(self.oscillation_info.keys())
        return self.unique_oscillating_asns

    def get_as_oscillation_count(self, asn: str):
        asn = int(asn)  
        if asn not in self.oscillation_info:    
            return 0
        return self.oscillation_info[asn]["oscillations"]

    def get_oscillating_variance_over_time(self):
        total_variance = []

        for i in range(0, len(self.all_stats) - 1):
            added_oscillating_asns = self.added_oscillating_asns_over_time[i]
            removed_oscillating_asns = self.removed_oscillating_asns_over_time[i]
            variance = (added_oscillating_asns + removed_oscillating_asns)
            total_variance.append(variance)
        return total_variance


    def load_route_oscillating_info(self):
        
        if len(self.oscillating_routes_over_time) > 0:
            return
        
        routes_removed_over_time = []
        routes_added_over_time = []
        all_removed_routes_over_time = []
        all_added_routes_over_time = []
        
        for i in range(1, len(self.all_stats)): 
            _, previous_routes_list = self.all_stats[i-1].get_unique_routes()
            _, current_routes_list = self.all_stats[i].get_unique_routes()
            previous_routes_set = {tuple(r) for r in previous_routes_list}
            current_routes_set = {tuple(r) for r in current_routes_list}
            removed_routes = previous_routes_set - current_routes_set
            added_routes = current_routes_set - previous_routes_set
            routes_removed_over_time.append(len(removed_routes))
            routes_added_over_time.append(len(added_routes))
            all_removed_routes_over_time.append(removed_routes)
            all_added_routes_over_time.append(added_routes)


        for i in range(len(routes_added_over_time)):
            routes_removed = routes_removed_over_time[i]
            routes_added = routes_added_over_time[i]
            
            self.oscillating_routes_over_time.append({
                "removed_count": routes_removed,
                "added_count": routes_added,
                "removed_routes": all_removed_routes_over_time[i],
                "added_routes": all_added_routes_over_time[i]
            })
        
        # Load oscillating_start_routes_over_time and oscillating_end_routes_over_time
        for i in range(1, len(self.all_stats)):
            start_count = sum(1 for route_info in self.route_oscillation_info if i in route_info["start_idxs"])
            end_count = sum(1 for route_info in self.route_oscillation_info if i in route_info["end_idxs"])
            
            self.oscillating_start_routes_over_time.append(start_count)
            self.oscillating_end_routes_over_time.append(end_count)

    def load_oscillating_lists(self, use_reachables=False):
        if len(self.all_stats) < 2:
            return

        # Pre-index oscillation counts for O(1) access
        start_counts = Counter(
            idx for info in self.oscillation_info.values() for idx in info.get("start_idxs", [])
        )
        end_counts = Counter(
            idx for info in self.oscillation_info.values() for idx in info.get("end_idxs", [])
        )

        for i in range(1, len(self.all_stats)):
            prev_stat = self.all_stats[i-1]
            curr_stat = self.all_stats[i]

            previous_asns = prev_stat.unique_reachables if use_reachables else prev_stat.unique_members
            current_asns = curr_stat.unique_reachables if use_reachables else curr_stat.unique_members

            removed_asns = previous_asns - current_asns
            added_asns = current_asns - previous_asns

            self.removed_asns_over_time.append(len(removed_asns))
            self.added_asns_over_time.append(len(added_asns))

            # Time-indexed counts
            self.oscillating_start_over_time.append(start_counts[i]) 
            self.oscillating_end_over_time.append(end_counts[i]) 

            # Added oscillating breakdowns
            added_osc_count = sum(1 for asn in added_asns if asn in self.oscillation_info)
            self.added_oscillating_asns_over_time.append(added_osc_count)
            self.added_non_oscillating_asns_over_time.append(len(added_asns) - added_osc_count)

            # Removed oscillating breakdowns (done in-place)
            removed_osc_count = sum(1 for asn in removed_asns if asn in self.oscillation_info)
            self.removed_oscillating_asns_over_time.append(removed_osc_count)
            self.removed_non_oscillating_asns_over_time.append(len(removed_asns) - removed_osc_count)

            self.all_added_asns_over_time.append(added_asns)
            self.all_removed_asns_over_time.append(removed_asns)
        
        assert len(self.removed_asns_over_time) == len(self.all_stats) - 1
        assert len(self.added_asns_over_time) == len(self.all_stats) - 1
        assert len(self.oscillating_start_over_time) == len(self.all_stats) - 1
        assert len(self.oscillating_end_over_time) == len(self.all_stats) - 1
        assert len(self.added_oscillating_asns_over_time) == len(self.all_stats) - 1
        assert len(self.added_non_oscillating_asns_over_time) == len(self.all_stats) - 1
        assert len(self.all_added_asns_over_time) == len(self.all_stats) - 1
        assert len(self.all_removed_asns_over_time) == len(self.all_stats) - 1
        
        for asns_removed in self.all_removed_asns_over_time:
            oscillating_count = sum(1 for asn in asns_removed if asn in self.oscillation_info)
            non_oscillating_count = len(asns_removed) - oscillating_count
            self.removed_oscillating_asns_over_time.append(oscillating_count)
            self.removed_non_oscillating_asns_over_time.append(non_oscillating_count)
    




def get_ases_that_did_not_come_back(all_stats, use_reachables=False, index=0) -> set:
    ases_first_removed = all_stats[index].unique_reachables.copy() if use_reachables else all_stats[index].unique_members.copy()
    for stat in all_stats[index+1:]:
        ases_first_removed -= stat.unique_reachables if use_reachables else stat.unique_members
    return ases_first_removed


def plot_as_presences_over_time(all_asn_presences, group=None, subfolder=None):
    
    presences_agreggations = [0] * len(all_asn_presences[0])
    for asn_presences in all_asn_presences:
        for i, presence in enumerate(asn_presences):
            presences_agreggations[i] += presence

    plot_list_as_line_plot(presences_agreggations, 
                           title="Number of Oscillating ASes Present Over Time" if group is None else f"Number of Oscillating ASes Present Over Time - Group {group}",
                           xlabel="Time Snapshots",
                           ylabel="Number of Oscillating ASes",
                           subfolder=subfolder)
    
def calculate_oscillation_metrics(all_stats: list[BGPDumpSnapshotStats], use_reachables=False, calculate_routes=False, snapshots_for_real_depeering: int = 0) -> OscillationMetrics:
    oscillation_info = {}  # asn -> {"start_idx": i, "end_idx": j, "comeback_times": []}
    route_oscillation_info = [] # {"path": ["123","234","345"], "start_idx": i, "end_idx": j}
    total_oscillations = 0
    total_routes_oscillations = 0

    attr_name = "unique_reachables" if use_reachables else "unique_members"

    num_snapshots = len(all_stats)
    asn_states = {} # asn -> {state_vars}, will contain all the ASes that have been seen at least once in the snapshots 
    route_states = {} if calculate_routes else None
    last_idx = num_snapshots - 1

    for i, stat in enumerate(all_stats):
        current_asns = getattr(stat, attr_name)

        for asn in current_asns:
            if asn not in asn_states:
                asn_states[asn] = {
                    "has_been_present": True,
                    "has_disappeared": False,
                    "first_absence_idx": None,
                    "pending_start_idx": None,
                    "start_idx": None,
                    "start_idxs": [],
                    "end_idx": None,
                    "end_idxs": [],
                    "comeback_times": [],
                    "presence_historic": [0] * num_snapshots,
                    "oscillations": 0,
                    "currently_in_oscillation": False,
                    "last_seen_idx": i
                }

            state = asn_states[asn]
            state["presence_historic"][i] = 1

            if state["has_disappeared"]:
                absence_duration = i - state["first_absence_idx"] if state["first_absence_idx"] is not None else 0
                if absence_duration >= snapshots_for_real_depeering:
                    state["oscillations"] += 1
                    state["comeback_times"].append(absence_duration)
                    state["currently_in_oscillation"] = False
                    if state["oscillations"] == 1:
                        state["end_idx"] = i
                    state["end_idxs"].append(i)
                    start_idx = state["pending_start_idx"] if state["pending_start_idx"] is not None else state["first_absence_idx"]
                    if start_idx is not None:
                        state["start_idxs"].append(start_idx)
                        if state["oscillations"] == 1:
                            state["start_idx"] = start_idx

                state["has_disappeared"] = False
                state["first_absence_idx"] = None
                state["pending_start_idx"] = None

            state["last_seen_idx"] = i

        for asn, state in asn_states.items():
            if state["last_seen_idx"] < i and state["has_been_present"] and not state["has_disappeared"]:
                state["has_disappeared"] = True
                state["first_absence_idx"] = i
                state["pending_start_idx"] = i
                state["currently_in_oscillation"] = True

        if calculate_routes:
            _, current_routes_list = stat.get_unique_routes()
            current_routes_set = {tuple(r) for r in current_routes_list}

            for r_tuple in current_routes_set:
                if r_tuple not in route_states:
                    route_states[r_tuple] = {
                        "path": list(r_tuple),
                        "member": int(r_tuple[0]) if len(r_tuple) > 0 else 0,
                        "reachable": int(r_tuple[-1]) if len(r_tuple) > 0 else 0,
                        "has_been_present": True,
                        "has_disappeared": False,
                        "first_absence_idx": None,
                        "pending_start_idx": None,
                        "start_idx": None,
                        "start_idxs": [],
                        "end_idx": None,
                        "end_idxs": [],
                        "comeback_times": [],
                        "presence_historic": [0] * num_snapshots,
                        "oscillations": 0,
                        "currently_in_oscillation": False,
                        "last_seen_idx": i
                    }

                state = route_states[r_tuple]
                state["presence_historic"][i] = 1

                if state["has_disappeared"]:
                    absence_duration = i - state["first_absence_idx"] if state["first_absence_idx"] is not None else 0
                    if absence_duration >= snapshots_for_real_depeering:
                        state["oscillations"] += 1
                        if state["currently_in_oscillation"]:
                            state["comeback_times"].append(absence_duration)
                        state["currently_in_oscillation"] = False
                        if state["oscillations"] == 1:
                            state["end_idx"] = i
                        state["end_idxs"].append(i)
                        start_idx = state["pending_start_idx"] if state["pending_start_idx"] is not None else state["first_absence_idx"]
                        if start_idx is not None:
                            state["start_idxs"].append(start_idx)
                            if state["oscillations"] == 1:
                                state["start_idx"] = start_idx

                    state["has_disappeared"] = False
                    state["first_absence_idx"] = None
                    state["pending_start_idx"] = None

                state["last_seen_idx"] = i

            for r_tuple, state in route_states.items():
                if state["last_seen_idx"] < i and state["has_been_present"] and not state["has_disappeared"]:
                    state["has_disappeared"] = True
                    state["first_absence_idx"] = i
                    state["pending_start_idx"] = i
                    state["currently_in_oscillation"] = True

    for asn, state in asn_states.items():
        if state["oscillations"] > 0:
            total_oscillations += state["oscillations"]
            oscillation_info[asn] = {
                "start_idx": state["start_idx"],
                "end_idx": state["end_idx"],
                "start_idxs": state["start_idxs"],
                "end_idxs": state["end_idxs"],
                "comeback_times": state["comeback_times"],
                "presence_historic": state["presence_historic"],
                "oscillations": state["oscillations"]
            }

    if calculate_routes:
        bar = Bar(max=max(len(all_stats) - 1, 1))
        for state in route_states.values():
            if state["oscillations"] > 0:
                total_routes_oscillations += state["oscillations"]
                route_oscillation_info.append({
                    "path": state["path"],
                    "member": state["member"],
                    "reachable": state["reachable"],
                    "start_idx": state["start_idx"],
                    "end_idx": state["end_idx"],
                    "start_idxs": state["start_idxs"],
                    "end_idxs": state["end_idxs"],
                    "comeback_times": state["comeback_times"],
                    "presence_historic": state["presence_historic"],
                    "oscillations": state["oscillations"]
                })
            bar.next()
        bar.finish()

    metrics = OscillationMetrics(oscillation_info, total_oscillations, all_stats, route_oscillation_info, snapshots_for_real_depeering=snapshots_for_real_depeering,

                        asn_states=asn_states
                                 )

    for asn, state in asn_states.items():
        if state["has_disappeared"] and state["first_absence_idx"] is not None:
            absence_duration = last_idx - state["first_absence_idx"]
            if absence_duration < snapshots_for_real_depeering:
                metrics.all_potential_depeerings.add(asn)
                metrics.all_potential_depeering_events.append((asn, state["pending_start_idx"]))
            else:
                metrics.all_did_not_come_backs.add(asn)
                metrics.all_did_not_come_back_events.append((asn, state["pending_start_idx"]))

    return metrics


def get_comeback_times_count_from_oscillation_info(oscillation_info):
    all_comeback_times = []
    for _, info in oscillation_info.items():
        all_comeback_times.extend(info["comeback_times"])
    
    comeback_times_count = {}
    for time in all_comeback_times:
        if time not in comeback_times_count:
            comeback_times_count[time] = 0
        comeback_times_count[time] += 1

    come_back_set = set(all_comeback_times)

    return comeback_times_count, come_back_set