"""

internet module

Reads/writes code sequences from/to a KOB wire.

"""

import socket
import struct
import threading
import time
from morsekob import VERSION, log

HOST = 'mtc-kob.dyndns.org'
PORT = 7890

DIS = 2  # Disconnect
DAT = 3  # Code or ID
CON = 4  # Connect
ACK = 5  # Ack

shortPacketFormat = struct.Struct('<hh')  # cmd, wire
idPacketFormat = struct.Struct('<hh 128s 4x i i 8x 208x 128s 8x')  # cmd, byts, id, seq, idflag, ver
codePacketFormat = struct.Struct('<hh 128s 4x i 12x 51i i 128x 8x')  # cmd, byts, id, seq, code list, n

NUL = '\x00'

class Internet:
    def __init__(self, officeID):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.address = socket.getaddrinfo(HOST, PORT, socket.AF_INET,
                socket.SOCK_DGRAM)[0][4]
        self.version = ('MorseKOB ' + VERSION).encode(encoding='ascii')
        self.officeID = officeID.encode(encoding='ascii')
        self.wireNo = 0
        self.sentSeqNo = 0
        self.rcvdSeqNo = -1
        self.tLastListener = 0
        self.disconnect()  # to establish a UDP connection with the server
        keepAliveThread = threading.Thread(target=self.keepAlive)
        keepAliveThread.daemon = True
        keepAliveThread.start()

    def connect(self, wireNo):
        self.wireNo = wireNo
        self.sendID()

    def disconnect(self):
        self.wireNo = 0
        shortPacket = shortPacketFormat.pack(DIS, 0)
        self.socket.sendto(shortPacket, self.address)

    def read(self):
        while True:
            buf = self.socket.recv(500)
            nBytes = len(buf)
            if nBytes == 2:
                pass  # ignore Ack packet
            elif nBytes == 496:  # code or ID packet
                self.tLastListener = time.time()
                # stnID, seqNo, *code = codePacketFormat.unpack(buf)  # works in Python 3.x
                cp = codePacketFormat.unpack(buf)  # Python 2.7...
                cmd, byts, stnID, seqNo, code = cp[0], cp[1], cp[2], cp[3], cp[4:]  # ...equivalent
                stnID, sep, fill = stnID.decode(encoding='ascii').partition(NUL)
                n = code[51]
                if n == 0 and seqNo == self.rcvdSeqNo + 2:  # ID packet
                    self.rcvdSeqNo = seqNo  # update sender's, ignore others
                if n > 0 and seqNo != self.rcvdSeqNo:  # code packet
                    if seqNo != self.rcvdSeqNo + 1:  # sequence break
                        code = (-0x7fff,) + code[1:n]
                    else:
                        code = code[:n]
                    self.rcvdSeqNo = seqNo
                    return code
            else:
                log.log('MorseKOB.internet received invalid record length: {0}'.
                        format(nBytes))

    def write(self, code):
        n = len(code)
        if n == 0:
            return
        codeBuf = code + (51-n)*(0,) + (n,)
        self.sentSeqNo += 1
        codePacket = codePacketFormat.pack(DAT, 492, self.officeID,
                self.sentSeqNo, *codeBuf)
        for i in range(2):
            self.socket.sendto(codePacket, self.address)
        
    def keepAlive(self):
        while True:
            self.sendID()
            time.sleep(10.0)  # send another keepalive sequence every ten seconds

    def sendID(self):
        try:
            self.address = socket.getaddrinfo(HOST, PORT, socket.AF_INET,
                    socket.SOCK_DGRAM)[0][4]
        except:
            log.log('morsekob.internet ignoring DNS lookup error')
        if self.wireNo:
            shortPacket = shortPacketFormat.pack(CON, self.wireNo)
            self.socket.sendto(shortPacket, self.address)
            self.sentSeqNo += 2
            idPacket = idPacketFormat.pack(DAT, 492, self.officeID,
                    self.sentSeqNo, 1, self.version)
            self.socket.sendto(idPacket, self.address)
