
 


def _resolve_asn_label(
    target_asn, # Union[int, str]
    asn_to_name_map = None, # : Optional[Dict[Union[int, str], str]]
) -> str:
    """Resolves a human-readable label for an ASN from the provided mapping."""
    if not asn_to_name_map:
        return f"ASN {target_asn}"

    clean_str = str(target_asn).upper().replace("AS", "").strip()
    try:
        clean_int = int(clean_str)
    except ValueError:
        clean_int = None

    return (
        asn_to_name_map.get(target_asn)
        or (asn_to_name_map.get(clean_int) if clean_int is not None else None)
        or asn_to_name_map.get(clean_str)
        or asn_to_name_map.get(f"AS{clean_str}")
        or f"ASN {target_asn}"
    )





hegemony_asn_map = { 
        3356: "Lumen (VPP)",
        3257: "GTT (VPP)", 
        6939: "Hurricane",
        8218: "Zayo (VPP)",
        24482: "SG GS",
        34549: "meerfarbig",
        202365: "Chronos",
        214292: "DE-CIX (VPP)",

        9002: "RETN Limited",
        1299: "Arelion (VPP)",
        21859: "Zenlayer",
        2914: "NTT",

        3491:"PCCW Global",
        32653:"eNetworks",
        328320:"Kurlec",

        174: "Cogent",

        6453: "TATA",

}