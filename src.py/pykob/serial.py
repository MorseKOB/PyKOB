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
import re  # RegEx
import threading
from threading import Event, Thread
import time
import traceback
from typing import Any, Callable

SERIAL_AVAILABLE = False
SERIAL_IMPL = ""
SERIAL_VERSION = -1.0

PORT_FIND_SDIF_KEY = "SDIF"
PORT_FIND_SDSEL_KEY = "SDSEL"
SDIF_SN_END = "_AES"
SDSEL_SN_END = "_AESSEL"

class PKSerialPortError(Exception):
    pass

try:
    import serial as pyserial
    import serial.tools.list_ports as psports
    SERIAL_AVAILABLE = True
    SERIAL_IMPL = pyserial.__name__
    SERIAL_VERSION = pyserial.VERSION
    log.debug("Serial support module: {}\n Version: {}".format(SERIAL_IMPL, SERIAL_VERSION), 2)
except:
    log.debug(traceback.format_exc(), 3)
    log.debug("Serial module could not be loaded.")

class PKSerial:
    '''
    Serial class to encapsulate PySerial to handle errors and retry/reconnect.
    '''
    def __init__(self, port=None, timeout=None, err_callback=None, status_callback=None, enable_retries=False):  # type: (Any,Any,Callable,Callable,bool) -> None
        self._err_callback = err_callback if err_callback is not None else self.null_err_callback
        self._status_callback = status_callback if status_callback is not None else self.null_status_callback
        self._retries_enabled = enable_retries      # type: bool
        self._pyserial = None
        self._lg_timeout = timeout
        if SERIAL_AVAILABLE:
            self._pyserial = pyserial
        else:
            self._err_callback("Serial module not available")
        self._port = None                           # type: pyserial.Serial|None
        self._port_name_used = None                 # type: str|None
        self._op_err_msg = None                     # type: str|None
        self._op_error_prev = None                  # type: str|None
        self._op_err_has_been_thrown = False        # type: bool
        self._module_ex_has_been_thrown = False     # type: bool
        self._reconnect_needed = False              # type: bool
        self._lg_cd = False                         # type: bool
        self._lg_cts = False                        # type: bool
        self._lg_dsr = False                        # type: bool
        self._lg_dtr = False                        # type: bool
        self._lg_ri = False                         # type: bool
        self._lg_rts = False                        # type: bool
        self._lg_timeout = timeout                  # type: float|None
        self._lg_write_timeout = None               # type: float|None

        # Thread to check port availability and to retry connection if lost
        self._thread_portchk = None                 # type: Thread|None
        self._portchk_t = time.time()               # type: float
        self._shutdown = Event()                    # type: Event

        self._port_requested = port                 # type: str|None
        self._port_to_use = None                    # type: str|None
        return

    def null_err_callback(self, msg):  # type: (str) -> None
        '''
        Error callback to use when one isn't supplied.
        '''
        log.debug("pykob.serial.PKSerial Error encountered: {}".format(msg), 5)
        return

    def null_status_callback(self, msg):  # type: (str) -> None
        '''
        Status callback to use when one isn't supplied.
        '''
        log.debug("pykob.serial.PKSerial Status: {}".format(msg), 5)
        return


    # #######################################################################
    # ### Properties wrapping 'Serial'                                    ###
    # #######################################################################

    @property
    def cd(self):  # type () -> bool
        s = self._lg_cd
        if (not self._chk_for_err()) and self._port is not None:
            try:
                s = self._port.cd
                self._lg_cd = s
            except Exception as ex:
                self._set_error(ex)
        return s

    @property
    def closed(self):  # type () -> bool
        self._chk_for_err()
        s = True
        try:
            s = self._port.closed if self._port is not None else True
        except Exception as ex:
            self._set_error(ex)
        return s

    @property
    def cts(self):  # type: () -> bool
        s = self._lg_cts
        if (not self._chk_for_err()) and self._port is not None:
            try:
                s = self._port.cts
                self._lg_cts = s
            except Exception as ex:
                self._set_error(ex)
        return s

    @property
    def dsr(self):  # type: () -> bool
        s = self._lg_dsr
        if (not self._chk_for_err()) and self._port is not None:
            try:
                s = self._port.dsr
                self._lg_dsr = s
            except Exception as ex:
                self._set_error(ex)
        return s

    @property
    def dtr(self):  # type: () -> bool
        s = self._lg_dtr
        if (not self._chk_for_err()) and self._port is not None:
            try:
                s = self._port.dtr
                self._lg_dtr = s
            except Exception as ex:
                self._set_error(ex)
        return s

    @dtr.setter
    def dtr(self, value):  # type: (bool) -> None
        self._lg_dtr = value
        if (not self._chk_for_err()) and self._port is not None:
            try:
                self._port.dtr = value
            except Exception as ex:
                self._set_error(ex)
        return

    @property
    def ri(self):  # type: () -> bool
        s = self._lg_ri
        if (not self._chk_for_err()) and self._port is not None:
            try:
                s = self._port.ri
                self._lg_ri = s
            except Exception as ex:
                self._set_error(ex)
        return s

    @property
    def rts(self):  # type: () -> bool
        s = self._lg_rts
        if (not self._chk_for_err()) and self._port is not None:
            try:
                s = self._port.rts
                self._lg_rts = s
            except Exception as ex:
                self._set_error(ex)
        return s

    @rts.setter
    def rts(self, value):  # type: (bool) -> None
        self._lg_rts = value
        if (not self._chk_for_err()) and self._port is not None:
            try:
                self._port.rts = value
            except Exception as ex:
                self._set_error(ex)
        return

    @property
    def timeout(self):  # Type: () -> float
        s = self._lg_timeout
        if (not self._chk_for_err()) and self._port is not None:
            try:
                s = self._port.timeout
                self._lg_timeout = s
            except Exception as ex:
                self._set_error(ex)
        return s

    @timeout.setter
    def timeout(self, value):  # Type: (float) -> None
        self._lg_timeout = value
        if (not self._chk_for_err()) and self._port is not None:
            try:
                self._port.timeout = value
            except Exception as ex:
                self._set_error(ex)
        return

    @property
    def write_timeout(self):  # Type: () -> float
        s = self._lg_write_timeout
        if (not self._chk_for_err()) and self._port is not None:
            try:
                s = self._port.write_timeout
                self._lg_write_timeout = s
            except Exception as ex:
                self._set_error(ex)
        return s

    @write_timeout.setter
    def write_timeout(self, value):  # type: (float) -> None
        self._lg_write_timeout = value
        if (not self._chk_for_err()) and self._port is not None:
            try:
                self._port.write_timeout = value
            except Exception as ex:
                self._set_error(ex)
        return

    # #######################################################################
    # ### Public 'Serial' Methods                                         ###
    # #######################################################################

    def close(self):  # type: () -> None
        if self._port is not None:
            try:
                self._port.close()
            except Exception as ex:
                self._set_error(ex)
            finally:
                self._port = None
        return

    def readline(self):  # type: () -> bytes
        read = bytes()
        if (not self._chk_for_err()) and self._port is not None:
            try:
                read = self._port.readline()
            except Exception as ex:
                self._set_error(ex)
        return read

    def write(self, data):  # type: (bytes|bytearray) -> int
        written = 0
        if (not self._chk_for_err()) and self._port is not None:
            try:
                written = self._port.write(data)
            except Exception as ex:
                self._set_error(ex)
        return written


    # #######################################################################
    # ### Internal Methods                                                ###
    # #######################################################################

    def _chk_for_err(self, allow_exception=False):  # type: (bool) -> bool # raises PKSerialError
        '''
        Check for an error (by checking the error message).
        If there is an error and retries are not enabled, or the `allow_exception`
        parameter is True, throw an exception. Otherwise, just return the status.
        '''
        if self._op_err_msg is not None:
            op_error = self._op_err_msg
            self._reconnect_needed = True
            if not op_error == self._op_error_prev:
                self._op_error_prev == op_error
                if not self._op_err_has_been_thrown:
                    if allow_exception or not self._retries_enabled:
                        self._op_err_has_been_thrown = True
                        self._op_err_msg = None
                        raise PKSerialPortError(op_error)
                    pass
                pass
            return True
        return False

    def _enable_retries(self):  # type: () -> None
        if self.serial_available and self._retries_enabled and not self._shutdown.is_set():
            self._thread_portchk = Thread(name="PKSerial-PortChk", target=self._thread_portchk_body)
            self._thread_portchk.start()
        return

    def _open_port(self): # type: () -> None
        if not self.serial_available:
            err_str = "PySerial module not available. Cannot open port: {}".format(self._port_requested)
            self._err_callback(err_str)
            if not self._module_ex_has_been_thrown:
                self._module_ex_has_been_thrown = True
                raise ModuleNotFoundError(err_str)
            if self._port_requested is None or len(self._port_requested) < 1:
                return
        self._port_to_use = self._port_requested
        if self._port_requested == PORT_FIND_SDIF_KEY or self._port_requested == PORT_FIND_SDSEL_KEY:
            """
            Look for a Silky-DESIGN Interface or Selector-Switch, by searching for a
            serial port with a serial number that ends in '_AESnnn' (nnn is the unit
            number '_AESnnnA' on Windows).
            Note: Early SD interfaces didn't have a unit number (nnn), and SilkyDESIGN-Selector
            switches have a serial number like '_AESSEL'.
            So, if the key is SDIF it is important to find interfaces and not selector switches.
            While, if the key is SDDEL it is important to find selector switches and not
            interfaces.
            If found, set the port ID. Else, indicate an error
            """
            sd_type = "Interface"
            sd_sel_srch = False
            if self._port_requested == PORT_FIND_SDSEL_KEY:
                sd_type = "Selector"
                sd_sel_srch = True
            level = 4 if self._reconnect_needed else 1
            log.debug("Try to find SD-{} on serial.".format(sd_type), level)
            re1 = re.compile(r"_AES([0-9]*)")
            re2 = re.compile(r"_AESSEL")
            sdif_port_id = None
            systemSerialPorts = psports.comports()
            for sp in systemSerialPorts:
                sn = sp.serial_number if sp.serial_number else ""
                m = re1.search(sn)
                if m:
                    # Found an SD device, see if it's an Interface or a Selector
                    is_sel = re2.search(sn)
                    if ((not sd_sel_srch) and (not is_sel)) or (sd_sel_srch and is_sel):
                        # We are looking for an Interface and this is one, or we are looking for a Selector and it is one.
                        sdif_port_id = sp.device
                        unit = m.group(1)
                        us = "" if not unit or len(unit) < 1 else " {}".format(unit)
                        log.log("\nSD-{}{} found on: {}\n".format(sd_type, us, sp.device), dt="")
                        break
                    pass
                pass
            self._port_to_use = sdif_port_id
            if self._port_to_use is None:
                if not self._reconnect_needed:
                    self._op_err_msg = "An SD-{} was not found.".format(sd_type)
                    log.debug(self._op_err_msg)
                return
            pass
        pass
        if self._port_to_use is not None:
            try:
                # Attempt to open the port
                self._port = pyserial.Serial(self._port_to_use)
                self._port.timeout = self._lg_timeout
                self._port.write_timeout = self._lg_write_timeout
                self._port_name_used = self._port_to_use
                self._op_err_msg = None
                self._op_error_prev = None
                self._op_err_has_been_thrown = False
                if self._reconnect_needed:
                    self._status_callback("Port '{}' connected".format(self._port_to_use))
                    self._reconnect_needed = False
            except Exception as ex:
                self._op_err_msg = "Error opening port '{}': {}".format(self._port_to_use, ex)
            pass
        return

    def _port_still_available(self, name):  # type: (str) -> bool
        systemSerialPorts = psports.comports()
        for sp in systemSerialPorts:
            spn = sp.device
            if name == spn:
                # Found the port we used
                return True
            pass
        return False

    def _set_error(self, ex):  # type: (Exception) -> None
        self._op_err_msg = "PKSerial Error: {}".format(ex)
        if self._port:
            try:
                self._port.close()
            except Exception:
                pass
            finally:
                self._port = None
                self._reconnect_needed = True
        if not self._op_err_has_been_thrown and not self._retries_enabled:
            self._err_callback(self._op_err_msg)
            self._op_err_has_been_thrown = True
            raise(PKSerialPortError(ex))
        else:
            self._status_callback(self._op_err_msg)
        return

    def _thread_portchk_body(self):  # type: () -> None
        """
        Called by the Port Check thread 'run' to assure the port is alive, or
        to retry opening it.
        """
        pass  # Breakpoint location for entering
        while not self._shutdown.is_set():
            now = time.time()
            if now - self._portchk_t > 3.2:
                self._portchk_t = now
                # If we have a port, try to access it. If we don't have a port
                # and one was requested, try to open it.
                if self._port is None:
                    if self._port_requested is not None and len(self._port_requested) > 0:
                        # try again to open it
                        self._open_port()
                else:
                    # We have a port, see if we can still access it without error
                    if not self._port_still_available(self._port_name_used):
                        self._port.close()
                        self._port = None
                        self._op_err_msg = "PKSerial Error: Port {} not available".format(self._port_name_used)
                    pass
                pass
            self._shutdown.wait(0.5)
        log.debug("{} thread done.".format(threading.current_thread().name))
        return



    # #######################################################################
    # ### Public properties specific to this class (not in 'Serial')      ###
    # #######################################################################

    @property
    def port_name_used(self):  # type: () -> str|None
        return self._port_name_used

    @property
    def port_requested(self):  # type: () -> str|None
        '''
        Name of the connected port (COMn, /dev/xxx) or None
        '''
        return self._port_requested

    @property
    def serial_available(self):  # type: () -> bool
        '''
        Indicate if the serial interface module is available.
        '''
        global SERIAL_AVAILABLE
        return SERIAL_AVAILABLE


    # #######################################################################
    # ### Public methods specific to this class (not in 'Serial')         ###
    # #######################################################################

    def exit(self):  # type: () -> None
        log.debug("PKSerial.exit - 1", 3)
        self.shutdown()
        if self._port and not self._port.closed:
            self._port.close()
            self._port = None
        if self._thread_portchk:
            self._thread_portchk.join()
        log.debug("PKSerial.exit - 2", 3)
        return

    def set_error_callback(self, err_callback):  # type: (Callable|None) -> None
        self._err_callback = err_callback if err_callback is not None else self.null_err_callback
        return

    def set_status_callback(self, status_callback):  # type: (Callable|None) -> None
        self._status_callback = status_callback if status_callback is not None else self.null_status_callback
        return

    def shutdown(self): # type: () -> None
        """
        Initiate shutdown of our operations (and don't start anything new),
        but DO NOT BLOCK.
        """
        if not self._shutdown.is_set():
            self._shutdown.set()
            log.debug("PKSerial.shutdown", 3)
            self._err_callback = self.null_err_callback
            self._status_callback = self.null_status_callback
        return

    def start(self):  # type: () -> None
        if self._port_requested is not None:
            self._open_port()
        self._enable_retries()
        self._chk_for_err(True)
        self._op_err_has_been_thrown = False        # Now allow exceptions from operations
        if self._op_err_msg is not None:
            self._err_callback(self._op_err_msg)
        return

