


import re


def get_formatted_asn_name(asn_name):

    
    asn_name = re.sub("AS[0-9]+", '', asn_name)

    asn_name = asn_name.replace("Telecomunicações", "").replace("TELECOMUNICACOES","").replace("Internet", "")

    return asn_name
