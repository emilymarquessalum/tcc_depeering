
import sys
from pathlib import Path
import warnings


sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))





from src.ripe_bviews.download_and_parse.load_configs import load_configs
from src.ripe_bviews.timeline.bview_vars import get_ip_version
from src.ripe_bviews.download_and_parse.load_bview_data import load_bview_data_timeline_from_configs
from src.ripe_bviews.timeline.bview_timeline_reachable_metrics import calculate_reachables_oscillation_came_back_info


config = load_configs("ixbr.json")
ip_version = get_ip_version(config)
all_stats, labels = load_bview_data_timeline_from_configs(config, ip_version=ip_version)     

came_back_info = calculate_reachables_oscillation_came_back_info(all_stats)



def test_reachables_come_back_more_with_same_members_than_new_and_different_members():
     
     assert came_back_info.summed_same_members() > (came_back_info.summed_only_new_members() + came_back_info.summed_different_members())
     

def test_reachables_with_same_members_come_back_with_same_as_path_length_more_than_better_and_worse_as_path_length():
     same_members = came_back_info.came_back_with_same_members
     same_as_path = len(same_members[0])
     better_as_path = len(same_members[1])
     worse_as_path = len(same_members[2])
     assert same_as_path > better_as_path and better_as_path > worse_as_path

# Expectation 2:
# worse AS Path Length > better AS Path Length & worse AS Path Length > same AS Path Length
def test_reachables_with_same_members_come_back_with_worse_as_path_length_more_than_better_and_same_as_path_length():
     new_members_worse_as_path = len(came_back_info.came_back_with_only_new_members[2])
     new_members_better_as_path = len(came_back_info.came_back_with_only_new_members[1])
     new_members_same_as_path = len(came_back_info.came_back_with_only_new_members[0])

     assert new_members_worse_as_path > new_members_better_as_path
     assert new_members_worse_as_path > new_members_same_as_path

     different_members_worse_as_path = len(came_back_info.came_back_with_different_members[2])
     different_members_better_as_path = len(came_back_info.came_back_with_different_members[1])
     different_members_same_as_path = len(came_back_info.came_back_with_different_members[0])

     assert different_members_worse_as_path > different_members_better_as_path
     assert different_members_better_as_path + different_members_same_as_path > different_members_worse_as_path
     
     #assert different_members_worse_as_path > different_members_same_as_path
 