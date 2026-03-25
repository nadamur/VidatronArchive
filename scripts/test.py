from adafruit_motorkit import MotorKit
import board
import busio

i2c = busio.I2C(board.SCL, board.SDA)
kit = MotorKit(i2c=i2c)