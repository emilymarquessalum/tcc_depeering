
import json
import os
from pathlib import Path
from progress.bar import Bar
import mmap
from dataclasses import dataclass, asdict, field

from definitions import ROOT_DIR, append_root, append_root
 


SAVE_RESULTS = True

# Summary data -> in-instance
# Details -> currently in-instance, but maybe make it into external file only, needs to be loaded manually
@dataclass
class RIBMonitorSnapshotStats:
    asn: str
    prefix: str = None
    date: str = None
    time: str = None
    total_lines: int = 0
    lines: int = 0  # Number of lines coming from monitor AS
    members: int = 0  # AS PATH most-left
    reachables: int = 0  # AS PATH most-right
    one_length_as_paths: int = 0
    count_as_origin: int = 0
    count_as_member: int = 0
    unique_members: set = field(default_factory=set)
    unique_reachables: set = field(default_factory=set)
    unique_monitors: set = field(default_factory=set)
    unique_next_hops_from_monitored_as: set = field(default_factory=set)
    unique_prefixes_from_monitored_as: set = field(default_factory=set)
    monitor_to_count: dict = field(default_factory=dict)
    times_as_was_in_aspath: int = 0
        
    def print_summary(self):
        print(f"Monitor: {self.prefix} - AS{self.asn}")
        print(f"Lines in snapshot: {self.total_lines}")
        print(f"Lines from monitor: {self.lines}")
        print(f"Lines where AS{self.asn} is origin: {self.count_as_origin}")
        print(f"Lines where AS{self.asn} is member: {self.count_as_member}")
        print(f"Unique members (most-left AS in AS PATH): {self.members}")
        print(f"Unique reachables (most-right AS in AS PATH): {self.reachables}")
        print(f"Unique monitors in snapshot: {len(self.unique_monitors)}")
        print(f"One-length AS PATHs from monitor: {self.one_length_as_paths}")
        print(f"Prefixes from monitored AS: {(self.unique_prefixes_from_monitored_as)}")
        print(f"unique_next_hops_from_monitored_as: {len(self.unique_next_hops_from_monitored_as)}")
        #print(f"Times AS{self.asn} was in AS PATH: {self.times_as_was_in_aspath}")
        '''
        print("Top monitors by number of lines:")
        sorted_monitors = sorted(self.monitor_to_count.items(), key=lambda x: x[1], reverse=True)
        for monitor, count in sorted_monitors[:10]:
            print(f"  {monitor}: {count} lines")
        ''' 
    
    def check_consistency(self): 
        for member in self.unique_members:
            if not member.isdigit():
                print("Member AS is not numeric:", member)
        for reachable in self.unique_reachables:
            if not reachable.isdigit():
                print("Reachable AS is not numeric:", reachable)
    
    # save as json
    def save_details(self, filename):
        filename = append_root(filename)
        save_file = Path(filename)
        save_file.parent.mkdir(parents=True, exist_ok=True)
        # Convert to dict and convert sets to lists for JSON serialization
        data = asdict(self)
        for key in data:
            if isinstance(data[key], set):
                data[key] = list(data[key])
        with save_file.open("w") as f:
            json.dump(data, f, indent=4)
    
    def load_details(self, filename):
        filename = append_root(filename)
        with open(filename, "r") as f:
            details = json.load(f)
            # Handle backward compatibility: old JSON had "members" and "reachables" keys
            if "members" in details and "unique_members" not in details:
                details["unique_members"] = details.pop("members")
            if "reachables" in details and "unique_reachables" not in details:
                details["unique_reachables"] = details.pop("reachables")
            # Convert lists back to sets for set fields
            set_fields = {'unique_members', 'unique_reachables', 'unique_monitors', 
                         'unique_next_hops_from_monitored_as', 'unique_prefixes_from_monitored_as'}
            for key in set_fields:
                if key in details and isinstance(details[key], list):
                    details[key] = set(details[key])
            # Update instance with loaded data
            for key, value in details.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            # Update members and reachables counts
            self.members = len(self.unique_members)
            self.reachables = len(self.unique_reachables)
    

    
def is_line_from_monitor(line, monitor_as, monitor_prefix):
    fields = line.decode('utf-8').strip().split("|")

    if monitor_prefix is not None:
        if monitor_as is None:
            return monitor_prefix in fields[8]
        field_splitted = fields[8].split(" ")
        return monitor_prefix in field_splitted and monitor_as in field_splitted
    else:
        return fields[8].endswith(" " + monitor_as)

