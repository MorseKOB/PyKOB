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
audio module

Provides audio for simulated sounder or tone.
"""

import wave
from pathlib import Path
from pykob import log
from pykob.config import AudioType
from threading import Event, Thread
from time import monotonic, sleep
from typing import List

class Audio:
    # Preferred (smallest) callback size, for the lowest latency/jitter.
    FRAMES_PER_BUFFER = 16
    # Callback sizes to try, in order, if the stream doesn't run with a smaller one.
    # PyAudio always opens the stream with the device's *low* default latency and offers no
    # way to change it, so the callback size is the only lever on the host buffer size.
    # Some audio servers (for example PipeWire with a large 'clock.min-quantum', reached
    # through its ALSA plugin) never consume from a host buffer smaller than their quantum.
    # The stream then stalls after the first callbacks and only silence is heard.
    # The stream can also run partially (consuming frames slower than the sample rate),
    # which is why the rate is measured rather than just checking for any progress.
    FRAMES_PER_BUFFER_FALLBACKS = (128, 512, 1024, 2048, 4096)
    # A newly opened stream is allowed to settle (pre-fill its buffers), then the rate at
    # which it consumes frames is measured. It must reach this fraction of the sample rate.
    STREAM_SETTLE_SECS = 0.06
    STREAM_CHECK_SECS = 0.15
    STREAM_CHECK_MIN_RATIO = 0.8

    def __init__(self, audio_type: AudioType = AudioType.SOUNDER):
        self._audio_type = audio_type
        self._audio_available = False
        self._pa = None
        self._pyaudio = None
        self._callback_retval = None
        try:
            import pyaudio
            self._pyaudio = pyaudio
            self._callback_retval = pyaudio.paContinue
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
        self._strm = None
        self._frames_per_buffer = Audio.FRAMES_PER_BUFFER
        self._frames_consumed = 0  # Frames requested by the stream (used to detect a stalled stream)

        if not self._audio_available:
            return
        self._pa = pyaudio.PyAudio()
        # Resource folder
        self._root_folder = Path(__file__).parent
        self._resource_folder = self._root_folder / "resources"
        # Audio files
        self._audio_files = (
            ["clack48.wav", "click48.wav"]
            if self._audio_type == AudioType.SOUNDER
            else ["tone0.wav", "tone750.wav"]
        )
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
        #
        self._apiInfo = self._pa.get_default_host_api_info()
        self._apiName = self._apiInfo["name"]
        self._devIdx = self._apiInfo["defaultOutputDevice"]
        self._devInfo = self._pa.get_device_info_by_index(self._devIdx)
        self._devName = self._devInfo["name"]
        self._open_stream()

    def _open_stream(self):
        """
        Open the output stream with the smallest callback size that the audio
        system actually consumes (see FRAMES_PER_BUFFER_FALLBACKS).
        """
        candidates = (Audio.FRAMES_PER_BUFFER,) + Audio.FRAMES_PER_BUFFER_FALLBACKS
        rate = self._frameRate[0]
        for fpb in candidates:
            self._frames_per_buffer = fpb
            self._nullFrames = bytes(self._frameWidth[0] * fpb)
            self._frames_consumed = 0
            self._strm = self._pa.open(
                rate=self._frameRate[0],
                channels=self._nChannels[0],
                format=self._sampleFormat[0],
                output=True,
                output_device_index=self._devIdx,
                frames_per_buffer=fpb,
                stream_callback=self._audio_callback
            )
            sleep(Audio.STREAM_SETTLE_SECS)
            c0 = self._frames_consumed
            t0 = monotonic()
            sleep(Audio.STREAM_CHECK_SECS)
            ratio = (self._frames_consumed - c0) / ((monotonic() - t0) * rate)
            if ratio >= Audio.STREAM_CHECK_MIN_RATIO:
                log.debug("audio: Stream running on '{}' ({}) with {} frames/buffer.".format(
                    self._devName, self._apiName, fpb), 2)
                return
            log.debug("audio: Stream with {} frames/buffer only runs at {:.0%} of {} Hz. Trying larger buffer.".format(
                fpb, ratio, rate), 2)
            self._strm.close()
            self._strm = None
        # Nothing worked. Keep the preferred size so we behave as before (and report it).
        log.warn("audio: Audio output on '{}' ({}) does not appear to be running. Synth sounder/tone may be silent.".format(
            self._devName, self._apiName))
        self._frames_per_buffer = Audio.FRAMES_PER_BUFFER
        self._nullFrames = bytes(self._frameWidth[0] * Audio.FRAMES_PER_BUFFER)
        self._strm = self._pa.open(
            rate=self._frameRate[0],
            channels=self._nChannels[0],
            format=self._sampleFormat[0],
            output=True,
            output_device_index=self._devIdx,
            frames_per_buffer=Audio.FRAMES_PER_BUFFER,
            stream_callback=self._audio_callback
        )

    def _audio_callback(self, in_data, frame_count, time_info, status_flags):
        self._frames_consumed += frame_count
        snd = self._sound
        frame_width = self._frameWidth[snd]
        i_frame = self._iFrame[snd]
        n = min(frame_count, self._nFrames[snd] - i_frame)
        if n <= 0:
            if frame_count == self._frames_per_buffer:
                return (self._nullFrames, self._callback_retval)
            return (bytes(frame_count * frame_width), self._callback_retval)
        outData = self._frames[snd][i_frame * frame_width:(i_frame + n) * frame_width]
        self._iFrame[snd] = i_frame + n
        if n < frame_count:
            # End of the sound - pad the rest of the buffer with silence
            outData += bytes((frame_count - n) * frame_width)
        return (outData, self._callback_retval)

    def audio_available(self):
        return self._audio_available

    def exit(self):
        """
        Stop and close the audio stream and release PortAudio.

        This must happen before the interpreter shuts down. Otherwise the PortAudio
        callback thread can call into a finalizing interpreter, which crashes
        (segmentation fault).
        """
        self.shutdown()
        self._audio_available = False
        strm, self._strm = self._strm, None
        if strm:
            try:
                strm.stop_stream()
                strm.close()
            except Exception as ex:
                log.debug("audio: Error closing stream: {}".format(ex), 2)
        pa, self._pa = self._pa, None
        if pa:
            try:
                pa.terminate()
            except Exception as ex:
                log.debug("audio: Error terminating PyAudio: {}".format(ex), 2)
        return

    def play(self, snd:int):
        if self._audio_available:
            self._iFrame[snd] = 0
            self._sound = snd

    def shutdown(self):
        """
        Initiate shutdown of our operations (and don't start anything new),
        but DO NOT BLOCK.
        """
        self._callback_retval = None if not self._pyaudio else self._pyaudio.paAbort
        self._iFrame[0] = self._nFrames[0]
        self._iFrame[1] = self._nFrames[1]
        return

''' Commented out to avoid pygame and its dependencies being included in binary builds.
class Audio2:

    def __init__(self, audio_type: AudioType = AudioType.SOUNDER):
        self._audio_type = audio_type
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
        self._audio_files = (
            ["clack48.wav", "click48.wav"]
            if self._audio_type == AudioType.SOUNDER
            else ["tone0.wav", "tone750.wav"]
        )
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

    def shutdown(self):
        """
        Initiate shutdown of our operations (and don't start anything new), 
        but DO NOT BLOCK.
        """
        self._shutdown.set()
        return
'''