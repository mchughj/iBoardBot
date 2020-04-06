
import time
import argparse

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from functools import partial
import logging
import urllib.parse
import threading

import bbcs
import bbimage
import freetype
import bbtext

from constants import MAX_HEIGHT, MAX_WIDTH

logging.basicConfig(level=logging.DEBUG, format='(%(threadName)-10s) %(message)s')

parser = argparse.ArgumentParser(description='Server for iBoardBot')
parser.add_argument('--port', type=int, help='Port to listen on', default=8080)
parser.add_argument('--data', type=str, help='Location to save persistent data', default='./data')
config = parser.parse_args()

DEVICE_URL_PREFIX = "/ibb-device/"
CLIENT_ID = "ID_IWBB"


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

  HEADER_COMMANDS_FOR_FIRST_PACKET = 3
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

    result += payload
    return result

  def _addFooterToData(self, payload):
    result  = payload 
    result += bbcs.moveTo(0,0)
    result += bbcs.stopDrawing()
    return result

  def _addNewBlock(self, isFirst, data):
    if len(self.queue) == 0:
      self.nextBlockNumber = 0

    self.nextBlockNumber += 1
    data = self._addHeaderToData(isFirst, self.nextBlockNumber, data)

    logging.info("addNewBlock - enqueue; nextBlockNumber: %d, size: %d", self.nextBlockNumber, len(data))

    entry = (self.nextBlockNumber, data)
    self.queue.append(entry)

  def getNextBlock(self, timeoutSeconds):
    logging.info("getNextBlock - on enter;")
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
    self.sendText("Font: <input size=\"127\" type=\"text\" value=\"fonts\\Exo2-Bold.otf\" name=\"f\"></BR>")
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
      urlEncodedArgs = urllib.parse.urlencode({CLIENT_ID:c, "x1":1200, "y1": 800, "x2": 1300, "y2": 950})
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

  def erase(self, clientId):
    c = self.clientManager.getClient(clientId)
    c.addNewDrawing(bbcs.eraseAll())

  def erasePortion(self, clientId, x1, y1, x2, y2):
    if not x1 < x2:
      raise "X1 must be less than x2"
    if not y1 < y2:
      raise "Y1 must be less than Y2"

    c = self.clientManager.getClient(clientId)
    c.addNewDrawing(bbcs.erasePortion(x1,y1,x2,y2))

  def addMockDrawing(self, clientId, size):
    c = self.clientManager.getClient(clientId)
    c.addNewDrawing(mockDrawData(size))

  def addImage(self, clientId, filename, scaleFactor, x, y):
    c = self.clientManager.getClient(clientId)

    i = bbimage.Image()
    i.setImageCharacteristics(scaleFactor)
    i.setFilename(filename)
    i.gen()

    (w, h) = i.getDimensions()

    if y == 0:
      y = MAX_HEIGHT - int((MAX_HEIGHT - h)/2)
    if x == 0:
      x = int((MAX_WIDTH - w) / 2)

    logging.debug("addImage - going get drawing string; w: %d, h: %d, x: %d, y: %d", 
        w, h, x, y)

    c.addNewDrawing(i.getDrawString(x, y))

  def addText(self, clientId, s, x, y, fontFace, size):
    c = self.clientManager.getClient(clientId)

    t = bbtext.Text()
    t.setFontCharacteristics(fontFace, size)
    t.setString(s)
    t.gen()

    (w, h) = t.getDimensions()

    if y == 0:
      y = int((MAX_HEIGHT - h) / 2)
    if x == 0:
      x = int((MAX_WIDTH - w) / 2)

    c.addNewDrawing(t.getDrawString(x, y))

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

      if "x1" in self.args:
        x1 = int(self.args["x1"][0])
        x2 = int(self.args["x2"][0])
        y1 = int(self.args["y1"][0])
        y2 = int(self.args["y2"][0])
        self.erasePortion(clientId, x1, y1, x2, y2)
      else:
        self.erase(clientId)

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

    elif self.path.startswith("/puttext?"):
      clientId = self.args[CLIENT_ID][0]
      text = self.args["TEXT"][0]

      self.enqueueText(clientId, text)
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
    logging.info("sendingDeviceEmptyResult; ")

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
    # Jason :: TODO: I need to accept post requests for images and other 
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
    server = ThreadingHTTPServer(('', config.port), handler)
    logging.info('Starting httpserver...')
    server.serve_forever()
  except KeyboardInterrupt:
    logging.info('^C received, shutting down server')
    server.socket.close()
  logging.info('Stopping...')

if __name__ == '__main__':
  main()

# vim: tabstop=2 shiftwidth=2 softtabstop=2 expandtab ignorecase