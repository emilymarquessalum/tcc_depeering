import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent

default_data_dir = REPO_ROOT / "data"

if not default_data_dir.exists():
    for parent in REPO_ROOT.parents:
        if (parent / "data").exists():
            default_data_dir = parent / "data"
            break

ROOT_DIR = os.getenv("ROOT_DIR", str(default_data_dir))
ROOT_DIR2 = "admin:///home/media/test"

def append_roots(file):
    roots = []
    for root in [ROOT_DIR, ROOT_DIR2]:
        if file.startswith(root):
            return [file]
        roots.append(os.path.join(root, file))
    return roots