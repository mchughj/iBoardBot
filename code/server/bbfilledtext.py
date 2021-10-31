
import cv2
import numpy as np
import bbimage

class FilledText(object):
  def __init__(self, bbcs, width, height, centered = True):
    self.bbcs = bbcs
    self.width = width
    self.height = height
    self.centered = centered
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
    (self.textWidth, self.textHeight), self.baseline = cv2.getTextSize(
            self.string, 
            self.font,
            self.fontScale, 
            self.fontLineThickness)

    if self.centered:
        self.textStartLowerLeftX = int((self.width - self.textWidth) / 2) 
        self.textStartLowerLeftY = self.height - int((self.height - self.textHeight) / 2)
    else:
        self.textStartLowerLeftX = 0
        self.textStartLowerLeftY = self.height - self.baseline 

    cv2.putText(self.mat, 
            self.string, 
            (self.textStartLowerLeftX, self.textStartLowerLeftY), 
            self.font,
            self.fontScale, 
            self.fontColor, 
            self.fontLineThickness)

    if 0:
      # This approach makes the board bot draw tons and tons of redundant lines.  
      # Messy.

      # After we have drawn the black text now we put small white lines through the text
      # so that the contours generate appropriate lines for the entire filled in area.
      # No worries about the white lines as the pen is thicker than the distance captured
      # between the resulting contours.
      self.mat[::2,:] = 0
    else:
      # Using a different font thicknesses draws the letters perfectly inset from
      # one another.  The important part here though is that the letters are drawn
      # black so that the white outline remains.

      # Put the text back on again but with a small thickness
      cv2.putText(self.mat, 
            self.string, 
            (self.textStartLowerLeftX, self.textStartLowerLeftY), 
            self.font,
            self.fontScale, 
            0,
            int(self.fontLineThickness / 8))

    if self.isBoxed:
        cv2.rectangle(self.mat, (0,0), (self.width-1, self.height-1), 255, 1)

    # cv2.imshow("Test",self.mat)
    # cv2.waitKey(0)

    self.bbImage = bbimage.Image(self.bbcs)
    self.bbImage.genFromImage(self.mat)

  def getDrawString(self, offsetX, offsetY):
    return self.bbImage.getDrawString(offsetX, offsetY)
