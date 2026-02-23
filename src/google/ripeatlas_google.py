
import datetime
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from progress.bar import Bar
import requests
    
from src.utils.graphs import plot_list_as_line_plot


def fetch_measurement_data(asn, start_date, end_date):
    # pass date to Unix timestamp
    start_date = int(start_date.timestamp())
    end_date = int(end_date.timestamp())  
    route = f"https://atlas.ripe.net/api/v2/measurements/?target_asn={asn}&start_time__gte={start_date}&start_time__lte={end_date}"
 
    #print(route)    
    #return {'count': 0, 'results': []}

    response = requests.get(route)
    if response.status_code == 200:
        data = response.json()
        return data 
    else:
        print(f"Error fetching data: {response.status_code}")
    return {'count': 0, 'results': []}

google_ases_for_search = [15169]

start_date = datetime.datetime(2024, 1, 1)
end_date = datetime.datetime.now()#datetime.datetime(2022, 1, 1)#datetime.datetime.now()

day_delta = datetime.timedelta(days=31)

for asn in google_ases_for_search:
     
    response = fetch_measurement_data(asn, start_date, start_date + day_delta)
 
    current_date = start_date
    average_speeds = []
    measurement_counts = [] 
    number_of_intervals = ((end_date - start_date).days) // 30
    i = 0
    bar = Bar(max=number_of_intervals)
    while i < number_of_intervals: 
        data = fetch_measurement_data(asn, current_date, current_date + day_delta)
        measurement_counts.append(data['count']) 
        #measurement_counts.append(len(data))
        current_date += day_delta 
        i += 1 
        bar.next()
    bar.finish()
    if False:
            average = 0 # LATENCY/SPEED calculation
            for measurement in data:
                
                latency = measurement.get('latency', 0)
                average += latency
            average /= len(data)
            average_speeds.append(average)
    dates_in_plot = []
    for i in range(len(measurement_counts)):
        date_value = start_date + i * day_delta
        if date_value.month == 1:
            date_str = date_value.strftime('%Y')
        else:
            date_str = date_value.strftime('%b %M')[:-2]
            date_str = date_str + date_value.strftime('%Y')[2:]
        dates_in_plot.append(date_str)
    plot_list_as_line_plot(measurement_counts, y=dates_in_plot,
                           title=f'Measurement Counts Over Time for ASN {asn}', xlabel='Time Intervals', ylabel='Number of Measurements')
    print("Sum:", sum(measurement_counts))
#this is an initial measurement and it can end up a little all over the place, but we can try to find some starting patterns 

# Check out of those measurements how many passed through an IXP
