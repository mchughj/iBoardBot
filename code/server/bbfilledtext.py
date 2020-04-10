
import cv2
import numpy as np
import bbimage
import logging

class FilledText(object):
  def __init__(self, bbcs, width, height):
    self.bbcs = bbcs
    self.width = width
    self.height = height
    self.mat = np.zeros((
      height,
      width,
      1), np.uint8)

    # Default values
    self.font = cv2.FONT_HERSHEY_SIMPLEX
    self.fontScale = 15
    self.fontColor = 255
    self.fontLineThickness = 50
    self.isBoxed = False

  def setBoxed(self, isBoxed):
    self.isBoxed = isBoxed

  def setFontCharacteristics(self, font, fontScale, fontLineThickness):
    self.font = font
    self.fontScale = fontScale
    self.fontLineThickness = fontLineThickness

  def setString(self, string):
    self.string = string

  def getDimensions(self):
    return (self.textWidth, self.textHeight)

  def getTextLowerLeftX(self):
    return self.textStartLowerLeftX

  def getTextLowerLeftY(self):
    return self.textStartLowerLeftY

  def gen(self):
    self.textWidth, self.textHeight = cv2.getTextSize(
            self.string, 
            self.font,
            self.fontScale, 
            self.fontLineThickness)[0]

    self.textStartLowerLeftX = int((self.width - self.textWidth) / 2) 
    self.textStartLowerLeftY = self.height - int((self.height - self.textHeight) / 2)

    cv2.putText(self.mat, 
            self.string, 
            (self.textStartLowerLeftX, self.textStartLowerLeftY), 
            self.font,
            self.fontScale, 
            self.fontColor, 
            self.fontLineThickness)

    # After we have drawn the black text now we put small white lines through the text
    # so that the contours generate appropriate lines for the entire filled in area.
    # No worries about the white lines as the pen is thicker than the distance captured
    # between the resulting contours.
    self.mat[::2,:] = 0

    cv2.rectangle(self.mat, (0,0), (self.width-1, self.height-1), 255, 1)

    self.bbImage = bbimage.Image(self.bbcs)
    self.bbImage.genFromImage(self.mat)

  def getDrawString(self, offsetX, offsetY):
    return self.bbImage.getDrawString(offsetX, offsetY)
