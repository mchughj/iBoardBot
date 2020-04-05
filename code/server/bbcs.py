
import logging
import struct

# bbcs = board bot command set

# This module implements functionality that encapsulates how to 
# to encode the basic commands to the iBoardBot

def _formPacket(arg1, arg2, arg3=None):
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


def moveTo(x, y):
  logging.info("moveTo; x: %d, y: %d", x, y)
  return _formPacket(x, y)

def blockIdentifier(blockNumber):
  return _formPacket(4009, blockNumber)

def packetStart():
  return _formPacket(4009, 4001)

def startDrawing():
  return _formPacket(0xFA, 0x1F, 0xA1)  #   4001 4001   [FA1FA1]    # Start drawing (new draw)

def stopDrawing():
  return _formPacket(0xFA, 0x20, 0x00)  #   4002 0000   [FA2000]    # Stop drawing

def liftPen():
  return _formPacket(0xFA, 0x30, 0x00)  #   4003 0000   [FA3000]    # Pen lift

def dropPen():
  return _formPacket(0xFA, 0x40, 0x00)  #   4004 0000   [FA3000]    # Pen down

def eraserDown():
  return _formPacket(4005, 0)

def eraseAll():
  result  = liftPen()
  result += eraserDown()
  for y in range(0, 1200, 100):
    result += moveTo(0, y)
    result += moveTo(3580, y)
    result += moveTo(0, y)

  for y in range(1100, 0, -100):
    result += moveTo(0, y)
    result += moveTo(3580, y)
    result += moveTo(0, y)

  result += moveTo(0, 0)

  return result

def erasePortion(x1,y1,x2,y2):
  result  = liftPen()
  result += moveTo(x1,y1)
  result += eraserDown()

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
    result += moveTo(x1, yMove)
    result += moveTo(x2, yMove)
    result += moveTo(x1, yMove)

  for yMove in range(y2, y1, -100):
    result += moveTo(x1, yMove)
    result += moveTo(x2, yMove)
    result += moveTo(x1, yMove)

  result += moveTo(0, 0)

  return result
