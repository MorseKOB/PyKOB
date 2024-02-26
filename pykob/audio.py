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

import wave
from pathlib import Path
from pykob import log
from threading import Event, Thread
from time import sleep
from typing import Any, List

class Audio:
    FRAMES_PER_BUFFER = 256

    def __init__(self):
        self._audio_available = False
        self._pa = None
        try:
            import pyaudio
            self._pa = pyaudio
            self._audio_available = True
        except:
            log.warn("Audio: PyAudio can't be loaded. Audio will not be available.")

        self._nChannels = [0, 0]
        self._frameRate = [0, 0]
        self._nFrames = [0, 0]
        self._frames = [None, None]
        self._nullFrames = None
        self._iFrame = [0, 0]
        self._sampleFormat = [0, 0]
        self._sampleWidth = [0, 0]
        self._sound = 0
        self._frameWidth = [0, 0]
        self._strm = [None, None]
        self._last_sound = -1

        if not self._audio_available:
            return
        self._pa = pyaudio.PyAudio()
        # Resource folder
        self._root_folder = Path(__file__).parent
        self._resource_folder = self._root_folder / "resources"
        # Audio files
        self._audio_files = ["clack48.wav", "click48.wav"]
        # self._audio_files = ["tone0.wav", "tone750.wav"]
        for i in range(len(self._audio_files)):
            fn = self._resource_folder / self._audio_files[i]
            log.debug("Load audio file: {}".format(fn), 8)
            f = wave.open(str(fn), mode='rb')
            self._nChannels[i] = f.getnchannels()
            self._sampleWidth[i] = f.getsampwidth()
            self._sampleFormat[i] = self._pa.get_format_from_width(self._sampleWidth[i])
            self._frameWidth[i] = self._nChannels[i] * self._sampleWidth[i]
            self._frameRate[i] = f.getframerate()
            self._nFrames[i] = f.getnframes()
            self._frames[i] = f.readframes(self._nFrames[i])
            self._iFrame[i] = self._nFrames[i]
            f.close()
        self._nullFrames = bytes(self._frameWidth[0] * Audio.FRAMES_PER_BUFFER)
        #
        self._apiInfo = self._pa.get_default_host_api_info()
        self._apiName = self._apiInfo["name"]
        self._devIdx = self._apiInfo["defaultOutputDevice"]
        self._devInfo = self._pa.get_device_info_by_index(self._devIdx)
        self._devName = self._devInfo["name"]
        for i in range(len(self._audio_files)):
            self._strm[i] = self._pa.open(
                rate=self._frameRate[i],
                channels=self._nChannels[i],
                format=self._sampleFormat[i],
                output=True,
                output_device_index=self._devIdx,
                frames_per_buffer=Audio.FRAMES_PER_BUFFER,
                stream_callback=self._audio_callback
            )

    def _audio_callback(self, in_data, frame_count, time_info, status_flags):
        if frame_count != Audio.FRAMES_PER_BUFFER:
            log.err("audio: Unexpected frame count request from PyAudio: {}".format(frame_count))
            return (self._nullFrames, 0)
        if self._iFrame[self._sound] + frame_count < self._nFrames[self._sound]:
            startByte = self._iFrame[self._sound] * self._frameWidth[self._sound]
            endByte = (self._iFrame[self._sound] + frame_count) * self._frameWidth[self._sound]
            outData = self._frames[self._sound][startByte:endByte]
            self._iFrame[self._sound] += frame_count
            return (outData, 0)
        else:
            return (self._nullFrames, 0)

    def audio_available(self):
        return self._audio_available

    def exit(self):
        self._iFrame[0] = self._nFrames[0]
        self._iFrame[1] = self._nFrames[1]

    def play(self, snd:int):
        if self._audio_available:
            log.debug("audio: play({})".format(snd), 8)
            self._sound = snd
            if not self._last_sound == self._sound:
                if self._last_sound >= 0:
                    self._iFrame[self._last_sound] = self._nFrames[self._last_sound]
                self._last_sound = self._sound
                self._iFrame[self._sound] = 0

class Audio2:
    def __init__(self):
        self._audio_available = False
        self._pg = None
        try:
            import pygame as pg
            from pygame import mixer
            from pygame.mixer import Sound
            pg.init()
            mixer.init()
            self._pg = pg
            self._mixer = mixer
            self._audio_available = True
        except:
            log.warn("Audio: pygame module can't be loaded. Audio will not be available.")

        # Get the Resource folder
        self._root_folder = Path(__file__).parent
        self._resource_folder = self._root_folder / "resources"
        # Audio files
        self._sounds:List[Sound,Sound] = [None, None]
        self._audio_files = ["clack48.wav", "click48.wav"]
        # self._audio_files:List[str,str] = ["tone0.wav", "tone750.wav"]
        for i in range(len(self._audio_files)):
            fn = self._resource_folder / self._audio_files[i]
            log.debug("Load audio file: {}".format(fn), 8)
            self._sounds[i] = self._mixer.Sound(str(fn))
        self._playing:Sound = None

    def audio_available(self):
        return self._audio_available

    def exit(self):
        log.debug("audio: EXIT", 4)
        if self._mixer:
            self._mixer.stop()
            self._mixer.quit()
        self._playing = None
        self._pg = None
        self._audio_available = False

    def play(self, snd:int):
        if self._audio_available:
            log.debug("audio: play({})".format(snd), 8)
            if self._playing:
                self._playing.stop()
                self._playing = None
            self._playing = self._sounds[snd].play()
