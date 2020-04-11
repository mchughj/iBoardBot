
import cv2
import numpy as np
import bbimage

class InverseTextBox(object):
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

  def setFontCharacteristics(self, font, fontScale, fontLineThickness):
    self.font = font
    self.fontScale = fontScale
    self.fontLineThickness = fontLineThickness

  def setRoundedRectangle(self, isRoundedRectangle):
    self.isRoundedRectangle = isRoundedRectangle

  def setString(self, string):
    self.string = string

  def gen(self):
    # Create white lines through the black image that provides a place where
    # the white text will show up on top of.
    self.mat[20:-20:24,20:-20] = 255

    textWidth, textHeight = cv2.getTextSize(
            self.string, 
            self.font,
            self.fontScale, 
            self.fontLineThickness)[0]

    bottomLeftCornerOfText = (int((self.width - textWidth) / 2), 
            self.height - int((self.height - textHeight) / 2))
    cv2.putText(self.mat, self.string, bottomLeftCornerOfText, self.font,
            self.fontScale, self.fontColor, self.fontLineThickness)

    if self.isRoundedRectangle:
      self.genRoundedRectangle(self.mat, self.width, self.height)

    self.bbImage = bbimage.Image(self.bbcs)
    self.bbImage.genFromImage(self.mat)

  def genRoundedRectangle(self, mat, w, h):
    borderRadius = 60
    thickness = 1
    edgeShift = 1
    color = 255

    cv2.line(mat, (borderRadius, edgeShift), (w - borderRadius, edgeShift), color, 4)
    cv2.line(mat, (borderRadius, h-thickness), (w - borderRadius, h - thickness), color, thickness)
    cv2.line(mat, (edgeShift, borderRadius), (edgeShift, h - borderRadius), color, thickness)
    cv2.line(mat, (w - thickness, borderRadius), (w - thickness, h - borderRadius), color, thickness)

    cv2.ellipse(mat, (borderRadius+ edgeShift, borderRadius+edgeShift), (borderRadius, borderRadius), 180, 0, 90, color, thickness)
    cv2.ellipse(mat, (w-(borderRadius+thickness), borderRadius), (borderRadius, borderRadius), 270, 0, 90, color, thickness)
    cv2.ellipse(mat, (w-(borderRadius+thickness), h-(borderRadius + thickness)), (borderRadius, borderRadius), 10, 0, 90, color, thickness)
    cv2.ellipse(mat, (borderRadius+edgeShift, h-(borderRadius + thickness)), (borderRadius, borderRadius), 90, 0, 90, color, thickness)

  def getDrawString(self, offsetX, offsetY):
    return self.bbImage.getDrawString(offsetX, offsetY)
