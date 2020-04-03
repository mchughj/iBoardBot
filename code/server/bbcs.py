
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
      logging.info("Three arguments; a1: %d, a2: %d, a3: %d", a1, a2, a3)
      return struct.pack("BBB", a1, a2, a3)
  else:
      logging.info("Two arguments; arg1: %d, arg2: %d", arg1, arg2)
      full       = (arg1 << 12) + arg2
      msbByte    = (full >> 16 ) & 0xFF
      middleByte = (full >> 8 )  & 0xFF
      lsbByte    = (full)        & 0xFF
      return struct.pack("BBB", msbByte, middleByte, lsbByte)


def moveTo(x, y):
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
