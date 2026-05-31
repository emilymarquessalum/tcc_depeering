


## TCC De-peering (TODO: Rename with official TCC name later)

Project, created in python, to analyze RRC RIB file data of IXPs and RouteServer data, for the paper "".
Mainly focused on generating metrics and making visualizations.
[TCC] (Link to TCC here)


* Looks at information like members/reachables over time, oscillating ASes, Route quality over time, etc;
* Uses matplotlib to create graphs;
* Calls an [elixir API] (add link later) that does the acquiring and parsing (it's a work in progress implementation because the access to the .json files is still direct so the informaation doesn't need to be returned by the API which would consume a lot of time since it's a lot of data... meaning, both systems need to be running locally and this system needs to know where the other one is located. Also, some processes like getting oscillation metrics maybe should be passed to elixir too, for performance sake);


Put this in the elixir README later:

Main routes:

GET /bview
query params: start_date, end_date, day_delta, time_delta, time_str, rrc, ip_version, asn, prefix

Downloads RRC data from URL (uses params to format it to find every file required). Uses bgpdump command programatically, with turns the ZIP files into a .txt with all routes. From those routes, it creates a .json file with only the required information for processing.
Returns 200 if successful (with empty body).

The system has a (WIP) functionality that makes it continue download and parsing processes that were started but didnt finish. 
