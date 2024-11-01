"""
MIT License

Copyright (c) 2020-24 PyKOB - MorseKOB in Python

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
"""
    Serial -
    Class that encapsulates the serial access (PySerial) to allow for centralized
    error handling, including retry and reconnect.

    The 'port_to_use' can be a serial port specification
        (COMx on Windows, /dev/tty... on *nix/Mac)
    or the special value 'SDSEL' (Silky-DESIGN Selector) or 'SDIF'
    (Silky-DESIGN Interface) to find a serial port with a serial number specifying
    a Silky-DESIGN component.

    Callbacks notify on error, but otherwise problems are handled by this class.
"""
from pykob import log
import traceback
from typing import Callable

SERIAL_AVAILABLE = False
SERIAL_IMPL = ""
SERIAL_VERSION = -1.0

PORT_FIND_SDIF_KEY = "SDIF"
SDIF_SN_END = "_AES"

try:
    import serial as pyserial
    import serial.tools.list_ports as psports
    SERIAL_AVAILABLE = True
    SERIAL_IMPL = pyserial.__name__
    SERIAL_VERSION = pyserial.VERSION
except:
    log.debug(traceback.format_exc(), 3)
    log.debug("Serial module could not be loaded.")
log.debug("Serial support module: {}\n Version: {}", 2)

class PKSerial:
    '''
    Serial class to encapsulate PySerial to handle errors and retry/reconnect.
    '''
    def __init__(self, errCallback=None):  # type: (Callable) -> None
        self._errCallback = errCallback if not errCallback is None else self.nullErrCallback
        self._pyserial = None
        if SERIAL_AVAILABLE:
            self._pyserial = pyserial
        else:
            self._errCallback("Serial module not available")
        self._port_name = None  # type: str|None
        self._port = None  # type: pyserial.Serial|None
        return

    def nullErrCallback(self, msg):  # type: (str) -> None
        '''
        Error callback to use when one isn't supplied.
        '''
        log.debug("pykob.Serial Error encountered: {}".format(msg), 5)
        return

    # ###########################################################
    # ### Properties specific to this class (not in 'Serial') ###
    # ###########################################################

    @property
    def serial_intrfc_available(self):  # type: () -> bool
        '''
        The serial interface module is available.
        '''
        return SERIAL_AVAILABLE

    @property
    def port_name(self):  # type: () -> str|None
        return self._port_name

    # ###########################################################
    # ### Properties wrapping 'Serial'                        ###
    # ###########################################################

    @property
    def closed(self):  # type () -> bool
        s = self._port.closed if self._port is not None else True
        return s

    @property
    def cts(self):  # type: () -> bool
        s = self._port.cts if self._port is not None else False
        return s

    @property
    def dsr(self):  # type: () -> bool
        s = self._port.dsr if self._port is not None else False
        return s

    @property
    def dtr(self):  # type: () -> bool
        s = self._port.dtr if self._port is not None else False
        return s

    @dtr.setter
    def dtr(self, s):  # type: (bool) -> None
        if self._port is not None:
            self._port.dtr = s
        return

    @property
    def rts(self):  # type: () -> bool
        s = self._port.rts if self._port is not None else False
        return s

    @rts.setter
    def rts(self, s):  # type: (bool) -> None
        if self._port is not None:
            self._port.rts = s
        return

    @property
    def write_timeout(self):  # Type: () -> float
        value = self._port.write_timeout if self._port is not None else 0.0
        return value

    @write_timeout.setter
    def write_timeout(self, value):  # type: (float) -> None
        if self._port is not None:
            self._port.write_timeout = value
        return

    def close(self):  # type: () -> None
        if self._port is not None:
            self._port.close()
        return

    def readline(self):  # type: () -> bytes
        read = bytes()
        if self._port is not None:
            read = self._port.readline()
        return read

    def write(self, data):  # type: (bytes|bytearray) -> int
        written = 0
        if self._port is not None:
            written = self._port.write(data)
        return written
