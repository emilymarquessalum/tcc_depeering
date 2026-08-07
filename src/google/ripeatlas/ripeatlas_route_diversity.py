"""
Module for calculating route diversity metrics from RIPEAtlas measurements.

Route diversity analysis includes:
- Number of unique paths observed
- ASN diversity (unique AS paths)
- Path length variations
- Hop-level changes over time
"""

from collections import defaultdict, Counter
from typing import List, Dict, Tuple, Set
import datetime
import ipaddress


def extract_as_path_from_measurement(measurement: Dict, debug: bool = False) -> Tuple[List[str], int]:
    """
    Extract the IP path from a measurement result.
    Note: RIPEAtlas measurements contain IP addresses from hops, not ASN data directly.
    This function extracts unique IPs in order of appearance which represent the path.
    
    Args:
        measurement: A measurement dict with 'result' containing traceroute data
        debug: If True, print debug information about the data structure
        
    Returns:
        Tuple of (ip_path_list, endtime) where ip_path_list is list of unique IPs
        Returns ([], None) if path cannot be extracted
    """
    if not measurement or "result" not in measurement:
        return [], None
    
    results = measurement["result"]
    if not isinstance(results, list) or len(results) == 0:
        return [], None
    
    first_result = results[0]
    if not isinstance(first_result, dict) or "result" not in first_result:
        return [], None
    
    hops = first_result["result"]
    if not isinstance(hops, list) or len(hops) == 0:
        return [], None
    
    endtime = first_result.get("endtime")
    ip_path = []
    seen_ips = set()
    
    # Extract IP addresses from each hop, maintaining order
    debug_printed = False
    for hop_idx, hop in enumerate(hops):
        if isinstance(hop, dict) and "result" in hop:
            hop_results = hop["result"]
            if isinstance(hop_results, list):
                for result_idx, result in enumerate(hop_results):
                    if isinstance(result, dict):
                        # Print debug info for first result
                        if debug and not debug_printed:
                            print(f"DEBUG: Sample result dict keys: {result.keys()}")
                            print(f"DEBUG: Full result: {result}")
                            debug_printed = True
                        
                        # Extract IP from 'from' field
                        ip = result.get("from")
                        if ip and ip not in seen_ips:
                            ip_path.append(ip)
                            seen_ips.add(ip)
    
    return ip_path, endtime


def extract_hop_sequence_from_measurement(measurement: Dict) -> Tuple[List[str], int]:
    """
    Extract the complete hop sequence (IP addresses) from a measurement.
    
    Args:
        measurement: A measurement dict with 'result' containing traceroute data
        
    Returns:
        Tuple of (hop_sequence, endtime) where hop_sequence is list of IP strings
        Returns ([], None) if sequence cannot be extracted
    """
    if not measurement or "result" not in measurement:
        return [], None
    
    results = measurement["result"]
    if not isinstance(results, list) or len(results) == 0:
        return [], None
    
    first_result = results[0]
    if not isinstance(first_result, dict) or "result" not in first_result:
        return [], None
    
    hops = first_result["result"]
    if not isinstance(hops, list) or len(hops) == 0:
        return [], None
    
    endtime = first_result.get("endtime")
    hop_sequence = []
    
    # Extract IPs from each hop
    for hop in hops:
        if isinstance(hop, dict) and "result" in hop:
            hop_results = hop["result"]
            if isinstance(hop_results, list):
                for result in hop_results:
                    if isinstance(result, dict):
                        ip = result.get("from")
                        if ip:
                            hop_sequence.append(ip)
    
    return hop_sequence, endtime


