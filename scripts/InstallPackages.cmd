:: Install the PyAudio and pySerial modules required by PyKOB.
:: Python 3 must be installed first.

@echo off
py -m pip install --upgrade pip
py -m pip install pipwin 
py -m pipwin install pyaudio
py -m pip install pyserial
pause
