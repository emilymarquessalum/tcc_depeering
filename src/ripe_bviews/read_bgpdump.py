import json
import os
from pathlib import Path
import warnings
from progress.bar import Bar
import mmap
from dataclasses import dataclass, asdict, field

from definitions import ROOT_DIR, append_root


SAVE_RESULTS = False

# BGP Dump format: TABLE_DUMP2|timestamp|type|monitor_ip|monitor_as|prefix|as_path|origin|next_hop|field9|field10|communities|field12|field13|field14
@dataclass
class BGPDumpSnapshotStats:
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
    mappings: dict = field(default_factory=dict)

    def print_summary(self):
        print(f"Monitor: {self.prefix} - AS{self.asn}")
        print(f"Lines in snapshot: {self.total_lines}")
        print(f"Lines from monitor: {self.lines}") 
        print(f"Unique members (most-left AS in AS PATH): {self.members}")
        print(f"Unique reachables (most-right AS in AS PATH): {self.reachables}")
        print(f"Unique monitors in snapshot: {len(self.unique_monitors)}")
        print(f"One-length AS PATHs from monitor: {self.one_length_as_paths}")
        print(f"Prefixes from monitored AS: {len(self.unique_prefixes_from_monitored_as)}")
        print(f"unique_next_hops_from_monitored_as: {len(self.unique_next_hops_from_monitored_as)}")

    def check_consistency(self):
        for member in self.unique_members:
            if not member.isdigit():
                print("Member AS is not numeric:", member)
        for reachable in self.unique_reachables:
            if not reachable.isdigit():
                print("Reachable AS is not numeric:", reachable)

    # save as json
    def save_details(self, filename):
        save_file = Path(append_root(filename))
        save_file.parent.mkdir(parents=True, exist_ok=True)
        # Convert to dict and convert sets to lists for JSON serialization
        data = asdict(self)
        if os.path.exists(save_file):
            return
        for key in data:
            if isinstance(data[key], set):
                data[key] = list(data[key])
        with save_file.open("w") as f:
            json.dump(data, f, indent=4)
        print(f"Saved details to {save_file}")

    def load_details(self, filename):
        with open(filename, "r") as f:
            details = json.load(f)
            # Handle backward compatibility: old JSON had "members" and "reachables" keys
            if "members" in details and "unique_members" not in details:
                details["unique_members"] = set(details["members"])
                details["members"] = len(details["unique_members"])
            if "reachables" in details and "unique_reachables" not in details:
                details["unique_reachables"] = set(details["reachables"]) 
                details["reachables"] = len(details["unique_reachables"])
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
            self.mappings = details.get("mapping", {})


