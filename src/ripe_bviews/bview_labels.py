


from datetime import datetime


def date_range_title(start_date, end_date):
    return f" from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
def date_range_title_config(config):
    start_date_str = config.get("start_date")
    end_date_str = config.get("end_date")
    start_date = None
    end_date = None
    if start_date_str:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    if end_date_str:
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        
    if start_date and end_date:
        return date_range_title(start_date, end_date)
    return ""
def time_delta_title(day_delta, time_delta):
    if day_delta == 0:
        return f"interval of {time_delta} hours"
    return f"interval of {day_delta} days"


def summarized_date_labels(labels):
    # these labels will have format like "2023/01/01 0800" and we will remove 
    # the "0800" and also remove all duplicates, so we will have one label per day, like "2023/01/01"
    summarized_labels = []
    seen_dates = set()
    for label in labels:
        date_part = label.split()[0]  # Get the date part (e.g., "2023/01/01")
        if True or date_part not in seen_dates:
            summarized_labels.append(date_part)
            seen_dates.add(date_part)
    return summarized_labels