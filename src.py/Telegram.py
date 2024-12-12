#!/usr/bin/env python3
"""
MIT License

Copyright (c) 2020-2024 PyKOB - MorseKOB in Python

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
Telegram.py

This presents a single, telegram style, page that can fill the entire
screen. The page will display messages entered on the keyboard or with a
connected key. Messages will be sounded on a connected sounder or using the
simulated sounder from the computer's audio.

After a configured period of time the page (screen) clears itself back to
a blank telegram form.

Telegram can connect to a Wire on a KOBServer to send the message to or
to receive messages from.

For the majority of the settings it reads the current configuration (the
same as MKOB and MRT) and it supports the common option flags. For options
specific to Telegram (time before clearing the page, font, font size, page
color, and more) it looks in the application's current directory.

    Use `--help` on the command line.

"""

import argparse
from ast import literal_eval
import json
from json import JSONDecodeError
import pygame
from pygame.font import Font
from pygame import Surface
import os
from os import path as path_func
import sys
from sys import platform as sys_platform
from sys import version as sys_version
from threading import Event
import time

from pykob import VERSION, config2, log, kob, internet, morse
from pykob.kob import CodeSource
from pykob import VERSION as PKVERSION
from pykob.config2 import Config
from pykob.internet import Internet
from pykob.kob import KOB
from pykob.morse import Reader, Sender

COMPILE_INFO = globals().get("__compiled__")
__version__ = '1.0.1'
VERSION = __version__ if COMPILE_INFO is None else __version__ + 'c'
TELEGRAM_VERSION_TEXT = "Telegram " + VERSION

TELEGRAM_CFG_FILE_NAME = "tg_config.tgc"

FLUSH    = 20  # time to wait before flushing decode buffer (dots)
STARTMSG = (-0x7fff, +2, -1000, +2)  # code sequence sent at start of telegram
ENDMSG   = (-1000, +1)  # ending code sequence
LATCH_CODE = (-0x7fff, +1)  # code sequence to force latching (close)
UNLATCH_CODE = (-0x7fff, +2)  # code sequence to unlatch (open)