def _read_bview(file1, monitor_as, monitor_prefix, date, time, save_details=True):
 
    print("Searching for AS:", monitor_as, "Prefix:", monitor_prefix)
    stats = RIBMonitorSnapshotStats(monitor_as, monitor_prefix, date, time)

    unique_members = set()
    unique_reachables = set()

    unique_monitors = set()

    buffering=10485760
    with open(file1, "rb", buffering=buffering) as f:

        filesize = os.path.getsize(file1) 
        bar = Bar('Processing', max=filesize)#/160) 

        start_time = os.times()
 
        with mmap.mmap(f.fileno(), length=0, access=mmap.ACCESS_READ) as mm:

            line_size_buffer = 0
            for line in iter(mm.readline, b""):
                line_size_buffer += len(line)
                #print(line)

                fields = line.decode('utf-8').strip().split("|")
                stats.total_lines += 1
                unique_monitors.add(fields[8])
                stats.monitor_to_count[fields[8]] = stats.monitor_to_count.get(fields[8], 0) + 1

                # found nothing...
                #if fields[8].find("(") != -1 or fields[8].find(")") != -1 or fields[8].find("[") != -1 or fields[8].find("]") != -1 or fields[8].find("{") != -1 or fields[8].find("}") != -1:
                #    print("Bad line:", fields[8]) 
                as_path = fields[2].strip().split(" ")
                if as_path[-1] == monitor_as: 
                    stats.count_as_origin += 1
                if as_path[0] == monitor_as:
                    stats.count_as_member += 1
                #line_matches = (monitor_prefix in fields[8] and monitor_as in fields[8]) if monitor_prefix is not None else fields[8].endswith(" " + monitor_as)
                line_matches = is_line_from_monitor(line, monitor_as, monitor_prefix)
                if line_matches:
                    stats.unique_prefixes_from_monitored_as.add(fields[8]) 
                    stats.unique_next_hops_from_monitored_as.add(fields[3])
                    stats.lines += 1
                    as_path = fields[2].strip().split(" ")
                    if len(as_path) > 1 or (len(as_path) == 1 and monitor_as != as_path[0]): 
                        #path_except_monitor_and_reachable = as_path[1:-1] if len(as_path) > 2 else []
                        #unique_members.update(path_except_monitor_and_reachable)
                        unique_members.add(as_path[0] if as_path[0] != monitor_as else as_path[1])
                        unique_reachables.add(as_path[-1])
                    if len(as_path) == 1:
                        stats.one_length_as_paths += 1
                        
                else:
                    # check if monitor_as is in as_path
                    as_path = fields[2].strip().split(" ")
                    if monitor_as in as_path:
                        stats.times_as_was_in_aspath += 1

                if stats.total_lines % 1000 == 0 and bar is not None:
                    bar.next(line_size_buffer)
                    line_size_buffer = 0
                    #bar.goto(stats.total_lines)
                    #bar.next(1000)

        if bar is not None:
            bar.finish()
        end_time = os.times()
        elapsed_time = end_time[4] - start_time[4]
        print(f"Time taken to process {file1}: {elapsed_time:.2f} seconds")


    stats.unique_monitors = unique_monitors
    stats.unique_members = unique_members
    stats.unique_reachables = unique_reachables
    stats.members = len(unique_members)
    stats.reachables = len(unique_reachables)

    if save_details and SAVE_RESULTS: 
        stats.save_details(append_root(f"stats_{file1}_{monitor_as}_{monitor_prefix}.json"))
    
    return stats

# check if stat file exists
def read_bview(file1, monitor_as, monitor_prefix=None, date=None, time=None):
    stats = RIBMonitorSnapshotStats(monitor_as, monitor_prefix, date, time)
    details_file =  append_root(f"stats_{file1}_{monitor_as}_{monitor_prefix}.json")

    if os.path.exists(details_file):
        print("Loading existing details from", details_file) 
        stats.load_details(details_file)
    else:
        stats = _read_bview(file1, monitor_as, monitor_prefix, date, time, save_details=True)
    return stats


def read_bviews(files, monitor_as, monitor_prefix, date=None, time=None):
    stats_list = []
    for file in files:
        stats = read_bview(file, monitor_as, monitor_prefix, date, time)
        stats_list.append(stats)
    return stats_list

def get_all_monitors_in_bview(file1):
    monitors = set()
    buffering=10485760
    with open(file1, "rb", buffering=buffering) as f:
        with mmap.mmap(f.fileno(), length=0, access=mmap.ACCESS_READ) as mm:
            for line in iter(mm.readline, b""):
                fields = line.decode('utf-8').strip().split("|")
                monitors.add(fields[8])
    return monitors
 
if __name__ == "__main__":
    # RRC15 -> São Paulo "26162", "22548"
    
    file = "data/rrc15/bview.20260122.0000.txt"
    #file = "loop_test.txt"
    
    #file = "data/rrc15/bview.20260120.0000.26162.txt" 
    #file = "data/rrc15/bview.20250906.0000.txt"
    #file = "aaabc.txt"
    #file = "data/RRC14/bview.20260122.0800.txt"
    #all_monitors = 
    #as_prefix = ("22548", "187.16.217.17")
    as_prefix = ("26162", "187.16.216.253") 
    #as_prefix = ("1280", "198.32.176.3")
    #as_prefix = ("26162", None)
    #as_prefix = ("26162", "2001:12f8::253") 
    #as_prefix = ("917","187.16.220.159")

    #results = verify_ripestat_count(as_prefix[0], as_prefix[1], "2026-01-16T08:00:00Z")
    #print("Official prefix count from RIPEstat:", results)
    if True:
        stats = read_bview(file, as_prefix[0], as_prefix[1])
        stats.print_summary()
    print("----")
    
    #stats.check_consistency()
     
    if False:
        with open(file, "rb") as f:
            with mmap.mmap(f.fileno(), length=0, access=mmap.ACCESS_READ) as mm:
                
                #total_lines = mm.read().count(b'\n')
                #print(f"Total lines in file: {total_lines}")
                # consistency checks
                count = 0
                for line in iter(mm.readline, b""):
                    if line.decode('utf-8').strip().split("|")[1].find(",") != -1:
                        print("Comma found in prefix field:", line.decode('utf-8').strip())
                    if line.decode('utf-8').find("187.16.216.254") != -1:
                        count += 1
                        print("Line with sec monitor prefix found:", line.decode('utf-8').strip())
                    #fields = line.decode('utf-8').strip().split("|")
                    #if fields[8] == "":
                    #    print("Empty field at 8 index")
                    #if fields[8].find(" ") == -1:
                    #    print("No space in field at 8 index:", fields[8])
                #print(f"Lines matching prefix: {count}")