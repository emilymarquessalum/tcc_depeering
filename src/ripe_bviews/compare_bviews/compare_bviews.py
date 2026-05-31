
import sys
from pathlib import Path



sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
import warnings

warnings.filterwarnings('ignore', category=UserWarning, message='.*Skipping download.*')
from src.ripe_bviews.read_bgpdump import BGPDumpSnapshotStats
from src.ripe_bviews.download_and_parse.load_configs import load_configs, print_config, simple_print_debug
from src.ripe_bviews.timeline.bview_timeline import get_ases_that_did_not_come_back

from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data_timeline_from_configs
from src.ripe_bviews.oscillations.bview_oscillation_logic import OscillationMetrics, calculate_oscillation_metrics

from src.ripe_bviews.timeline.bview_vars import get_subfolder
from src.utils.graphs import plot_list_as_line_plot, plot_stacked_bar_plot
from src.ripe_bviews.compare_bviews.compare_rankings import compare_top_asn_rankings
from dataclasses import dataclass
from typing import List, Dict, Set, Optional

# Static features (we are not very interested in those): ASes in common (memberXreachable)
# Timeline features: Which ASes that left the IXP1 also left IXP2 at that timeframe or in a different one


@dataclass
class PeeringEvent:
    """Represents a peering or de-peering event for an ASN at a specific IXP."""
    event_type: str  # "peer" or "depeer"
    ixp_name: str
    index: int
    timestamp: str  # date/time label
    is_member: bool  # True if member (in unique_members), False if only reachable
    

