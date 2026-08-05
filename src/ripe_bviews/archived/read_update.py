

from dataclasses import dataclass, field

@dataclass
class UpdateFileStats:
    lines_count: int = 0  # total lines of the file
    depeering: int = 0  # lines that are "-"
    depeering_repaired: int = 0  # depeerings that have a following "+" line with same prefix and next hop
    depeering_repair_better_path: int = 0  # depeerings that were repaired with a better AS path (unused for now)
    unique_depeered_prefixes: set = field(default_factory=set)  # set of unique prefixes that were depeered
    unique_depeered_next_hops: set = field(default_factory=set)  # set of unique next hops that were depeered
    as_path_count: dict = field(default_factory=dict)  # map of AS-path-length->quantity of all lines
    depeer_replacement_count: dict = field(default_factory=dict)  # map of AS-path-length->quantity of repaired depeerings
    asn_originators_of_depeered_repared_prefixes: set = field(default_factory=set)  

    def print_summary(self):
        print(f"Total lines: {self.lines_count}")
        print(f"Total depeerings: {self.depeering} ({(self.depeering/self.lines_count)*100:.2f}% of lines)")
        print(f"Total repaired depeerings: {self.depeering_repaired} ({(self.depeering_repaired/self.depeering)*100:.2f}% of depeerings)")
        print(f"Unique depeered prefixes: {len(self.unique_depeered_prefixes)} ({(len(self.unique_depeered_prefixes)/self.depeering)*100:.2f}% of depeerings)")
        print(f"Unique depeered next hops: {len(self.unique_depeered_next_hops)}") 
        print(f"Total repaired depeerings with better path: {self.depeering_repair_better_path}")

    def save(self, filename):
        with open(filename, "w") as f:
            f.write(f"Total lines: {self.lines_count}\n")
            f.write(f"Total depeerings: {self.depeering} ({(self.depeering/self.lines_count)*100:.2f}% of lines)\n")
            f.write(f"Total repaired depeerings: {self.depeering_repaired} ({(self.depeering_repaired/self.depeering)*100:.2f}% of depeerings)\n")
            f.write(f"Unique depeered prefixes: {len(self.unique_depeered_prefixes)} ({(len(self.unique_depeered_prefixes)/self.depeering)*100:.2f}% of depeerings)\n")
            f.write(f"Unique depeered next hops: {len(self.unique_depeered_next_hops)}\n")
            f.write(f"Total repaired depeerings with better path: {self.depeering_repair_better_path}\n")
    
    def load(self, filename):
        with open(filename, "r") as f:
            lines = f.readlines()
            self.lines_count = int(lines[0].split(": ")[1])
            self.depeering = int(lines[1].split(": ")[1].split(" ")[0])
            self.depeering_repaired = int(lines[2].split(": ")[1].split(" ")[0])
            self.unique_depeered_prefixes = set(range(int(lines[3].split(": ")[1].split(" ")[0])))
            self.unique_depeered_next_hops = set(range(int(lines[4].split(": ")[1])))
            self.depeering_repair_better_path = int(lines[5].split(": ")[1])

def get_update_line(line):
    fields = line.strip().split("|") 
    return fields

def read_update(date, asn, focus_prefix=None, focus_next_hop_asn=None, focus_asn_in_as_path=None):
    stats = UpdateFileStats()

    with open(f"data/update_{date}.{asn}.txt", "r") as file:
        lines = file.readlines()

        lines_count = len(lines)
        stats.lines_count = lines_count

        for i in range(len(lines)):
            line = lines[i]
            line_fields = get_update_line(line)

            if len(line_fields[2].split()) > 0:
                stats.as_path_count[len(line_fields[2].split())] = stats.as_path_count.get(len(line_fields[2].split()), 0) + 1
            if line.startswith("+"):
                if focus_asn_in_as_path:
                        as_path = line_fields[2].split(' ')
                        if focus_asn_in_as_path in as_path:
                            print(f"Depeering line: {line.strip()}")
                            print(f"Repair line: {next_line.strip()}")

            if line.startswith("-"):
                
                stats.unique_depeered_prefixes.add(line_fields[1])
                stats.unique_depeered_next_hops.add(line_fields[8].split()[0])
                stats.depeering += 1
                next_line = lines[i + 1] if i + 1 < len(lines) else ""
                if next_line.startswith("+"):
                    prefix = line_fields[1]
                    next_line_fields = get_update_line(next_line)   
                    next_prefix = next_line_fields[1]

                    
                    stats.asn_originators_of_depeered_repared_prefixes.add(next_line_fields[2].split()[-1])
                            
                    if focus_prefix and focus_prefix == line_fields[1]:
                        if focus_next_hop_asn and focus_next_hop_asn == next_line_fields[8].split()[1]:
                            print(f"Depeering line: {line.strip()}")
                            print(f"Repair line: {next_line.strip()}")

                    next_peer_ip = next_line_fields[8].split()[0]
                    peer_ip_depeering = line_fields[8].split()[0]
                    if prefix == next_prefix and peer_ip_depeering == next_peer_ip: 
                        stats.depeering_repaired += 1 
                        stats.depeer_replacement_count[
                            len(next_line_fields[2].split(' '))
                        ] = stats.depeer_replacement_count.get(
                            len(next_line_fields[2].split(' ')), 0
                        ) + 1
    return stats