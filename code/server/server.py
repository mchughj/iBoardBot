#!/home/pi/.virtualenvs/cv/bin/python

import time
import argparse
import logging

logging.basicConfig(level=logging.INFO, format='(%(threadName)-10s) %(message)s')

from http.server import BaseHTTPRequestHandler

use_threaded_server = True
try:
    from http.server import ThreadingHTTPServer
except:
    logging.info("Falling back to the standard HttpServer class")
    use_threaded_server = False
    from http.server import HTTPServer

from functools import partial
import urllib.parse
import threading
import os.path

import bbcs
import bbimage
import bbinversetextbox
import bbshape
import freetype
import bbtext
import bbfilledtext
import cv2
import socket

import json

from constants import MAX_HEIGHT, MAX_WIDTH

parser = argparse.ArgumentParser(description='Server for iBoardBot')
parser.add_argument('--port', type=int, help='Port to listen on', default=80)
parser.add_argument('--mockScreen', default=False, action = "store_true", help='Use a fake board')
config = parser.parse_args()

if config.mockScreen:
  from screen_bbcs import Bbcs
else:
  from bbcs import Bbcs

bbcs = Bbcs()

DEVICE_URL_PREFIX = "/ibb-device/"
CLIENT_ID = "ID_IWBB"

# Return the primary IP address for this box.  
def getIP():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP


def mockDrawData(size = 0):
  if size == 0:
    result  = bbcs.liftPen()
    result += bbcs.moveTo(0,0)
    result += bbcs.moveTo(1000, 1000)
    result += bbcs.dropPen() 
    result += bbcs.moveTo(1500, 1000)
    result += bbcs.liftPen()
  else:
    result  = bbcs.liftPen()
    result += bbcs.moveTo(0,0)
    for x in range(size * 2):
      for y in range(size * 5):
        result += bbcs.moveTo(1000 + (x*100), 1000 - (y*25)) 
        result += bbcs.dropPen() 
        result += bbcs.moveTo(1050 + (x*100), 1000 - (y*25))
        result += bbcs.liftPen() 

  logging.info("mockData - done; size: %d, resultSize: %d", size, len(result))
  return result


class NoWorkException(Exception):
  pass

