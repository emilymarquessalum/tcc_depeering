

# Source - https://stackoverflow.com/a/25389715
# Posted by jrd1, modified by community. See post 'Timeline' for change history
# Retrieved 2026-02-12, License - CC BY-SA 4.0

import os


ROOT_DIR = os.path.dirname(os.path.abspath(__file__)) + "/src/ripe_bviews/" # This is your Project Root


ROOT_DIR = "/home/emily/Desktop/projects/furg/tcc_depeering_elixir/data/"
def append_root(file):
    if file.startswith(ROOT_DIR):
        return file
    return os.path.join(ROOT_DIR, file)