class PGDisplay:
    """
    Holds a PyGame display surface and provides useful methods that operate on
    the display/Surface.
    """
    def __init__(self, width, height, page_color, text_color, font, font_size=0, side_margin=0):  # type: (int, int, any, any, str|Font, int, int) -> None
        self._scr_size = (width, height)
        self._screen = pygame.display.set_mode(self._scr_size)  # 'flags' can have pygame.FULLSCREEN
        self._clock = pygame.time.Clock()
        self._page_color = page_color
        self._text_color = text_color
        self._font = font if isinstance(font, Font) else pygame.font.SysFont(font, font_size)
        self._text_left_margin = side_margin
        self._text_right_margin = self._screen.get_width() - self._text_left_margin
        self._text_x = 0
        self._text_y = 0
        self._shutdown = Event()
        return

    @property
    def caption(self):  # type: () -> str
        return pygame.display.get_caption()
    @caption.setter
    def caption(self, s):  # type: (str) -> None
        pygame.display.set_caption(s)
        return

    @property
    def height(self):  # type: () -> int
        return self._screen.height

    @property
    def width(self):  # type: () -> int
        return self._screen.width


    def blit(self, sprite, pos, update=True, set_text_top=True):  # type: (Surface, tuple[int,int], bool, bool) -> None
        """
        Blit (draw/render) a Surface sprite onto the form.
        """
        self._screen.blit(sprite, pos)
        if set_text_top:
            # Set the text y value to be below the bottom of the sprite
            sh = sprite.get_height()
            self._text_y = pos[1] + sh
        if update:
            pygame.display.update()
        return

    def exit(self):  # type: () -> None
        self._screen = None
        pygame.display.quit()
        return

    def form_update(self):  # type: () -> None
        pygame.display.update()
        return

    def new_form(self, update=True, scroll_time=0.0):  # type: (bool, float) -> None
        """
        Display a new, blank, form...
        If scroll_time is 0 the form will just be cleared instantly.
        If scroll_time is non-zero it is the time, in seconds, to take to scroll the
        contents off.
        A positive value will scroll the contents up, negative down.
        """
        if scroll_time == 0:
            self._screen.fill(self._page_color)
        else:
            dy = 4
            dir = -1 if scroll_time > 0 else 1
            st = abs(scroll_time)
            si = int(((self._screen.height / dy) / st) + 0.5)
            pt = st / si
            rec_top = 0 if dir > 0 else self._screen.height - dy
            scroll_to_go = self._screen.height
            ddy = dy * dir
            while scroll_to_go > 0:
                self._screen.scroll(dx=0, dy=ddy)
                # fill the evacuated space
                fr = pygame.Rect(0,rec_top,self._screen.width, dy)
                self._screen.fill(self._page_color, fr)
                pygame.display.update()
                scroll_to_go -= dy
                if scroll_to_go < dy:
                    dy = scroll_to_go
                self._shutdown.wait(pt)
            pass
        pass
        self._text_x = self._text_left_margin
        self._text_y = 0
        if update:
            pygame.display.update()
        return

    def line_advance(self, lines=1):  # type: (int) -> None
        self._text_x = self._text_left_margin
        self._text_y += (self._font.get_linesize() * lines)
        return

    def output(self, text, bold=False, italic=False, update=True, spacing=1.0):  # type: (str, bool, float) -> None
        if text is None:
            return
        lines_of_words = [word.split(' ') for word in text.splitlines()]
        font = self._font
        font.bold = bold
        font.italic = italic
        space_width = font.size(' ')[0]
        spacing_width = int(space_width * spacing)
        x = self._text_x
        y = self._text_y
        first_line = True
        for line in lines_of_words:
            if not first_line:
                # New Line
                x = self._text_left_margin
                y += font.get_linesize()
            first_word = True
            for word in line:
                if not first_word:
                    x += spacing_width
                word_glyphs = font.render(word, True, self._text_color)
                word_width, word_height = word_glyphs.get_size()
                if x + word_width > self._text_right_margin:
                    x = self._text_left_margin
                    y += word_height
                self._screen.blit(word_glyphs, (x,y))
                x += int(word_width + (spacing_width * 0.2))
                first_word = False
            first_line = False
        if update:
            pygame.display.update()
        # Update our positions
        self._text_x = x
        self._text_y = y
        return

    def scroll(self, plines):  # type: (int) -> None
        """
        Scroll the display/form up (positive) or down (negative) by
        pixel-lines.
        """
        self._text_y += plines
        return

    def shutdown(self):  # type: () -> None
        self._shutdown.set()
        return

    def start(self):  # type: () -> None
        self._screen.fill(self._page_color)
        pygame.display.update()
        return

class ConfigLoadError(Exception):
    pass

