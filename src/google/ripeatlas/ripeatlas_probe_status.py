



import requests

def check_probe_changes(probe_id: int, date1: str, date2: str):
    """
    Checks if a RIPE Atlas probe changed location or ASN between two dates (YYYY-MM-DD).
    """
    url = "https://atlas.ripe.net/api/v2/probes/archive/"
    
    # Fetch archive snapshots for date1 and date2
    snapshots = {}
    for dt in [date1, date2]:
        params = {
            "probe": probe_id,
            "date": dt
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        results = response.json().get("results", [])
        
        if not results:
            print(f"No archive data found for probe {probe_id} on {dt}.")
            return
        
        snapshots[dt] = results[0]

    snap1 = snapshots[date1]
    snap2 = snapshots[date2]

    # Extract ASN metadata (IPv4 and IPv6)
    asn1 = (snap1.get("asn_v4"), snap1.get("asn_v6"))
    asn2 = (snap2.get("asn_v4"), snap2.get("asn_v6"))

    # Extract Location metadata (Latitude, Longitude, Country)
    loc1 = (snap1.get("geometry", {}).get("coordinates"), snap1.get("country_code"))
    loc2 = (snap2.get("geometry", {}).get("coordinates"), snap2.get("country_code"))

    print(f"--- Probe {probe_id} Comparison ({date1} vs {date2}) ---")

    return asn1 != asn2 or loc1 != loc2
    # Check ASN changes
    if asn1 != asn2:
        print(f"  ASN Changed:")
        print(f"    {date1}: IPv4 ASN={asn1[0]}, IPv6 ASN={asn1[1]}")
        print(f"    {date2}: IPv4 ASN={asn2[0]}, IPv6 ASN={asn2[1]}")
    else:
        print(f"  ASN: Unchanged (IPv4: {asn1[0]}, IPv6: {asn1[1]})")

    # Check Location changes
    if loc1 != loc2:
        print(f"  Location Changed:")
        print(f"    {date1}: Coordinates={loc1[0]}, Country={loc1[1]}")
        print(f"    {date2}: Coordinates={loc2[0]}, Country={loc2[1]}")
    else:
        print(f"  Location: Unchanged (Coordinates: {loc1[0]}, Country: {loc1[1]})")

    

# Example Usage
if __name__ == "__main__":
    PROBE_ID = 10001
    DATE_1 = "2024-01-01"
    DATE_2 = "2026-01-01"
    
    change_happened = check_probe_changes(PROBE_ID, DATE_1, DATE_2)
    print("Change Detected:", change_happened)