class CompareBViewEvents:
    """
    Tracks and describes peering/de-peering events for individual ASNs across multiple IXPs.
    Provides a timeline of events for a given ASN showing when it peered/de-peered.
    """
    
    def __init__(self, ixp1_name: str, ixp2_name: str):
        self.ixp1_name = ixp1_name
        self.ixp2_name = ixp2_name
        # Dict mapping ASN -> List of PeeringEvents sorted by index
        self.asn_events: Dict[int, List[PeeringEvent]] = {}
        # Store initial snapshot data for context
        self.initial_members_ixp1: Set[int] = set()
        self.initial_members_ixp2: Set[int] = set()
        # Track how many IXPs each ASN was initially peered to (0, 1, or 2)
        self.initial_peered_count: Dict[int, int] = {}
        
    def load_data(self, all_stats_ixp1: List, all_stats_ixp2: List, 
                  labels_ixp1: List[str], labels_ixp2: List[str]):
        """
        Load timeline data from both IXPs and build event history.
        
        Args:
            all_stats_ixp1: List of BGPDumpSnapshotStats for IXP1
            all_stats_ixp2: List of BGPDumpSnapshotStats for IXP2
            labels_ixp1: Time labels for IXP1 snapshots
            labels_ixp2: Time labels for IXP2 snapshots
        """
        # Store initial state from first snapshots
        if all_stats_ixp1:
            self.initial_members_ixp1 = set(all_stats_ixp1[0].unique_members)
        if all_stats_ixp2:
            self.initial_members_ixp2 = set(all_stats_ixp2[0].unique_members)
        
        # Calculate initial_peered_count for each ASN
        all_asns = self.initial_members_ixp1.union(self.initial_members_ixp2)
        for asn in all_asns:
            count = 0
            if asn in self.initial_members_ixp1:
                count += 1
            if asn in self.initial_members_ixp2:
                count += 1
            self.initial_peered_count[asn] = count
        
        # Process IXP1 events
        self._process_ixp_timeline(all_stats_ixp1, labels_ixp1, self.ixp1_name)
        
        # Process IXP2 events (labels might differ, so use corresponding indices)
        min_length = min(len(all_stats_ixp2), len(labels_ixp2))
        self._process_ixp_timeline(all_stats_ixp2[:min_length], labels_ixp2[:min_length], self.ixp2_name)
    
    def _process_ixp_timeline(self, all_stats: List, labels: List[str], ixp_name: str):
        """
        Process a single IXP's timeline and track peering/de-peering events.
        ASNs present in snapshot 0 are not counted as peering events.
        """
        if not all_stats:
            return
        
        # Initialize with first snapshot to avoid counting baseline ASNs as peering
        current_members: Set[int] = set(all_stats[0].unique_members)
        current_reachables: Set[int] = set(all_stats[0].unique_reachables)
        
        # Start from index 1 to skip the baseline snapshot
        for index, (stats, label) in enumerate(zip(all_stats[1:], labels[1:]), start=1):
            new_members = set(stats.unique_members)
            new_reachables = set(stats.unique_reachables)
            
            # Find ASNs that peered (new members/reachables)
            peered_members = new_members - current_members
            peered_reachables = (new_reachables - current_reachables) - new_members
            
            for asn in peered_members:
                self._add_event(asn, PeeringEvent(
                    event_type="peer",
                    ixp_name=ixp_name,
                    index=index,
                    timestamp=label,
                    is_member=True
                ))
            
            for asn in peered_reachables:
                self._add_event(asn, PeeringEvent(
                    event_type="peer",
                    ixp_name=ixp_name,
                    index=index,
                    timestamp=label,
                    is_member=False
                ))
            
            # Find ASNs that de-peered (removed from members/reachables)
            depeered_members = current_members - new_members
            depeered_reachables = current_reachables - new_reachables
            
            for asn in depeered_members:
                self._add_event(asn, PeeringEvent(
                    event_type="depeer",
                    ixp_name=ixp_name,
                    index=index,
                    timestamp=label,
                    is_member=True
                ))
            
            for asn in depeered_reachables:
                self._add_event(asn, PeeringEvent(
                    event_type="depeer",
                    ixp_name=ixp_name,
                    index=index,
                    timestamp=label,
                    is_member=False
                ))
            
            current_members = new_members
            current_reachables = new_reachables
    
    def _add_event(self, asn: int, event: PeeringEvent):
        """Add an event to an ASN's event history."""
        if asn not in self.asn_events:
            self.asn_events[asn] = []
        self.asn_events[asn].append(event)
    
    def get_asn_timeline_description(self, asn: int) -> str:
        """
        Get a human-readable description of all peering/de-peering events for an ASN.
        Includes the initial state before the timeline of events.
        
        Args:
            asn: The AS Number to describe
            
        Returns:
            A string describing the ASN's peering history in chronological order
        """
        if asn not in self.asn_events:
            return f"ASN {asn}: No events found (never peered or data not loaded)"
        
        events = self.asn_events[asn]
        # Sort by index to ensure chronological order
        events = sorted(events, key=lambda e: e.index)
        
        lines = [f"ASN {asn} Timeline:"]
        lines.append("=" * 60)
        
        # Print initial state
        ixp1_initial = asn in self.initial_members_ixp1
        ixp2_initial = asn in self.initial_members_ixp2
        
        if ixp1_initial and ixp2_initial:
            initial_state = f"Started period peered to both {self.ixp1_name} and {self.ixp2_name}"
        elif ixp1_initial:
            initial_state = f"Started period peered to {self.ixp1_name}, but not to {self.ixp2_name}"
        elif ixp2_initial:
            initial_state = f"Started period peered to {self.ixp2_name}, but not to {self.ixp1_name}"
        else:
            initial_state = f"Started period not peered to either {self.ixp1_name} or {self.ixp2_name}"
        
        lines.append(f"Initial state: {initial_state}")
        lines.append("-" * 60)
        
        for event in events:
            event_desc = "peered" if event.event_type == "peer" else "de-peered"
            peering_type = "as member" if event.is_member else "as reachable"
            lines.append(
                f"  [{event.index}] {event.timestamp}: {event_desc} in {event.ixp_name} ({peering_type})"
            )
        
        return "\n".join(lines)
    
    def get_asn_metric_counts(self, asn: int) -> Dict[str, int]:
        """
        Count different types of peering and de-peering events for an ASN.
        
        Args:
            asn: The AS Number to analyze
            
        Returns:
            Dictionary with counts of different event types
        """
        counts = {
            "peered-both-same-time": 0,
            "peered-both-different-time": 0,
            "peered-only-ixp1": 0,
            "peered-only-ixp2": 0,
            "depeered-both-same-time": 0,
            "depeered-both-different-time": 0,
            "depeered-only-ixp1": 0,
            "depeered-only-ixp2": 0,
            "initial-peered-count": self.initial_peered_count.get(asn, 0),
        }
        
        events = self.get_asn_events(asn)
        
        # Get peering and de-peering events by type and IXP
        ixp1_peer_indices = set()
        ixp2_peer_indices = set()
        ixp1_depeer_indices = set()
        ixp2_depeer_indices = set()
        
        for event in events:
            if event.event_type == "peer":
                if event.ixp_name == self.ixp1_name:
                    ixp1_peer_indices.add(event.index)
                else:
                    ixp2_peer_indices.add(event.index)
            elif event.event_type == "depeer":
                if event.ixp_name == self.ixp1_name:
                    ixp1_depeer_indices.add(event.index)
                else:
                    ixp2_depeer_indices.add(event.index)
        
        # Count peering events
        peer_same_time = len(ixp1_peer_indices.intersection(ixp2_peer_indices))
        counts["peered-both-same-time"] = peer_same_time
        
        # For "different-time", only count indices where BOTH have peer events at different indices
        # Pair up the unpaired indices to get the count
        peer_only_ixp1 = ixp1_peer_indices - ixp2_peer_indices
        peer_only_ixp2 = ixp2_peer_indices - ixp1_peer_indices
        peer_different_time = min(len(peer_only_ixp1), len(peer_only_ixp2))
        counts["peered-both-different-time"] = peer_different_time
        
        # Subtract the paired "different-time" events from the "only" counts
        counts["peered-only-ixp1"] = len(peer_only_ixp1) - peer_different_time
        counts["peered-only-ixp2"] = len(peer_only_ixp2) - peer_different_time
        
        # Count de-peering events
        depeer_same_time = len(ixp1_depeer_indices.intersection(ixp2_depeer_indices))
        counts["depeered-both-same-time"] = depeer_same_time
        
        # For "different-time", only count indices where BOTH have depeer events at different indices
        # Pair up the unpaired indices to get the count
        depeer_only_ixp1 = ixp1_depeer_indices - ixp2_depeer_indices
        depeer_only_ixp2 = ixp2_depeer_indices - ixp1_depeer_indices
        depeer_different_time = min(len(depeer_only_ixp1), len(depeer_only_ixp2))
        counts["depeered-both-different-time"] = depeer_different_time
        
        # Subtract the paired "different-time" events from the "only" counts
        counts["depeered-only-ixp1"] = len(depeer_only_ixp1) - depeer_different_time
        counts["depeered-only-ixp2"] = len(depeer_only_ixp2) - depeer_different_time
        
        return counts
    
    def get_asn_summary_description(self, asn: int) -> str:
        """
        Get a concise narrative description of an ASN's peering history.
        
        Args:
            asn: The AS Number to describe
            
        Returns:
            A narrative string describing the ASN's peering events
        """
        if asn not in self.asn_events:
            return f"ASN {asn} has no recorded peering events."
        
        events = self.asn_events[asn]
        events = sorted(events, key=lambda e: e.index)
        
        description = f"ASN {asn}: "
        
        if not events:
            return description + "No events recorded."
        
        event_descriptions = []
        for event in events:
            action = "peered" if event.event_type == "peer" else "de-peered"
            peering_type = "as member" if event.is_member else "as reachable"
            event_descriptions.append(
                f"{action} in {event.ixp_name} at index {event.index} ({peering_type})"
            )
        
        description += ", then ".join(event_descriptions) + "."
        return description
    
    def get_asn_events(self, asn: int) -> List[PeeringEvent]:
        """
        Get all events for a specific ASN, sorted chronologically.
        
        Args:
            asn: The AS Number
            
        Returns:
            List of PeeringEvent objects sorted by index
        """
        if asn not in self.asn_events:
            return []
        return sorted(self.asn_events[asn], key=lambda e: e.index)
    
    def get_ixp_specific_events(self, asn: int, ixp_name: str) -> List[PeeringEvent]:
        """
        Get all events for an ASN at a specific IXP.
        
        Args:
            asn: The AS Number
            ixp_name: The IXP name to filter by
            
        Returns:
            List of PeeringEvent objects for that IXP, sorted by index
        """
        events = self.get_asn_events(asn)
        filtered = [e for e in events if e.ixp_name == ixp_name]
        return filtered
    
    def get_ixp1_only_events(self, asn: int) -> List[PeeringEvent]:
        """Get all events for an ASN in IXP1 only."""
        return self.get_ixp_specific_events(asn, self.ixp1_name)
    
    def get_ixp2_only_events(self, asn: int) -> List[PeeringEvent]:
        """Get all events for an ASN in IXP2 only."""
        return self.get_ixp_specific_events(asn, self.ixp2_name)
    
    def get_simultaneous_events(self, asn: int) -> List[tuple]:
        """
        Get peering/de-peering events that happened simultaneously in both IXPs.
        
        Args:
            asn: The AS Number
            
        Returns:
            List of tuples (event1, event2) where both happened at same index
        """
        ixp1_events = self.get_ixp1_only_events(asn)
        ixp2_events = self.get_ixp2_only_events(asn)
        
        simultaneous = []
        for e1 in ixp1_events:
            for e2 in ixp2_events:
                if e1.index == e2.index and e1.event_type == e2.event_type:
                    simultaneous.append((e1, e2))
        
        return sorted(simultaneous, key=lambda x: x[0].index)
    
    def _print_asn_category(self, category_name: str, asn_set: Set[int], max_inline: int = 20):
        """Helper method to print ASN categories with conditional listing."""
        print(f"{category_name}: {len(asn_set)}")
        if asn_set and len(asn_set) <= max_inline:
            print(f"  {sorted(asn_set)}\n")
        else:
            if asn_set:
                print("  (listing omitted - too many entries)\n")
            else:
                print()
    
    def _categorize_asns_by_events(self) -> tuple:
        """Categorize all ASNs by their event patterns."""
        categories = [set() for _ in range(8)]
        metric_keys = [
            "peered-both-same-time", "peered-both-different-time",
            "peered-only-ixp1", "peered-only-ixp2",
            "depeered-both-same-time", "depeered-both-different-time",
            "depeered-only-ixp1", "depeered-only-ixp2"
        ]
        
        for asn in self.asn_events.keys():
            metrics = self.get_asn_metric_counts(asn)
            for i, key in enumerate(metric_keys):
                if metrics[key] > 0:
                    categories[i].add(asn)
        
        return tuple(categories)
    
    def print_comparison_results(self):
        """Print comparison results using event-based analysis."""
        categories = self._categorize_asns_by_events()
        peered_both_same, peered_both_diff, peered_only_1, peered_only_2, \
            depeered_both_same, depeered_both_diff, depeered_only_1, depeered_only_2 = categories
        
        print(f"\n{'='*70}")
        print(f"Event-Based Comparison: {self.ixp1_name} vs {self.ixp2_name}")
        print(f"{'='*70}\n")
        
        print("PEERING EVENTS")
        print("-" * 70)
        self._print_asn_category("ASNs peered in both at same time", peered_both_same)
        self._print_asn_category("ASNs peered in both at different times", peered_both_diff)
        self._print_asn_category(f"ASNs peered only in {self.ixp1_name}", peered_only_1)
        self._print_asn_category(f"ASNs peered only in {self.ixp2_name}", peered_only_2)
        
        print("\nDE-PEERING EVENTS")
        print("-" * 70)
        self._print_asn_category("ASNs de-peered from both at same time", depeered_both_same)
        self._print_asn_category("ASNs de-peered from both at different times", depeered_both_diff)
        self._print_asn_category(f"ASNs de-peered only from {self.ixp1_name}", depeered_only_1)
        self._print_asn_category(f"ASNs de-peered only from {self.ixp2_name}", depeered_only_2)
        
        print(f"{'='*70}\n")


