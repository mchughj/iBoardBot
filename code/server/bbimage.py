
import cv2
import logging
import os.path
from constants import MAX_HEIGHT, MAX_WIDTH

class Image(object):
  def __init__(self, bbcs):
    self.bbcs = bbcs
    self.scaleFactor = 1
    self.width = 0
    self.height = 0

  def setImageCharacteristics(self, scaleFactor):
    self.scaleFactor = scaleFactor

  def getDimensions(self):
    return (self.width * self.scaleFactor, self.height * self.scaleFactor)

  def genFromFile(self, filename):
    fullFilename = os.path.join(os.path.dirname(__file__),filename)
    logging.info("genFromFile - loading file; fullFilename: %s", fullFilename)
    image = cv2.imread(fullFilename)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 11, 17, 17)
    edged = cv2.Canny(gray, 30, 200)

    self.genContours(edged)

  def genFromImage(self, image):
    self.genContours(image)

  def genContours(self, image):
    contours, _ = cv2.findContours(image, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    # ret, thresh = cv2.threshold(gray,100,255,0)
    
    # Find the maximum x and y in order to come up with the scale factor
    self.minX = min([coordinate[0] for singleContour in contours for element in singleContour for coordinate in element] )
    self.minY = min([coordinate[1] for singleContour in contours for element in singleContour for coordinate in element] )
    self.maxX = max([coordinate[0] for singleContour in contours for element in singleContour for coordinate in element] )
    self.maxY = max([coordinate[1] for singleContour in contours for element in singleContour for coordinate in element] )

    self.contours = contours
    self.width = self.maxX - self.minX
    self.height = self.maxY - self.minY

    if self.scaleFactor == 0:
      xFactor = MAX_WIDTH / self.width
      yFactor = MAX_HEIGHT / self.height
      self.scaleFactor = min(xFactor, yFactor)

    logging.info("genContours - done; minX: %d, maxX: %d, minY: %d, maxY: %d, "
        "width: %d, height: %d, numberContours: %d", 
        self.minX, self.maxX, self.minY, self.maxY, self.width, self.height,
        len(self.contours))


  def getDrawString(self, offsetX, offsetY):
    logging.info("getDrawString - offset values; offsetX: %d, offsetY: %d", 
        offsetX, offsetY)

    result = self.bbcs.liftPen()
    for c in self.contours:
      area = cv2.contourArea(c)
      if len(c) >= 2:
        logging.debug("getDrawString - drawing contour; area: %d, len: %d", 
            area, len(c))

        start = c[0]
        result += self.bbcs.liftPen()
        logging.debug("drawImage - lifting pen;")
        result += self.bbcs.moveTo(int(start[0][0] * self.scaleFactor) + offsetX,
            offsetY - int(start[0][1] * self.scaleFactor))
        result += self.bbcs.dropPen()
        logging.debug("drawImage - dropping pen;")
        for e in c[1:]:
          result += self.bbcs.moveTo(int(e[0][0] * self.scaleFactor) + offsetX,
              offsetY - int(e[0][1] * self.scaleFactor))
        logging.debug("drawImage - lifting pen;")
        result += self.bbcs.liftPen()

      else:
        logging.info("drawImage - skipping singletons; len: %d", len(c))

    result += self.bbcs.liftPen()
    return result
