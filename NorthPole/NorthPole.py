"""

NorthPole.py is a simple, GUI-less MorseKOB client.

To send, type on the keyboard and press Enter. Type a tilde (~) to open the
wire, and a plus sign (+) to close it.

Incoming Morse is decoded and displayed on the system console, a character at
a time. Note: with Linux you can use the following command to save a copy of
the console output to a file:
     python NorthPole.py | tee stdout foo.txt

Ctrl-Q quits the program. (You still have to press Enter.)

The program can drive a sounder by specifying the PORT parameter. A simulated
sounder can be activated by setting AUDIO to True (this only works if PyAudio
has been installed). Input from a key is not currently supported.

Merry Christmas!

"""

import sys
from morsekob import internet, morse, kob

# specify configuration options
ID = 'CB - NorthPole'
WIRE = 119
WPM = 18
AUDIO = False
PORT = None
#internet.HOST = '192.168.1.104'  # specify alternate server name or address

# decode incoming code packet from internet
def internetCallback(code):
    kob.sounder(code)
    reader.decode(code)

# print decoded Morse character
def readerCallback(char, spacing):
    if spacing > 3:
        sys.stdout.write('\n')
    if spacing > 0.5:
        sys.stdout.write(' ')
    sys.stdout.write(char)
    if char == '=':
        sys.stdout.write('\n')
    sys.stdout.flush()

# activate morsekob modules
wire = internet.Internet(ID, callback=internetCallback)
sender = morse.Sender(WPM)
reader = morse.Reader(WPM, callback=readerCallback)
kob = kob.KOB(port=PORT, audio=AUDIO)

# main program loop to accept keyboard input
wire.connect(WIRE)
running = True
while running:
    try:
        line = input()
    except:  # quit on EOF
        running = False
        break
    for char in line:
        if ord(char) == 17:  # quit on Ctrl-Q
            running = False
            break
        code = sender.encode(char)
        wire.write(code)
        kob.sounder(code)

# clean up when done
wire.disconnect()