class Client(object):

  HEADER_COMMANDS_FOR_FIRST_PACKET = 4
  SIZE_OF_COMMAND = 3
  HEADER_COMMANDS_FOR_SUBSEQUENT_PACKET = 2

  def __init__(self, clientId):
    self.numberOfAccesses = 1
    self.clientId = clientId
    self.createdMs = round(time.time() * 1000)
    self.lastAccessMs = round(time.time() * 1000)
    self.lock = threading.Lock()
    self.condition = threading.Condition()
    self.queue = []
    self.nextBlockNumber = 0
    self.nextWeatherSlot = 0

  def recordAccess(self):
    self.numberOfAccesses += 1
    self.lastAccessMs = round(time.time() * 1000)

  def popQueueUntilBlockNumber(self, blockNumber):
    logging.info("popQueueUntilBlockNumber - onEnter; blockNumber: %d", blockNumber)
    numPopped = 0
    with self.condition:
      while len(self.queue):
        logging.info("popQueueUntilBlockNumber - queue has more items; len: %d", len(self.queue))
        (qBlockNumber, qItem) = self.queue[0]
        logging.info("popQueueUntilBlockNumber - top of queue; qBlockNumber: %d", qBlockNumber)
        if qBlockNumber <= blockNumber:
          numPopped += 1
          self.queue = self.queue[1:]
        else:
          break
      logging.info("popQueueUntilBlockNumber - done with work; numPopped: %d, size of Queue remaining: %d", numPopped, len(self.queue))

  def clearQueue(self):
    with self.condition:
      self.queue = []

  def addNewDrawing(self, payload):
    # The data can be arbitrary size and we need to break it up into sizes at
    # most 768 - HEADER_SIZE bytes long at a maximum that can be transferred in
    # a single chunk.

    # First add the footer to the payload
    data = self._addFooterToData(payload)

    numBlocks = 0;
    headerSize = Client.HEADER_COMMANDS_FOR_FIRST_PACKET * Client.SIZE_OF_COMMAND
    isFirst = True

    with self.condition:
      while len(data) > 0:
        numBlocks+=1
        dataSize = len(data)
        if dataSize + headerSize > 768:
          dataSize = 768 - headerSize

        self._addNewBlock(isFirst, data[:dataSize])
        data = data[dataSize:]

        headerSize = Client.HEADER_COMMANDS_FOR_SUBSEQUENT_PACKET * Client.SIZE_OF_COMMAND
        isFirst = False
      self.condition.notify()

    logging.info("addNewDrawing - done; numBlocks: %d", numBlocks)

  def _addHeaderToData(self, isFirst, blockNumber, payload):
    result  = bbcs.packetStart()
    result += bbcs.blockIdentifier(blockNumber) 

    if isFirst:
      result += bbcs.startDrawing()
      result += bbcs.liftPen()

    result += payload
    return result

  def _addFooterToData(self, payload):
    result  = payload 
    result += bbcs.liftPen()
    result += bbcs.moveTo(0,0)
    result += bbcs.stopDrawing()
    return result

  def _addNewBlock(self, isFirst, data):
    if len(self.queue) == 0:
      self.nextBlockNumber = 0

    self.nextBlockNumber += 1
    data = self._addHeaderToData(isFirst, self.nextBlockNumber, data)

    logging.info("addNewBlock - enqueue; nextBlockNumber: %d, size: %d, isFirst: %s", self.nextBlockNumber, len(data), str(isFirst))

    entry = (self.nextBlockNumber, data)
    self.queue.append(entry)

  def getNextBlock(self, timeoutSeconds):
    with self.condition:
      while len(self.queue) == 0:
        result = self.condition.wait(timeoutSeconds)
        if result == False:
          logging.info("getNextResult - no work available; timeoutSeconds: %d", timeoutSeconds)
          raise NoWorkException()

      (blockNumber, data) = self.queue[0]
      logging.info("getNextBlock - found a block; blockNumber: %d", blockNumber)
      return (blockNumber, data)

  def getQueueSize(self):
    with self.condition:
      return len(self.queue)

  def getNextWeatherSlot(self):
      return self.nextWeatherSlot

  def setNextWeatherSlot(self, slot):
      self.nextWeatherSlot = slot


class ClientManager(object):
  def __init__(self):
    self.clientDevices = {}

  def getClientIds(self):
    return self.clientDevices.keys()

  def getOrMakeClient(self, clientId):
    c = self.getClient(clientId)
    if c is None:
      logging.info("getOrMakeClient - creating new client; clientId: %s", clientId);
      c = Client(clientId)
      self.clientDevices[clientId] = c
    return c

  def getClient(self, clientId):
    if clientId in self.clientDevices.keys():
      c = self.clientDevices[clientId]
      c.recordAccess()
      return c
    else:
      return None


