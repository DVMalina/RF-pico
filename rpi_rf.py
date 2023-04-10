"""
Sending and receiving 433/315Mhz signals with low-cost GPIO RF Modules on a Raspberry Pi.
"""

import utime
from collections import namedtuple

from machine import Pin

MAX_CHANGES = 67

"""Pulse parameters, values in usec"""
THRESHOLD_SYNC = 15000
THRESHOLD_TICK = 300
SCALE_TIME_US = 3

Debug1 = Pin(16, Pin.OUT)
Debug2 = Pin(17, Pin.OUT)

Protocol = namedtuple('Protocol',
                      ['pulselength',
                       'sync_high', 'sync_low',
                       'zero_high', 'zero_low',
                       'one_high', 'one_low'])
PROTOCOLS = (None,
             Protocol(350, 1, 31, 1, 3, 3, 1),
             Protocol(650, 1, 10, 1, 2, 2, 1),
             Protocol(100, 30, 71, 4, 11, 9, 6),
             Protocol(380, 1, 6, 1, 3, 3, 1),
             Protocol(500, 6, 14, 1, 2, 2, 1),
             Protocol(200, 1, 10, 1, 5, 1, 1))

class RFDevice:
    """Representation of a GPIO RF device."""

    # pylint: disable=too-many-instance-attributes,too-many-arguments
    def __init__(self, gpio,
                 tx_proto=1, tx_pulselength=None, tx_repeat=10, tx_length=24, rx_tolerance=70):
        """Initialize the RF device."""
        self.gpio = gpio
        self.tx_enabled = False
        self.tx_proto = tx_proto
        if tx_pulselength:
            self.tx_pulselength = tx_pulselength
        else:
            self.tx_pulselength = PROTOCOLS[tx_proto].pulselength
        self.tx_repeat = tx_repeat
        self.tx_length = tx_length
        self.rx_enabled = False
        self.rx_tolerance = rx_tolerance
        # internal values
        self._rx_timings = [0] * (MAX_CHANGES + 1)
        self._rx_last_timestamp = 0
        self._rx_change_count = 0
        self._rx_repeat_count = 0
        # successful RX values
        self.rx_code = None
        self.rx_code_timestamp = None
        self.rx_proto = tx_proto
        self.rx_repeat = tx_repeat
        self.rx_bitlength = None
        self.rx_pulselength = None

        print("Using GPIO " + str(gpio))

    def cleanup(self):
        """Disable TX and RX and clean up GPIO."""
        if self.tx_enabled:
            self.disable_tx()
        if self.rx_enabled:
            self.disable_rx()
        print("Cleanup pin")
        Pin(self.gpio, Pin.IN, Pin.PULL_DOWN)

    def enable_tx(self):
        """Enable TX, set up GPIO."""
        if self.rx_enabled:
            print("RX is enabled, not enabling TX")
            return False
        if not self.tx_enabled:
            self.tx_enabled = True
            print(self.gpio)
            self.tx_pin = Pin(self.gpio, Pin.OUT)
            print("TX enabled")
        return True

    def disable_tx(self):
        """Disable TX, reset GPIO."""
        if self.tx_enabled:
            # set up GPIO pin as input for safety
            self.tx_pin = Pin(self.gpio, Pin.IN, Pin.PULL_DOWN)
            self.tx_enabled = False
            print("TX disabled")
        return True

    def tx_code(self, code):
        """
        Send a decimal code.
        
        """
        rawcode = '0'*(self.tx_length + 0 - len(bin(code)[2:])) + bin(code)[2:]
        
        if self.tx_proto == 6:
            nexacode = ""
            for b in rawcode:
                if b == '0':
                    nexacode = nexacode + "01"
                if b == '1':
                    nexacode = nexacode + "10"
            rawcode = nexacode
            self.tx_length = 64
        
        print("TX code: " + str(code))
        return self.tx_bin(rawcode)

    def tx_bin(self, rawcode):
        """Send a binary code."""
        print("TX bin: " + str(rawcode))
        for _ in range(0, self.tx_repeat):
            if self.tx_proto == 6:
                if not self.tx_sync():
                    return False
            for byte in range(0, self.tx_length):
                if rawcode[byte] == '0':
                    if not self.tx_l0():
                        return False
                else:
                    if not self.tx_l1():
                        return False
            if not self.tx_sync():
                return False

        return True

    def tx_l0(self):
        """Send a '0' bit."""
        if not 0 < self.tx_proto < len(PROTOCOLS):
            print("Unknown TX protocol")
            return False
        return self.tx_waveform(PROTOCOLS[self.tx_proto].zero_high,
                                PROTOCOLS[self.tx_proto].zero_low)

    def tx_l1(self):
        """Send a '1' bit."""
        if not 0 < self.tx_proto < len(PROTOCOLS):
            print("Unknown TX protocol")
            return False
        return self.tx_waveform(PROTOCOLS[self.tx_proto].one_high,
                                PROTOCOLS[self.tx_proto].one_low)

    def tx_sync(self):
        """Send a sync."""
        if not 0 < self.tx_proto < len(PROTOCOLS):
            print("Unknown TX protocol")
            return False
        return self.tx_waveform(PROTOCOLS[self.tx_proto].sync_high,
                                PROTOCOLS[self.tx_proto].sync_low)

    def tx_waveform(self, highpulses, lowpulses):
        """Send basic waveform."""
        if not self.tx_enabled:
            print("TX is not enabled, not sending data")
            return False
        #print(highpulses,lowpulses)
        #print("Pulse lenth unit time [us]:", self.tx_pulselength * SCALE_TIME_US)
        self.tx_pin.high()
        self._sleep((highpulses * self.tx_pulselength * SCALE_TIME_US))
        self.tx_pin.low()
        self._sleep((lowpulses * self.tx_pulselength * SCALE_TIME_US))
        return True
    
    def enable_rx(self):
        """Enable RX, set up GPIO and add event detection."""
        if self.tx_enabled:
            print("TX is enabled, not enabling RX")
            return False
        if not self.rx_enabled:
            self.rx_enabled = True
            self.rx_pin = Pin(self.gpio, Pin.IN, Pin.PULL_DOWN)
            self.rx_pin.irq(trigger=Pin.IRQ_FALLING|Pin.IRQ_RISING, handler=self.rx_callback)
            print("RX enabled")
        return True

    def disable_rx(self):
        """Disable RX, remove GPIO event detection."""
        if self.rx_enabled:
            self.rx_pin.irq(handler=None)
            self.rx_enabled = False
            print("RX disabled")
        return True
    
    def received_rx(self):
        code = self.rx_code 
        if self.rx_code:
            self.rx_code = None
        return code

    def rx_callback(self, rx_pin):
        """RX callback for GPIO event detection. Handle basic signal detection."""
        timestamp = int(utime.ticks_us())
        duration = timestamp - self._rx_last_timestamp
        
        """Ignoring pulses shorter than THRESHOLD_TICK""" 
        if duration > THRESHOLD_TICK:
            Debug1.toggle()
            """Synchronizing to a pulse longer than THRESHOLD_SYNC"""
            if duration > THRESHOLD_SYNC:
                Debug2.toggle()
                self._rx_repeat_count += 1
                self._rx_change_count -= 1
                
                if self._rx_change_count > 1:
                
                    #print("Changes:", self._rx_change_count)
                    #print("Buffer:", self._rx_timings)
                    #print("Trunc:", self._rx_timings[0:self._rx_change_count])
                
                    #if self._rx_waveform(self.rx_proto, self._rx_change_count, timestamp):
                    #    print("RX code " + str(self.rx_code))
                    self._rx_waveform(self.rx_proto, self._rx_change_count, timestamp)

                self._rx_change_count = 0

            if self._rx_change_count >= MAX_CHANGES:
                self._rx_change_count = 0
                self._rx_repeat_count = 0
                
            self._rx_timings[self._rx_change_count] = duration
            self._rx_change_count += 1

        self._rx_last_timestamp = timestamp

    def _rx_waveform(self, pnum, change_count, timestamp):
        """Detect waveform and format code."""
        code = 0
        delay = int(self._rx_timings[0] / PROTOCOLS[pnum].sync_low)
        #print("Defined pulsewidth", delay)
        delay_tolerance = delay * self.rx_tolerance / 100

        for i in range(1, change_count, 2):
            if (abs(self._rx_timings[i] - delay * PROTOCOLS[pnum].zero_high) < delay_tolerance and
                abs(self._rx_timings[i+1] - delay * PROTOCOLS[pnum].zero_low) < delay_tolerance):
                code <<= 1
            elif (abs(self._rx_timings[i] - delay * PROTOCOLS[pnum].one_high) < delay_tolerance and
                  abs(self._rx_timings[i+1] - delay * PROTOCOLS[pnum].one_low) < delay_tolerance):
                code <<= 1
                code |= 1
            else:
                return False

        if self._rx_change_count > 6 and code != 0:
            self.rx_code = code
            self.rx_code_timestamp = timestamp
            return True

        return False

    def _sleep(self, delay):     
        utime.sleep_us(delay)
