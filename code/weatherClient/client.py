
# This is a weather client that interacts with an iBoardBot server instance
# at regular intervals to display the latest weather information.
# Without special arguments the program will run forever and do a full update of the
# entire board once every 24 hours and partial updates every hour otherwise.

import argparse
import time
import logging
import urllib.parse
import requests
import datetime
import calendar

WEATHER_API = "http://api.openweathermap.org/"
FULL_WEATHER = "data/2.5/weather/"
CITY_ID = "5809844"
CLIENT_ID = "2C3AE83E11C6"

logging.basicConfig(level=logging.DEBUG, format='(%(threadName)-10s) %(message)s')

parser = argparse.ArgumentParser(description='Server for iBoardBot')
parser.add_argument('--serverName', 
        type=str, 
        default="localhost",
        help='Server name where the board bot server is runnng.  Defaults to localhost.')

parser.add_argument('--onceFull', 
        help='Run a single time and then stop',
        default = False, 
        action = "store_true")

parser.add_argument('--oncePartial', 
        help='Run a single time and then stop',
        default = False, 
        action = "store_true")

parser.add_argument('--partialRefreshPeriodicity', 
        type=int, 
        help='Number of seconds to delay before a partial refresh',
        default = 3600)

parser.add_argument('--fullRefreshPeriodicity', 
        type=int, 
        help='Number of seconds to delay before a full refresh', 
        default = 86400)

parser.add_argument('--weatherAPIKey', 
        type=str, 
        help='The weather API Key to use',
        required=True)

config = parser.parse_args()


def makeWeatherRequest():
  params = {'id':CITY_ID, 'units': 'imperial', 'appid': config.weatherAPIKey}
  r = requests.get(url = WEATHER_API + FULL_WEATHER, params = params) 
  return r.json() 

def fullRefresh():
  data = makeWeatherRequest()

  current_temp = data["main"]["temp"]
  temp_min = data["main"]["temp_min"]
  temp_max = data["main"]["temp_max"]
  icon_code = data["weather"][0]["icon"]
  condition = int(data["weather"][0]["id"])
  description = data["weather"][0]["description"]
  time = data["dt"]

  d = datetime.datetime.fromtimestamp(int(time))
  dayName = calendar.day_abbr[d.weekday()].upper()

  timeString = "{:02d}:{:02d}".format(d.hour, d.minute)
  day = "{:02d}".format(d.day)

  # Condition codes:  https://openweathermap.org/weather-conditions
  if condition == 800:
    conditionString = "SUNNY"
  elif condition > 800:
    conditionString = "CLOUDY"
  else:
    condition /= 100

    if condition == 7:
      conditionString = "CLOUDY"
    elif condition == 6:
      conditionString = "SNOW"
    elif condition == 5:
      conditionString = "RAIN"
    elif condition == 3:
      conditionString = "RAIN"
    else:
      conditionString = "UNKNOWN"

  logging.info("fullRefresh - got information; d: %s, current_temp: %s, temp_min: %s, temp_max: %s, description: %s", 
      d, current_temp, temp_min, temp_max, description)

  # Make the request to the boardBot server instance.  First clear the screen and then
  # do the full weather update.
  boardBotParams = {'ID_IWBB': CLIENT_ID }
  boardRequest = requests.get(
      url = "http://{url}/erase".format(url=config.serverName),
      params = boardBotParams)
  if not boardRequest.ok:
    logging.info("fullRefresh - error in clearing the board")
    return False

  boardBotParams = {
      'ID_IWBB': CLIENT_ID,
      'time': timeString,
      'dayOfWeek': dayName,
      'dayOfMonth': day,
      'temperature': "{:0.1f}".format(current_temp),
      'minTemperature': int(temp_min),
      'maxTemperature': int(temp_max),
      'condition': conditionString,
      'description': description.upper()}

  boardRequest = requests.get(
      url = "http://{url}/weather".format(url=config.serverName),
      params = boardBotParams)
  return boardRequest.ok


def partialRefresh():
  data = makeWeatherRequest()

  current_temp = data["main"]["temp"]
  time = data["dt"]
  d = datetime.datetime.fromtimestamp(int(time))
  timeString = "{:02d}:{:02d}".format(d.hour, d.minute)

  logging.info("partialRefresh - got information; d: %s, current_temp: %s", 
      d, current_temp)

  # Make the request to the boardBot server instance

  boardBotParams = {
      'ID_IWBB': CLIENT_ID,
      'time': timeString,
      'temperature': "{:0.1f}".format(current_temp),
      }

  boardRequest = requests.get(
      url = "http://{url}/updateWeather".format(url=config.serverName),
      params = boardBotParams)
  return boardRequest.ok

  

  
def main():
  if config.onceFull:
    fullRefresh()
  if config.oncePartial:
    partialRefresh()

  if not (config.onceFull or config.oncePartial):
    lastFullRefresh = 0
    lastPartialRefresh = 0
    while True:
      t = time.time()

      if lastFullRefresh + config.fullRefreshPeriodicity < t:
        logging.info("main - going to do a full refresh; lastFullRefresh: %d, time: %d", 
            lastFullRefresh, t)
        lastFullRefresh = t
        lastPartialRefresh = t
        fullRefresh()

      if lastPartialRefresh + config.partialRefreshPeriodicity < t:
        logging.info("main - going to do a partial refresh; lastPartialRefresh: %d, time: %d", 
            lastPartialRefresh, t)
        lastPartialRefresh = t
        partialRefresh()

      logging.info("main - Sleeping for awhile;")
      time.sleep(5*60)

if __name__ == '__main__':
  main()

# vim: tabstop=2 shiftwidth=2 softtabstop=2 expandtab ignorecase
