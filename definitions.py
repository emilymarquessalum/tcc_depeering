

# Source - https://stackoverflow.com/a/25389715
# Posted by jrd1, modified by community. See post 'Timeline' for change history
# Retrieved 2026-02-12, License - CC BY-SA 4.0

import os


ROOT_DIR = os.path.dirname(os.path.abspath(__file__)) + "/data/" 


#ROOT_DIR = "/home/emily/Desktop/projects/furg/tcc_depeering_elixir/data/"
ROOT_DIR2 = "admin:///home/media/test"

ROOT_DIR = "c:\\Users\\Anna_Sales\\"
def append_roots(file):
    roots = []

    for root in [ROOT_DIR, ROOT_DIR2]:
        if file.startswith(root):
            return [file]
        roots.append(os.path.join(root, file))

    return roots