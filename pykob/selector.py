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
    Selector -
    Class that monitors a full UART interface for one of four handshake
    signals being active. Or a value from 0 to 15 (0x00 - 0xFF) using the
    handshake signals: RI(bit-3) CD(bit-2) DSR(bit-1) CTS(bit-0)

    The value can be read as needed and a callback can be supplied that is
    called when the value changes.
"""
from enum import Enum, IntEnum, unique
import sys
import time
import threading
from threading import Event, Thread
import traceback
from typing import Optional

from pykob import log

serialModuleAvailable = False
try:
    import serial
    serialModuleAvailable = True
except:
    log.err("Module pySerial is not available. Selector cannot be used.")

global POLE_CYCLE_TIME_MIN
POLE_CYCLE_TIME_MIN = 0.01

@unique
class SelectorMode(IntEnum):
    OneOfFour = 1
    Binary = 2
    BinaryAnd1of4 = 3

@unique
class SelectorChange(IntEnum):
    OneOfFour = 1
    Binary = 2
    BinaryAnd1of4 = 3

class SelectorLoadError(Exception):
    def __init__(self, port:Optional[str]=None, ex:Optional[Exception]=None):
        Exception.__init__(ex)
        self._parent = ex
        self._port = port
        return

    @property
    def parent(self) -> Optional[Exception]:
        return self._parent

    @property
    def port(self) -> Optional[str]:
        return self._port

class Selector:
    def __init__(self, portToUse:str, mode:SelectorMode=SelectorMode.OneOfFour,
            pole_cycle_time:float=0.1, steady_time:float=0.8, on_change=None) -> None:
        self._portToUse = portToUse
        self._port = None
        self._mode = mode
        self._pole_cycle_time = pole_cycle_time if pole_cycle_time >= POLE_CYCLE_TIME_MIN else POLE_CYCLE_TIME_MIN
        self._steady_time = steady_time
        self._on_change = on_change
        self._one_of_four = 0
        self._binary_value = 0
        self._raw_value = 0
        self._t_last_change = time.time()
        #
        self._shutdown = Event()
        self._thread_port_checker = Thread(name='Selector-PortReader', daemon=True, target=self._thread_port_checker_body)

    def _thread_port_checker_body(self):
        """
        Called by the Port Checker thread `run` to read the handshake values from the port.
        """
        try:
            values_need_updating = False
            oof_changed = False
            binary_changed = False
            while not self._shutdown.is_set():
                b0 = 1 if self._port.cts else 0
                b1 = 2 if self._port.dsr else 0
                b2 = 4 if self._port.cd else 0
                b3 = 8 if self._port.ri else 0
                rval = (b3+b2+b1+b0)
                if not rval == self._raw_value:
                    self._raw_value = rval
                    values_need_updating = True
                    self._t_last_change = time.time()
                else:
                    # The value read is the same as last time
                    # see if enough time has passed to record it.
                    now = time.time()
                    if (now - self._t_last_change) >= self._steady_time:
                        if values_need_updating:
                            if not self._binary_value == rval:
                                self._binary_value = rval
                                binary_changed = True
                            # 1 of 4 only if a single bit is set
                            oof = 0
                            if rval == 1:
                                oof = 1
                            elif rval == 2:
                                oof = 2
                            elif rval == 4:
                                oof = 3
                            elif rval == 8:
                                oof = 4
                            if not oof == self._one_of_four:
                                self._one_of_four = oof
                                oof_changed = True
                            # Call On-Change?
                            if self._on_change:
                                if (oof_changed and self._mode == SelectorMode.OneOfFour):
                                    self._on_change(SelectorChange.OneOfFour, self._one_of_four)
                                else:
                                    change = (SelectorChange.BinaryAnd1of4 if binary_changed and oof_changed else
                                        (SelectorChange.Binary if binary_changed else SelectorChange.OneOfFour))
                                    if (binary_changed and self._mode == SelectorMode.Binary):
                                        self._on_change(change, self._binary_value)
                                    else:
                                        self._on_change(change, (self._binary_value, self._one_of_four))
                            # Clear the flags
                            values_need_updating = False
                            oof_changed = False
                            binary_changed = False
                    self._shutdown.wait(self._pole_cycle_time)
        finally:
            log.debug("{} thread done.".format(threading.current_thread().name))
        return

    @property
    def binary_value(self):
        return self._binary_value

    @property
    def one_of_four(self):
        return self._one_of_four

    @property
    def raw_value(self):
        return self._raw_value

    def exit(self):
        """
        Stop the threads and exit.
        """
        self.shutdown()
        if self._thread_port_checker and self._thread_port_checker.is_alive():
            self._thread_port_checker.join(timeout=2.0)
        if self._port and not self._port.closed:
            self._port.close()
            self._port = None

    def shutdown(self):
        """
        Initiate shutdown of our operations (and don't start anything new),
        but DO NOT BLOCK.
        """
        self._shutdown.set()
        return

    def start(self):
        try:
            self._port = serial.Serial(self._portToUse)
            self._thread_port_checker.start()
            log.debug("The port '{}' for the Selector is available.".format(self._portToUse))
        except Exception as ex:
            log.log("Serial port '{}' not available. The Selector will not function.\n".format(self._portToUse), dt="")
            log.debug("Selector exception: {}".format(ex))
            raise SelectorLoadError(self._portToUse, ex)

"""
Test code
"""
if __name__ == "__main__":
    # Self-test
    __test_selector = None

    def __test_on_change(change, value):
        global __test_selector
        print("Test On Change: {}".format(change))
        print(" value: {}".format(value))
        print(" Binary: {}".format(__test_selector.binary_value))
        print(" 1 of 4: {}".format(__test_selector.one_of_four))

    try:
        log.set_logging_level(log.DEBUG_MIN_LEVEL)
        port = sys.argv[1] if len(sys.argv) == 2 else 'COM4'
        __test_selector = Selector(port, SelectorMode.OneOfFour, on_change=__test_on_change)
        __test_selector.start()
        while True:
            time.sleep(10.0)
            print("Selector Raw Value: {}  1of4: {}".format(
                __test_selector.raw_value, __test_selector.one_of_four))
    except Exception as ex:
        print(ex)
        sys.exit(1)     # Indicate this was an abnormal exit
    except KeyboardInterrupt:
        if __test_selector:
            __test_selector.exit()
        print()
        sys.exit(0)     # Indicate this was a normal exit
