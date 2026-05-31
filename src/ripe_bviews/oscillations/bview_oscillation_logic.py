

from src.ripe_bviews.read_bgpdump import BGPDumpSnapshotStats
from src.utils.graphs import plot_list_as_line_plot

from progress.bar import Bar

class OscillationMetrics:
    def __init__(self, oscillation_info: dict, total_oscillations: int, all_stats, route_oscillation_info: list = None):
        self.oscillation_info: dict = oscillation_info
        self.total_oscillations = total_oscillations
        self.all_stats: list[BGPDumpSnapshotStats] = all_stats
        self.route_oscillation_info: list = route_oscillation_info if route_oscillation_info is not None else []

        self.oscillating_start_over_time = []
        self.oscillating_end_over_time = []

        self.removed_asns_over_time = []
        self.added_asns_over_time = []

        self.added_oscillating_asns_over_time = []
        self.added_non_oscillating_asns_over_time = []


        self.all_did_not_come_backs = set()
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
 
        for i in range(1, len(self.all_stats)): 

            previous_asns = self.all_stats[i-1].unique_members if not use_reachables else self.all_stats[i-1].unique_reachables
            current_asns = self.all_stats[i].unique_members if not use_reachables else self.all_stats[i].unique_reachables

            # ex: [1,2,3] - [1,2] = [3] (3 was removed)
            removed_asns = previous_asns - current_asns
            # ex: [1,2,3] - [2,3] = [1] (1 was added)
            added_asns = current_asns - previous_asns

            self.removed_asns_over_time.append(len(removed_asns))
            self.added_asns_over_time.append(len(added_asns))

            #start_count = sum(1 for asn, info in self.oscillation_info.items() if info["start_idx"] == i)
            #end_count = sum(1 for asn, info in self.oscillation_info.items() if info["end_idx"] == i)
            start_count = sum(1 for asn, info in self.oscillation_info.items() if i in info["start_idxs"])
            end_count = sum(1 for asn, info in self.oscillation_info.items() if i in info["end_idxs"])

            self.oscillating_start_over_time.append(start_count) 
            self.oscillating_end_over_time.append(end_count) 

   
            
            oscillating_count = sum(1 for asn in added_asns if asn in self.oscillation_info)
            non_oscillating_count = len(added_asns) - oscillating_count
            
            self.added_oscillating_asns_over_time.append(oscillating_count)
            self.added_non_oscillating_asns_over_time.append(non_oscillating_count)
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
        
        for i in range(len(self.all_removed_asns_over_time)):
            asns_removed = self.all_removed_asns_over_time[i]
            did_not_come_back: list[int] = []
            for asn in asns_removed:
                came_back = False
                for j in range(i+1, len(self.all_stats)-1):
                    future_asns = self.all_stats[j+1].unique_members if not use_reachables else self.all_stats[j+1].unique_reachables
                    if asn in future_asns:
                        came_back = True
                        break
                if not came_back: 
                    did_not_come_back.append(asn)
                    self.all_did_not_come_backs.add(asn)

            # Count oscillating ASes that were removed (regardless of whether they come back)
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
    
