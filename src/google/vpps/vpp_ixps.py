

import json 

import sys
from pathlib import Path




sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.caidapeeringdb.ixp_region import plot_ixps_by_region
from src.caidapeeringdb.ixp_size import plot_ixps_by_size_ranges
from src.caidapeeringdb.caidapeeringdb_load import get_all_files, get_all_ixps, get_all_ixps_from_organization, get_all_organizations, get_all_organizations_that_own_ixps, get_asinfo_from_asn, get_asns_of_info_type, get_asns_types_peeringdb, get_data

from src.google.vpps.vpp_region import plot_vpp_count_by_region
from src.utils.graphs import plot_map_as_bar_plot



all_files = get_all_files()

print(all_files[-1])
data = get_data(all_files[-1])
 
with open(Path(__file__).parent / "google_vpps.json", "r") as f:
        vpps_data = json.load(f)
        vpps_list = vpps_data.get("gold", []) + vpps_data.get("silver", [])




def get_all_vpps_whose_name_matches_an_ixp_name(vpps, ixps):
    print("total number of vpps to compare with ixps:", len(vpps))

    vpp_names_that_are_ixps = set()
    vpp_ixp_ids = set()

    for ixp in ixps:
        ixp_name = ixp.get("name", "").lower()
        ixp_id = ixp.get("id")
        for vpp in vpps:
            vpp_name = vpp.get("isp_name", "").split("\n")[0].lower()
            if vpp_name in ixp_name or ixp_name in vpp_name:
                vpp_names_that_are_ixps.add(vpp_name)
                vpp_ixp_ids.add(ixp_id)
                break

    return list(vpps), vpp_names_that_are_ixps, vpp_ixp_ids


def get_all_vpps_whose_name_matches_an_organization_that_owns_ixps(vpps, data):
        organizations = get_all_organizations_that_own_ixps(data)

        vpp_names_that_are_organizations_owning_ixps = set()
        vpp_ixp_ids = set()

        for org in organizations:
            org_name = org.get("name", "").lower()
            for vpp in vpps:
                vpp_name = vpp.get("isp_name", "").split("\n")[0].lower()
                if vpp_name in org_name or org_name in vpp_name:
                    vpp_names_that_are_organizations_owning_ixps.add(vpp_name)
                    
                    ixps = get_all_ixps_from_organization(org.get("id"), data)
                    vpp_ixp_ids.update([ixp.get("id") for ixp in ixps])
                    break

        return list(vpps), vpp_names_that_are_organizations_owning_ixps, vpp_ixp_ids

def get_org_information_from_vpps(vpps, data):
    organizations = get_all_organizations(data)
    org_info_from_vpps = {}

    for org in organizations:
        org_name = org.get("name", "").lower()
        for vpp in vpps:
            vpp_name = vpp.get("isp_name", "").split("\n")[0].lower()
            if vpp_name in org_name or org_name in vpp_name:
                org_info_from_vpps[vpp.get("isp_name")] = org
                break

    return org_info_from_vpps

if False:
        vpps, vpp_names_that_are_ixps, vpp_ixp_ids = get_all_vpps_whose_name_matches_an_ixp_name(vpps_list, get_all_ixps(data))
                
        vpps_that_are_ixps = [vpp for vpp in vpps if vpp.get("isp_name", "").split("\n")[0].lower() in vpp_names_that_are_ixps]

        print(f"Number of Google VPP ASNs that are also IXPs: {len(vpps_that_are_ixps)}") 
        print([vpp_name for vpp_name in vpp_names_that_are_ixps])


        plot_vpp_count_by_region(list(vpps_that_are_ixps), title_suffix="(That are also IXPs)")
        plot_ixps_by_region(all_files, list(vpp_ixp_ids), title_suffix="(IXPs coming from VPPs)")

        plot_ixps_by_size_ranges(data, list(vpp_ixp_ids), title_suffix="(IXPs coming from VPPs)")


org_info_from_vpps = get_org_information_from_vpps(vpps_list, data)

