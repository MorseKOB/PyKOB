"""
MIT License

Copyright (c) 2020 PyKOB - MorseKOB in Python

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

import socket
import struct
import time
from pykob import VERSION, config, log
from threading import Event, Thread

HOST_DEFAULT = "mtc-kob.dyndns.org"
PORT_DEFAULT = 7890

DIS = 2  # Disconnect
DAT = 3  # Code or ID
CON = 4  # Connect
ACK = 5  # Ack

shortPacketFormat = struct.Struct("<hh")  # cmd, wire
idPacketFormat = struct.Struct("<hh 128s 4x i i 8x 208x 128s 8x")  # cmd, byts, id, seq, idflag, ver
codePacketFormat = struct.Struct("<hh 128s 4x i 12x 51i i 128s 8x")  # cmd, byts, id, seq, code list, n, txt

NUL = '\x00'

class Internet:
    def __init__(self, officeID, code_callback=None, record_callback=None, pckt_callback=None, mka=None):
        self.host = HOST_DEFAULT
        self.port = PORT_DEFAULT
        self.mka = mka # MKOBAction - to be able to display warning messages to the user
        self.address = None
        s = config.server_url
        if s:
            # see if a port was included
            # ZZZ error checking - should have 0 or 1 ':' and if port is included it should be numeric
            hp = s.split(':',1)
            if len(hp) == 2:
                self.port = hp[1]
            self.host = hp[0]
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.version = ("PyKOB " + VERSION).encode(encoding='latin-1')
        self.officeID = officeID if officeID != None else ""
        self.wireNo = 0
        self.sentSeqNo = 0
        self.rcvdSeqNo = -1
        self.tLastListener = 0.0
        self.threadStop = Event()
        self.disconnect()  # to establish a UDP connection with the server
        self.keepAliveThread = Thread(name='Internet-KeepAlive', daemon=True, target=self.keepAlive)
        self.keepAliveThread.start()
        self._code_callback = code_callback
        self._packet_callback = pckt_callback
        self._record_callback = record_callback
        self.internetReadThread = None
        if code_callback or record_callback:
            self.internetReadThread = Thread(name='Internet-DataRead', daemon=True, target=self.callbackRead)
            self.internetReadThread.start()
        self.ID_callback = None
        self.sender_callback = None

    @property
    def packet_callback(self):
        return self._packet_callback
    
    @packet_callback.setter
    def packet_callback(self, cb):
        self._packet_callback = cb

    def _get_address(self, renew=False):
        if not self.address or renew:
            success = False
            while not success:
                try:
                    self.address = socket.getaddrinfo(self.host, self.port, socket.AF_INET, socket.SOCK_DGRAM)[0][4]
                    success = True
                except (OSError, socket.gaierror) as ex:
                    # Network error
                    s = "Network error ({}) - Retrying in 5 seconds".format(ex)
                    log.warn(s)
                    if self.mka:
                        self.mka.trigger_reader_append_text("{}\n".format(s))
                    time.sleep(5.0)
        return self.address

    def connect(self, wireNo):
        self.wireNo = wireNo
        self.sendID()

    def disconnect(self):
        self.wireNo = 0
        shortPacket = shortPacketFormat.pack(DIS, 0)
        try:
            self.socket.sendto(shortPacket, self._get_address())
        except:
            self._get_address(renew=True)

    def exit(self):
        """
        Stop the threads and exit.
        """
        self.threadStop.set()

    def callbackRead(self):
        """
        Called by the Internet Read thread `run` to read code from the internet connection.
        """
        while not self.threadStop.is_set():
            code = self.read()
            if self._code_callback:
                self._code_callback(code)
            if self._record_callback:
                self._record_callback(code)

    def read(self):
        while True:
            success = False
            buf = None
            nBytes = 0
            while not success:
                try:
                    buf = self.socket.recv(500)
                    nBytes = len(buf)
                    success = True
                except (OSError, socket.gaierror) as ex:
                    # Network error
                    s = "Network error ({}) - Retrying in 5 seconds".format(ex)
                    log.warn(s)
                    if self.mka:
                        self.mka.trigger_reader_append_text("{}\n".format(s))
                    time.sleep(5.0)
            if nBytes == 2:
                # ignore Ack packet, but indicate that it was received
                if self._packet_callback:
                    self._packet_callback("\n<rcvd: {}>".format(ACK))
            elif nBytes == 496:  # code or ID packet
                self.tLastListener = time.time()
                cp = codePacketFormat.unpack(buf)
                cmd, byts, stnID, seqNo, code = cp[0], cp[1], cp[2], cp[3], cp[4:]
                stnID, sep, fill = stnID.decode(encoding='latin-1').partition(NUL)
                n = code[51]
                if n == 0:  # ID packet
                    if self.ID_callback:
                        self.ID_callback(stnID)
                    if seqNo == self.rcvdSeqNo + 2:
                        self.rcvdSeqNo = seqNo  # update sender's seq no, ignore others
                elif n > 0 and seqNo != self.rcvdSeqNo:  # code packet
                    if self.sender_callback:
                        self.sender_callback(stnID)
                    if seqNo != self.rcvdSeqNo + 1:  # sequence break
                        code = (-0x7fff,) + code[1:n]
                    else:
                        code = code[:n]
                    self.rcvdSeqNo = seqNo
                    if self._packet_callback:
                        self._packet_callback("\n<rcvd: {}:{}>".format(DAT, code))
                    return code
            else:
                log.warn("PyKOB.internet received invalid record length: {0}".format(nBytes))

    def write(self, code, txt=""):
        n = len(code)
        if n == 0:
            return
        if n > 50:
            log.warn("PyKOB.internet: code sequence too long: {0}".format(n))
            return
        codeBuf = code + (51-n)*(0,) + (n, txt.encode(encoding='latin-1'))
        self.sentSeqNo += 1
        codePacket = codePacketFormat.pack(
                DAT, 492, self.officeID.encode('latin-1'),
                self.sentSeqNo, *codeBuf)
        for i in range(2):
            try:
                self.socket.sendto(codePacket, self._get_address())
            except:
                self._get_address(renew=True)
        # Write packet info if requested
        if self._packet_callback:
            self._packet_callback("\n<sent: {}:{}>".format(DAT, code))


    def keepAlive(self):
        while not self.threadStop.is_set():
            self.sendID()
            time.sleep(10.0)  # send another keepalive sequence every ten seconds

    def sendID(self):
        if self.wireNo:
            try:
                shortPacket = shortPacketFormat.pack(CON, self.wireNo)
                self.socket.sendto(shortPacket, self._get_address())
                self.sentSeqNo += 2
                idPacket = idPacketFormat.pack(DAT, 492, self.officeID.encode('latin-1'),
                        self.sentSeqNo, 1, self.version)
                self.socket.sendto(idPacket, self.address)
                if self._packet_callback:
                    self._packet_callback("\n<sent: {}>".format(DAT))
                if self.ID_callback:
                    self.ID_callback(self.officeID)
            except (OSError, socket.gaierror) as ex:
                self._get_address(renew=True)

    def set_officeID(self, officeID):
        """Sets the office/station ID for use on a connected wire"""
        self.officeID = officeID if officeID != None else ""

    def monitor_IDs(self, ID_callback):
        """start monitoring incoming and outgoing station IDs"""
        self.ID_callback = ID_callback

    def monitor_sender(self, sender_callback):
        """start monitoring changes in current sender"""
        self.sender_callback = sender_callback

    def record_code(self, record_callback):
        """Start recording code received and sent"""
        self._record_callback = record_callback