class TelegramConfig:
    """
    Container for the Telegram specific configuration values.
    """
    FONT_KEY = "font"
    FONT_BOLD_KEY = "font_bold"
    FONT_ITALIC_KEY = "font_italic"
    FONT_SIZE_KEY = "font_size"
    PAGE_CLEAR_IDLE_TIME_KEY = "page_clear_idle_time"
    PAGE_CLEAR_SPEED_KEY = "page_clear_speed"
    PAGE_COLOR_KEY = "page_color"
    TEXT_COLOR_KEY = "text_color"
    MASTHEAD_FILE_PATH = "masthead_file"
    MASTHEAD_FONT_KEY = "masthead_font"
    MASTHEAD_FONT_SIZE_KEY = "masthead_font_size"
    MASTHEAD_TEXT_KEY = "masthead_text"
    MASTHEAD_TEXT_COLOR_KEY = "masthead_text_color"
    SIDE_MARGIN_KEY = "side_margin"
    TOP_MARGIN_KEY = "top_margin"


    def __init__(self, tgcfg_file_path):  # type: (str|None) -> None
        self._cfg_filep = tgcfg_file_path
        # Default values...
        self._font = "courier"  # type: str
        self._font_bold = False  # type: bool
        self._font_italic = False  # type: bool
        self._font_size = 20  # type: int
        self._text_color = "black"  # type: str|tuple[int,int,int]
        self._page_clear_idle_time = 8.0  # type: float  # Seconds of idle before clear
        self._page_clear_speed = 1.8  # type: float  # Time to take to scroll the page (can be negative)
        self._page_color = (198,189,150)  # type: str|tuple[int,int,int] # Tan
        self._masthead_filep = None  # type: str|None
        self._masthead_font = self._font
        self._masthead_font_size = self._font_size
        self._masthead_text = None  # type: str|None
        self._masthead_text_color = "black"  # type: str|tuple[int,int,int]
        self._side_margin = 28  # type: int
        self._top_margin = 38  # type: int
        # Read the Config values from JSON file if a path was provided
        if self._cfg_filep is not None:
            self.load()
        return

    @property
    def cfg_file_path(self):  # type: () -> str|None
        return self._cfg_filep
    @cfg_file_path.setter
    def cfg_file_path(self, path):  # type: (str|None) -> None
        self._cfg_filep = path
        return

    @property
    def font(self):  # type: () -> str
        return self._font

    @property
    def font_bold(self):  # type: () -> bool
        return self._font_bold

    @property
    def font_italic(self):  # type: () -> bool
        return self._font_italic

    @property
    def font_size(self):  # type: () -> int
        return self._font_size

    @property
    def masthead_file(self):  # type: () -> str
        return self._masthead_filep

    @property
    def masthead_font(self):  # type: () -> str
        return self._masthead_font

    @property
    def masthead_font_size(self):  # type: () -> int
        return self._masthead_font_size

    @property
    def masthead_text(self):  # type: () -> str
        return self._masthead_text

    @property
    def masthead_text_color(self):  # type: () -> str|tuple[int,int,int]
        return self._masthead_text_color

    @property
    def page_clear_idle_time(self):  # type: () -> float
        return self._page_clear_idle_time

    @property
    def page_clear_speed(self):  # type: () -> float
        return self._page_clear_speed

    @property
    def page_color(self):  # type: () -> str|tuple[int,int,int]
        return self._page_color

    @property
    def side_margin(self):  # type: () -> int
        return self._side_margin

    @property
    def text_color(self):  # type: () -> str|tuple[int,int,int]
        return self._text_color

    @property
    def top_margin(self):  # type: () -> int
        return self._top_margin



    def load(self, filep=None):  # type: (str|None) -> None
        """
        Load this config from a Configuration file (json).

        filepath: File path to use. If 'None', use the path last loaded from or saved to.
                If 'None' is supplied, and a path hasn't been established, raise a
                FileNotFoundError exception.

        Raises: FileNotFoundError if a path hasn't been established.
                System may throw other file related exceptions.
        """
        filepath = filep if filep is not None else self._cfg_filep
        if not filepath:
            e = FileNotFoundError("File path not yet established")
            raise e

        self._cfg_filep = filepath
        errors = 0
        try:
            dirpath, filename = os.path.split(filepath)
            data = None  # type: dict[str:Any]|None
            with open(filepath, 'r', encoding="utf-8") as fp:
                data = json.load(fp)
            if data:
                for key, value in data.items():
                    try:
                        match key:
                            case self.FONT_KEY:
                                self._font = value
                            case self.FONT_BOLD_KEY:
                                self._font_bold = value
                            case self.FONT_ITALIC_KEY:
                                self._font_italic = value
                            case self.FONT_SIZE_KEY:
                                self._font_size = int(value)
                            case self.PAGE_CLEAR_IDLE_TIME_KEY:
                                self._page_clear_idle_time = value
                            case self.PAGE_CLEAR_SPEED_KEY:
                                self._page_clear_speed = value
                            case self.PAGE_COLOR_KEY:
                                self._page_color = literal_eval(value) if value and value[0] == '(' else value
                            case self.TEXT_COLOR_KEY:
                                self._text_color = literal_eval(value) if value and value[0] == '(' else value
                            case self.MASTHEAD_FILE_PATH:
                                self._masthead_filep = value
                            case self.MASTHEAD_FONT_KEY:
                                self._masthead_font = value
                            case self.MASTHEAD_FONT_SIZE_KEY:
                                self._masthead_font_size = int(value)
                            case self.MASTHEAD_TEXT_KEY:
                                self._masthead_text = value
                            case self.MASTHEAD_TEXT_COLOR_KEY:
                                self._masthead_text_color = literal_eval(value) if value and value[0] == '(' else value
                            case self.SIDE_MARGIN_KEY:
                                self._side_margin = int(value)
                            case self.TOP_MARGIN_KEY:
                                self._top_margin = int(value)
                            case _:
                                raise KeyError()
                    except KeyError as ke:
                        log.warn("Loading configuration file: {}  Unknown property: {}  With value: {}".format(filename, key, value))
                        errors += 1
                    pass
                #
            else:
                log.warn("No data loaded from {}".format(filepath))
                errors += 1
            if errors > 0:
                log.warn("Loading configuration file: {}  Encountered {} error(s).".format(filename, errors))
        except JSONDecodeError as jde:
            log.debug(jde)
            raise ConfigLoadError(jde)
        except Exception as ex:
            log.debug(ex)
            raise ConfigLoadError(ex)
        return