org_region_count = {}
print(list((org_info_from_vpps).values())[0])
for vpp_name, info in org_info_from_vpps.items():
    org_region = info["country"]
    if org_region not in org_region_count:
        org_region_count[org_region] = 0
    org_region_count[org_region] += 1

print("Organization country count from VPPs:", org_region_count)

# Country to continent mapping
country_to_continent = {
    # North America
    "US": "North America", "CA": "North America", "MX": "North America",
    # South America
    "BR": "South America", "AR": "South America", "CO": "South America", "CL": "South America",
    "PE": "South America", "VE": "South America", "EC": "South America", "PY": "South America",
    "UY": "South America", "GY": "South America", "SR": "South America", "FG": "South America",
    # Europe
    "DE": "Europe", "FR": "Europe", "UK": "Europe", "GB": "Europe", "IT": "Europe", "ES": "Europe",
    "NL": "Europe", "BE": "Europe", "CH": "Europe", "AT": "Europe", "SE": "Europe", "NO": "Europe",
    "DK": "Europe", "FI": "Europe", "PL": "Europe", "CZ": "Europe", "RO": "Europe", "PT": "Europe",
    "GR": "Europe", "HU": "Europe", "IE": "Europe", "IS": "Europe", "LU": "Europe", "SI": "Europe",
    "HR": "Europe", "SK": "Europe", "BG": "Europe", "LT": "Europe", "LV": "Europe", "EE": "Europe",
    "MT": "Europe", "CY": "Europe", "RS": "Europe", "BA": "Europe", "ME": "Europe", "XK": "Europe",
    "AL": "Europe", "MK": "Europe", "BY": "Europe", "UA": "Europe", "MD": "Europe",
    # Asia
    "CN": "Asia", "JP": "Asia", "IN": "Asia", "SG": "Asia", "HK": "Asia", "TH": "Asia",
    "MY": "Asia", "ID": "Asia", "PH": "Asia", "VN": "Asia", "KR": "Asia", "TW": "Asia",
    "PK": "Asia", "BD": "Asia", "LK": "Asia", "NP": "Asia", "KZ": "Asia", "UZ": "Asia",
    "TJ": "Asia", "KG": "Asia", "TM": "Asia", "IR": "Asia", "IQ": "Asia", "SA": "Asia",
    "AE": "Asia", "QA": "Asia", "KW": "Asia", "BH": "Asia", "OM": "Asia", "YE": "Asia",
    "JO": "Asia", "IL": "Asia", "PS": "Asia", "LB": "Asia", "SY": "Asia", "TR": "Asia",
    "AF": "Asia", "MM": "Asia", "LA": "Asia", "KH": "Asia", "BT": "Asia", "MG": "Asia",
    # Africa
    "ZA": "Africa", "NG": "Africa", "EG": "Africa", "ET": "Africa", "KE": "Africa", "GH": "Africa",
    "TZ": "Africa", "UG": "Africa", "RW": "Africa", "DZ": "Africa", "MA": "Africa", "TN": "Africa",
    "LY": "Africa", "SD": "Africa", "SS": "Africa", "ER": "Africa", "DJ": "Africa", "SO": "Africa",
    "ZM": "Africa", "ZW": "Africa", "MW": "Africa", "MZ": "Africa", "AO": "Africa", "BW": "Africa",
    "NA": "Africa", "LS": "Africa", "SZ": "Africa", "GA": "Africa", "CG": "Africa", "CD": "Africa",
    "CM": "Africa", "CF": "Africa", "TD": "Africa", "CI": "Africa", "SN": "Africa", "ML": "Africa",
    "BF": "Africa", "NE": "Africa", "BJ": "Africa", "TG": "Africa", "LR": "Africa", "SL": "Africa",
    "GN": "Africa", "GW": "Africa", "CV": "Africa", "ST": "Africa", "SC": "Africa", "MU": "Africa",
    "KM": "Africa",
    # Oceania
    "AU": "Oceania", "NZ": "Oceania", "FJ": "Oceania", "PG": "Oceania", "SB": "Oceania", "VU": "Oceania",
    "TO": "Oceania", "WS": "Oceania", "KI": "Oceania", "MH": "Oceania", "FM": "Oceania", "PW": "Oceania",
}