def calculate_oscillation_metrics(all_stats: list[BGPDumpSnapshotStats], use_reachables=False, calculate_routes=False) -> OscillationMetrics:
    oscillation_info = {}  # asn -> {"start_idx": i, "end_idx": j, "comeback_times": []}
    route_oscillation_info = [] # {"path": ["123","234","345"], "start_idx": i, "end_idx": j}
    total_oscillations = 0
    total_routes_oscillations = 0
     
    attr_name = "unique_reachables" if use_reachables else "unique_members"
    
    num_snapshots = len(all_stats)
    asn_states = {} # asn -> {state_vars}
    
    for i, stat in enumerate(all_stats):
        current_asns = getattr(stat, attr_name)
        
        # Track all unique ASNs encountered so far to handle those NOT in current snapshot
        for asn in current_asns:
            if asn not in asn_states:
                asn_states[asn] = {
                    "has_been_present": True,
                    "has_disappeared": False,
                    "first_absence_idx": None,
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
                # Came back after disappearing - this IS oscillation
                state["oscillations"] += 1
                if state["first_absence_idx"] is not None and state["currently_in_oscillation"]:
                    state["comeback_times"].append(i - state["first_absence_idx"])
                state["currently_in_oscillation"] = False # oscilaltion ends untill the AS disappears again
                if state["oscillations"] == 1:  # First time coming back
                    state["end_idx"] = i
                state["has_disappeared"] = False # makes sure we are not counting oscillations multiple times if the AS disappears and comes back multiple times in a row
                # end idxs counts the exact moment the AS came back after disappearing, 
                # which in our definition of oscillation, 
                #  is i+a, where a counts the amount of time in snapshots that the AS 
                # was not present in the oscillation period (a > 1, because it counts the i+1 snapshot too)
                state["end_idxs"].append(i)
            
            state["last_seen_idx"] = i

        # Check for disappearances
        for asn, state in asn_states.items():
            if state["last_seen_idx"] < i: # Not in current snapshot
                if state["has_been_present"] and not state["has_disappeared"]:
                    # If it disappears after being present, this could be oscillation
                    # or it could be the AS will never come back (not oscillating)
                    # Disappeared after being present
                    state["has_disappeared"] = True
                    state["first_absence_idx"] = i
                    state["start_idx"] = i
                    state["currently_in_oscillation"] = True
                    # start_ids are counted the first time the AS disappears.
                    # which in our definition of oscillation, is the first time the AS is not present (i+1)
                    # after being present for some time (0 up to i)
                    state["start_idxs"].append(i)

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

        bar = Bar(max=len(all_stats)-1)
        route_states = {}
        for i, stat in enumerate(all_stats):
            bar.next()

            _, current_routes_list = stat.get_unique_routes()
            current_routes_set = {tuple(r) for r in current_routes_list}
            
            for r_tuple in current_routes_set:
                if r_tuple not in route_states:
                    route_states[r_tuple] = {
                        "has_been_present": True,
                        "has_disappeared": False,
                        "first_absence_idx": None,
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
                    # Came back after disappearing - this IS oscillation
                    state["oscillations"] += 1
                    if state["first_absence_idx"] is not None and state["currently_in_oscillation"]:
                        state["comeback_times"].append(i - state["first_absence_idx"])
                    state["currently_in_oscillation"] = False
                    if state["oscillations"] == 1:  # First time coming back
                        state["end_idx"] = i
                    state["has_disappeared"] = False
                    state["end_idxs"].append(i)
                state["last_seen_idx"] = i

            for r_tuple, state in route_states.items():
                if state["last_seen_idx"] < i:
                    if state["has_been_present"] and not state["has_disappeared"]:
                        # Route disappeared after being present
                        state["has_disappeared"] = True
                        state["first_absence_idx"] = i
                        state["start_idx"] = i
                        state["currently_in_oscillation"] = True
                        state["start_idxs"].append(i)
       
        for r_tuple, state in route_states.items():
            if state["oscillations"] > 0:
                total_routes_oscillations += state["oscillations"]
                route_oscillation_info.append({
                    "path": list(r_tuple),
                    "member": int(list(r_tuple)[0]),
                    "reachable": int(list(r_tuple)[-1]),  
                    "start_idx": state["start_idx"],
                    "end_idx": state["end_idx"],
                    "start_idxs": state["start_idxs"],
                    "end_idxs": state["end_idxs"],
                    "comeback_times": state["comeback_times"],
                    "presence_historic": state["presence_historic"],
                    "oscillations": state["oscillations"]
                })
        bar.finish()
    return OscillationMetrics(oscillation_info, total_oscillations, all_stats, route_oscillation_info)


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