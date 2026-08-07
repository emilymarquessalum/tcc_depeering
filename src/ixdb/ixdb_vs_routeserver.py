

import os

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))  

from src.ripe_bviews.routeserver.routeserver_changes_by_filtered import get_routeserver

from src.ixdb.main import get_participants_of_ixp



ixp_sao_paulo_id = 791
latest_date_ixdb = "20251104" 


participants = []

participants = get_participants_of_ixp(ixp_sao_paulo_id)

route_server_data = get_routeserver("ix-br", latest_date_ixdb)

neighbours = route_server_data["SP-rs2-v4"]["neighbors"] + route_server_data["SP-rs2-v6"]["neighbors"]

routeserver_members = set([str(neighbour["asn"]) for neighbour in neighbours])

participants_asns = set([str(participant["asn"]) for participant in participants])


routeserver_members_that_dont_announce_routes = set()

for neighbour in neighbours:
    if not neighbour["routes_received"]:
        routeserver_members_that_dont_announce_routes.add(int(neighbour["asn"]))

print(f"Number of participants in IXP São Paulo: {len(participants_asns)}")
print(f"Number of members in Route Server: {len(routeserver_members)}")
print(f"Number of members in Route Server that do not announce routes: {len(routeserver_members_that_dont_announce_routes)}")

print("---")


participants_also_in_routeserver = sum(1 for asn in participants_asns if asn in routeserver_members)
participants_not_in_routeserver = sum(1 for asn in participants_asns if asn not in routeserver_members)
print(f"Number of participants that are also in the Route Server: {participants_also_in_routeserver}")
print(f"Number of participants that are NOT in the Route Server: {participants_not_in_routeserver}")

print("---")


routeserver_not_in_participants = sum(1 for asn in routeserver_members if asn not in participants_asns)
print(f"Number of Route Server members that are NOT participants: {routeserver_not_in_participants}")

#print(participants_asns)
#print(routeserver_members)
#members_in_route_server_that_are_not_participants = [asn for asn in routeserver_members if asn not in participants_asns]
#print(members_in_route_server_that_are_not_participants)