# Group by continent
continent_count = {}
for country, count in org_region_count.items():
    # Replace empty string with "Global"
    if country == "":
        continent = "Global"
    else:
        continent = country_to_continent.get(country, "Unknown")
    
    if continent not in continent_count:
        continent_count[continent] = 0
    continent_count[continent] += count

print("\nOrganization count by continent from VPPs:", continent_count)

# Plot the distribution using utility function
plot_map_as_bar_plot(
    continent_count,
    title='Distribution of Google VPP Organizations by Continent',
    xlabel='Continent',
    ylabel='Number of Organizations',
    subfolder='vpps',
    sort_by_size=True,
    use_rotated_labels=True
)

#sys.exit(0)
vpps, vpp_names_that_are_organizations_owning_ixps, vpp_ixp_ids = get_all_vpps_whose_name_matches_an_ixp_name(vpps_list, get_all_ixps(data))


vpps_that_are_organizations_owning_ixps = [vpp for vpp in vpps if vpp.get("isp_name", "").split("\n")[0].lower() in vpp_names_that_are_organizations_owning_ixps]

print(f"Number of Google VPP ASNs that are also Organizations owning IXPs: {len(vpps_that_are_organizations_owning_ixps)}")
print([vpp_name for vpp_name in vpp_names_that_are_organizations_owning_ixps])

plot_ixps_by_region(all_files, list(vpp_ixp_ids), title_suffix="(IXPs coming from VPPs)")
#plot_ixps_by_size_ranges(data, list(vpp_ixp_ids), title_suffix="(IXPs coming from VPPs)")

plot_vpp_count_by_region(list(vpps_that_are_organizations_owning_ixps), title_suffix="(That own IXPs)")

# Apply continent mapping to VPPs that own IXPs
vpp_org_region_count = {}
vpps_without_org_info = []
for vpp in vpps_that_are_organizations_owning_ixps:
    vpp_name = vpp.get("isp_name", "")
    if vpp_name in org_info_from_vpps:
        org_info = org_info_from_vpps[vpp_name]
        org_region = org_info.get("country", "")
        if org_region not in vpp_org_region_count:
            vpp_org_region_count[org_region] = 0
        vpp_org_region_count[org_region] += 1
    else:
        vpps_without_org_info.append(vpp_name)

print(f"\nVPPs that own IXPs but have no organization info: {vpps_without_org_info}")

print("Organization country count from VPPs that own IXPs:", vpp_org_region_count)

# Group by continent
vpp_continent_count = {}
for country, count in vpp_org_region_count.items():
    # Replace empty string with "Global"
    if country == "":
        continent = "Global"
    else:
        continent = country_to_continent.get(country, "Unknown")
    
    if continent not in vpp_continent_count:
        vpp_continent_count[continent] = 0
    vpp_continent_count[continent] += count

# Add VPPs without organization info to Unknown continent
if vpps_without_org_info:
    if "Unknown" not in vpp_continent_count:
        vpp_continent_count["Unknown"] = 0
    vpp_continent_count["Unknown"] += len(vpps_without_org_info)

print("Organization count by continent from VPPs that own IXPs:", vpp_continent_count)

# Plot the distribution
plot_map_as_bar_plot(
    vpp_continent_count,
    title='Distribution of Google VPP Organizations (That Own IXPs) by Continent',
    xlabel='Continent',
    ylabel='Number of Organizations',
    subfolder='vpps',
    sort_by_size=True,
    use_rotated_labels=True
)


'''

count_of_vpps_asns_in_route_servers = len(vpps_in_route_servers)

print(f"By looking at {len(route_servers)} ASNs that are Route Servers,")
print(f"And comparing with {len(vpps_asn_map)} Google VPP ASNs,")
print(f"Number of Google VPP ASNs that are also Route Servers: {count_of_vpps_asns_in_route_servers}")
print(vpps_in_route_servers)

for vpp_asn in vpps_in_route_servers:
        asn_info = get_asinfo_from_asn(data, int(vpp_asn))
        print(asn_info["name"])
'''

#get_all_ixps