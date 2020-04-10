
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
FORECAST_WEATHER = "data/2.5/forecast/"
CITY_ID = "5809844"
CLIENT_ID = "2C3AE83E11C6"

logging.basicConfig(level=logging.DEBUG, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

parser = argparse.ArgumentParser(description='Server for iBoardBot')
parser.add_argument('--serverName', 
        type=str, 
        default="localhost",
        help='Server name where the board bot server is runnng.  Defaults to localhost.')

parser.add_argument('--onceFull', 
        help='Run a single time with full information printed and then stop',
        default = False, 
        action = "store_true")

parser.add_argument('--oncePartial', 
        help='Run a single time with partial information printed and then stop',
        default = False, 
        action = "store_true")

parser.add_argument('--hours', 
        type=int, 
        nargs='+',
        help='A list of hours for which, at the top of the hour, a full refresh will be executed.',
        default = [5, 10, 15])

parser.add_argument('--weatherAPIKey', 
        type=str, 
        help='The weather API Key to use',
        required=True)

parser.add_argument('--sleepSeconds', 
        type=int, 
        help='Number of seconds to sleep before waking up and checking for forward progress', 
        default = 300)

config = parser.parse_args()

# Track the prior day seen so that I can recognize when the current day has changed.
priorDay = 0
dayLow = 1000
dayHigh = -1000

def hasDayChanged():
  global priorDay

  d = datetime.datetime.fromtimestamp(time.time())
  if d.day != priorDay:
    priorDay = d.day
    return True
  else:
    return False

def getTemperatureForecast():
  global priorDay, dayLow, dayHigh

  params = {'id':CITY_ID, 'units': 'imperial', 'appid': config.weatherAPIKey}
  r = requests.get(url = WEATHER_API + FORECAST_WEATHER, params = params) 
  data = r.json()

  for i in range(12):
    itemTime = data["list"][i]["dt"]
    d = datetime.datetime.fromtimestamp(int(itemTime))
    if d.day == priorDay:
      itemMin = float(data["list"][i]["main"]["temp_min"])
      itemMax = float(data["list"][i]["main"]["temp_max"])
      logging.info(
          "getTemperatureForecast - found another entry for today; itemMin: %d, itemMax: %d",
          itemMin, itemMax)
      dayLow = min(dayLow, itemMin)
      dayHigh = max(dayHigh, itemMax)
      
  logging.info("getTemperatureForecast - final values; dayLow: %d, dayHigh: %d", 
      dayLow, dayHigh)
  return dayLow, dayHigh


def makeWeatherRequest():
  params = {'id':CITY_ID, 'units': 'imperial', 'appid': config.weatherAPIKey}
  r = requests.get(url = WEATHER_API + FULL_WEATHER, params = params) 
  return r.json() 

def fullRefresh():

  data = None
  try:
    data = makeWeatherRequest()
    (tempMin, tempMax) = getTemperatureForecast()
  except Exception as e:
    logging.exception("error in getting weather or forecast")
    return False

  currentTemp = data["main"]["temp"]
  condition = int(data["weather"][0]["id"])
  description = data["weather"][0]["description"]
  time = data["dt"]

  tempMin = min(tempMin, currentTemp)
  tempMax = max(tempMax, currentTemp)

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

  logging.info("fullRefresh - got information; d: %s, currentTemp: %s, tempMin: %s, tempMax: %s, description: %s", 
      d, currentTemp, tempMin, tempMax, description)

  try:
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
        'temperature': "{:0.1f}".format(currentTemp),
        'minTemperature': int(tempMin),
        'maxTemperature': int(tempMax),
        'condition': conditionString,
        'description': description.upper()}

    boardRequest = requests.get(
        url = "http://{url}/weather".format(url=config.serverName),
        params = boardBotParams)
    return boardRequest.ok
  except Exception as e:
    logging.exception("error in contacting boardbot;")
    return False


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

lastFullRefresh = 0
priorHour = 0

def shouldDoFullRefresh(hours, t):
  global priorHour

  d = datetime.datetime.fromtimestamp(time.time())
  if d.hour != priorHour:
    priorHour = d.hour
    # The hour has changed so presumably I am somewhere near the top of the hour
    # Look to see if this hour is one in which I should do a full refresh.
    if d.hour in hours:
      logging.info("shouldDoFullRefresh - hour has changed and in list; hour: %d, hours: %s",
          d.hour, hours)
      return True
    else:
      logging.info("shouldDoFullRefresh - hour has changed but not in list; hour: %d, hours: %s",
          d.hour, hours)
  return False


  
def main():
  if config.onceFull:
    fullRefresh()
  if config.oncePartial:
    partialRefresh()

  if not (config.onceFull or config.oncePartial):

    while True:
      t = time.time()
      dayChanged = hasDayChanged()
      if dayChanged:
        logging.info("main - day has changed so resetting low and high;")
        # Reset the high and low day forcast information
        dayLow = 1000
        dayHigh = -1000

      if shouldDoFullRefresh(config.hours, t):
        lastFullRefresh = t
        fullRefresh()

      logging.info("main - going to Sleep; secondsToSleep: %d", config.sleepSeconds)
      time.sleep(config.sleepSeconds)

if __name__ == '__main__':
  main()

# vim: tabstop=2 shiftwidth=2 softtabstop=2 expandtab ignorecase