class RIBCompare:

    def __init__(self):
        
        self.ases_that_left_at_the_same_time = set()
        self.ases_that_left = set()
        self.ases_that_left_only_ixp1 = set()
        self.ases_that_left_only_ixp2 = set()
        self.ases_that_left_only_ixp1_but_ixp2_has_it_too = set()
        self.ases_that_left_only_ixp2_but_ixp1_has_it_too = set()

        self.ases_that_entered_at_the_same_time = set()
        self.ases_that_entered = set() # ASes that entered both IXPs but not at the same time
        self.ases_that_entered_only_ixp1 = set()
        self.ases_that_entered_only_ixp2 = set()

        self.reachables_that_left_at_the_same_time = set()
        self.reachables_that_left = set()
        self.reachables_that_left_only_ixp1 = set()
        self.reachables_that_left_only_ixp2 = set()

    

    def load_data(self, oscillation_metrics_1: OscillationMetrics, oscillation_metrics_2: OscillationMetrics,
                  reachables_oscillation_metrics_1: OscillationMetrics, reachables_oscillation_metrics_2: OscillationMetrics):
        
        total_range_added = min(len(oscillation_metrics_1.all_added_asns_over_time), len(oscillation_metrics_2.all_added_asns_over_time))
        ases_that_entered_ixp1 = set()
        ases_that_entered_ixp2 = set()

        total_range_removed = min(len(oscillation_metrics_1.all_removed_asns_over_time), len(oscillation_metrics_2.all_removed_asns_over_time))
        ases_that_left_ixp1 = set()
        ases_that_left_ixp2 = set()

        for i in range(total_range_added):
            ases_added_1 = oscillation_metrics_1.all_added_asns_over_time[i]
            ases_added_2 = oscillation_metrics_2.all_added_asns_over_time[i] 
            ases_entered_at_the_same_time = ases_added_1.intersection(ases_added_2)
            self.ases_that_entered_at_the_same_time.update(ases_entered_at_the_same_time)
            ases_that_entered_ixp1.update(ases_added_1) 
            ases_that_entered_ixp2.update(ases_added_2)
            self.ases_that_entered_only_ixp1.update(ases_added_1 - ases_added_2)
            self.ases_that_entered_only_ixp2.update(ases_added_2 - ases_added_1)
        
        self.ases_that_entered = ases_that_entered_ixp1.intersection(ases_that_entered_ixp2)

        for i in range(total_range_removed):
            ases_removed_1 = oscillation_metrics_1.all_removed_asns_over_time[i]
            ases_removed_2 = oscillation_metrics_2.all_removed_asns_over_time[i] 
            ases_left_at_the_same_time = ases_removed_1.intersection(ases_removed_2)
            self.ases_that_left_at_the_same_time.update(ases_left_at_the_same_time)
            ases_that_left_ixp1.update(ases_removed_1) 
            ases_that_left_ixp2.update(ases_removed_2)

            removed_from_ixp1_only = ases_removed_1 - ases_removed_2
            removed_from_ixp2_only = ases_removed_2 - ases_removed_1
            self.ases_that_left_only_ixp1.update(removed_from_ixp1_only)
            self.ases_that_left_only_ixp2.update(removed_from_ixp2_only)
            
            unique_members_from_ixp1 = set(oscillation_metrics_1.all_stats[i].unique_members)
            unique_members_from_ixp2 = set(oscillation_metrics_2.all_stats[i].unique_members)

            self.ases_that_left_only_ixp1_but_ixp2_has_it_too.update(
                removed_from_ixp1_only.intersection(unique_members_from_ixp2)
            )
            self.ases_that_left_only_ixp2_but_ixp1_has_it_too.update(
                removed_from_ixp2_only.intersection(unique_members_from_ixp1)
            )

        self.ases_that_left = ases_that_left_ixp1.intersection(ases_that_left_ixp2)

        reachables_that_left_ixp1 = set()
        reachables_that_left_ixp2 = set()
        for i in range(total_range_removed):
            reachables_removed_1 = reachables_oscillation_metrics_1.all_removed_asns_over_time[i]
            reachables_removed_2 = reachables_oscillation_metrics_2.all_removed_asns_over_time[i] 
            reachables_left_at_the_same_time = reachables_removed_1.intersection(reachables_removed_2)
            self.reachables_that_left_at_the_same_time.update(reachables_left_at_the_same_time)
            reachables_that_left_ixp1.update(reachables_removed_1) 
            reachables_that_left_ixp2.update(reachables_removed_2)
            self.reachables_that_left_only_ixp1.update(reachables_removed_1 - reachables_removed_2)
            self.reachables_that_left_only_ixp2.update(reachables_removed_2 - reachables_removed_1)
        self.reachables_that_left = reachables_that_left_ixp1.intersection(reachables_that_left_ixp2)

    def print_comparison_results(self):
        print(f"Considering ASes that left both IXPs")
        
        print("---")
        
        print(f"Members that entered both at the same time: {len(self.ases_that_entered_at_the_same_time)} ({self.ases_that_entered_at_the_same_time})")
        print(f"Members that entered both, but in different times: {len(self.ases_that_entered)} ({self.ases_that_entered})")
        print(f"Members that entered only IXP1: {len(self.ases_that_entered_only_ixp1)}")
        print(f"Members that entered only IXP2: {len(self.ases_that_entered_only_ixp2)}")

        print("---")
        
        print(f"Members that left both at the same time: {len(self.ases_that_left_at_the_same_time)} ({self.ases_that_left_at_the_same_time})")
        print(f"Members that left both, but at different times: {len(self.ases_that_left)} ({self.ases_that_left})")
        print(f"Members that left only IXP1: {len(self.ases_that_left_only_ixp1)}")
        print(f"Members that left only IXP2: {len(self.ases_that_left_only_ixp2)}")

        print(f"Members that left only IXP1, but IXP2 still has it: {len(self.ases_that_left_only_ixp1_but_ixp2_has_it_too)}")
        print(f"Members that left only IXP2, but IXP1 still has it: {len(self.ases_that_left_only_ixp2_but_ixp1_has_it_too)}")

        print("---")

        print(f"Reachables that left both at the same time: {len(self.reachables_that_left_at_the_same_time)}")
        print(f"Reachables that left both, but at different times: {len(self.reachables_that_left)}")
        print(f"Reachables that left only IXP1: {len(self.reachables_that_left_only_ixp1)}")
        print(f"Reachables that left only IXP2: {len(self.reachables_that_left_only_ixp2)}")


