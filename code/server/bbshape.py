
import cv2
import numpy as np
import bbimage
import logging

class VLine(object):
  def __init__(self, bbcs):
    self.bbcs = bbcs
    self.height = 0

  def setHeight(self, height):
    self.height = height

  def gen(self):
    pass

  def getDrawString(self, offsetX, offsetY):
    result  = self.bbcs.liftPen()
    result += self.bbcs.moveTo(offsetX, offsetY)
    result += self.bbcs.dropPen()
    result += self.bbcs.moveTo(offsetX, offsetY+self.height)
    result += self.bbcs.liftPen()

    return result

class Circle(object):
  def __init__(self, bbcs):
    self.bbcs = bbcs
    self.radius = 10
    self.thickness = 1

  def setRadius(self, radius):
    self.radius = radius

  def setThickness(self, thickness):
    self.thickness = thickness

  def gen(self):
    self.mat = np.zeros((
      self.radius*2,
      self.radius*2,
      1), np.uint8)
    cv2.circle(self.mat, (self.radius, self.radius), self.radius, 255,
        self.thickness)

  def getDrawString(self, offsetX, offsetY):
    self.bbImage = bbimage.Image(self.bbcs)
    self.bbImage.genFromImage(self.mat)

    return self.bbImage.getDrawString(offsetX, offsetY)
