
# This is a weather client that interacts with an iBoardBot server instance
# at regular intervals to display the latest weather information.
# Without special arguments the program will run forever and do a full update of the
# entire board once every 24 hours and partial updates every hour otherwise.

import argparse
import calendar
import datetime
import json
import logging
import pprint
import requests
import threading
import time
import urllib.parse

WEATHER_API = "http://api.openweathermap.org/"
FULL_WEATHER = "data/2.5/weather/"
FORECAST_WEATHER = "data/2.5/forecast/"
CITY_ID = "5809844"
CLIENT_ID = "2C3AE83E11C6"

logging.basicConfig(level=logging.DEBUG, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

parser = argparse.ArgumentParser(description='Weather client - and server - for iBoardBot')
parser.add_argument('--serverName', 
        type=str, 
        default="localhost",
        help='Server name where the board bot server is runnng.  Defaults to localhost.')

parser.add_argument('--serverPort', 
        type=int, 
        default=80,
        help='Server port where the board bot server is runnng.  Defaults to 80.')

parser.add_argument('--localPort', 
        type=int, 
        default=8080,
        help='Local port that I will listen on, when running forever, to handle incoming requests')

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


class WeatherManager(object):
  def __init__(self):
    self.currentDay = 0
    self.dayLow = 1000
    self.dayHigh = -1000
    self.lastFullRefresh = 0
    self.priorHour = 0

  def runOnceFull(self):
    self.trackDayChanges()
    self.fullRefresh()

  def runOncePartial(self):
    self.trackDayChanges()
    self.partialRefresh()

  def _runForever(self):
    while True:
      t = time.time()
      self.trackDayChanges()

      if self.shouldDoFullRefresh(config.hours, t):
        self.lastFullRefresh = t
        self.fullRefresh()

      logging.info("main - going to Sleep; secondsToSleep: %d", config.sleepSeconds)
      time.sleep(config.sleepSeconds)

  def run(self):
    t1 = threading.Thread(target=self._runForever, daemon=True)
    t1.start()

  def shouldDoFullRefresh(self, hours, t):
    d = datetime.datetime.fromtimestamp(time.time())
    if d.hour != self.priorHour:
      self.priorHour = d.hour
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

  def partialRefresh(self):
    data = self.makeWeatherRequest()
    currentTemp = data["main"]["temp"]

    (hour, hourModifier, day, dayName) = self.getDateAndTimeInformation()
    timeString = "{:02d} {}".format(hour, hourModifier)

    logging.info("partialRefresh - got information; timeString: %s, currentTemp: %s", 
        timeString, currentTemp)

    # Make the request to the boardBot server instance
    boardBotParams = {
        'ID_IWBB': CLIENT_ID,
        'time': timeString,
        'temperature': int(currentTemp),
        }

    boardRequest = requests.get(
        url = "http://{url}:{port}/updateWeather".format(url=config.serverName, port=config.serverPort),
        params = boardBotParams)
    return boardRequest.ok

  def fullRefresh(self):
    data = None
    try:
      data = self.makeWeatherRequest()
      (tempMin, tempMax) = self.getTemperatureForecast()
    except Exception as e:
      logging.exception("error in getting weather or forecast")
      return False

    currentTemp = data["main"]["temp"]
    condition = int(data["weather"][0]["id"])
    description = data["weather"][0]["description"]
    time = data["dt"]

    tempMin = min(tempMin, currentTemp)
    tempMax = max(tempMax, currentTemp)

    (hour, hourModifier, day, dayName) = self.getDateAndTimeInformation()
    timeString = "{:02d} {}".format(hour, hourModifier)
    dayString = "{:02d}".format(day)

    # Condition codes:  https://openweathermap.org/weather-conditions
    if condition == 800:
      conditionString = "SUNNY"
    elif condition > 800:
      conditionString = "CLOUDY"
    else:
      generalCondition = int(condition / 100)

      if generalCondition == 7:
        conditionString = "CLOUDY"
      elif generalCondition == 6:
        conditionString = "SNOW"
      elif generalCondition == 5:
        conditionString = "RAIN"
      elif generalCondition == 3:
        conditionString = "RAIN"
      else:
        conditionString = "UNKNOWN"

    logging.info("fullRefresh - got information; timeString: %s, currentTemp: %s, tempMin: %s, "
        "tempMax: %s, description: %s, condition: %d, conditionString: %s", timeString, 
        currentTemp, tempMin, tempMax, description, condition, conditionString)

    try:
      # Make the request to the boardBot server instance.  First clear the screen and then
      # do the full weather update.
      boardBotParams = {'ID_IWBB': CLIENT_ID }
      boardRequest = requests.get(
          url = "http://{url}:{port}/erase".format(url=config.serverName, port=config.serverPort),
          params = boardBotParams)
      if not boardRequest.ok:
        logging.info("fullRefresh - error in clearing the board")
        return False

      boardBotParams = {
          'ID_IWBB': CLIENT_ID,
          'time': timeString,
          'dayOfWeek': dayName,
          'dayOfMonth': dayString,
          'temperature': int(currentTemp),
          'minTemperature': int(tempMin),
          'maxTemperature': int(tempMax),
          'condition': conditionString,
          'description': description.upper()}
      
      logging.info("Making request to http://{url}:{port}/weather - params: {params}".format(
          url=config.serverName, port=config.serverPort, params=pprint.pformat(boardBotParams)))
      boardRequest = requests.get(
          url = "http://{url}:{port}/weather".format(url=config.serverName, port=config.serverPort),
          params = boardBotParams)
      return boardRequest.ok
    except Exception as e:
      logging.exception("error in contacting boardbot;")
      return False

  def trackDayChanges(self):
    d = datetime.datetime.fromtimestamp(time.time())
    if d.day != self.currentDay:
      self.currentDay = d.day
      logging.info("trackDayChanges - day has changed so resetting low and high;")
      # Reset the high and low day forcast information
      self.dayLow = 1000
      self.dayHigh = -1000
    else:
      return False

  def getTemperatureForecast(self):
    params = {'id':CITY_ID, 'units': 'imperial', 'appid': config.weatherAPIKey}
    r = requests.get(url = WEATHER_API + FORECAST_WEATHER, params = params) 
    data = r.json()

    logging.debug("getTemperatureForecast - fetched the forecast;")

    for i in range(12):
      itemTime = data["list"][i]["dt"]
      d = datetime.datetime.fromtimestamp(int(itemTime))
      if d.day == self.currentDay:
        itemMin = float(data["list"][i]["main"]["temp_min"])
        itemMax = float(data["list"][i]["main"]["temp_max"])
        logging.info(
            "getTemperatureForecast - found another entry for today; itemMin: %d, itemMax: %d",
            itemMin, itemMax)
        self.dayLow = min(self.dayLow, itemMin)
        self.dayHigh = max(self.dayHigh, itemMax)
        
    logging.info("getTemperatureForecast - final values; dayLow: %d, dayHigh: %d", 
        self.dayLow, self.dayHigh)
    return self.dayLow, self.dayHigh


  def makeWeatherRequest(self):
    params = {'id':CITY_ID, 'units': 'imperial', 'appid': config.weatherAPIKey}
    r = requests.get(url = WEATHER_API + FULL_WEATHER, params = params) 
    return r.json() 


  def getDateAndTimeInformation(self):
    # Use the current time and not the time found in any web requests because those responses
    # may contain times in the past so that the information is internally consisten. 
    # (e.g., the time may be a few minutes old so that it reflects the time that temperature 
    # readings were taken).
    d = datetime.datetime.fromtimestamp(time.time())

    hour = d.hour
    hourModifier = "AM"
    if hour == 0:
      # Midnight is hour zero otherwise known as 12 AM (Ante Meridiem)
      hour = 12
    elif hour >= 12:
      # Otherwise the 12th hour begins the PM cycle.  
      hourModifier = "PM"
      if hour > 12:
        # The last hour - value 23 - is 11PM.  After that hour 0 turns into 12 AM.
        hour -= 12

    dayName = calendar.day_abbr[d.weekday()].upper()

    return hour, hourModifier, d.day, dayName

class MyHandler(BaseHTTPRequestHandler):
  def __init__(self, weatherManager, *args, **kwargs):
    self.weatherManager = weatherManager
    super(MyHandler, self).__init__(*args, **kwargs)

  def sendText(self, s):
    self.wfile.write(bytes(s,"utf-8"))

  def showInfo(self):
    logging.info("showInfo")

    self.send_response(200)
    self.send_header('Content-type', 'text/html')
    self.end_headers()

    self.sendText("<html>")
    self.sendText("<head>")
    self.sendText("</head>")

    self.sendText("<h1>iBoardBoy Server</h1>")
    self.sendText("Add image to be displayed")
    self.sendText("<br><br>")
    self.sendText("<form method=\"get\" action=\"addImage\">")
    self.sendText("ClientId: <input size=\"127\" type=\"text\" name=\"ID_IWBB\" value=\"{}\"></BR>".format(clientId))
    self.sendText("Image Filename: <input size=\"127\" type=\"text\" name=\"filename\"></BR>")
    self.sendText("Scaling Factor: <input size=\"127\" type=\"text\" value=\"0\" name=\"scaleFactor\"></BR>")
    self.sendText("x: <input size=\"127\" type=\"text\" value=\"0\" name=\"x\"></BR>")
    self.sendText("y: <input size=\"127\" type=\"text\" value=\"0\" name=\"y\"></BR>")
    self.sendText("<input type=\"submit\" value=\"Submit\">")
    self.sendText("</form>")
    self.sendText("</html>")

  def getStatus(self, clientId):
    logging.info("getStatus")
    self.send_response(200)
    self.send_header('Content-type', 'text/json')

    c = self.getOrMakeClient(clientId)

    data = { 
        "clientId": clientId,
        "createdMs": c.createdMs,
        "lastAccessMs": c.lastAccessMs,
        "queueSize": c.getQueueSize(),
        }

    self.sendText(json.dumps(data))

  def showMainMenu(self, message = None):
    logging.info("showMainMenu")
    self.send_response(200)
    self.send_header('Content-type', 'text/html')
    self.end_headers()
    self.sendText("<html>")
    self.sendText("<head>")
    self.sendText("<style>")
    self.sendText("table, th, td {")
    self.sendText("  border: 1px solid black;")
    self.sendText("  border-collapse: collapse;")
    self.sendText("}")
    self.sendText("</style>")
    self.sendText("</head>")
    self.sendText("<h1>iBoardBot Server</h1>")
    self.sendText("<br>")
    if message:
      self.sendText("<font color=\"red\">(")
      self.sendText(message)
      self.sendText("</font>)</hr></br>")

    self.sendText("<br>")
    self.sendText("Clients<br>")
    self.sendText("<table style=\"width:100%\">")
    self.sendText("<tr><th>ID</th><th>Queue Size</th><th>Actions</th></tr>")
    clientIds = self.clientManager.getClientIds()
    for c in clientIds:
      self.sendText("<tr><td>")
      self.sendText(c)
      self.sendText("</td><td>")
      self.sendText(str(self.clientManager.getClient(c).getQueueSize() ))
      self.sendText("</td><td>")
      urlEncodedArgs = urllib.parse.urlencode({CLIENT_ID:c, "size":0 })
      self.sendText("[")
      self.sendText("<a href=\"/addMockDrawing?{args}\">Drawing</a>".format(args=urlEncodedArgs))
      self.sendText("|")
      urlEncodedArgs = urllib.parse.urlencode({CLIENT_ID:c, "size":1 })
      self.sendText("<a href=\"/addMockDrawing?{args}\">Big Drawing</a>".format(args=urlEncodedArgs))
      self.sendText("|")
      urlEncodedArgs = urllib.parse.urlencode({CLIENT_ID:c})
      self.sendText("<a href=\"/addImage?{args}\">Image</a>".format(args=urlEncodedArgs))
      self.sendText("|")
      urlEncodedArgs = urllib.parse.urlencode({CLIENT_ID:c})
      self.sendText("<a href=\"/addText?{args}\">Text</a>".format(args=urlEncodedArgs))
      self.sendText("|")
      urlEncodedArgs = urllib.parse.urlencode({CLIENT_ID:c})
      self.sendText("<a href=\"/clearQueue?{args}\">Clear Queue</a>".format(args=urlEncodedArgs))
      self.sendText("|")
      urlEncodedArgs = urllib.parse.urlencode({CLIENT_ID:c})
      self.sendText("<a href=\"/erase?{args}\">Erase</a>".format(args=urlEncodedArgs))
      self.sendText("|")
      urlEncodedArgs = urllib.parse.urlencode({CLIENT_ID:c, "x1":1200, "y1":
        800, "x2": 1300, "y2": 950, "finalSweep": 1})
      self.sendText("<a href=\"/erase?{args}\">Erase Middle</a>".format(args=urlEncodedArgs))
      self.sendText("]")
      self.sendText("</td>")
      self.sendText("</tr>")
    self.sendText("</table>")
    self.sendText("</html>")

  def do_GET(self):
    logging.debug("do_GET - received a GET request; path: %s", self.path)

    parsePath = urllib.parse.urlparse(self.path)
    self.path = parsePath.path
    self.args = urllib.parse.parse_qs(parsePath.query)

    logging.debug("do_GET - pulled apart path and args; path: %s, args: %s",
        self.path, self.args)

    if self.path == "/":
      self.getStatus()
    elif self.path == "/favicon.ico":
      self.send_error(404)
    elif self.path == "/doFull":
      self.weatherManager.fullRefresh()
    else:
      logging.debug("do_GET - unknown command; path: %s", self.path)
      self.send_error(404)

  def getStatus(self):
    logging.info("getStatus")
    self.send_response(200)
    self.send_header('Content-type', 'text/json')

    data = { 
        "currentDay": self.weatherManager.currentDay,
        "dayLow": self.weatherManager.dayLow,
        "dayHigh": self.weatherManager.dayHigh,
        "lastFullRefresh": self.weatherManager.lastFullRefresh,
        "priorHour": self.weatherManager.priorHour,
        }
    self.sendText(json.dumps(data))


def main():
  weatherManager = WeatherManager()
  if config.onceFull:
    weather.runOnceFull()

  if config.oncePartial:
    weather.runOncePartial()

  if not (config.onceFull or config.oncePartial):
    # Otherwise let weatherManager run forever and also start up the http server.
    weatherManager.run()
    try:
      handler = partial(MyHandler, weatherManager)
      server = ThreadingHTTPServer(('', config.localPort), handler)
      logging.info('Starting httpserver...')
      server.serve_forever()
    except KeyboardInterrupt:
      logging.info('^C received, shutting down server')
      server.socket.close()
    logging.info('Stopping...')

if __name__ == '__main__':
  main()

# vim: tabstop=2 shiftwidth=2 softtabstop=2 expandtab ignorecase