def get_ases_in_common(stats_ixp1: BGPDumpSnapshotStats, stats_ixp2: BGPDumpSnapshotStats):

    members_in_common = set(stats_ixp1.unique_members).intersection(set(stats_ixp2.unique_members))
    reachables_in_common = set(stats_ixp1.unique_reachables).intersection(set(stats_ixp2.unique_reachables))
    

    return  members_in_common, reachables_in_common

def get_stats_from_compared_ixps():
    configs_ix1 = load_configs("ixbr.json")
    configs_ix1 = load_configs("MIX-IT.json")
         
    configs_ix2 = load_configs("AMS-IX.json")

    subfolder = get_subfolder(configs_ix1, ip_version="v4") + "_vs_" + configs_ix2.get("name", "Unknown") 

    ignored_dates = ["20251205.0000"]
    all_stats_ix1, labels_ix1 = load_bview_data_timeline_from_configs(configs_ix1, ignored_dates=ignored_dates)
    all_stats_ix2, labels_ix2 = load_bview_data_timeline_from_configs(configs_ix2, ignored_dates=ignored_dates)

    simple_print_debug(configs_ix1)
    simple_print_debug(configs_ix2)

    return all_stats_ix1, all_stats_ix2, configs_ix1, configs_ix2, subfolder, labels_ix1


