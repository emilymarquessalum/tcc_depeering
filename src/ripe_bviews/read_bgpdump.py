import json
import os
from pathlib import Path
import warnings
from progress.bar import Bar
import mmap
from dataclasses import dataclass, asdict, field
from collections import defaultdict

from definitions import append_roots
from collections import Counter


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
    unique_members: set[int] = field(default_factory=set)
    unique_reachables: set[int] = field(default_factory=set)
    unique_monitors: set[int] = field(default_factory=set)
    unique_next_hops_from_monitored_as: set[int] = field(default_factory=set)
    unique_prefixes_from_monitored_as: set[str] = field(default_factory=set)
    monitor_to_count: dict = field(default_factory=dict)
    times_as_was_in_aspath: int = 0
    mappings: dict[str, list[dict]] = field(default_factory=dict) # member_as-> list of dicts with keys "reachable" and "as_path"
    prefix_mappings: dict[str, list[dict]] = field(default_factory=dict) # member_as-> list of string (prefixes)
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

    def datetime_str(self):
        return f"{self.date}.{self.time}"
    def date_as_datetime(self):
        from datetime import datetime
        return datetime.strptime(self.date, "%Y%m%d")
    
    def check_consistency(self):
        for member in self.unique_members:
            if not isinstance(member, int):
                print("Member AS is not a number:", member)
        for reachable in self.unique_reachables:
            if not isinstance(reachable, int):
                print("Reachable AS is not a number:", reachable)


    def get_all_reachables_for_member(self, member_asn: str | int) -> set[str]:
        
        member_asn_str = str(member_asn)
        reachables = set()
        for mapping in self.mappings.get(member_asn_str, []):
            reachables.add(mapping["reachable"])
        return reachables
    

    def get_all_unique_reachables_for_members(self) -> dict[str, set[str]]:
 
        

        # Step 1: Count global frequencies of each reachable
        global_reachable_counts = Counter()
        
        # Pre-aggregate reachables per AS to handle potential duplicates within the same AS
        as_to_reachables: dict[str, set[str]] = {}

        for asn, mappings in self.mappings.items():
            # Using a set comprehension handles any duplicate reachables inside the same AS
            reachables_set = {mapping["reachable"] for mapping in mappings}
            as_to_reachables[asn] = reachables_set
            
            # Update the global counts
            global_reachable_counts.update(reachables_set)

        # Step 2: Filter for reachables that appeared exactly once globally
        unique_reachables_per_as = {}
        for asn, reachables_set in as_to_reachables.items():
            # Keep only the reachables whose global count is exactly 1
            unique_set = {r for r in reachables_set if global_reachable_counts[r] == 1}
            unique_reachables_per_as[asn] = unique_set

        return unique_reachables_per_as

    def get_all_members_that_allow_asn_to_be_reachable(self, reachable_asn: str | int) -> set[str]:

        allowing_members = set()
        for mapping_asn, reachables in self.mappings.items():
            reachables_asn = [r["reachable"] for r in reachables]
            if int(reachable_asn) in reachables_asn:
                allowing_members.add(mapping_asn)
        return allowing_members
    
    def get_all_non_unique_reachables_for_members(self) -> dict[str, set[str]]:
        """
        Returns a dictionary mapping each member_asn to a set of its NON-UNIQUE reachables.
        A reachable is non-unique if it is reachable via more than one AS.
        """
        from collections import Counter

        # Pass 1: Count global frequencies of each reachable
        global_reachable_counts = Counter()
        as_to_reachables: dict[str, set[str]] = {}

        for asn, mappings in self.mappings.items():
            reachables_set = {mapping["reachable"] for mapping in mappings}
            as_to_reachables[asn] = reachables_set
            global_reachable_counts.update(reachables_set)

        # Pass 2: Filter for reachables that appeared MORE THAN ONCE globally
        non_unique_reachables_per_as = {}
        for asn, reachables_set in as_to_reachables.items():
            # Keep only the reachables whose global count is > 1
            shared_set = {r for r in reachables_set if global_reachable_counts[r] > 1}
            non_unique_reachables_per_as[asn] = shared_set

        return non_unique_reachables_per_as


    def get_top_members_by_reachables(self, top_n=10) -> list[tuple[str, int]]:
        member_reachable_counts = []
        for member_asn, reachables in self.mappings.items():
            unique_reachables_for_member = set()
            for mapping in reachables:
                unique_reachables_for_member.add(mapping["reachable"])
            member_reachable_counts.append((member_asn, len(unique_reachables_for_member)))
        
        member_reachable_counts.sort(key=lambda x: x[1], reverse=True)
        return member_reachable_counts[:top_n]

    def get_prefix_mappings_for(self, type_of_mapping: str):
        prefix_mappings_member_has, prefix_mappings_member_reaches, prefix_mappings_asn_has = self.get_prefix_mappings()
        if type_of_mapping == "Owned by the Member":
            return prefix_mappings_member_has
        elif type_of_mapping == "Reached by the Member":
            return prefix_mappings_member_reaches
        elif type_of_mapping == "Owned by ASN (member or reachable)":
            return prefix_mappings_asn_has
        else:
            raise ValueError(f"Invalid type_of_mapping: {type_of_mapping}. Must be one of 'Owned by the Member', 'Reached by the Member', or 'Owned by ASN (member or reachable)'.")
    def get_prefix_mappings(self):
        prefix_mappings_member_has = defaultdict(set)
        prefix_mappings_member_reaches = defaultdict(set)
        prefix_mappings_asn_has = defaultdict(set)
        #prefix_mappings_reachable_has = defaultdict(set)

        for member, reachables in self.mappings.items():
            for mapping in reachables:
                reachable = mapping["reachable"]
                prefix = mapping.get("prefix", None)

                if prefix is None:
                    continue
                    #raise ValueError(f"Prefix is None for member {member} reaching {reachable} in mapping: {mapping}")
                if str(member) == str(reachable): 
                    prefix_mappings_member_has[member].add(prefix)
                else:
                    prefix_mappings_member_reaches[member].add(prefix)
                prefix_mappings_asn_has[reachable].add(prefix) 


        return prefix_mappings_member_has, prefix_mappings_member_reaches, prefix_mappings_asn_has


    def get_unique_prefix_mappings(self):
        prefix_mappings_member_has, _, _ = self.get_prefix_mappings()

        unique_prefixes = set()

        for member, prefixes in prefix_mappings_member_has.items():
            for prefix in prefixes:
                unique_prefixes.add(prefix )
        return unique_prefixes

    def get_shortest_as_path_length_for_member_to_reach_asn(self, member_asn: str | int, reachable_asn: str | int, remove_prepend: bool = True) -> tuple[int | None, list[str] | None]:
    
        shortest_path = None
        shortest_length = float("inf")
        member_asn_str = str(member_asn)
        for mapping in self.mappings.get(member_asn_str, []):
            if mapping["reachable"] == reachable_asn:
                as_path_length = len(mapping["as_path"])
                if remove_prepend and as_path_length > 1:
                    as_path_length = len([asn for idx, asn in enumerate(mapping["as_path"]) if idx == 0 or asn != mapping["as_path"][idx - 1]])
                if as_path_length < shortest_length:
                    shortest_length = as_path_length
                    shortest_path = mapping["as_path"]

        return shortest_length if shortest_length != float("inf") else None, shortest_path
    

    def get_shortest_as_path_length_for_reachable(self, reachable_asn: str | int, remove_prepend: bool = True) -> tuple[int | None, list[str] | None]:
    
        shortest_path = None
        shortest_length = float("inf")
        members_allowing_reachable = self.get_all_members_that_allow_asn_to_be_reachable(reachable_asn)
        for member in members_allowing_reachable:
            for mapping in self.mappings.get(member, []):
                if mapping["reachable"] == reachable_asn:
                    as_path_length = len(mapping["as_path"])
                    if remove_prepend and as_path_length > 1:
                        as_path_length = len([asn for idx, asn in enumerate(mapping["as_path"]) if idx == 0 or asn != mapping["as_path"][idx - 1]])
                    if as_path_length < shortest_length:
                        shortest_length = as_path_length
                        shortest_path = mapping["as_path"]
    
        return shortest_length if shortest_length != float("inf") else None, shortest_path  

    def get_worst_as_path_length_for_reachable(self, reachable_asn: str | int, remove_prepend: bool = True) -> tuple[int | None, list[str] | None]:
    
        longest_path = None
        longest_length = -1
        members_allowing_reachable = self.get_all_members_that_allow_asn_to_be_reachable(reachable_asn)
        for member in members_allowing_reachable:
            for mapping in self.mappings.get(member, []):
                if mapping["reachable"] == reachable_asn:
                    as_path_length = len(mapping["as_path"])
                    if remove_prepend and as_path_length > 1:
                        as_path_length = len([asn for idx, asn in enumerate(mapping["as_path"]) if idx == 0 or asn != mapping["as_path"][idx - 1]])
                    if as_path_length > longest_length:
                        longest_length = as_path_length
                        longest_path = mapping["as_path"]
    
        return longest_length if longest_length != -1 else None, longest_path

    def get_all_reachables_to_members_map(self): 
        if hasattr(self, '_reachability_map_cache'):
            return self._reachability_map_cache
        
        reach_map = defaultdict(set)
        
        for member, reachables in self.mappings.items():
            for asn in reachables:
                reach_map[asn["reachable"]].add(member)
                
        self._reachability_map_cache = reach_map
        return reach_map
    
    def get_unique_routes(self) -> tuple[set[str], list[list[str]]]:
        unique_routes = set()
        for member, reachables in self.mappings.items():
            for mapping in reachables:
                complete_path = [str(member)]
                complete_path.extend([str(asn) for asn in mapping["as_path"]])
                complete_path_str = "->".join(complete_path)
                unique_routes.add(complete_path_str)
            
        unique_routes_list = [route.split("->") for route in unique_routes]  
        return unique_routes, unique_routes_list
    
    def get_unique_prefixes(self) -> set[str]:
        unique_prefixes = set()
        for member, prefixes in self.prefix_mappings.items():
            unique_prefixes.update(prefixes)
        return unique_prefixes

    def get_top_members_by_prefix_count(self, prefix_mappings, top_n=10) -> list[tuple[str, int]]:
  

        member_prefix_counts = []
        for member_asn, prefixes in prefix_mappings.items():
            member_prefix_counts.append((member_asn, len(prefixes)))
        
        member_prefix_counts.sort(key=lambda x: x[1], reverse=True)
        return member_prefix_counts[:top_n]

    def get_top_members_by_address_count(self, prefix_mappings, top_n=10) -> list[tuple[str, int]]:
        """Get top ASes by total aggregated address count from their prefixes."""
        import ipaddress
        
        member_address_counts = []
        for member_asn, prefixes in prefix_mappings.items():
            total_addresses = 0
            for prefix in prefixes:
                try:
                    network = ipaddress.ip_network(prefix, strict=False)
                    total_addresses += network.num_addresses
                except (ValueError, TypeError):
                    continue
            member_address_counts.append((member_asn, total_addresses))
        
        member_address_counts.sort(key=lambda x: x[1], reverse=True)
        return member_address_counts[:top_n]

    def get_top_members_by_unique_prefix_count(self, prefix_mappings, top_n=10) -> list[tuple[str, int]]:
        """Get top ASes by number of globally unique prefixes (prefixes not shared with others)."""
        from collections import Counter
        
        # Count prefix occurrences across all members
        all_prefixes_iter = (prefix for prefixes in prefix_mappings.values() for prefix in prefixes)
        prefix_counts = Counter(all_prefixes_iter)
        
        # Calculate unique prefix counts per member
        member_unique_prefix_counts = []
        for member_asn, prefixes in prefix_mappings.items():
            unique_prefixes = [p for p in prefixes if prefix_counts[p] == 1]
            member_unique_prefix_counts.append((member_asn, len(unique_prefixes)))
        
        member_unique_prefix_counts.sort(key=lambda x: x[1], reverse=True)
        return member_unique_prefix_counts[:top_n]

    def get_top_members_by_unique_address_count(self, prefix_mappings, top_n=10) -> list[tuple[str, int]]:
        """Get top ASes by aggregated address count from their globally unique prefixes."""
        import ipaddress
        from collections import Counter
        
        # Count prefix occurrences across all members
        all_prefixes_iter = (prefix for prefixes in prefix_mappings.values() for prefix in prefixes)
        prefix_counts = Counter(all_prefixes_iter)
        
        # Calculate unique address counts per member
        member_unique_address_counts = []
        for member_asn, prefixes in prefix_mappings.items():
            unique_prefixes = [p for p in prefixes if prefix_counts[p] == 1]
            total_addresses = 0
            for prefix in unique_prefixes:
                try:
                    network = ipaddress.ip_network(prefix, strict=False)
                    total_addresses += network.num_addresses
                except (ValueError, TypeError):
                    continue
            member_unique_address_counts.append((member_asn, total_addresses))
        
        member_unique_address_counts.sort(key=lambda x: x[1], reverse=True)
        return member_unique_address_counts[:top_n]

    def sanity_check_on_mappings(self):
        if len(self.mappings) == 0:
            print("Warning: mappings is empty. This may indicate an issue with parsing or that no AS paths were found.")
            return
        for member_asn, reachables in self.mappings.items():
            for mapping in reachables:
                if "reachable" not in mapping:
                    print(f"Mapping for member {member_asn} is missing 'reachable' key: {mapping}")
                if "as_path" not in mapping:
                    print(f"Mapping for member {member_asn} is missing 'as_path' key: {mapping}")
                if not isinstance(mapping.get("as_path", []), list):
                    print(f"'as_path' is not a list in mapping for member {member_asn}: {mapping}")
                if "prefix" not in mapping:
                    print(f"Mapping for member {member_asn} is missing 'prefix' key: {mapping}")
                if mapping.get("prefix") is not None and not isinstance(mapping.get("prefix"), str):
                    print(f"'prefix' is not a string in mapping for member {member_asn}: {mapping}")
                    
    def sanity_check_on_prefix_mappings(self):

        if len(self.prefix_mappings) == 0:
            print("Warning: prefix_mappings is empty. This may indicate an issue with parsing or that no prefixes were found.")
            return
        for member_asn, prefixes in self.prefix_mappings.items():
            for prefix in prefixes:
                if prefix is None:
                    print(f"Prefix is None for member {member_asn}")
                if not isinstance(prefix, str):
                    print(f"Prefix is not a string for member {member_asn}: {prefix}")
                elif "/" not in prefix:
                    print(f"Prefix does not contain '/': {prefix} for member {member_asn}")

    def get_top_members_by_prefix_length(self, prefix_length, top_n=10) -> list[tuple[str, int]]:
        """Get top ASes by address count for a specific prefix length."""
        import ipaddress
        
        member_length_addresses = []
        for member_asn, prefixes in self.prefix_mappings.items():
            total_addresses = 0
            for prefix in prefixes:
                try:
                    plen = int(prefix.split("/")[1])
                    if plen == prefix_length:
                        network = ipaddress.ip_network(prefix, strict=False)
                        total_addresses += network.num_addresses
                except (ValueError, TypeError, IndexError):
                    continue
            if total_addresses > 0:
                member_length_addresses.append((member_asn, total_addresses))
        
        member_length_addresses.sort(key=lambda x: x[1], reverse=True)
        return member_length_addresses[:top_n]

    def get_top_members_by_prefix_length_count(self, prefix_length, top_n=10) -> list[tuple[str, int]]:
        """Get top ASes by count of prefixes for a specific prefix length."""
        member_length_prefix_counts = []
        for member_asn, prefixes in self.prefix_mappings.items():
            count = 0
            for prefix in prefixes:
                try:
                    plen = int(prefix.split("/")[1])
                    if plen == prefix_length:
                        count += 1
                except (ValueError, TypeError, IndexError):
                    continue
            if count > 0:
                member_length_prefix_counts.append((member_asn, count))
        
        member_length_prefix_counts.sort(key=lambda x: x[1], reverse=True)
        return member_length_prefix_counts[:top_n]
    
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
        print(filename)
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
            self.prefix_mappings = details.get("prefix_mapping", {})


