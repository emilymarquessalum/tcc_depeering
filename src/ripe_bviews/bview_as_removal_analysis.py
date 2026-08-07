 

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.graphs import plot_list_as_line_plot


from datetime import datetime, timedelta
import warnings
from src.ripe_bviews.oscillations.bview_oscillation_logic import get_ases_that_did_not_come_back
from src.ripe_bviews.timeline.bview_timeline import load_bview_data



warnings.filterwarnings('ignore', category=UserWarning, message='.*Skipping download.*')
start_date = datetime(2025, 10, 20)
end_date = datetime(2026, 1, 1)#datetime.datetime(202
day_delta = timedelta(days=3)


subfolder = start_date.strftime("%Y%m%d") + "_" + end_date.strftime("%Y%m%d") + "_" + str(day_delta.days) + "days/"
all_stats, labels = load_bview_data(start_date, end_date, ("26162", "187.16.216.253"), "rrc15", day_delta=day_delta)



ases_that_did_not_come_backs = []

for i in range(len(all_stats)-2):
    ases_that_did_not_come_backs.append(get_ases_that_did_not_come_back(all_stats, use_reachables=False, index=i))

as_count_not_come_backs = [len(ases) for ases in ases_that_did_not_come_backs]
plot_list_as_line_plot(as_count_not_come_backs, y=labels[1:-1], title='ASes Removed That Did Not Come Back Over Time considering dates ' + start_date.strftime("%Y-%m-%d") + " to " + end_date.strftime("%Y-%m-%d"), xlabel='Date', ylabel='Number of ASes', subfolder=subfolder)