def plot_asn_presence_over_time(asn, all_stats_ix1, all_stats_ix2, labels_ix1, configs_ix1, configs_ix2, subfolder):
    """
    Plot the presence/absence of a specific ASN across both IXPs over time.
    Creates a stacked bar plot showing presence (1) or absence (0) for each IXP.
    
    Args:
        asn: The AS number to track
        all_stats_ix1: List of BGPDumpSnapshotStats for IXP1
        all_stats_ix2: List of BGPDumpSnapshotStats for IXP2
        labels_ix1: Time labels for each snapshot
        configs_ix1: Configuration for IXP1
        configs_ix2: Configuration for IXP2
        subfolder: Subfolder to save the plot in
    """
    # Get presence data for each IXP over time
    ixp1_presence = []
    ixp2_presence = []
    
    min_length = min(len(all_stats_ix1), len(all_stats_ix2))
    
    for i in range(min_length):
        # Check if ASN is present in IXP1
        ixp1_has_asn = 1 if asn in all_stats_ix1[i].unique_members else 0
        ixp1_presence.append(ixp1_has_asn)
        
        # Check if ASN is present in IXP2
        ixp2_has_asn = 1 if asn in all_stats_ix2[i].unique_members else 0
        ixp2_presence.append(ixp2_has_asn)
    
    # Trim labels to match data length
    labels = labels_ix1[:min_length]
    
    # Create stacked bar plot
    ixp1_name = configs_ix1.get("name", "IXP1")
    ixp2_name = configs_ix2.get("name", "IXP2")
    
    plot_stacked_bar_plot(
        data_lists=[ixp1_presence, ixp2_presence],
        labels=[ixp1_name, ixp2_name],
        x_labels=labels,
        title=f"ASN {asn} Presence Over Time",
        xlabel="Date",
        ylabel="Present (1) or Absent (0)",
        colors=['#2ecc71', '#e74c3c'],  # Green for presence, Red for absence (but stacked, so will show different)
        subfolder=subfolder,
        max_labels=20
    )