class Telegram:
    """
    Telegram operations.
    """
    def __init__(self, app_name_version, wire, cfg, tgcfg):  # type: (str, int, Config, TelegramConfig) -> None
        self._app_name_version = app_name_version  # type: str
        self._wire = wire  # type: int
        self._cfg = cfg  # type: Config
        self._tgcfg = tgcfg
        self._masthead = None  # type: Surface|None
        self._internet = None  # type: Internet|None
        self._kob = None  # type: KOB|None
        self._reader = None  # type: Reader|None
        self._sender = None  # type: Sender|None
        self._form = None  # type: PGDisplay|None
        self._clock = None
        self._running = False  # type: bool
        self._dt = 0  # type: int
        self._last_display_t = sys.float_info.min  # type: float  # force welcome screen
        self._last_decode_t = sys.float_info.max  # type: float  # no decodes so far
        self._flush_t = FLUSH * (1.2 / cfg.min_char_speed)  # type: float  # convert dots to seconds

        #
        self._closed = Event()  # type: Event
        self._control_c_pressed = Event()  # type: Event
        self._shutdown = Event()  # type: Event
        self._shutdown_started = Event()  # type: Event
        #
        # (same as MRT)
        self._connected = False  # type bool
        self._internet_station_active = False  # type: bool #True if a remote station is sending
        self._last_received_para = False # type: bool #The last character received was a Paragraph ('=')
        self._last_advanced_under = False # type: bool #The last character printed was '_' and line advance
        self._local_loop_active = False  # type: bool #True if sending on key or keyboard
        self._our_office_id = cfg.station if not cfg.station is None else ""  # type: str
        self._sender_current = ""  # type: str
        return

    def _display_text(self, char, update=True, spacing=1.0):  # type: (str, bool, float) -> None
        """
        Callback function for displaying text on the form.
        """
        self._form.output(char, self._tgcfg.font_bold, self._tgcfg.font_italic, update, spacing)
        self._last_display_t = time.time()
        return

    def _emit_local_code(self, code, code_source, char=None):  # type: (tuple[int,...], kob.CodeSource, str|None) -> None
        """
        Emit local code. That involves:
        1. Send code to the wire if connected
        2. Decode the code and display it if from the key or keyboard

        This is used from the key thread or the Telegram main loop to emit code once they
        determine it should be emitted.
        """
        kob_ = self._kob
        if kob_:
            kob_.internet_circuit_closed = not self._internet_station_active
        self._handle_sender_update(self._our_office_id)
        if not code_source == kob.CodeSource.key:  # Code from the key is automatically sounded
            kob_.soundCode(code, code_source)
        if self._reader:
            self._last_decode_t = sys.float_info.max
            self._reader.decode(code)
            self._last_decode_t = time.time()
        if self._connected and self._cfg.remote:
            self._internet.write(code)
        return

    # flush last characters from decode buffer
    def _flush_reader(self):
        self._last_decode_t = sys.float_info.max
        self._reader.flush()
        return

    def _form_new(self, fresh=False):  # type: (bool) -> None
        """
        Clear the form and display the masthead.
        If `fresh` create a new, fresh form.
        If not, scroll the current form off.
        """
        log.debug("Telegram._form_new", 2)
        scroll = 0.0 if fresh else self._tgcfg.page_clear_speed
        self._form.new_form(scroll_time=scroll)
        self._output_masthead()
        self._form.form_update()
        self._last_display_t = sys.float_info.max
        return

    # handle input from telegraph key
    def _from_key(self, code):
        """
        Handle inputs received from the external key.
        Only send if the circuit is open.

        Called from the 'KOB-KeyRead' thread.
        """
        if len(code) > 0:
            if code[-1] == 1: # special code for closer/circuit closed
                self._set_virtual_closer_closed(True)
                return
            elif code[-1] == 2: # special code for closer/circuit open
                self._set_virtual_closer_closed(False)
                return
        # if not self._internet_station_active and self._local_loop_active:
        if self._local_loop_active:
            self._emit_local_code(code, kob.CodeSource.key)
        return

    # handle input from internet
    def _from_internet(self, code):
        # self._kob.sounder(code)
        # else:
        #     display(code)
        if self._connected:
            if not self._sender_current == self._our_office_id:
                self._kob.soundCode(code, kob.CodeSource.wire)
                if code == STARTMSG:
                    self._form_new()
                elif code == ENDMSG:
                    # Don't do anything at end. Timeout or new message (STARTMSG)
                    # will display a new form.
                    pass
                else:
                    if self._reader:
                        self._reader.decode(code)
            if len(code) > 0 and code[-1] == +1:
                self._internet_station_active = False
            else:
                self._internet_station_active = True
            self._kob.internet_circuit_closed = not self._internet_station_active
        return

    # handle input from keyboard
    def _from_keyboard(self, char):
        """
        Handle inputs received from the keyboard sender.
        Only send if the circuit is open.

        Called from the Telegram main loop.
        """
        if char:
            code = self._sender.encode(char)
            if len(code) > 0:
                if code[-1] == 1: # special code for closer/circuit closed
                    self._set_virtual_closer_closed(True)
                    return
                elif code[-1] == 2: # special code for closer/circuit open
                    self._set_virtual_closer_closed(False)
                    print('[+ to close key]', flush=True)
                    sys.stdout.flush()
                    return
            # if not self._internet_station_active and self._local_loop_active:
            if self._local_loop_active:
                self._emit_local_code(code, kob.CodeSource.keyboard, char)
        return

    def _from_reader(self, char, spacing):
        if not char == '=':
            if self._last_received_para:
                self._form.line_advance()
            self._last_received_para = False
        else:
            self._last_received_para = True
        halfSpaces = min(max(int(2 * spacing + 0.5), 0), 10)
        fullSpace = False
        if halfSpaces > 0:
            halfSpaces -=1
        if halfSpaces >= 2:
            fullSpace = True
            halfSpaces = (halfSpaces - 1) // 2
        # print("Char:{} Spacing:{} HalfSp:{} FullSp:{}".format(char, spacing, halfSpaces, fullSpace))
        for i in range(halfSpaces):
            self._display_text(' ', update=False, spacing=0.15)
        if fullSpace:
            self._display_text(' ', update=False, spacing=0.65)
        self._display_text(char)
        if char == '_':
            if not self._last_advanced_under:
                self._form.line_advance()
                self._last_advanced_under = True
            pass
        else:
            self._last_advanced_under = False
        return

    def _handle_sender_update(self, sender):
        """
        Handle a <<Current_Sender>> message by:
        1. Displaying the sender if new
        """
        if not self._sender_current == sender:
            self._sender_current = sender
            print()
            print(f"<<{self._sender_current}>>", flush=True)
        return

    def _output_masthead(self):
        """
        Render the top section of the form.
        """
        if self._masthead is not None:
            lf = (self._form.width // 2) - (self._masthead.width // 2)
            if lf < 0:
                lf = 0
            top = self._tgcfg.top_margin
            log.debug("Masthead BLIT", 3)
            self._form.blit(self._masthead, (lf,top), update=False, set_text_top=True)
        else:
            log.debug("Masthead text output", 3)
            self._form.output(self._tgcfg._masthead_text, bold=True, italic=False, update=False)
        self._form.line_advance(2)
        return

    def _print_start_info(self):
        cfgname = "Global" if not self._cfg.get_filepath() else self._cfg.get_filepath()
        print("Using configuration: {}".format(cfgname))
        if self._wire == 0:
            print("Not connecting to a wire.")
            print("Our Station/Office: " + self._our_office_id)
        else:
            print("Connecting to wire: " + str(self._wire))
            print("Connecting as Station/Office: " + self._our_office_id)
        if self._cfg.decode_at_detected:
            print("Using the detected incoming character speed for decoding.")
        # Let the user know if 'invert key input' is enabled (typically only used for MODEM input)
        if self._cfg.invert_key_input:
            print("IMPORTANT! Key input signal invert is enabled (typically only used with a MODEM). " + \
                "To enable/disable this setting use `Configure --iki`.")
        return

    def _set_local_loop_active(self, active):
        """
        Set local_loop_active state

        True: Key or Keyboard active (Circuit Closer OPEN)
        False: Circuit Closer (physical and virtual) CLOSED
        """
        self._local_loop_active = active
        self._kob.energize_sounder((not active), kob.CodeSource.local)
        return

    def _set_virtual_closer_closed(self, closed):
        """
        Handle change of Circuit Closer state.

        A state of:
        True: 'latch'
        False: 'unlatch'
        """
        self._kob.virtual_closer_is_open = not closed
        code = LATCH_CODE if closed else UNLATCH_CODE
        # if not self._internet_station_active:
        if True:  # Allow breaking in to an active wire message
            if self._cfg.local:
                if not closed:
                    self._handle_sender_update(self._our_office_id)
                if self._reader:
                    self._reader.decode(code)
        if self._connected and self._cfg.remote:
            self._internet.write(code)
        if len(code) > 0:
            if code[-1] == 1:
                # Unlatch (Key closed)
                self._set_local_loop_active(False)
                if self._reader:
                    self._reader.flush()
            elif code[-1] == 2:
                # Latch (Key open)
                self._set_local_loop_active(True)
        return



    # ########################################################################
    #
    # Public Methods
    #
    # ########################################################################


    def exit(self):
        if not self._closed.is_set():
            self._closed.set()
            print("\nClosing...")
            self._shutdown.set()
            time.sleep(0.8)
            log.debug("Telegram.exit - 1", 3)
            self.shutdown()
            log.debug("Telegram.exit - 2", 3)
            kob_ = self._kob
            if kob_:
                log.debug("Telegram.exit - 3a", 3)
                kob_.exit()
                log.debug("Telegram.exit - 3b", 3)
            inet = self._internet
            if inet:
                log.debug("Telegram.exit - 4a", 3)
                inet.exit()
                log.debug("Telegram.exit - 4b", 3)
            rdr = self._reader
            if rdr:
                log.debug("Telegram.exit - 5a", 3)
                rdr.exit()
                log.debug("Telegram.exit - 5b", 3)
            sndr = self._sender
            if sndr:
                log.debug("Telegram.exit - 6a", 3)
                sndr.exit()
                log.debug("Telegram.exit - 6b", 3)
            disp = self._form
            if disp:
                log.debug("Telegram.exit - 7a", 3)
                disp.exit()
                log.debug("Telegram.exit - 7b", 3)
        return

    def main_loop(self):
        self._print_start_info()
        if not self._wire == 0:
            self._internet.connect(self._wire)
            self._connected = True
            kob_ = self._kob
            if kob_:
                kob_.internet_circuit_closed = not self._internet_station_active
                kob_.wire_connected = self._connected
        self._shutdown.wait(0.5)
        try:
            while not self._shutdown.is_set():
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:  # stop if window closed
                        self._shutdown.set()
                        break
                    elif event.type == pygame.KEYDOWN:
                        c = event.unicode
                        if c == '\x11':  # quit on ^Q
                            self._shutdown.set()
                            break
                        elif c == '\x03':  # quit on ^C
                            self._shutdown.set()
                            self._control_c_pressed.set()
                            break
                        elif c == '\x18':  # display a new form on ^X
                            self._form_new()
                        else:  # otherwise handle keyboard input
                            if c == '\x1B':  # Escape toggles the virtual closer
                                open_vcloser = not self._kob.virtual_closer_is_open
                                if open_vcloser:
                                    c = '~'
                                else:
                                    c = '+'
                            self._from_keyboard(c)
                if time.time() - self._flush_t > self._last_decode_t:
                    self._flush_reader()
                if time.time() > self._last_display_t + self._tgcfg.page_clear_idle_time:
                    self._form_new()
                self._shutdown.wait(0.010)  # wait a bit before getting the next event
                if self._control_c_pressed.is_set():
                    raise KeyboardInterrupt
                self._shutdown.wait(0.02)
            pass
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        finally:
            self.exit()
        return

    def shutdown(self):
        if self._shutdown_started.is_set():
            return  # Shutdown is already underway (or done)
        self._shutdown_started.set()
        log.debug("Telegram.shutdown - 1", 3)
        self._shutdown.set()
        log.debug("Telegram.shutdown - 2", 3)
        kob_ = self._kob
        if kob_:
            log.debug("Telegram.shutdown - 3a", 3)
            kob_.shutdown()
            log.debug("Telegram.shutdown - 3b", 3)
        inet = self._internet
        if inet:
            log.debug("Telegram.shutdown - 4a", 3)
            inet.shutdown()
            log.debug("Telegram.shutdown - 4b", 3)
        rdr = self._reader
        if rdr:
            log.debug("Telegram.shutdown - 5a", 3)
            rdr.shutdown()
            log.debug("Telegram.shutdown - 5b", 3)
        sndr = self._sender
        if sndr:
            log.debug("Telegram.shutdown - 6a", 3)
            sndr.shutdown()
            log.debug("Telegram.shutdown - 6b", 3)
        disp = self._form
        if disp:
            log.debug("Telegram.shutdown - 7a", 3)
            disp.shutdown()
            log.debug("Telegram.shutdown - 7b", 3)
        return

    def start(self):
        """
        Start everything up.
        """
        self._kob = KOB(
            interfaceType=self._cfg.interface_type,
            useSerial=self._cfg.use_serial,
            portToUse=self._cfg.serial_port,
            useGpio=self._cfg.use_gpio,
            useAudio=self._cfg.sound,
            audioType=self._cfg.audio_type,
            useSounder=self._cfg.sounder,
            invertKeyInput=self._cfg.invert_key_input,
            soundLocal=self._cfg.local,
            sounderPowerSaveSecs=self._cfg.sounder_power_save,
            virtual_closer_in_use=True,
            keyCallback=self._from_key,
            )
        if (self._wire is not None):
            self._internet = internet.Internet(
                officeID=self._cfg.station,
                code_callback=self._from_internet,
                appver=self._app_name_version,
                server_url=self._cfg.server_url,
                err_msg_hndlr=log.warn
            )
            self._internet.monitor_sender(self._handle_sender_update) # Set callback for monitoring current sender
        self._sender = morse.Sender(
            wpm=self._cfg.text_speed,
            cwpm=self._cfg.min_char_speed,
            codeType=self._cfg.code_type,
            spacing=self._cfg.spacing
            )
        self._reader = morse.Reader(
            wpm=self._cfg.text_speed,
            cwpm=self._cfg.min_char_speed,
            codeType=self._cfg.code_type,
            callback=self._from_reader,
            decode_at_detected=self._cfg.decode_at_detected
            )
        font = self._tgcfg.font
        fsize = self._tgcfg.font_size
        page_c = self._tgcfg.page_color
        text_c = self._tgcfg.text_color
        side_margin = self._tgcfg.side_margin
        self._form = PGDisplay(0, 0, page_c, text_c, font, fsize, side_margin)
        self._form.caption = "Telegram"
        self._clock = pygame.time.Clock()
        if self._tgcfg.masthead_file is not None:
            mfile = self._tgcfg.masthead_file
            try:
                self._masthead = pygame.image.load(mfile).convert_alpha()
            except FileNotFoundError as fnf:
                if self._tgcfg.masthead_text is not None:
                    log.warn("Masthead file not found: '{}' Will use the Masthead text instead.".format(mfile), dt="")
                    try:
                        font = None  # type: Font|None
                        fpath = pygame.font.match_font(self._tgcfg.masthead_font)
                        if fpath is not None:
                            font = pygame.font.Font(fpath, self._tgcfg.masthead_font_size)
                        else:
                            font = pygame.font.SysFont(self._tgcfg.masthead_font, self._tgcfg.masthead_font_size)
                        self._masthead = font.render(self._tgcfg.masthead_text, True, self._tgcfg.masthead_text_color)
                    except Exception as ex:
                        log.warn("Error rendering the Masthead text '{}': {}".format(self._tgcfg.masthead_text, ex), dt="")
                    pass
                else:
                    log.error("Masthead file not found: '{}'".format(mfile), dt="")
                    raise fnf
                pass
            pass
        self._form_new(fresh=True)
        self._running = True
        self._dt = 0
        return


"""
Main code
"""
if __name__ == "__main__":
    telegram = None
    exit_status = 0

    try:
        # Process command option arguments
        arg_parser = argparse.ArgumentParser(description="Telegram "
            + "- Display a telegram form with local and received messages. "
            + "Telegram specific configuration is in the 'tg_config.tgc' file.",
            parents= [
                config2.sound_override,
                config2.sounder_override,
                config2.use_gpio_override,
                config2.use_serial_override,
                config2.serial_port_override,
                config2.station_override,
                config2.min_char_speed_override,
                config2.text_speed_override,
                config2.config_file_override,
                config2.logging_level_override,
            ],
            exit_on_error=False
        )
        arg_parser.add_argument("wire", nargs='?', type=int,
            help="Wire to connect to. If specified, this is used rather than the configured wire. " +
                "Use 0 to not connect to a wire (local only).")

        args = arg_parser.parse_args()

        print(TELEGRAM_VERSION_TEXT)
        print(" Python: " + sys_version + " on " + sys_platform)
        #print(" Pygame: " + pygame.system.)
        print(" pykob: " + PKVERSION)
        # pygame setup
        pygame.init()  # This is required, plus it prints the PyGame-CE version


        cfg = config2.process_config_args(args)
        log.set_logging_level(cfg.logging_level)
        # Use the wire from the command line if one was specified, else use the one configured.
        wire = args.wire if args.wire else cfg.wire

        # Create the Telegram instance
        #  See if the Telegram Config exists
        if (path_func.isfile(TELEGRAM_CFG_FILE_NAME)):
            tg_config = TelegramConfig(TELEGRAM_CFG_FILE_NAME)
        else:
            log.warn("Telegram configuration file '{}' not found. Using default values.".format(TELEGRAM_CFG_FILE_NAME), dt="")
            tg_config = TelegramConfig(None)
        telegram = Telegram(TELEGRAM_VERSION_TEXT, wire, cfg, tg_config)
        telegram.start()
        telegram.main_loop()  # This doesn't return until Telegram exits
        exit_status = 0
    except KeyboardInterrupt:
        # ^C or ^Q are allowed to exit
        pass
    except Exception as ex:
        log.error("Error: {}".format(ex), dt="")
    finally:
        if telegram is not None:
            telegram.shutdown()
            telegram.exit()
            telegram = None
    sys.exit(exit_status)