def _read_bgpdump(file1, monitor_as, monitor_prefix, date, time, rrc, ip_version, save_details=True, skip_if_missing=True):

    print("Searching for AS:", monitor_as, "Prefix:", monitor_prefix)
    print("Date:", date, "Time:", time)
    stats = BGPDumpSnapshotStats(monitor_as, monitor_prefix, date, time)

    unique_members = set()
    unique_reachables = set()
    unique_monitors = set()
    mappings = dict()

    buffering = 10485760
    
    # Check if files exist before attempting to open
    if skip_if_missing and not os.path.exists(file1):
        print(f"File not found and skip_if_missing=True, returning None: {file1}")
        return None
    
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
    
        stats.save_details(get_stats_filenames(monitor_as, monitor_prefix, date, time, rrc, ip_version)[0])
 
    return stats

def get_stats_filenames(monitor_as, monitor_prefix, date, time, rrc, ip_version):
    #return append_roots(f"cache/{rrc}/{monitor_prefix}/bview_cache.{date}.{time}.json")
     return append_roots(f"cache/{rrc}/{ip_version}/bview_cache.{date}.{time}.json") 
    #return append_root(f"cache/bview_cache.{date}.{time}_{monitor_as}_{monitor_prefix}.json")


def read_bgpdump_from_file_options(files, monitor_as, rrc, ip_version, monitor_prefix=None, date=None, time=None,
                                   skip_if_missing=0) -> list[BGPDumpSnapshotStats]:
    
    for file in files:
        stats = read_bgpdump(file, monitor_as, rrc, ip_version, monitor_prefix, date, time, skip_if_missing=skip_if_missing)
        if stats is not None:
            return stats
    print("No files found for given options.")
    return None

def read_bgpdump(file1, monitor_as, rrc, ip_version, monitor_prefix=None, date=None, time=None, skip_if_missing=0) -> BGPDumpSnapshotStats:
    stats = BGPDumpSnapshotStats(monitor_as, monitor_prefix, date, time)
    #details_file = f"data/stats_{file1}_{monitor_as}_{monitor_prefix}.json"
    details_files = get_stats_filenames(monitor_as, monitor_prefix, date, time, rrc, ip_version)
    for details_file in details_files:
        if os.path.exists(details_file):
            warnings.warn(f"Loading details from file: {details_file}")
            stats.load_details(details_file)
            return stats 
    raise ValueError(f"Details file not found: {details_file}")
    #print("Details file not found, processing bgpdump:", details_file)
        
    #stats = _read_bgpdump(file1, monitor_as, monitor_prefix, date, time, save_details=True, skip_if_missing=(skip_if_missing > 0))
    

def does_bgpdump_file_exist(monitor_as, monitor_prefix, date: str, time, rrc, ip_version):
    files = get_stats_filenames(monitor_as, monitor_prefix, date.replace("-", ""), time, rrc, ip_version)

    for file in files:
        if os.path.exists(file):
            return True
    return False

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