def plot_ases_in_common_over_time(labels_ix1, all_stats_ix1, all_stats_ix2, subfolder):
    members_in_common_over_time = []
    reachables_in_common_over_time = []
    for stat_ix1, stat_ix2 in zip(all_stats_ix1, all_stats_ix2):
        members_in_common_over_time.append(len(set(stat_ix1.unique_members).intersection(set(stat_ix2.unique_members))))
        reachables_in_common_over_time.append(len(set(stat_ix1.unique_reachables).intersection(set(stat_ix2.unique_reachables))))
    plot_list_as_line_plot(members_in_common_over_time, y=labels_ix1, title="Members in Common Over Time", subfolder=subfolder)
    plot_list_as_line_plot(reachables_in_common_over_time, y=labels_ix1, title="Reachables in Common Over Time", subfolder=subfolder)


if __name__ == "__main__":

    

    all_stats_ix1, all_stats_ix2, configs_ix1, configs_ix2, subfolder, labels_ix1 = get_stats_from_compared_ixps()
    
    plot_asn_presence_over_time(208808, all_stats_ix1, all_stats_ix2, labels_ix1, configs_ix1, configs_ix2, subfolder)
    
    
    comparer = CompareBViewEvents("MIX-IT", "AMS-IX")
    comparer.load_data(all_stats_ix1, all_stats_ix2, labels_ix1, labels_ix1)

    # Get detailed timeline
    print(comparer.get_asn_timeline_description(208808))

    # Get concise narrative
    print(comparer.get_asn_summary_description(208808))
    # Output: "ASN 208808: peered in MIX-IT at index 0 (as member), peered in AMS-IX at index 5 (as member), then de-peered in MIX-IT at index 12 (as member)..."

    # Get just the events
    events = comparer.get_asn_events(208808)
    simultaneous = comparer.get_simultaneous_events(208808)

    print(comparer.get_asn_metric_counts(208808))

    comparer.print_comparison_results()
    sys.exit(0)
    members_in_common, reachables_in_common = get_ases_in_common(all_stats_ix1[0], all_stats_ix2[0])
    print(f"ASes in common (members)) at the start: {len(members_in_common)} (% of IXP1: {(len(members_in_common)/len(all_stats_ix1[0].unique_members))*100:.2f}%, of IXP2: {(len(members_in_common)/len(all_stats_ix2[0].unique_members))*100:.2f}%)")
    print(f"ASes in common (reachables) at the start: {len(reachables_in_common)}")
    
    
    metrics_ix1 = calculate_oscillation_metrics(all_stats_ix1)
    metrics_ix2 = calculate_oscillation_metrics(all_stats_ix2)

    metrics_ix1.load_oscillating_lists()
    metrics_ix2.load_oscillating_lists()

    reachable_metrics_ix1 = calculate_oscillation_metrics(all_stats_ix1, use_reachables=True)
    reachable_metrics_ix2 = calculate_oscillation_metrics(all_stats_ix2, use_reachables=True)
    reachable_metrics_ix1.load_oscillating_lists(use_reachables=True)
    reachable_metrics_ix2.load_oscillating_lists(use_reachables=True)

    comparer = RIBCompare()
    comparer.load_data(metrics_ix1, metrics_ix2, reachable_metrics_ix1, reachable_metrics_ix2)
    comparer.print_comparison_results() 



    compare_top_asn_rankings(all_stats_ix1, all_stats_ix2, top_n=10)

    plot_ases_in_common_over_time(labels_ix1, all_stats_ix1, all_stats_ix2, subfolder)
    
    retroactive = max(int(0.1 * len(all_stats_ix1)), 1)
    
    
    print(f"ASes that were present in the first {retroactive} snapshots (from total of {len(all_stats_ix1)}, ({(retroactive/len(all_stats_ix1))*100:.2f}%).")
    ases_removed_that_did_not_come_back_ixp1 = get_ases_that_did_not_come_back([stat.unique_members for stat in all_stats_ix1],
                                                                          retrospective=retroactive)
    
    print_config(configs_ix1, ip_version="v4")
    
    print(f"ASes that existed in the first {retroactive} snapshots, but were removed and did not come back: {len(ases_removed_that_did_not_come_back_ixp1)}")


    ases_removed_that_did_not_come_back_ixp1_that_exist_in_ixp2 = ases_removed_that_did_not_come_back_ixp1.intersection(set(all_stats_ix2[0].unique_members))
    print(f"ASes that existed in the first {retroactive} snapshots, but were removed and did not come back in IXP1, but still exist in IXP2: {len(ases_removed_that_did_not_come_back_ixp1_that_exist_in_ixp2)}")

    ases_removed_that_did_not_come_back_ixp2 = get_ases_that_did_not_come_back([stat.unique_members for stat in all_stats_ix2],
                                                                          retrospective=retroactive)
    
    print("---")
    print_config(configs_ix2, ip_version="v4")
        
    print(f"ASes that existed in the first {retroactive} snapshots, but were removed and did not come back: {len(ases_removed_that_did_not_come_back_ixp2)}")

    ases_removed_that_did_not_come_back_ixp2_that_exist_in_ixp1 = ases_removed_that_did_not_come_back_ixp2.intersection(set(all_stats_ix1[0].unique_members))
    print(f"ASes that existed in the first {retroactive} snapshots, but were removed and did not come back in IXP2, but still exist in IXP1: {len(ases_removed_that_did_not_come_back_ixp2_that_exist_in_ixp1)}")

    print("---")
    ases_removed_from_both = ases_removed_that_did_not_come_back_ixp1.intersection(ases_removed_that_did_not_come_back_ixp2)
    print(f"ASes that existed in the first {retroactive} snapshots, but were removed and did not come back in both IXPs: {len(ases_removed_from_both)}")

    