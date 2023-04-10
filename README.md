# RF-pico
# Based on rpi-rf project ported to Pico 
# Basic communication with low-cost 433MHz RF-modules
# Two types of low-cost RF-modules have been used with RPI-pico
# Superheterodyne type (left photo) and Supergenerator (right photo)
# Preferred to use superheterodyne type due to a good sensitvity
# The supergenerator apeared to work only for 3m range with this simplified protocol :(

# Use library file rpi_rf.py that contains all the needed receive-transmit functions
# Two shell files rf_comm_receive.py and rf_comm_transmitt.py show usage examples 

# The implementation works within range of 20m inside a countryside house
