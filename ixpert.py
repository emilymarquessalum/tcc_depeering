import requests


def search_prefix(prefix, silent_errors=True):

    url = f"https://ixpert.info/api/prefix_search/?prefix={prefix}&ip_version=v4"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data
    else:
        if not silent_errors:
            print(f"Error: {response.status_code}")
            print(f"Response: {response.text}")
        return None