def calculate_route_diversity(measurement_data: List[List[Dict]]) -> Dict:
    """
    Calculate comprehensive route diversity metrics from measurement data.
    
    Args:
        measurement_data: List of lists of measurements, typically grouped by time interval
        
    Returns:
        Dictionary containing:
        - unique_as_paths: Number of unique AS paths observed
        - unique_hop_sequences: Number of unique IP hop sequences
        - as_path_frequency: Dict mapping AS paths to their frequencies
        - hop_sequence_frequency: Dict mapping hop sequences to frequencies
        - as_diversity_score: Ratio of unique paths to total measurements
        - path_length_distribution: Dict of path lengths to counts
        - dominant_path: The most common AS path
        - path_changes_over_time: List of tuples (time, as_path)
    """
    
    as_paths = []
    hop_sequences = []
    as_path_frequencies = defaultdict(int)
    hop_sequence_frequencies = defaultdict(int)
    path_lengths = []
    paths_over_time = []
    
    total_measurements = 0
    successful_extractions = 0
    debug_count = 0
    
    # Flatten and process all measurements
    for measurement_list in measurement_data:
        for measurement in measurement_list:
            total_measurements += 1
            
            # Extract AS path (use debug on first measurement)
            as_path, endtime = extract_as_path_from_measurement(measurement, debug=(debug_count == 0))
            debug_count += 1
            
            if as_path:
                successful_extractions += 1
                as_path_tuple = tuple(as_path)
                as_paths.append(as_path_tuple)
                as_path_frequencies[as_path_tuple] += 1
                path_lengths.append(len(as_path))
                paths_over_time.append((endtime, as_path_tuple))
            
            # Extract hop sequence
            hop_seq, _ = extract_hop_sequence_from_measurement(measurement)
            if hop_seq:
                hop_seq_tuple = tuple(hop_seq)
                hop_sequences.append(hop_seq_tuple)
                hop_sequence_frequencies[hop_seq_tuple] += 1
    
    # Calculate diversity metrics
    unique_as_paths = len(set(as_paths))
    unique_hop_sequences = len(set(hop_sequences))
    
    diversity_score = 0
    if total_measurements > 0:
        diversity_score = unique_as_paths / total_measurements
    
    # Find dominant path
    dominant_path = None
    dominant_count = 0
    if as_path_frequencies:
        dominant_path, dominant_count = max(as_path_frequencies.items(), key=lambda x: x[1])
    
    # Calculate path length distribution
    path_length_dist = Counter(path_lengths)
    
    # Sort paths over time by endtime
    paths_over_time_sorted = sorted(
        [(t, p) for t, p in paths_over_time if t is not None],
        key=lambda x: x[0]
    )
    
    return {
        'unique_as_paths': unique_as_paths,
        'unique_hop_sequences': unique_hop_sequences,
        'total_measurements': total_measurements,
        'successful_extractions': successful_extractions,
        'as_path_frequency': dict(as_path_frequencies),
        'hop_sequence_frequency': dict(hop_sequence_frequencies),
        'diversity_score': diversity_score,
        'path_length_distribution': dict(path_length_dist),
        'dominant_path': dominant_path,
        'dominant_path_count': dominant_count,
        'paths_over_time': paths_over_time_sorted,
        'avg_path_length': sum(path_lengths) / len(path_lengths) if path_lengths else 0,
    }


def calculate_route_diversity_per_interval(measurement_data: List[List[Dict]]) -> List[Dict]:
    """
    Calculate route diversity for each time interval separately.
    
    Args:
        measurement_data: List of lists of measurements grouped by time interval
        
    Returns:
        List of diversity metrics dictionaries, one per interval
    """
    
    interval_diversities = []
    
    for measurement_list in measurement_data:
        as_paths = []
        hop_sequences = []
        path_lengths = []
        
        for measurement in measurement_list:
            as_path, _ = extract_as_path_from_measurement(measurement)
            if as_path:
                as_paths.append(tuple(as_path))
                path_lengths.append(len(as_path))
            
            hop_seq, _ = extract_hop_sequence_from_measurement(measurement)
            if hop_seq:
                hop_sequences.append(tuple(hop_seq))
        
        # Calculate metrics for this interval
        unique_as_paths = len(set(as_paths))
        unique_hop_sequences = len(set(hop_sequences))
        total_measurements = len(measurement_list)
        
        diversity_score = 0
        if total_measurements > 0:
            diversity_score = unique_as_paths / total_measurements
        
        interval_diversity = {
            'unique_as_paths': unique_as_paths,
            'unique_hop_sequences': unique_hop_sequences,
            'total_measurements': total_measurements,
            'diversity_score': diversity_score,
            'avg_path_length': sum(path_lengths) / len(path_lengths) if path_lengths else 0,
            'successful_measurements': len(as_paths) + len(hop_sequences),
        }
        
        interval_diversities.append(interval_diversity)
    
    return interval_diversities


def detect_route_changes(paths_over_time: List[Tuple[int, Tuple[str, ...]]]) -> List[Tuple[int, str]]:
    """
    Detect when the dominant route changes over time.
    
    Args:
        paths_over_time: List of (endtime, as_path) tuples sorted by time
        
    Returns:
        List of (time, event_description) tuples marking route changes
    """
    
    if not paths_over_time:
        return []
    
    changes = []
    previous_path = None
    
    for endtime, as_path in paths_over_time:
        if previous_path is not None and previous_path != as_path:
            changes.append((
                endtime,
                f"Route changed from {' -> '.join(previous_path)} to {' -> '.join(as_path)}"
            ))
        previous_path = as_path
    
    return changes


