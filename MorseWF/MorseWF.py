#!/usr/bin/env python

"""

MorseWF.py

Supports the Wells Fargo Museums' telegraph displays. Accepts input from a key,
echos the input to a local sounder while also sending the Morse over the
internet to remote museum locations. All incoming and outgoing Morse is
decoded and the text is displayed on a monitor.

Optional command line parameters [default values in brackets]:
    wire - default wire to use in the absence of a jack box [0: none]
    idText - office call, etc. [if wire is specified, then idText is required]
    wpm - nominal code speed for decoding Morse [15]

MorseWF.py obtains certain configuration parameters from the file config.py
located in the same folder as the program itself. These parameters
are:
    PORT - which serial port to use for a key and/or sounder
    JACKPORT - which serial port to use for the jack box
    AUDIO - whether or not to enable the simulated sounder

Usage examples:
    py MorseWF.py  # local operation, default speed
    py MorseWF.py 201 "SF - Wells Fargo, San Francisco"  # wire 201
    py MorseWF.py 201 "PO - Wells Fargo, Portland" 18  # 18 wpm
    py MorseWF.py 0 "" 12  # decode characters at 12 wpm

Change history:

MorseWF 1.6  2019-02-21
- added SCREENSIZE parameter to config.py

MorseWF 1.5  2014-10-08
- added jack box interface
- fixed doubledecoding bug

MorseWF 1.4
- added config parameters for FONTNAME and FONTSIZE

MorseWF 1.3
- made compatible with MorseKOB 4.0-14 module library
- changed to International Morse
- changed default code speed to 15 wpm

"""

# import system and MorseKOB 4.0 library modules
import sys
import time
import threading
import pygame
import serial
import morsekob
from morsekob import kob, internet, morse, display, log
import config

# define constants
VERSION    = '1.6'
SCROLLWAIT = 50  # time to wait before clearing the screen (sec)
SCROLLTIME = 20  # time to spend scrolling the screen (sec)

# log configuration information
log.log('MorseWF ' + VERSION)
log.log('MorseKOB ' + morsekob.VERSION)

# get command line parameters
nargs = len(sys.argv)
wire = int(sys.argv[1]) if nargs > 2 else None
idText = sys.argv[2] if nargs > 2 else None
wpm = int(sys.argv[3]) if nargs > 3 else 15

# display decoded Morse as text
spaces = 0
def displayChar(char, spacing):
    global tLastDisplay, spaces
    if char == ' ':
        spaces += 1
    else:
        myDisplay.show(char, spaces + spacing)
        spaces = 0
    tLastDisplay = time.time()

# initialize MorseKOB 4.0 modules
myKOB = kob.KOB(config.PORT, config.AUDIO)
myReader = morse.Reader(wpm, codeType=morse.INTERNATIONAL, callback=displayChar)
mySender = morse.Sender(wpm, codeType=morse.INTERNATIONAL)
myInternet = internet.Internet(idText)
if wire:
    myInternet.connect(wire)
display.FONTNAME = config.FONTNAME
display.FONTSIZE = config.FONTSIZE
display.SCREENSIZE = config.SCREENSIZE
myDisplay = display.Display()

#--- Define Functions ---

# handle input from telegraph key    
def kobInput():
    global tLastDecode
    while True:
        code = myKOB.key()
        tLastDecode = sys.float_info.max
        myReader.decode(code)
        tLastDecode = time.time()
        if wire:
            myInternet.write(code)

# handle input from internet
def internetInput():
    global tLastDecode
    while True:
        code = myInternet.read()
        tLastDecode = sys.float_info.max
        myKOB.sounder(code)
        myReader.decode(code)
        tLastDecode = time.time()

# handle input from keyboard
def keyboardInput(char):
    if char:
        displayChar(char, 0)
        code = mySender.encode(char)
        myKOB.sounder(code)
        if wire:
            myInternet.write(code)

# handle input from jack box
def jackboxInput():
    global wire
    char = b'@'
    while True:
        c = jackbox.read()
        if c != char:
            char = c
            if c == b'@':
                wire = 0
            elif c == b'A':
                wire = 202
            elif c == b'B':
                wire = 203
            elif c == b'D':
                wire = 205
            else:
                log.log('Invalid jack box state.')
                wire = 0
            if wire:
                myInternet.connect(wire)
            else:
                myInternet.disconnect()
    
# start asynchronous thread
def launchThread(defn):
    thread = threading.Thread(target=defn)
    thread.daemon = True
    thread.start()

#--- Main Program ---

tLastDisplay = sys.float_info.max  # nothing on screen
tLastDecode = sys.float_info.max  # no decodes so far
flush = 10 * (1.2 / wpm)  # wait 10 dotlengths before flushing decode buffer
if myKOB.port:
    launchThread(kobInput)
if config.JACKPORT:
    jackbox = serial.Serial(config.JACKPORT, baudrate=9600)
    launchThread(jackboxInput)
elif wire:
    myInternet.connect(wire)
launchThread(internetInput)
    
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:  # stop if Esc key pressed
                running = False
            else:  # otherwise handle keyboard input
                keyboardInput(event.unicode)
    if time.time() - tLastDecode > flush:
        tLastDecode = sys.float_info.max
        myReader.flush()
    if time.time() - tLastDisplay > SCROLLWAIT:
        myDisplay.newLine(1)  # scroll up one pixel
    if time.time() - tLastDisplay > SCROLLWAIT + SCROLLTIME:
        tLastDisplay = sys.float_info.max  # nothing on screen
    time.sleep(0.010)

if wire:
    myInternet.disconnect()  # disconnect from wire when done
