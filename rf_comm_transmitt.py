from rpi_rf import RFDevice
import time
from machine import Pin

Button = Pin(14, Pin.IN, Pin.PULL_UP)

RF_TX = 6
code = 255
rfdevice = RFDevice(RF_TX,1)
rfdevice.enable_tx()

while True:
    if (not(Button.value())):
        rfdevice.tx_code(code)

#rfdevice.cleanup()
