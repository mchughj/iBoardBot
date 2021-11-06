
import logging
import struct

from constants import MAX_HEIGHT, MAX_WIDTH

# bbcs = board bot command set

# This module implements functionality that encapsulates how to 
# to encode the basic commands to the iBoardBot.

class Bbcs(object):
  def _formPacket(self, arg1, arg2, arg3=None):
    if not arg3 is None:
        a1 = arg1 & 0xFF
        a2 = arg2 & 0xFF
        a3 = arg3 & 0xFF
        return struct.pack("BBB", a1, a2, a3)
    else:
        full       = (arg1 << 12) + arg2
        msbByte    = (full >> 16 ) & 0xFF
        middleByte = (full >> 8 )  & 0xFF
        lsbByte    = (full)        & 0xFF
        return struct.pack("BBB", msbByte, middleByte, lsbByte)


  def moveTo(self, x, y):
    logging.debug("moveTo; x: %d, y: %d", x, y)
    if y<0:
        y = 0
    if x<0:
        x = 0
    if y>=MAX_HEIGHT:
        y = MAX_HEIGHT-1
    if x>=MAX_WIDTH:
        x = MAX_WIDTH-1
    return self._formPacket(x, y)

  def blockIdentifier(self, blockNumber):
    return self._formPacket(4009, blockNumber)

  def packetStart(self):
    return self._formPacket(4009, 4001)

  def startDrawing(self):
    return self._formPacket(0xFA, 0x1F, 0xA1)  #   4001 4001   [FA1FA1]    # Start drawing (new draw)

  def stopDrawing(self):
    return self._formPacket(0xFA, 0x20, 0x00)  #   4002 0000   [FA2000]    # Stop drawing

  def liftPen(self):
    return self._formPacket(0xFA, 0x30, 0x00)  #   4003 0000   [FA3000]    # Pen lift

  def dropPen(self):
    return self._formPacket(0xFA, 0x40, 0x00)  #   4004 0000   [FA3000]    # Pen down

  def eraserDown(self):
    return self._formPacket(4005, 0)

  def eraserDownNoPause(self):
    return self._formPacket(4007, 0)

  def eraserUp(self):
    # There is no explicit eraser up command in the firmware since there are 
    # only three states: 
    #  1/  Erase mode (eraser down)
    #  2/  Draw mode (drop pen)
    #  3/  Move mode (lift pen) 
    # So to support this I just change into move mode
    return self.liftPen()

  def eraseAll(self, offset=50, moveY=100):
    result = self.eraserDown()
    topY = 1200
    # Jason :: If you ever want to test the erase functionality without erasing everything.
    # topY = 200
    for y in range(0, topY, moveY):
      result += self.moveTo(0, y)
      result += self.moveTo(3580, y)
      result += self.moveTo(0, y)

    for y in range(topY-offset, 0, -moveY):
      result += self.moveTo(0, y)
      result += self.moveTo(3580, y)
      result += self.moveTo(0, y)

    result += self.moveTo(0, 0)

    return result

  def erasePortion(self, x1,y1,x2,y2,finalSweep):
    result  = self.liftPen()
    result += self.moveTo(x1,y1)
    result += self.eraserDown()

    x1 -= 50
    if x1 < 0:
        x1 = 0
    x2 += 50
    if x2 > 3580:
        x2 = 3580
    
    y1 -= 50
    if y1 < 0:
        y1 = 0

    y2 += 50
    if y2 > 1100:
        y2 = 1100

    for yMove in range(y1, y2+99, 100):
      result += self.moveTo(x1, yMove)
      result += self.moveTo(x2, yMove)
      result += self.moveTo(x1, yMove)

    for yMove in range(y2, y1, -100):
      result += self.moveTo(x1, yMove)
      result += self.moveTo(x2, yMove)
      result += self.moveTo(x1, yMove)

    # If finalSweep is true then do a final pass along the right hand wall.
    # This is because the erase pushes the debris to that side and I would rather have
    # it at the bottom.  This turned out to not look as good as I would like.
    if finalSweep:
      for i in range(3):
        result += self.eraserUp()
        result += self.moveTo(max(x1,x2),min(y1,y2))
        result += self.eraserDown()
        result += self.moveTo(max(x1,x2),max(y1,y2))

    result += self.eraserUp()

    return result
