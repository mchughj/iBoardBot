
import time
import struct
import queue
import argparse

from http.server import BaseHTTPRequestHandler, HTTPServer

from functools import partial
import logging
import urllib.parse

logging.basicConfig(level=logging.DEBUG, format='(%(threadName)-10s) %(message)s')

parser = argparse.ArgumentParser(description='Server for iBoardBot')
parser.add_argument('--port', type=int, help='Port to listen on', default=8080)
parser.add_argument('--data', type=str, help='Location to save persistent data', default='./data')
config = parser.parse_args()

is_first = True

DEVICE_URL_PREFIX = "/ibb-device/"


class Client(object):
  def __init__(self, clientId):
    self.numberOfAccesses = 1
    self.clientId = clientId
    self.createdMs = round(time.time() * 1000)
    self.lastAccessMs = round(time.time() * 1000)
    self.queue = queue.Queue()

  def recordAccess(self):
    self.numberOfAccesses += 1
    self.lastAccessMs = round(time.time() * 1000)

  def getQueue(self):
    return self.queue


class ClientManager(object):
  def __init__(self):
    self.clientDevices = {}

  def getClientIds(self):
    return self.clientDevices.keys()

  def getOrMakeClient(self, clientId):
    c = self.getClient(clientId)
    if c is None:
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

  def showMainMenu(self):
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
    self.sendText("<br><br>")
    self.sendText("Clients<br>")
    self.sendText("<table style=\"width:100%\">")
    self.sendText("<tr><th>ID</th><th>Queue Size</th></tr>")
    clientIds = self.clientManager.getClientIds()
    for c in clientIds:
      self.sendText("<tr><td>")
      self.sendText(c)
      self.sendText("</td><td>")
      self.sendText(self.clientManager.getClient(c).getQueue().qsize() )
      self.sendText("</td>")
    self.sendText("</table>")
    self.sendText("</html>")

  def do_GET(self):
    logging.debug("do_GET - received a GET request; path: %s", self.path)

    if self.path.startswith("http://"):
      # Instead of just the path it appears that the path argument
      # has the entire string for the URL in it.  This shouldn't happen and
      # is likely a bug in the firmware for the iBoardBot
      parsePath = urllib.parse.urlparse(self.path)
      logging.debug("do_GET - transformed path; parsePath: %s", parsePath)

      self.path = parsePath.path
      self.args = urllib.parse.parse_qs(parsePath.query)

      logging.debug("do_GET - pulled apart path and args; path: %s, args: %s",
          self.path, self.args)
    else:
      queryArgsLocation = self.path.find("?")
      if queryArgsLocation > 0:
        self.args = urllib.parse.parse_qs(self.path[queryArgsLocation+1:])
      else:
        self.args = urllib.parse.parse_qs("")
      logging.debug("do_GET - path left alone; args: %s", self.args)

    if self.isDeviceRequest():
      logging.debug("do_GET - this is a device request;")
      self.handleDeviceRequest()
    else:
      logging.debug("do_GET - this is (potentially) a control plane request;")
      self.handleControlPlaneRequest()

  def isDeviceRequest(self):
    return self.path.startswith(DEVICE_URL_PREFIX)

  def handleDeviceRequest(self):
    clientId = self.args["ID_IWBB"][0]
    if "NUM" in self.args:
      ackBlockNumber = self.args["NUM"][0]
    else:
      ackBlockNumber = None

    self.getNextDeviceBlock(clientId, ackBlockNumber)

  def handleControlPlaneRequest(self):
    if self.path == "/":
      self.showMainMenu()
    elif self.path == "/favicon.ico":
      self.send_error(404)
    elif self.path.startswith("/puttext?"):
      clientId = self.args["ID_IWBB"][0]
      text = self.args["TEXT"][0]

      self.enqueueText(clientId, text)
    else:
      logging.debug("handleControlPlaneRequest - unknown command; path: %s",
        self.path)
      self.send_error(404)

  def getNextDeviceBlock(self, clientId, ackBlockNumber):
    logging.info("Got a device request; clientId: %s, ackBlockNumber: %s",
        clientId, ackBlockNumber)
    
    c = self.clientManager.getOrMakeClient(clientId)
    if ackBlockNumber:
      c.ackBlockNumber(ackBlockNumber)

    if is_first:
      c.getQueue().push(mockResult)
      is_first = False

    if c.getQueue().empty():
      self.sendDeviceEmptyResult()
    else:
      self.sendDeviceResult(c.getQueue().get())

  def sendDeviceEmptyResult(self):
    logging.info("sendingDeviceEmptyResult; ")

    # Any result which has less than 6 bytes in the body is considered to
    # be an empty result and will cause the device to repoll at a later time.
    self.send_response(200)
    self.send_header('Content-type', 'text/html')
    self.send_header("Content-Length", "2")
    self.end_headers()
    self.wfile.write(bytes("OK","utf-8"))

  def sendDeviceResult(self, data):
    logging.info("sendDeviceResult - data;")

    self.send_response(200)
    self.send_header('Content-type', 'text/html')
    self.send_header("Content-Length", str(len(data)))
    self.end_headers()
    self.wfile.write(data)

  def mockResult(self):
    result  = struct.pack("BBB", 0xFA, 0x9f, 0xA1 )   #   4009 4001   [FA9FA1]    # Start
    result += struct.pack("BBB", 0xFA, 0x90, 0x01 )   #   4009 0001   [FA9001]    # Block number (this number is calculated by the server)
    result += struct.pack("BBB", 0xFA, 0x1F, 0xA1 )   #   4001 4001   [FA1FA1]    # Start drawing (new draw)
    result += struct.pack("BBB", 0xFA, 0x30, 0x00 )   #   4003 0000   [FA3000]    # pen lift
    result += struct.pack("BBB", 0x00, 0x00, 0x00 )   #   0000 0000   [000000]    # Move to X = 0, Y = 0
    result += struct.pack("BBB", 0x3E, 0x83, 0xE8 )   #   1000 1000   [3E83E8]    # Move to X = 100mm, Y = 100mm
    result += struct.pack("BBB", 0xFA, 0x40, 0x00 )   #   4004 0000   [FA4000]    # pen down (draw)
    result += struct.pack("BBB", 0x5D, 0xC3, 0xE8 )   #   1500 1000   [5DC3E8]    # Move to  X = 150mm, Y = 100mm
    result += struct.pack("BBB", 0xFA, 0x30, 0x00 )   #   4003 0000   [FA3000]    # Pen lift
    result += struct.pack("BBB", 0x00, 0x00, 0x00 )   #   0000 0000   [000000]    # Move to 0,0
    result += struct.pack("BBB", 0xFA, 0x20, 0x00 )   #   4002 0000   [FA2000]    # Stop drawing

    return result

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
