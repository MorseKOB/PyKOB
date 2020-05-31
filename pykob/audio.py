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
audio module

Provides audio for simulated sounder.
"""

import os
import wave
from pykob import log
try:
    import pyaudio
    ok = True
except:
    log.log('PyAudio not installed.')
    ok = False

BUFFERSIZE = 16

nFrames = [0, 0]
frames = [None, None]
nullFrames = None
iFrame = [0, 0]
sound = 0
if ok:
    pa = pyaudio.PyAudio()
    filename = ['clack48.wav', 'click48.wav']
    path = os.path.dirname(os.path.abspath(__file__))
    for i in range(2):
        fn = os.path.join(path, filename[i])
        f = wave.open(fn, mode='rb')
        nChannels = f.getnchannels()
        sampleWidth = f.getsampwidth()
        sampleFormat = pa.get_format_from_width(sampleWidth)
        frameWidth = nChannels * sampleWidth
        frameRate = f.getframerate()
        nFrames[i] = f.getnframes()
        frames[i] = f.readframes(nFrames[i])
        iFrame[i] = nFrames[i]
        f.close()
    nullFrames = bytes(frameWidth*BUFFERSIZE)

def play(snd):
    global sound
    sound = snd
    iFrame[sound] = 0

def callback(in_data, frame_count, time_info, status_flags):
    if frame_count != BUFFERSIZE:
        log.log('Unexpected frame count request from PyAudio:', frame_count)
    if iFrame[sound] + frame_count < nFrames[sound]:
        startByte = iFrame[sound] * frameWidth
        endByte = (iFrame[sound] + frame_count) * frameWidth
        outData = frames[sound][startByte:endByte]
        iFrame[sound] += frame_count
        return (outData, pyaudio.paContinue)
    else:
        return(nullFrames, pyaudio.paContinue)

if ok:
    apiInfo = pa.get_default_host_api_info()
    apiName = apiInfo['name']
    devIdx = apiInfo['defaultOutputDevice']
    devInfo = pa.get_device_info_by_index(devIdx)
    devName = devInfo['name']
    strm = pa.open(rate=frameRate, channels=nChannels, format=sampleFormat,
            output=True, output_device_index=devIdx, frames_per_buffer=BUFFERSIZE,
            stream_callback=callback)
