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
internet module

Reads/writes code sequences from/to a KOB wire.
"""
import re  # RegEx
import select
import socket
import struct
import threading
from threading import Event, Lock, Thread
import time
from typing import Any, Callable, Optional

from pykob import VERSION, config2, log, util
from pykob.config2 import Config

HOST_DEFAULT = "mtc-kob.dyndns.org"
PORT_DEFAULT = 7890

DIS = 2  # Disconnect
DAT = 3  # Code or ID
CON = 4  # Connect
ACK = 5  # Ack

NUL = '\x00'

shortPacketFormat = struct.Struct("<hh")  # cmd, wire
idPacketFormat = struct.Struct("<hh 128s 4x i i 8x 208x 128s 8x")  # cmd, byts, id, seq, idflag, ver
codePacketFormat = struct.Struct("<hh 128s 4x i 12x 51i i 128s 8x")  # cmd, byts, id, seq, code list, n, txt


class Internet:
    def __init__(self, officeID='', code_callback=None, record_callback=None, pckt_callback=None, appver=None, server_url=None, err_msg_hndlr=None):
        self._host = HOST_DEFAULT
        self._port = PORT_DEFAULT
        self._err_msg_hndlr = err_msg_hndlr if err_msg_hndlr else log.warn  # Function that can take a string
        self._ip_address = None  # Set when a connection is made
        s = None if not server_url else server_url.strip()
        if s and len(s) > 0:
            # Parse the URL into components
            ex = re.compile("^([^: ]*)((:?)([0-9]*))$")
            m = ex.match(s)
            h = m.group(1)
            cp = m.group(2)
            c = m.group(3)
            p = m.group(4)
            if h and len(h) > 0:
                self._host = h
            if p and len(p) > 0:
                try:
                    self._port = int(p)
                except ValueError:
                    self._err_msg_hndlr("Invalid port value '{}'. Using default {}".format(p, PORT_DEFAULT))
                    self._port = PORT_DEFAULT
        # Application name/version to register with on the server
        self._appver = None if appver == None or appver.strip() == "" else appver.strip()
        if appver:
            self._app = "{} (PK-{})".format(appver, VERSION).encode(encoding='latin-1')
        else:
            self._app = "PyKOB {}".format(VERSION).encode(encoding='latin-1')
        self._office_id = util.str_empty_or_value(officeID)
        self._wire_no = 0
        self._threadsGuard: Lock = Lock()
        self._shutdown: Event = Event()
        self._connected: Event = Event()
        self._sent_seq_no = 0
        self._rcvd_seq_no = -1
        self._t_last_listener = 0.0
        self._socket: Optional[socket.socket] = None
        socket.setdefaulttimeout(3.0)
        self._socketRDGuard: Lock = Lock()  # Guard for reading from the socket (get RD then WR for both)
        self._socketWRGuard: Lock = Lock()  # Guard for writing to the socket (get RD then WR for both)
        self._thread_inet_read: Thread = Thread(name="Internet-Data-Read", target=self._thread_inet_read_body)
        self._thread_keep_alive: Thread = Thread(name="Internet-Keep-Alive", target=self._thread_keep_alive_body)
        self._code_callback = code_callback
        self._packet_callback = pckt_callback
        self._record_callback = record_callback
        self._ID_callback = None
        self._sender_callback = None
        self._current_sender = None
        self._inet_available_check_time = 0
        self._internet_available = self.check_internet_available()
        return

    @property
    def connected(self) -> bool:
        return self._connected.is_set()

    @property
    def err_msg_hndlr(self):
        return self._err_msg_hndlr

    @property
    def host(self) -> str:
        """
        The host address being used.
        """
        return self._host

    @property
    def internet_available(self) -> bool:
        if int(time.time() - self._inet_available_check_time) > 10:
            self.check_internet_available()
        return self._internet_available

    @err_msg_hndlr.setter
    def err_msg_hndlr(self, f):
        self._err_msg_hndlr = f if not f is None else log.warn

    @property
    def packet_callback(self):
        return self._packet_callback

    @packet_callback.setter
    def packet_callback(self, cb):
        self._packet_callback = cb

    @property
    def port(self) -> int:
        """
        The host port being used.
        """
        return self._port

    def _thread_inet_read_body(self):
        """
        Called by the Internet Read thread `run` to read code from the internet connection.
        """
        while not self._shutdown.is_set():
            if self._connected.wait(0.01):
                code = self.read()
                if code and len(code) > 0 and self._connected.is_set() and not self._shutdown.is_set():
                    if self._code_callback:
                        self._code_callback(code)
                    if self._record_callback:
                        self._record_callback(code)
                else:
                    pass
            pass
        log.debug("{} thread done.".format(threading.current_thread().name))
        return

    def _thread_keep_alive_body(self):
        """
        Called by the Keep Alive thread `run` to send our ID to the internet connection.
        """
        while not self._shutdown.is_set():
            if self._connected.is_set():
                self._current_sender = None  # clear the current sender so it will update
                self.sendID()
                self._shutdown.wait(10.0)  # send another keepalive sequence every ten seconds
            self._shutdown.wait(1.0)  # don't hog CPU when we aren't connected
            pass
        log.debug("{} thread done.".format(threading.current_thread().name))
        return

    def _close_socket(self):
        log.debug("internet._close_socket - Getting socketGuards", 7)
        with self._socketRDGuard:
            with self._socketWRGuard:
                log.debug("internet._close_socket -  socketGuard-ed", 7)
                if self._socket:
                    # On Mac/Linux calling shutdown if the socket isn't connected is an error.
                    if self._connected.is_set():
                        self._socket.shutdown(socket.SHUT_RDWR)
                    self._socket.close()
                    self._socket = None
                log.debug("internet._close_socket -   socketGuards-release", 7)
        return

    def _create_socket(self):
        if self._shutdown.is_set():
            return
        log.debug("internet._create_socket - Getting socketGuards", 7)
        with self._socketRDGuard:
            with self._socketWRGuard:
                log.debug("internet._create_socket -  socketGuard-ed", 7)
                if not self._socket:
                    self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    self._socket.setblocking(False)
                    self._socket.settimeout(0.001)
                log.debug("internet._create_socket -   socketGuards-release", 7)
        self._get_address(renew=True)
        self.sendID()
        return

    def _start_wire_threads(self):
        if self._shutdown.is_set():
            return
        with self._threadsGuard:
            if not self._shutdown.is_set():
                if not self._thread_inet_read.is_alive():
                    self._thread_inet_read.start()
                if not self._thread_keep_alive.is_alive():
                    self._thread_keep_alive.start()
                while not (self._thread_inet_read.is_alive() and self._thread_keep_alive.is_alive()):
                    self._shutdown.wait(0.01)
            pass  #
        return

    def _get_address(self, renew=False):
        if not self._ip_address or renew:
            success = False
            while not success and not self._shutdown.is_set():
                try:
                    log.debug("internet._get_address - Connecting to host:{} port:{}".format(self._host, self._port))
                    self._ip_address = socket.getaddrinfo(self._host, self._port, socket.AF_INET, socket.SOCK_DGRAM)[0][4]
                    success = True
                    log.debug("internet._get_address - Received IP address:{}".format(self._ip_address), 2)
                except (OSError, socket.gaierror) as ex:
                    # Network error
                    s = "Network error: {} (Retrying in 5 seconds)".format(ex)
                    self._err_msg_hndlr("{}".format(s))
                    self._shutdown.wait(5.0)
        return self._ip_address

    def _stop_internet_threads(self):
        with self._threadsGuard:
            try:
                self._connected.clear()
                self._shutdown.set()
                self._close_socket()
            finally:
                if self._thread_keep_alive and self._thread_keep_alive.is_alive():
                    self._thread_keep_alive.join()
                    self._thread_keep_alive = None
                if self._thread_inet_read and self._thread_inet_read.is_alive():
                    self._thread_inet_read.join()
                    self._thread_inet_read = None
            pass
        return

    def connect(self, wireNo):
        self.disconnect()
        if self._shutdown.is_set():
            return
        self._wire_no = wireNo
        self._create_socket()
        self.sendID()
        self._connected.set()
        self._start_wire_threads()

    def disconnect(self, on_disconnect=None):
        if self._connected.is_set():
            self._wire_no = 0
            shortPacket = shortPacketFormat.pack(DIS, 0)
            try:
                log.debug("internet.disconnect - Getting socketWRGuard", 7)
                with self._socketWRGuard:
                    log.debug("internet.disconnect -  socketWRGuard-ed", 7)
                    if self._socket:
                        self._socket.sendto(shortPacket, self._get_address())
                log.debug("internet.disconnect -   socketWRGuard-release", 7)
            except:
                self._get_address(renew=True)
            finally:
                self._close_socket()
                pass
            self._connected.clear()
        if on_disconnect:
            on_disconnect()
        return

    def exit(self):
        """
        Stop the threads and exit.
        """
        self.shutdown()
        self._stop_internet_threads()
        return

    def check_internet_available(self, testhost="8.8.8.8", port=53):
        """
        Host: 8.8.8.8 (google-public-dns-a.google.com)
        OpenPort: 53/tcp
        Service: domain (DNS/TCP)
        """
        if self._shutdown.is_set():
            return False
        skt = None
        self._internet_available = False
        try:
            skt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            skt.connect((testhost, port))
            skt.close()
            self._internet_available = True
        except socket.error as ex:
            pass
        finally:
            self._inet_available_check_time = time.time()
        return self._internet_available

    def read(self):
        while self._socket and self._connected.is_set() and not self._shutdown.is_set():
            success = False
            buf = None
            nBytes = 0
            code = None
            while self._socket and self._connected.is_set() and not success and not self._shutdown.is_set():
                try:
                    # log.debug("internet.read - Getting socketRDGuard", 7)
                    with self._socketRDGuard:
                        # log.debug("internet.read -  socketRDGuard-ed", 7)
                        if self._socket:
                            data_ready = select.select([self._socket], [], [], 0)  # Check readability and never block
                            if len(data_ready[0]) > 0:
                                buf = self._socket.recv(500)
                                if not self._connected.is_set() or self._shutdown.is_set():
                                    return code
                                nBytes = len(buf)
                                if nBytes == 0:
                                    continue
                                success = True
                            else:
                                if self._shutdown.wait(0.005):
                                    break
                                else:
                                    continue
                        # log.debug("internet.read -   socketRDGuard-release", 7)
                except (TimeoutError) as toe:
                    # On timeout, just continue so we can check our flags
                    continue
                except (OSError) as ex1:
                    if ex1.errno == 10038:
                        return None  # Socket closed
                    if ex1.errno == 22:
                        return None  # Socket not ready
                    if ex1.errno == 9:
                        return None  # Socket closed
                    s = "Network error during read: {} (Retrying in 5 seconds)".format(ex1)
                    self._err_msg_hndlr("{}".format(s))
                    self._shutdown.wait(5.0)
                    continue
            log.debug("internet.read - recv:[{}]".format(buf), 6)
            if nBytes == 2:
                # ignore Ack packet, but indicate that it was received
                if self._packet_callback:
                    self._packet_callback("\n<rcvd: {}>".format(ACK))
            elif nBytes == 496:  # code or ID packet
                self._t_last_listener = time.time()
                cp = codePacketFormat.unpack(buf)
                cmd, byts, stnID, seqNo, code = cp[0], cp[1], cp[2], cp[3], cp[4:]
                stnID, sep, fill = stnID.decode(encoding='latin-1').partition(NUL)
                n = code[51]
                if n == 0:  # ID packet
                    if self._ID_callback:
                        self._ID_callback(stnID)
                    if seqNo == self._rcvd_seq_no + 2:
                        self._rcvd_seq_no = seqNo  # update sender's seq no, ignore others
                elif n > 0 and seqNo != self._rcvd_seq_no:  # code packet
                    if self._sender_callback:
                        if not self._current_sender or not self._current_sender == stnID:
                            self._current_sender = stnID
                            self._sender_callback(self._current_sender)
                    if seqNo != self._rcvd_seq_no + 1:  # sequence break
                        code = (-0x7fff,) + code[1:n]
                    else:
                        code = code[:n]
                    self._rcvd_seq_no = seqNo
                    if self._packet_callback:
                        self._packet_callback("\n<rcvd: {}:{}>".format(DAT, code))
                    return code
            elif not self._shutdown.is_set() and self._connected.is_set():
                log.warn("pykob.internet received invalid record length: {0}".format(nBytes))
            return
        return

    def write(self, code, txt=""):
        if self._connected.is_set() and not self._shutdown.is_set():
            n = len(code)
            if n == 0:
                return
            if n > 50:
                log.warn("PyKOB.internet: code sequence too long: {0}".format(n))
                return
            codeBuf = code + (51-n)*(0,) + (n, txt.encode(encoding='latin-1'))
            self._sent_seq_no += 1
            codePacket = codePacketFormat.pack(
                    DAT, 492, self._office_id.encode('latin-1'),
                    self._sent_seq_no, *codeBuf)
            for i in range(2):  # Retry once if we get an error trying to send.
                try:
                    log.debug("internet.write - Getting socketWRGuard", 7)
                    with self._socketWRGuard:
                        log.debug("internet.write -  socketWRGuard-ed", 7)
                        if self._socket:
                            log.debug("internet.write - sendto:[{}]".format(codePacket), 6)
                            self._socket.sendto(codePacket, self._get_address())
                    log.debug("internet.write -   socketWRGuard-release", 7)
                    break
                except:
                    self._get_address(renew=True)
            # Write packet info if requested
            if self._packet_callback:
                self._packet_callback("\n<sent: {}:{}>".format(DAT, code))
        return

    def sendID(self):
        if self._connected.is_set() and not self._shutdown.is_set():
            try:
                log.debug("internet.sendID - Getting socketWRGuard", 7)
                with self._socketWRGuard:
                    log.debug("internet.sendID -  socketWRGuard-ed", 7)
                    if self._socket:
                        shortPacket = shortPacketFormat.pack(CON, self._wire_no)
                        self._socket.sendto(shortPacket, self._get_address())
                        self._sent_seq_no += 2
                        idPacket = idPacketFormat.pack(DAT, 492, self._office_id.encode('latin-1'),
                                self._sent_seq_no, 1, self._app)
                        self._socket.sendto(idPacket, self._ip_address)
                    log.debug("internet.sendID -   socketWRGuard-release", 7)
                if self._packet_callback:
                    self._packet_callback("\n<sent: {}>".format(DAT))
                if self._ID_callback:
                    self._ID_callback(self._office_id)
            except (OSError, socket.gaierror) as ex:
                self._get_address(renew=True)
        return

    def set_officeID(self, officeID):
        """Sets the office/station ID for use on a connected wire"""
        self._office_id = util.str_empty_or_value(officeID)

    def monitor_IDs(self, ID_callback):
        """start monitoring incoming and outgoing station IDs"""
        self._ID_callback = ID_callback

    def monitor_sender(self, sender_callback):
        """start monitoring changes in current sender"""
        self._sender_callback = sender_callback
        self._current_sender = None

    def record_code(self, record_callback):
        """Start recording code received and sent"""
        self._record_callback = record_callback

    def shutdown(self):
        """
        Initiate shutdown of our operations (and don't start anything new), 
        but DO NOT BLOCK.
        """
        self.disconnect()
        self._shutdown.set()
        self._ID_callback = None
        self._sender_callback = None
        self._record_callback = None
        return