def calculate_asn_diversity(measurement_data: List[List[Dict]]) -> Dict:
    """
    Calculate diversity metrics specific to ASNs appearing in paths.
    
    Args:
        measurement_data: List of lists of measurements
        
    Returns:
        Dictionary containing:
        - unique_asns: Set of all unique ASNs seen
        - asn_frequency: Dict mapping ASN to frequency
        - most_common_asns: Top 10 most frequently seen ASNs
        - asn_hop_positions: Dict mapping ASN to list of hop positions where it appears
    """
    
    unique_asns = set()
    asn_frequency = Counter()
    asn_hop_positions = defaultdict(list)
    
    for measurement_list in measurement_data:
        for measurement in measurement_list:
            as_path, _ = extract_as_path_from_measurement(measurement)
            
            for hop_position, asn in enumerate(as_path):
                unique_asns.add(asn)
                asn_frequency[asn] += 1
                asn_hop_positions[asn].append(hop_position)
    
    most_common = asn_frequency.most_common(10)
    
    return {
        'unique_asns': unique_asns,
        'asn_count': len(unique_asns),
        'asn_frequency': dict(asn_frequency),
        'most_common_asns': most_common,
        'asn_hop_positions': dict(asn_hop_positions),
    }


def extract_ip_prefixes(ip_address: str, prefix_length: int = 24) -> str:
    """
    Extract a network prefix from an IP address.
    
    Args:
        ip_address: IP address as string (e.g., '192.0.2.1')
        prefix_length: Length of the prefix to extract (default: /24)
        
    Returns:
        Network prefix as string (e.g., '192.0.2.0/24'), or empty string if invalid
    """
    try:
        ip = ipaddress.ip_address(ip_address)
        network = ipaddress.ip_network(f"{ip}/{prefix_length}", strict=False)
        return str(network)
    except ValueError:
        return ""


def calculate_prefix_diversity(measurement_data: List[List[Dict]], prefix_length: int = 24) -> Dict:
    """
    Calculate route diversity based on IP prefixes instead of full paths.
    
    Args:
        measurement_data: List of lists of measurements
        prefix_length: Length of prefix to use (default: /24)
        
    Returns:
        Dictionary containing:
        - unique_prefixes: Number of unique prefixes seen
        - prefix_frequency: Dict mapping prefixes to frequencies
        - most_common_prefixes: Top 10 most common prefixes
        - prefix_diversity_score: Ratio of unique prefixes to total IPs seen
        - total_unique_ips: Count of unique individual IP addresses
    """
    
    unique_prefixes = set()
    prefix_frequency = Counter()
    unique_ips = set()
    total_ips = 0
    
    for measurement_list in measurement_data:
        for measurement in measurement_list:
            ip_path, _ = extract_as_path_from_measurement(measurement)
            
            for ip in ip_path:
                total_ips += 1
                unique_ips.add(ip)
                prefix = extract_ip_prefixes(ip, prefix_length)
                if prefix:
                    unique_prefixes.add(prefix)
                    prefix_frequency[prefix] += 1
    
    prefix_diversity_score = 0
    if total_ips > 0:
        #prefix_diversity_score = len(unique_prefixes) / total_ips
        prefix_diversity_score = len(unique_ips) / total_ips
    most_common = prefix_frequency.most_common(10)
    
    return {
        'unique_prefixes': len(unique_prefixes),
        'prefix_frequency': dict(prefix_frequency),
        'most_common_prefixes': most_common,
        'prefix_diversity_score': prefix_diversity_score,
        'total_unique_ips': len(unique_ips),
        'total_ips_seen': total_ips,
        'prefix_length': prefix_length,
    }


# todo: probably remove this one
# iuf you dont, fix the diversity score
def calculate_prefix_diversity_per_interval(measurement_data: List[List[Dict]], prefix_length: int = 24) -> List[Dict]:
    """
    Calculate prefix diversity for each time interval separately.
    
    Args:
        measurement_data: List of lists of measurements grouped by time interval
        prefix_length: Length of prefix to use (default: /24)
        
    Returns:
        List of prefix diversity metrics dictionaries, one per interval
    """
    
    interval_prefix_diversities = []
    
    for measurement_list in measurement_data:
        unique_prefixes = set()
        prefix_frequency = Counter()
        total_ips = 0
        
        for measurement in measurement_list:
            ip_path, _ = extract_as_path_from_measurement(measurement)
            
            for ip in ip_path:
                total_ips += 1
                prefix = extract_ip_prefixes(ip, prefix_length)
                if prefix:
                    unique_prefixes.add(prefix)
                    prefix_frequency[prefix] += 1
        
        prefix_diversity_score = 0
        if total_ips > 0:
            prefix_diversity_score = len(unique_prefixes) / total_ips
        
        interval_diversity = {
            'unique_prefixes': len(unique_prefixes),
            'total_ips': total_ips,
            'prefix_diversity_score': prefix_diversity_score,
            'most_common_prefix': prefix_frequency.most_common(1)[0] if prefix_frequency else None,
            'prefix_length': prefix_length,
        }
        
        interval_prefix_diversities.append(interval_diversity)
    
    return interval_prefix_diversities