class MyHandler(BaseHTTPRequestHandler):
  def __init__(self, clientManager, *args, **kwargs):
    self.clientManager = clientManager
    super(MyHandler, self).__init__(*args, **kwargs)

  def sendText(self, s):
    self.wfile.write(bytes(s,"utf-8"))

  def showAddTextScreen(self, clientId):
    logging.info("showAddTextScreen")

    self.send_response(200)
    self.send_header('Content-type', 'text/html')
    self.end_headers()

    self.sendText("<html>")
    self.sendText("<head>")
    self.sendText("</head>")

    self.sendText("<h1>iBoardBoy Server</h1>")
    self.sendText("Add text to be displayed")
    self.sendText("<br><br>")
    self.sendText("<form method=\"get\" action=\"addText\">")
    self.sendText("Text: <input size=\"127\" type=\"text\" name=\"s\"></BR>")
    self.sendText("ClientId: <input size=\"127\" type=\"text\" name=\"ID_IWBB\" value=\"{}\"></BR>".format(clientId))
    self.sendText("Size: <input size=\"127\" type=\"text\" value=\"256\" name=\"size\"></BR>")
    self.sendText("Font: <input size=\"127\" type=\"text\" value=\"{}\" name=\"f\"></BR>".format(os.path.join(os.path.dirname(__file__),'fonts','Exo2-Bold.otf')))
    self.sendText("x: <input size=\"127\" type=\"text\" value=\"0\" name=\"x\"></BR>")
    self.sendText("y: <input size=\"127\" type=\"text\" value=\"0\" name=\"y\"></BR>")
    self.sendText("<input type=\"submit\" value=\"Submit\">")
    self.sendText("</form>")
    self.sendText("</html>")

  def showAddImageScreen(self, clientId):
    logging.info("showAddImageScreen")

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
    self.send_header('Content-type', 'application/json')
    self.end_headers()

    c = self.clientManager.getOrMakeClient(clientId)

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

    self.sendText("Weather server can be found <a href=\"http://{IP}:8080/\">here</a>.<BR>".format(IP=getIP()))
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

    if self.isDeviceRequest():
      logging.debug("do_GET - this is a device request;")
      self.handleDeviceRequest()
    else:
      logging.debug("do_GET - this is (potentially) a control plane request;")
      self.handleControlPlaneRequest()

  def isDeviceRequest(self):
    return self.path.startswith(DEVICE_URL_PREFIX)

  def clearQueue(self, clientId):
    c = self.clientManager.getClient(clientId)
    c.clearQueue()

  def erase(self, clientId, veryClean=False):
    c = self.clientManager.getOrMakeClient(clientId)
    logging.info("erase - received a request; clientId: %s, queue size: %d, veryClean: %s", clientId,
        c.getQueueSize(), str(veryClean))
    c.addNewDrawing(bbcs.eraseAll())
    c.addNewDrawing(bbcs.eraseAll(offset=25, moveY=50))
    logging.info("erase - done enqueueing work; queue size: %d", c.getQueueSize())

  def erasePortion(self, clientId, x1, y1, x2, y2, finalSweep):
    if not x1 < x2:
      raise "X1 must be less than x2"
    if not y1 < y2:
      raise "Y1 must be less than Y2"

    c = self.clientManager.getClient(clientId)
    c.addNewDrawing(bbcs.erasePortion(x1,y1,x2,y2,finalSweep))

  def addMockDrawing(self, clientId, size):
    c = self.clientManager.getOrMakeClient(clientId)
    c.addNewDrawing(mockDrawData(size))

  def addImage(self, clientId, filename, scaleFactor, x, y):
    c = self.clientManager.getOrMakeClient(clientId)

    i = bbimage.Image(bbcs)
    i.setImageCharacteristics(scaleFactor)
    i.genFromFile(filename)

    (w, h) = i.getDimensions()

    if y == 0:
      y = MAX_HEIGHT - int((MAX_HEIGHT - h)/2)
    if x == 0:
      x = int((MAX_WIDTH - w) / 2)

    logging.debug("addImage - getting string; w: %d, h: %d, x: %d, y: %d", 
        w, h, x, y)

    c.addNewDrawing(i.getDrawString(x, y))


  # addWeatherStartOfDay is a different type of weather view from the normal
  # 'addWeather' mechanism.  In this one at the start of the day a call to
  # clear the board is made and then a call to here is made.  This outlines the
  # weather information available at the start of the day.  As the day
  # progresses then the additional datapoints, however many there are, are
  # added to the same board without clearing the screen.  
  #
  # Here is an example URL invocation:
  #   http://localhost:8080/weatherStartOfDay?ID_IWBB=111&dayOfWeek=Wed&dayOfMonth=2&time=12&temperature=101&minTemperature=32&maxTemperature=132&description=Cloudy&condition=CLOUDY&iconFilename=w/rain.png
  #
  def addWeatherStartOfDay(self, clientId, dayOfWeek, dayOfMonth, time, temperature,
      minTemperature, maxTemperature, description, iconFilename):
    logging.info("addWeatherStartOfDay - received the request to add the weather")

    c = self.clientManager.getOrMakeClient(clientId)
    s = ""

    # The display is setup in two regions
    #
    # +----------------------------------------------------------------------------------+
    # |    Weds     |                          Time 1 - Temperature  X                   |
    # |             |                          Time 2 - Temperature  Y                   |
    # |    DAY      |                                                                    |
    # |  Of MONTH   |                                                                    |
    # |             |                                                                    |
    # |  Min/Max    |                                                                    |
    # |   Temp      |                                                                    |
    # +----------------------------------------------------------------------------------+
    #        middleColumnLeft     
    middleColumnLeft = 1000

    # ---------------------------------------------
    # Draw the vertical line separating the regions
    # ---------------------------------------------
    l = bbshape.VLine(bbcs)
    l.setHeight(1000)
    l.gen()
    s = l.getDrawString(offsetX=middleColumnLeft, offsetY=50)
    c.addNewDrawing(s)
    s = ""

    # ------------------
    # Draw Left region
    # ------------------

    # Draw the day of the week (e.g., "Wed").
    y = 850
    x = 200
    width = 700
    height = 250
    t = bbtext.Text(bbcs)
    t.setFontCharacteristics(os.path.join(os.path.dirname(__file__),'fonts','Exo2-Bold.otf'), 256)
    t.setString(dayOfWeek)
    t.gen()
    c.addNewDrawing(t.getDrawString((x, y, width, height)))

    # Generate date component of the display
    width = 700
    height = 500
    y = 300 + height
    x = 210
    
    t = bbinversetextbox.InverseTextBox(bbcs, width, height)
    t.setRoundedRectangle(True)
    t.setString(dayOfMonth)
    t.gen()
    c.addNewDrawing(t.getDrawString(x, y))

    # Draw the estimated range of min and max temperature.  
    # This isn't super accurate but Kathi likes to see it.
    y = 80
    x = 225
    width = 700
    height = 120
    
    t = bbtext.Text(bbcs)
    t.setFontCharacteristics(os.path.join(os.path.dirname(__file__),'fonts','cnc_v.ttf'), size=128, sizeBetweenCharacters=20, spaceSize=35)
    t.setString(minTemperature + " / " + maxTemperature)
    t.setBoxed(False)
    t.gen()
    c.addNewDrawing(t.getDrawString((x, y, width, height)))

    # -----------------
    # Draw right region
    # -----------------
    s = self.drawWeatherInfoSlotted(slot=0, x=middleColumnLeft, time=time, temperature=temperature, description=description, iconFilename=iconFilename)

    c.addNewDrawing(s)
    c.setNextWeatherSlot(1)

    self.send_response(200)
    self.send_header('Content-type', 'text/html')
    self.end_headers()

  def drawWeatherInfoSlotted(self, x, slot, time, temperature, description, iconFilename):
    # Draw a single 'row' in the slotted information as the day progresses.
    # Overall it looks like this:
    #
    # +----------------------------------------------------------------------------------+
    # | Hour | am/pm |  Temperature  | Image | Description (roughly 12 characters)       |
    # +----------------------------------------------------------------------------------+
    #
    hourLeft = x + 100
    ampmLeft = x + 350
    temperatureLeft = x + 600 
    imageLeft = x + 1010
    descriptionLeft = x + 1255

    height = 150
    y = 950 - (slot * 200) 

    hour = time[0:2]
    ampmString = time[-2:]

    logging.info( "drawWeatherInfoSlotted - going to draw text; x: {x}, y: {y}, slot: {slot}, height: {height}, time: {time}, hour: {hour}, ampmp: {ampmString}, temperature: {temp}, description: {d}".format(x=x, y=y, slot=slot, height=height, time=time, hour=hour, ampmString=ampmString, temp=temperature, d=description))

    t = bbtext.Text(bbcs)
    t.setFontCharacteristics(os.path.join(os.path.dirname(__file__),'fonts','cnc_v.ttf'), size=164, sizeBetweenCharacters=30, spaceSize=45)
    t.setString(hour)
    t.setBoxed(False)
    t.gen()
    result = t.getDrawString((hourLeft, y))

    t.setString(ampmString)
    t.gen()
    result += t.getDrawString((ampmLeft, y))

    t.setString("- " + temperature) 
    t.setSpaceSize(15)
    t.gen()
    result += t.getDrawString((temperatureLeft, y))

    # Add the little circle for the degrees
    circle = bbshape.Circle(bbcs)
    circle.setRadius(15)
    circle.gen()
    result += circle.getDrawString(
        t.getTextLowerLeftX() + t.getTextDimensions()[0], 
        (y + t.getTextDimensions()[1]))

    i = bbimage.Image(bbcs)
    i.setImageCharacteristics(1)
    i.genFromFile("imgs/{}".format(iconFilename))
    (w, h) = i.getDimensions()
    result += i.getDrawString(imageLeft, y+h)

    # Add the description
    t.setString(description)
    t.setBoxed(False)
    t.gen()
    result += t.getDrawString((descriptionLeft, y))

    return result

  # addWeatherDatapoint will add a new datapoint to the existing weather
  # display.  This is purely addative and requires the first call to
  # addWeatherStartOfDay to be called to establish the base view and the first
  # datapoint.
  def addWeatherDatapoint(self, clientId, time, temperature, description, iconFilename):
    logging.info("addWeatherDatapoint - received the request to add the next line to the weather display")

    c = self.clientManager.getOrMakeClient(clientId) 
    slot = c.getNextWeatherSlot()

    middleColumnLeft = 1000

    c.addNewDrawing( self.drawWeatherInfoSlotted(slot=slot, x=middleColumnLeft, time=time, temperature=temperature, description=description, iconFilename=iconFilename))
    c.setNextWeatherSlot(slot+1)

    self.send_response(200)
    self.send_header('Content-type', 'text/html')
    self.end_headers()

  def addWeather(self, clientId, dayOfWeek, dayOfMonth, time, temperature,
      minTemperature, maxTemperature, description, conditionString):
    logging.info("addWeather - received the request to add the weather")
    c = self.clientManager.getOrMakeClient(clientId)

    # Seperator for the date from the weather
    l = bbshape.VLine(bbcs)
    l.setHeight(900)
    l.gen()
    s = l.getDrawString(1150, 100)

    rhsX = 1275
    rhsFullWidth = 2175

    # Current temperature
    width = rhsFullWidth
    height = 375
    x = rhsX
    y = 950
    t = bbfilledtext.FilledText(bbcs, width, height)
    t.setBoxed(True)
    t.setFontCharacteristics(cv2.FONT_HERSHEY_SIMPLEX, 10, 25)
    t.setString(time + " - " + temperature)
    t.gen()
    s += t.getDrawString(x, y)

    logging.info("addWeather - going to draw the circle; t.getDimensions: %s",
        t.getDimensions())

    circle = bbshape.Circle(bbcs)
    circle.setRadius(20)
    circle.gen()
    s += circle.getDrawString(
        x + t.getTextLowerLeftX() + t.getDimensions()[0], 
        (y - height) + (t.getDimensions()[1] + 95))

    width = rhsFullWidth - 700
    height = 225
    x = rhsX + 600
    y = 350
    t = bbtext.Text(bbcs)
    t.setFontCharacteristics(os.path.join(os.path.dirname(__file__),'fonts','Exo2-Bold.otf'), 150)
    t.setString(minTemperature + " / " + maxTemperature)
    t.setBoxed(False)
    t.gen()
    s += t.getDrawString((x, y))

    width = rhsFullWidth - 700
    height = 275
    x = rhsX + 600
    y = 90
    t = bbtext.Text(bbcs)
    t.setFontCharacteristics(os.path.join(os.path.dirname(__file__),'fonts','Exo2-Bold.otf'), 164)
    t.setString(description)
    t.setBoxed(False)
    t.gen()
    s += t.getDrawString((x, y))

    c.addNewDrawing(s)

    iconFile = None
    if conditionString == "SUNNY":
      iconFile = "imgs/sunny.png"
    elif conditionString == "CLOUDY":
      iconFile = "imgs/cloudy.png"
    elif conditionString == "SNOW":
      iconFile = "imgs/snow.png"
    elif conditionString == "RAIN":
      iconFile = "imgs/rain.png"
    else:
      logging.info("addWeather - unknown condition string; conditionString: %s",
          conditionString)
      iconFile = "imgs/question.png"

    i = bbimage.Image(bbcs)
    i.setImageCharacteristics(2)
    i.genFromFile(iconFile)
    (w, h) = i.getDimensions()

    x = rhsX + 50
    y = 490
    c.addNewDrawing(i.getDrawString(x, y))

    y = 800
    x = 250
    width = 700
    height = 250
    t = bbtext.Text(bbcs)
    t.setFontCharacteristics(os.path.join(os.path.dirname(__file__),'fonts','Exo2-Bold.otf'), 256)
    t.setString(dayOfWeek)
    t.gen()
    c.addNewDrawing(t.getDrawString((x, y, width, height)))

    # Generate date component of the display
    width = 700
    height = 500
    y = 140 + height
    x = 275
    
    t = bbinversetextbox.InverseTextBox(bbcs, width, height)
    t.setRoundedRectangle(True)
    t.setString(dayOfMonth)
    t.gen()
    c.addNewDrawing(t.getDrawString(x, y))

    self.send_response(200)
    self.send_header('Content-type', 'text/html')
    self.end_headers()

  def addText(self, clientId, s, x, y, fontFace, size):
    c = self.clientManager.getOrMakeClient(clientId)

    t = bbtext.Text(bbcs)
    t.setFontCharacteristics(fontFace, size)
    t.setString(s)
    t.gen()

    (w, h) = t.getDimensions()

    if y == 0:
      y = int((MAX_HEIGHT - h) / 2)
    if x == 0:
      x = int((MAX_WIDTH - w) / 2)

    c.addNewDrawing(t.getDrawString((x, y)))

  def handleDeviceRequest(self):
    clientId = self.args[CLIENT_ID][0]
    if "NUM" in self.args:
      ackBlockNumber = int(self.args["NUM"][0])
    else:
      ackBlockNumber = None

    self.getNextDeviceBlock(clientId, ackBlockNumber)

  def handleControlPlaneRequest(self):
    if self.path == "/":
      self.showMainMenu()
    elif self.path == "/favicon.ico":
      self.send_error(404)
    elif self.path == "/clearQueue":
      clientId = self.args[CLIENT_ID][0]
      self.clearQueue(clientId)
      self.showMainMenu("Queue cleared!")
    elif self.path == "/erase":
      clientId = self.args[CLIENT_ID][0]
      veryClean = False
      if "VERY_CLEAN" in self.args:
        veryClean = True

      if "x1" in self.args:
        x1 = int(self.args["x1"][0])
        x2 = int(self.args["x2"][0])
        y1 = int(self.args["y1"][0])
        y2 = int(self.args["y2"][0])
        self.erasePortion(clientId, x1, y1, x2, y2, false)
      else:
        self.erase(clientId, veryClean)

      self.showMainMenu("Erased!")
    elif self.path == "/addMockDrawing":
      clientId = self.args[CLIENT_ID][0]
      size = int(self.args["size"][0])
      self.addMockDrawing(clientId, size)
      self.showMainMenu("Mock drawing added!")

    elif self.path == "/addImageScreen":
      clientId = self.args[CLIENT_ID][0]
      self.showAddImageScreen(clientId)

    elif self.path == "/addImage":
      clientId = self.args[CLIENT_ID][0]

      if not "filename" in self.args:
        self.showAddImageScreen(clientId)
      else:
        scaleFactor = float(self.args["scaleFactor"][0])
        filename = self.args["filename"][0]
        x = int(self.args["x"][0])
        y = int(self.args["y"][0])
        self.addImage(clientId, filename, scaleFactor, x, y)
        self.showMainMenu("Image added!")

    elif self.path == "/addTextScreen":
      clientId = self.args[CLIENT_ID][0]
      self.showAddTextScreen(clientId)
    elif self.path == "/addText":
      clientId = self.args[CLIENT_ID][0]
      if not "s" in self.args:
        self.showAddTextScreen(clientId)
      else:
        size = int(self.args["size"][0])
        f = self.args["f"][0]
        s = self.args["s"][0]
        x = int(self.args["x"][0])
        y = int(self.args["y"][0])
        self.addText(clientId, s, x, y, f, size)
        self.showMainMenu("Text added!")

    elif self.path == "/weather":
      clientId = self.args[CLIENT_ID][0]
      dayOfWeek = self.args["dayOfWeek"][0]
      dayOfMonth = self.args["dayOfMonth"][0]
      time = self.args["time"][0]
      temperature = self.args["temperature"][0]
      minTemperature = self.args["minTemperature"][0]
      maxTemperature = self.args["maxTemperature"][0]
      description = self.args["description"][0]
      condition = self.args["condition"][0]
      self.addWeather(clientId, dayOfWeek, dayOfMonth, time, temperature,
          minTemperature, maxTemperature, description, condition)

      self.showMainMenu("Showed weather")

    elif self.path == "/weatherStartOfDay":
      clientId = self.args[CLIENT_ID][0]
      dayOfWeek = self.args["dayOfWeek"][0]
      dayOfMonth = self.args["dayOfMonth"][0]
      time = self.args["time"][0]
      temperature = self.args["temperature"][0]
      minTemperature = self.args["minTemperature"][0]
      maxTemperature = self.args["maxTemperature"][0]
      description = self.args["description"][0]
      iconFilename = self.args["iconFilename"][0]
      self.addWeatherStartOfDay(clientId, dayOfWeek, dayOfMonth, time, temperature,
          minTemperature, maxTemperature, description, iconFilename)

      self.showMainMenu("Showed weather start of day")

    elif self.path == "/weatherDatapoint":
      clientId = self.args[CLIENT_ID][0]
      time = self.args["time"][0]
      temperature = self.args["temperature"][0]
      description = self.args["description"][0]
      iconFilename = self.args["iconFilename"][0]
      self.addWeatherDatapoint(clientId, time, temperature, description, iconFilename)

      self.showMainMenu("Showed weather datapoint")


    elif self.path.startswith("/puttext?"):
      clientId = self.args[CLIENT_ID][0]
      text = self.args["TEXT"][0]

      self.enqueueText(clientId, text)
    elif self.path.startswith("/status"):
      clientId = self.args[CLIENT_ID][0]

      self.getStatus(clientId)
    else:
      logging.debug("handleControlPlaneRequest - unknown command; path: %s",
        self.path)
      self.send_error(404)

  def getNextDeviceBlock(self, clientId, ackBlockNumber):
    logging.info("getNextDeviceBlock - Got a request; clientId: %s, ackBlockNumber: %s",
        clientId, ackBlockNumber)
    
    c = self.clientManager.getOrMakeClient(clientId)
    if ackBlockNumber:
      c.popQueueUntilBlockNumber(ackBlockNumber)

    try:
      (blockNumber, data) = c.getNextBlock(timeoutSeconds=10)
      self.sendDeviceResult(data)
    except NoWorkException:
      self.sendDeviceEmptyResult()


  def sendDeviceEmptyResult(self):
    logging.debug("sendingDeviceEmptyResult; ")

    # Any result which has less than 6 bytes in the body is considered to
    # be an empty result and will cause the device to repoll at a later time.
    self.send_response(200)
    self.send_header('Content-type', 'text/html')
    self.send_header("Content-Length", "2")
    self.end_headers()
    self.sendText("OK")

  def sendDeviceResult(self, data):
    logging.info("sendDeviceResult - onEnter;")

    self.send_response(200)
    self.send_header('Content-type', 'text/html')
    self.send_header("Content-Length", str(len(data)))
    self.end_headers()
    self.wfile.write(data)


  def do_POST(self):
    # TODO: I need to accept post requests for images and other 
    # use cases.  Must extend/write this.
    body = self.rfile.read(int(self.headers.getheader('Content-Length')))

    self.send_response(200)
    self.send_header("Content-Type", "text/ascii")
    self.send_header("Content-Length", "2")
    self.end_headers()
    self.wfile.write("OK")

  
def main():
  clientManager = ClientManager()
  try:
    handler = partial(MyHandler, clientManager)
    if use_threaded_server:
        server = ThreadingHTTPServer(('', config.port), handler)
    else:
        server = HTTPServer(('', config.port), handler)

    logging.info('Starting httpserver...')
    server.serve_forever()
  except KeyboardInterrupt:
    logging.info('^C received, shutting down server')
    server.socket.close()
  logging.info('Stopping...')

if __name__ == '__main__':
  main()

# vim: tabstop=2 shiftwidth=2 softtabstop=2 expandtab ignorecase
