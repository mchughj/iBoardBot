
import logging
import struct
import numpy as np
import cv2

from constants import MAX_HEIGHT, MAX_WIDTH

# screen-bbcs = This is a screen rendering boardbot command set.
# Instead of sending the commands to the board bot they are displayed.

class Bbcs(object):
  def __init__(self):
    self.penIsDown = False
    self.mat = None
    self.currentLocation = (0,0)
    self.screenNumber = 0
    self.mat = None
    self.scaleFactor = 0.33
    self.width = int(MAX_WIDTH*self.scaleFactor)
    self.height = int(MAX_HEIGHT*self.scaleFactor)
    logging.info("__init__ setting up screen area; scaleFactor: %f, "
        "MAX_WIDTH: %d, MAX_HEIGHT: %d, self.width: %d, self.height: %d",
        self.scaleFactor, MAX_WIDTH, MAX_HEIGHT, self.width, self.height)
    self.mat = np.zeros((
      self.height,
      self.width,
      3), np.uint8)

  def moveTo(self, x, y):
    y = MAX_HEIGHT - y
    newLocation = (int(self.scaleFactor * x), int(self.scaleFactor * y))
    if self.penIsDown:
      if 0:
        logging.info("moveTo - drawing line; from: %s, to: %s", self.currentLocation, newLocation)
      cv2.line(self.mat, self.currentLocation, newLocation, (255,0,0), 1, 4)
    else:
      if 0: 
        logging.info("moveTo - just relocating; newLocation: %s", newLocation)

    self.currentLocation = newLocation
    return ""

  def blockIdentifier(self, blockNumber):
    return ""

  def packetStart(self):
    return ""

  def startDrawing(self):
    return ""

  def stopDrawing(self):
    cv2.imshow(str(self.screenNumber),self.mat)
    cv2.waitKey(0)
    cv2.destroyWindow(str(self.screenNumber))
    return ""

  def liftPen(self):
    self.penIsDown = False
    return ""

  def dropPen(self):
    self.penIsDown = True
    return ""

  def eraserDown(self):
    self.penIsDown = False
    return ""

  def eraseAll(self):
    self.screenNumber += 1
    self.mat = np.zeros((
      self.height,
      self.width, 3), np.uint8)
    return ""

  def erasePortion(self, x1,y1,x2,y2):
    return ""
