import freetype
import logging

class Text(object):
  def __init__(self, bbcs):
    self.bbcs = bbcs
    self.text = ""
    self.points = []
    self.contours = []
    self.dimensions = []
    self.width = 0
    self.height = 0
    self.isBoxed = False

  def setFontCharacteristics(self, font, size):
    self.size = size
    self.sizeBetweenCharacters = int(self.size/10)
    self.spaceSize = self.sizeBetweenCharacters * 2
    self.face = freetype.Face(font)
    self.face.set_char_size(size)

  def setBoxed(self, isBoxed):
    self.isBoxed = isBoxed

  def setString(self, string):
    self.string = string

  def gen(self):
    self.width = 0
    self.height = 0

    for s in self.string:
      self.face.load_char(s)
      o = self.face.glyph.outline
      bbox = self.face.bbox

      if len(o.points) == 0:
        logging.info("gen - no point information; char: %s", s)
        characterWidth = self.spaceSize
        characterHeight = 0
      else:
        characterWidth = max([ p[0] for p in o.points ])
        characterHeight = max([ p[1] for p in o.points ])

        logging.info("gen - character info; char: %s, bbox.yMin: %d, "
                     "bbox.yMax: %d, bbox.xMin: %d, bbox.xMax: %d, "
                     "characterHeight: %d, characterWidth: %d",
              s, bbox.yMin, bbox.yMax, bbox.xMin, bbox.xMax, 
              characterHeight, characterWidth)

      self.width += characterWidth
      self.width += self.sizeBetweenCharacters 

      if self.height < characterHeight:
        self.height = characterHeight

      logging.info("gen - overall dimensions; width: %d, height: %d", 
            self.width, self.height)

      self.points.append(o.points)
      self.contours.append(o.contours)
      self.dimensions.append((characterWidth, characterHeight))
  
  def getDimensions(self):
    return (self.width, self.height)

  def getTextLowerLeftX(self):
    return self.textStartLowerLeftX

  def getTextLowerLeftY(self):
    return self.textStartLowerLeftY

  def getDrawString(self, dimensions):

    if len(dimensions) == 2:
      lowerLeftX, lowerLeftY = dimensions
      result  = self.bbcs.liftPen()
    elif len(dimensions) == 4:
      # Assumption here is that the text should be centered
      # relative to the lowerLeftX, lowerLeftY and width and 
      # height passed in
      lowerLeftX, lowerLeftY, width, height = dimensions
      result = self.bbcs.liftPen()
      if self.isBoxed:
        result += self.bbcs.moveTo(lowerLeftX, lowerLeftY)
        result += self.bbcs.dropPen()
        result += self.bbcs.moveTo(lowerLeftX+width, lowerLeftY)
        result += self.bbcs.moveTo(lowerLeftX+width, lowerLeftY+height)
        result += self.bbcs.moveTo(lowerLeftX, lowerLeftY+height)
        result += self.bbcs.moveTo(lowerLeftX, lowerLeftY)
        result += self.bbcs.liftPen()

      lowerLeftX += int((width - self.width) / 2)
      lowerLeftY += int((height - self.height) / 2)

      logging.info("getDrawString - got new lower left;  self.width: %d, "
              "self.height: %d, width: %d, height: %d, lowerLeftX: %d, "
              "lowerLeftY: %d", self.width, self.height, width, height,
              lowerLeftX, lowerLeftY)

    self.textStartLowerLeftX = lowerLeftX
    self.textStartLowerLeftY = lowerLeftY 

    result += self.bbcs.moveTo(lowerLeftX, lowerLeftY)

    for i in range(len(self.string)):
      (characterCommands, lowerLeftX, lowerLeftY) = self._getDrawCharacter(
          self.points[i], self.contours[i], self.dimensions[i], 
          lowerLeftX, lowerLeftY)
      result += characterCommands

    return result

  def _getDrawCharacter(self, points, contours, dimensions, lowerLeftX, lowerLeftY):
    start = 0
    result = self.bbcs.moveTo(lowerLeftX, lowerLeftY)

    for c in contours:
      end = c
      p = points[start:end+1]
      p.append(points[start])
      result += self.bbcs.moveTo(
          lowerLeftX + points[start][0], lowerLeftY +
          points[start][1])
      result += self.bbcs.dropPen()
      for individualPoint in p[1:]:
        result += self.bbcs.moveTo(
            lowerLeftX + individualPoint[0], 
            lowerLeftY + individualPoint[1])
      result += self.bbcs.liftPen()
      start = end + 1

    newLowerLeftX = lowerLeftX + dimensions[0] + self.sizeBetweenCharacters

    return (result, newLowerLeftX, lowerLeftY)