def _read_bgpdump(file1, monitor_as, monitor_prefix, date, time, save_details=True):

    print("Searching for AS:", monitor_as, "Prefix:", monitor_prefix)
    print("Date:", date, "Time:", time)
    stats = BGPDumpSnapshotStats(monitor_as, monitor_prefix, date, time)

    unique_members = set()
    unique_reachables = set()
    unique_monitors = set()
    mappings = dict()

    buffering = 10485760
    with open(file1, "rb", buffering=buffering) as f:

        filesize = os.path.getsize(file1)
        bar = Bar('Processing', max=filesize)

        start_time = os.times()
        
        if filesize == 0:
            print("File is empty:", file1)
            return stats

        with mmap.mmap(f.fileno(), length=0, access=mmap.ACCESS_READ) as mm:

            line_size_buffer = 0
            for line in iter(mm.readline, b""):
                line_size_buffer += len(line)

                try:
                    fields = line.decode('utf-8').strip().split("|")
                    
                    if len(fields) < 7:
                        continue
                    
                    stats.total_lines += 1
                    monitor_ip = fields[3] 
                    prefix = fields[5]
                    as_path_str = fields[6]
                    next_hop = fields[8]

                    unique_monitors.add(monitor_ip)
                    stats.monitor_to_count[monitor_ip] = stats.monitor_to_count.get(monitor_ip, 0) + 1

                    # Parse AS path
                    as_path = as_path_str.strip().split(" ") if as_path_str.strip() else []

                    # Check if AS is origin
                    if len(as_path) > 0 and as_path[-1] == monitor_as:
                        stats.count_as_origin += 1

                    # Check if AS is member
                    if len(as_path) > 0 and as_path[0] == monitor_as:
                        stats.count_as_member += 1

                    stats.unique_prefixes_from_monitored_as.add(prefix)
                    stats.unique_next_hops_from_monitored_as.add(next_hop)
                    stats.lines += 1
                        
                    if len(as_path) > 1 or (len(as_path) == 1 and monitor_as != as_path[0]):
                            unique_members.add(as_path[0] if len(as_path) > 0 and as_path[0] != monitor_as else (as_path[1] if len(as_path) > 1 else ""))
                            if len(as_path) > 0:
                                unique_reachables.add(as_path[-1])
                        
                    if len(as_path) == 1:
                            stats.one_length_as_paths += 1
                    else:
                        # Check if monitor_as is in as_path
                        if monitor_as in as_path:
                            stats.times_as_was_in_aspath += 1

                except Exception as e:
                    print(f"Error processing line: {e}")
                    continue

                if stats.total_lines % 1000 == 0 and bar is not None:
                    bar.next(line_size_buffer)
                    line_size_buffer = 0

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
    
        stats.save_details(get_stats_filename(monitor_as, monitor_prefix, date, time))

    return stats

def get_stats_filename(monitor_as, monitor_prefix, date, time, rrc, ip_version):
    return append_root(f"cache/{rrc}/{ip_version}/bview_cache.{date}.{time}.json")
    return append_root(f"cache/bview_cache.{date}.{time}_{monitor_as}_{monitor_prefix}.json")

def read_bgpdump(file1, monitor_as, rrc, ip_version, monitor_prefix=None, date=None, time=None) -> BGPDumpSnapshotStats:
    stats = BGPDumpSnapshotStats(monitor_as, monitor_prefix, date, time)
    #details_file = f"data/stats_{file1}_{monitor_as}_{monitor_prefix}.json"
    details_file = get_stats_filename(monitor_as, monitor_prefix, date, time, rrc, ip_version)
    if os.path.exists(details_file):
        warnings.warn(f"Loading details from file: {details_file}")
        stats.load_details(details_file)
    else: 
        print("Details file not found, processing bgpdump:", details_file)
        stats = _read_bgpdump(file1, monitor_as, monitor_prefix, date, time, save_details=True)
    return stats


def read_bgpdumps(files, monitor_as, monitor_prefix, ip_version, date=None, time=None) -> list[BGPDumpSnapshotStats]:
    stats_list = []
    for file in files:
        stats = read_bgpdump(file, monitor_as, monitor_prefix, ip_version, date=date, time=time)
        stats_list.append(stats)
    return stats_list


def get_all_monitors_in_bgpdump(file1):
    monitors = set()
    buffering = 10485760
    with open(file1, "rb", buffering=buffering) as f:
        with mmap.mmap(f.fileno(), length=0, access=mmap.ACCESS_READ) as mm:
            for line in iter(mm.readline, b""):
                try:
                    fields = line.decode('utf-8').strip().split("|")
                    if len(fields) >= 4:
                        monitors.add(fields[3])  # monitor_ip field
                except Exception:
                    continue
    return monitors


if __name__ == "__main__":
    # Example usage
    file = "data/rrc15/results_bgpdump.txt"
    file = "data/rrc15/bview.20260122.0000.26162.txt"
    as_prefix = ("26162", "187.16.216.253")

    if os.path.exists(file):
        stats = read_bgpdump(file, as_prefix[0], as_prefix[1], rrc="rrc15",ip_version="v4")
        stats.print_summary()
    else:
        print(f"File {file} not found")
