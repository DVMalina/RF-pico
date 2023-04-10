from rpi_rf import RFDevice

RF_RX = 13

rfdevice = RFDevice(RF_RX,1)
rfdevice.enable_rx()
while True:
    received_code = rfdevice.received_rx()
#    if (received_code == code):
#        rfdevice.cleanup()
    if (received_code != None):
        print("Received code ", received_code, " Timestamp ", rfdevice._rx_last_timestamp)
        #rfdevice.cleanup()
        #rfdevice.rx_code = None
        #break
