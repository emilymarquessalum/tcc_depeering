

from src.utils.graphs import plot_list_as_line_plot


class OscillationMetrics:
    def __init__(self, oscillation_info: dict, total_oscillations: int, all_stats):
        self.oscillation_info = oscillation_info
        self.total_oscillations = total_oscillations
        self.all_stats = all_stats

        self.oscillating_start_over_time = []
        self.oscillating_end_over_time = []

        self.removed_asns_over_time = []
        self.added_asns_over_time = []

        self.added_oscillating_asns_over_time = []
        self.added_non_oscillating_asns_over_time = []


        self.all_did_not_come_backs = set()
        self.removed_oscillating_asns_over_time = []
        self.removed_non_oscillating_asns_over_time = []
        self.all_removed_asns_over_time = []
        

    def get_oscillating_variance_over_time(self):
        total_variance = []

        for i in range(0, len(self.all_stats) - 1):
            added_oscillating_asns = self.added_oscillating_asns_over_time[i]
            removed_oscillating_asns = self.removed_oscillating_asns_over_time[i]
            variance = (added_oscillating_asns + removed_oscillating_asns)
            total_variance.append(variance)
        return total_variance

    def load_oscillating_lists(self):
 
        for i in range(1, len(self.all_stats)): 

            previous_asns = self.all_stats[i-1].unique_members
            current_asns = self.all_stats[i].unique_members

            removed_asns = previous_asns - current_asns
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
 
            self.all_removed_asns_over_time.append(removed_asns)

        for i in range(len(self.all_removed_asns_over_time)):
            asns_removed = self.all_removed_asns_over_time[i]
            did_not_come_back = []
            for asn in asns_removed:
                came_back = False
                for j in range(i+1, len(self.all_stats)-1):
                    future_asns = self.all_stats[j+1].unique_members
                    if asn in future_asns:
                        came_back = True
                        break
                if not came_back:
                    did_not_come_back.append(asn)
                    self.all_did_not_come_backs.add(asn)
            oscillating_count = sum(1 for asn in did_not_come_back if asn in self.oscillation_info)
            non_oscillating_count = len(did_not_come_back) - oscillating_count
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
    
def calculate_oscillation_metrics(all_stats, use_reachables=False) -> OscillationMetrics:
    oscillation_info = {}  # asn -> {"start_idx": i, "end_idx": j, "comeback_times": []}
    total_oscillations = 0
     
    attr_name = "unique_reachables" if use_reachables else "unique_members"
     
    all_asns = set()
    for stat in all_stats:
        all_asns.update(getattr(stat, attr_name))
    # if an AS existed at a time i, left at a time i+1, and came back at a time i+a (a > 1),
    # start_idx should be i and end_idx should be i+b
    for asn in all_asns:
        presence = [asn in getattr(stat, attr_name) for stat in all_stats]
        oscillations = 0
        first_absence_idx = None
        comeback_times = []  # times (in snapshots) to come back
        start_idx = None
        start_idxs = []
        end_idx = None
        end_idxs = []
        has_been_present = presence[0]  # Was this AS present at the start?
        has_disappeared = False  # Has this AS disappeared after being present?
        presence_historic = [1 if p else 0 for p in presence]
        currently_in_oscillation = False # added this to make sure we are not doing conflicting logic
        
        
        for i in range(0, len(presence)):
            if presence[i] and not has_been_present:
                # By design this condition is only caught once.
                # First time appearing - this is NOT oscillation
                # it can happen at the very beggining of our timeline, 
                # or later if an AS enters for the first time 
                # In our definition of oscillation,
                # the last time this condition is True before other conditions, 
                # its the index "i".
                has_been_present = True
            elif not presence[i] and has_been_present:
                # If it disappears after being present, this could be oscillation
                # or it could be the AS will never come back (not oscillating)
                if not has_disappeared:
                    # Disappeared after being present
                    has_disappeared = True
                    first_absence_idx = i
                    start_idx = i
                    currently_in_oscillation = True
                    # start_ids are counted the first time the AS disappears.
                    # which in our definition of oscillation, is the first time the AS is not present (i+1)
                    # after being present for some time (0 up to i)
                    start_idxs.append(i)
            elif presence[i] and has_disappeared:
                # Came back after disappearing - this IS oscillation
                oscillations += 1
                
                if first_absence_idx is not None and currently_in_oscillation:
                    comeback_times.append(i - first_absence_idx)
                currently_in_oscillation = False # oscilaltion ends untill the AS disappears again
                if oscillations == 1:  # First time coming back
                    end_idx = i
                has_disappeared = False # makes sure we are not counting oscillations multiple times if the AS disappears and comes back multiple times in a row
                # end idxs counts the exact moment the AS came back after disappearing, 
                # which in our definition of oscillation, 
                #  is i+a, where a counts the amount of time in snapshots that the AS 
                # was not present in the oscillation period (a > 1, because it counts the i+1 snapshot too)
                end_idxs.append(i)
        
        total_oscillations += oscillations
        if oscillations > 0:
            oscillation_info[asn] = {
                "start_idx": start_idx,
                "end_idx": end_idx,
                "start_idxs": start_idxs,
                "end_idxs": end_idxs,
                "comeback_times": comeback_times,
                "presence_historic": presence_historic,
                "oscillations": oscillations
            }
    
    return OscillationMetrics(oscillation_info, total_oscillations, all_stats)


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