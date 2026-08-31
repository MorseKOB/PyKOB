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
    Class that monitors:
     1) Full UART interface monitoring four handshake signals
        RI(bit-3) CD(bit-2) DSR(bit-1) CTS(bit-0)
     2) Four GPIO pins (typically on a Raspberry Pi)
        GPIO05(bit-3) GPIO06(bit-2) GPIO13(bit-1) GPIO19(bit-0)
        (these are 4 in a row on the RPi header: 29,31,33,35)
    It can check for one of the four signals being active (1,2,3,4). Or it can
    use them to read a value from 0 to 15 (0x00 - 0x0F). 

    The value can be read as needed and a callback can be supplied that is
    called when the value changes.

    The 'portToUse' can be a serial port specification
        (COMx on Windows, /dev/tty... on *nix/Mac),
    the special value 'SDSEL' (Silky-DESIGN Selector) to find a
    serial port with a serial number ending in '_AESSEL' ('_AESSELA' on Windows),
    or 'GPIO' to use the four GPIO pins.
"""
from enum import Enum, IntEnum, unique
import sys
import time
import threading
from threading import Event, Thread
import traceback
from typing import Optional

from pykob import log
from pykob import serial as pkserial

serialModuleAvailable = pkserial.SERIAL_AVAILABLE
if not serialModuleAvailable:
    log.err("Module pySerial is not available. Selector cannot be used.")

SEL_FIND_SDSEL = pkserial.PORT_FIND_SDSEL_KEY
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

class SDSelectorNotFound(Exception):
    pass

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

class GpioSwitch:
    def __init__(self, gpio_dev, p0=19, p1=13, p2=6, p3=5) -> None:
        self._gpio_dev = gpio_dev
        self._pins = {"b0": p0, "b1": p1, "b2": p2, "b3": p3}
        self._b0 = 0
        self._b1 = 0
        self._b2 = 0
        self._b3 = 0
        self._op_err_msg = None

        try:
            import gpiod
            from gpiod.line import Direction, Bias

            # Configure settings for a pull-up switch input
            input_settings = gpiod.LineSettings(
                direction=Direction.INPUT,
                bias=Bias.PULL_UP
            )
            # Request all 4 lines in a single call
            self._line_request = gpiod.request_lines(
                self._gpio_dev,
                config={
                    self._pins["b0"]: input_settings,
                    self._pins["b1"]: input_settings,
                    self._pins["b2"]: input_settings,
                    self._pins["b3"]: input_settings
                }
            )
        except ImportError:
            log.debug("Error loading 'gpiod' module (is it installed?)")
            raise   # <- re-raise that exception
        except PermissionError as pex:
            log.error("Permission error accessing GPIO hardware: {}".format(pex), dt="")
            raise
        except Exception as ex:
            raise

    @property
    def b0(self):  # type: () -> int
        s = 0
        if (not self.has_error()):
            s = self._b0
        return s

    @property
    def b1(self):  # type: () -> int
        s = 0
        if (not self.has_error()):
            s = self._b0
        return s

    @property
    def b2(self):  # type: () -> int
        s = 0
        if (not self.has_error()):
            s = self._b0
        return s

    @property
    def b3(self):  # type: () -> int
        s = 0
        if (not self.has_error()):
            s = self._b0
        return s


    def close(self) -> None:
        log.debug("GpioSwitch.close - 1", 3)
        self._close_pins()
        log.debug("GpioSwitch.close - 2", 3)
        return

    def has_error(self) -> None:
        return self._op_err_msg is not None

    def read_pins(self) -> None:
        try:
            # Pins are active low, so 0 is ON and 1 is OFF
            self._b0 = 1 - self._line_request.get_value(self._pins["b0"]).value
            self._b1 = 1 - self._line_request.get_value(self._pins["b1"]).value
            self._b2 = 1 - self._line_request.get_value(self._pins["b2"]).value
            self._b3 = 1 - self._line_request.get_value(self._pins["b3"]).value
        except Exception as ex:
            self._set_error(ex)
            raise
        return

    def _close_pins(self):  # type: () -> None
        if self._line_request:
            try:
                self._line_request.close()
            except Exception:
                pass
            self._line_request = None
        return

    def _set_error(self, ex):  # type: (Exception) -> None
        self._op_err_msg = "GpioSwitch (gpiod) Error: {}".format(ex)
        self._close_pins()
        self._has_error = True
        return



class Selector:
    def __init__(self, portToUse:str, mode:SelectorMode=SelectorMode.OneOfFour,
            pole_cycle_time:float=0.1, steady_time:float=0.8, on_change=None, status_msg_hdlr=None, retries_enabled=False) -> None:
        self._status_msg_hdlr = status_msg_hdlr if status_msg_hdlr is not None else self._null_status_hdlr
        self._portToUse = portToUse
        self._useGPIO = False
        self._gpio_dev = None
        self._gpiosw = None
        self._port = None
        self._mode = mode
        self._pole_cycle_time = pole_cycle_time if pole_cycle_time >= POLE_CYCLE_TIME_MIN else POLE_CYCLE_TIME_MIN
        self._steady_time = steady_time
        self._on_change = on_change
        self._retries_enabled = retries_enabled
        self._one_of_four = 1
        self._binary_value = 0
        self._raw_value = 0
        self._t_last_change = time.time()
        #
        self._shutdown = Event()
        self._thread_port_checker = Thread(name='Selector-PortReader', daemon=True, target=self._thread_port_checker_body)

    def _null_status_hdlr(self, msg):  # type: (str|None) -> None
        log.debug("Selector status: {}".format(msg), 5)
        return

    def _thread_port_checker_body(self):
        """
        Called by the Port Checker thread `run` to read the switch values from the port.
        """
        try:
            values_need_updating = False
            oof_changed = False
            binary_changed = False
            while not self._shutdown.is_set():
                b0 = 0
                b1 = 0
                b2 = 0
                b3 = 0
                if self._port:
                    if not self._port.closed:
                        b0 = 1 if self._port.cts else 0
                        b1 = 2 if self._port.dsr else 0
                        b2 = 4 if self._port.cd else 0
                        b3 = 8 if self._port.ri else 0
                elif self._gpiosw:
                    b0 = self._gpiosw.b0
                    b1 = (self._gpiosw.b1 << 1)
                    b2 = (self._gpiosw.b2 << 2)
                    b3 = (self._gpiosw.b3 << 3)
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
                    pass
                self._shutdown.wait(self._pole_cycle_time)
            pass
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

    @property
    def selector_change_type(self):  # type: () -> SelectorChange
        """
        The type of change this selector produces.
        """
        return self._
    @property
    def selector_mode(self):  # type: () -> SelectorMode
        """
        The mode the selector is being used in:
            1 of 4 or Binary
        """
        return self._mode

    @property
    def selector_value(self):  # type: () -> int
        """
        The value of the selector that is appropriate for the mode:
            1,2,3,4 - For 1 of 4
            0-15 - For Binary
        """
        if self._mode == SelectorMode.OneOfFour:
            return self._one_of_four
        return self._binary_value

    def exit(self):
        """
        Stop the threads and exit.
        """
        self.shutdown()
        if self._thread_port_checker and self._thread_port_checker.is_alive():
            self._thread_port_checker.join(timeout=2.0)
        if self._port and not self._port.closed:
            self._port.exit()
            self._port = None
        if self._gpiosw:
            self._gpiosw.close()
            self._gpiosw = None
        return

    def shutdown(self):
        """
        Initiate shutdown of our operations (and don't start anything new),
        but DO NOT BLOCK.
        """
        self._shutdown.set()
        return

    def start(self):  # type: () -> bool
        """
        Start up the selector. Return true if all is good.
        If we aren't able to find a selector switch, but retries are enabled
        (so we might find a selector switch later) return false.
        If we don't find a selector switch and retries aren't enabled, raise
        an exception.
            Note: Retries aren't applicable to a GPIO Switch

        Return: True is all is good. False if retrying in background. Exception if error.
        """
        try:
            # If the portToUse is "gpio" see if we have a GPIO to use else we try to find a serial module
            if self._portToUse.lower() == "gpio":
                self._useGPIO = True
                from pykob import gpio
                self._gpio_dev = gpio.get_gpio_dev()
                if self._gpio_dev is not None:
                    log.debug("GPIO found on '{}' for the Selector".format(self._gpio_dev))
                    self._gpiosw = GpioSwitch(self._gpio_dev)
                    self._gpiosw.read_pins()     # Do a read to see if there are any errors
                else:
                    log.log("GPIO 'pin' hardware not found. Selector cannot be used.\n", dt="")
                    raise SDSelectorNotFound("No usable GPIO Hardware")
            else:
                self._port = pkserial.PKSerial(
                    self._portToUse,
                    err_callback=self._status_msg_hdlr,
                    status_callback=self._status_msg_hdlr,
                    enable_retries=self._retries_enabled
                )
                self._port.start()
                v = self._port.cts  # Do a read to see if there are any errors
                if self._port.port_name_used is not None:
                    log.debug("The port '{}' for the Selector is available.".format(self._port.port_name_used))
                else:
                    log.log("Selector serial port '{}' problem.\n".format(self._portToUse), dt="")
        except Exception as ex:
            log.debug("Selector exception: {}".format(ex))
            if self._useGPIO:
                log.log("GPIO error. Selector cannot be used.\n", dt="")
            else:
                log.log("Selector serial port '{}' error. ".format(self._portToUse), dt="")
                if self._retries_enabled:
                    log.log("Will retry connection in the background.\n", dt="")
                    # Return False and retry finding a selector.
                    return False
                else:
                    log.log("Selector cannot be used.\n", dt="")
            raise SDSelectorNotFound(ex)
        finally:
            if self._gpiosw is not None or self._port is not None:
                self._thread_port_checker.start()
        return True

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
        port = sys.argv[1] if len(sys.argv) == 2 else 'SDSEL'
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
