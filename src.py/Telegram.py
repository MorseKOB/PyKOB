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
from pygame import Rect, Surface, typing
from pygame.typing import ColorLike, RectLike
import os
from os import path as path_func
import sys
from sys import platform as sys_platform
from sys import version as sys_version
from threading import Event
import time
import traceback

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

class TGDisplay:
    """
    Holds a PyGame display surface and provides useful methods that operate on
    the display/Surface and display a telegram form
    """

    ''' Black color constant '''
    BLACK = (0,0,0)

    def __init__(self,
                screensize,
                tgcfg
        ):  # type: (tuple[int,int]|None, TelegramConfig) -> None
        """
        screensize: The size of the screen in pixels, width and height. Or None to automatically select the size based on the hardware.
        """
        pygame.display.init()
        pygame.font.init()
        self._scr_size = screensize if screensize is not None else pygame.display.list_modes()[0]
        self._screen = pygame.display.set_mode(self._scr_size, pygame.FULLSCREEN)  # 'flags' can have pygame.FULLSCREEN
        self._clock = pygame.time.Clock()
        self._tgcfg = tgcfg
        #
        # START OF CONFIG PROPERTIES
        ## Page features
        self._page_width = min(tgcfg.page_width, self._screen.width)
        self._page_color = tgcfg.page_color
        self._scroll_speed = tgcfg.page_clear_speed  # type: float
        ## Margins
        self._side_margin = tgcfg.side_margin
        self._top_margin = tgcfg.top_margin
        ## Text features
        self._wrap_columns = tgcfg.wrap_columns
        self._text_color = tgcfg.text_color
        fpath = pygame.font.match_font(tgcfg.text_font)
        if fpath is not None:
            self._font = pygame.font.Font(fpath, tgcfg.text_font_size)
        else:
            self._font = pygame.font.SysFont(None, tgcfg.text_font_size)
        # END OF CONFIG PROPERTIES
        self._space_width = self._font.size(' ')[0]
        self._text_line_height = self._font.get_linesize()
        self._spaces = 0
        #
        # Calculate the page left from the screen width and the page width
        self._page_left = (self._screen.width - self._page_width) // 2
        self._page_rect = (self._page_left, 0, self._page_width, self._screen.height)
        self._text_leftmost = self._page_left + self._side_margin
        self._text_right_max = self._page_left + (self._page_width - self._side_margin)
        self._text_wrap_x = max((self._text_leftmost + (4 * self._space_width)), (self._text_right_max - (self._wrap_columns * self._space_width)))
        self._text_x = self._text_leftmost
        self._text_y = 0
        #
        # Masthead holder. It will be generated in `start`
        self._masthead = None  # type: Surface|None
        #
        # Rendered characters used for the Key Closer state on the display form.
        self._KC_closed_sprite = None  # type: Surface|None
        self._KC_open_sprite = None  # type: Surface|None
        self._KC_state_bg = None  # type: Surface|None
        self._KC_state_pt = (0,0)  # type: tuple[int,int]
        # Flags/Events
        self._shutdown = Event()
        return

    def _output_masthead(self):
        """
        Render the top section of the form.
        """
        lf = (self._screen.width // 2) - (self._masthead.width // 2)
        if lf < 0:
            lf = 0
        top = self._tgcfg.top_margin
        log.debug("TGDisplay._output_masthead", 3)
        self._screen.blit(self._masthead, (lf,top))
        self._text_y += self._masthead.get_height() + self._text_line_height
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
    def page_color(self):  # type: () -> ColorLike
        return self._page_color

    @property
    def page_width(self):  # type: () -> int
        return self._page_width

    @property
    def width(self):  # type: () -> int
        return self._screen.width


    def advance(self, pixel_rows):  # type: (int) -> None
        """
        Advance the Y position by `pixel_rows`. Positive values move Y down the screen
        and may scroll the page up. Negative values move Y up the screen and may scroll
        the page down.
        """
        self._text_y += (pixel_rows)
        sh = self._screen.height
        if (self._text_y >= sh):
            self._screen.scroll(0, self._text_y - sh)
            self._text_y = sh - 1
        elif (self._text_y < 0):
            self._screen.scroll(0, (0 - self._text_y))
            self._text_y = 0
        return

    def blit(self, sprite, topleft, update=False):  # type: (Surface, tuple[int,int], bool, bool) -> None
        """
        Blit (draw/render) a Surface sprite onto the form.
        """
        self._screen.blit(sprite, topleft)
        if update:
            pygame.display.flip()
        return

    def erase_closer_state(self, update=False):  # type: (bool) -> None
        self._screen.blit(self._KC_state_bg, self._KC_statebg_pt)
        if update:
            pygame.display.flip()
        return

    def exit(self):  # type: () -> None
        self._screen = None
        pygame.display.quit()
        return

    def fill(self, color, rect):  # type: (ColorLike, RectLike) -> None
        self._screen.fill(color, rect)
        return

    def form_update(self):  # type: () -> None
        pygame.display.flip()
        return

    def line_advance(self, lines=1):  # type: (int) -> None
        self._text_x = self._text_leftmost
        self.advance(self._text_line_height * lines)
        return

    def new_form(self, fresh=False, update=True):  # type: (bool, bool, float) -> None
        """
        Clear the form and display the masthead.
        If `fresh`, instantly create a new form.
        If not, scroll the current form off and replace it.
        """
        log.debug("TGDisplay.new_form", 2)
        scroll_time = 0.0 if fresh else self._scroll_speed
        self.erase_closer_state()
        if scroll_time == 0:
            self._screen.fill(TGDisplay.BLACK)  # Background
            self._screen.fill(self._page_color, self._page_rect)
            self._text_x = self._text_leftmost
            self._text_y = 0
            self._output_masthead()
        else:
            # ZZZ try putting something below the bottom
            rect = Rect(0, self._screen.height - 20, 100, 60)
            self._screen.blit(self._masthead, rect)
            pygame.display.flip()
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
                fr = pygame.Rect(self._page_left,rec_top,self._page_width, dy)
                self._screen.fill(self._page_color, fr)
                pygame.display.flip()
                scroll_to_go -= dy
                if scroll_to_go < dy:
                    dy = scroll_to_go
                self._shutdown.wait(pt)
            pass
        pass
        self._text_x = self._text_leftmost
        self._text_y = 0
        self._output_masthead()
        if update:
            pygame.display.flip()
        return

    def print(self, text, bold=False, italic=False, update=True, spacing=0.0):  # type: (str, bool, bool, bool, float) -> None
        if text is None:
            return
        screen_output = False
        for c in text:
            if c == '\r' or c == '\n':
                self.line_advance()
                continue
            if c == ' ':
                self._spaces += 1
                continue
            if c < ' ':
                continue
            font = self._font
            font.bold = bold
            font.italic = italic
            space = int(self._space_width * (self._spaces + spacing))
            char_glyph = font.render(c, True, self._text_color)
            glyph_width = char_glyph.get_width()
            text_end_x = self._text_x + space + glyph_width
            if ((self._spaces > 0) and (text_end_x > self._text_wrap_x)) or (text_end_x > self._text_right_max):
                space = 0
                self.line_advance()
            self._screen.blit(char_glyph, (self._text_x + space, self._text_y))
            self._text_x += space + glyph_width
            self._spaces = 0
            screen_output = True
        if update and screen_output:
            pygame.display.flip()
        return

    def show_closer_state(self, open):  # type: (bool) -> None
        """
        Render a 'O' or 'C' in the bottom left corner of the screen
        based on the open/closed state. Erase what might have been
        there.
        """
        self.erase_closer_state(update=False)
        if open:
            self._screen.blit(self._KC_open_sprite, self._KC_state_pt)
        else:
            self._screen.blit(self._KC_closed_sprite, self._KC_state_pt)
        return

    def shutdown(self):  # type: () -> None
        self._shutdown.set()
        return

    def start(self):  # type: () -> None
        #
        # Get Masthead ready
        if self._tgcfg.masthead_file is not None:
            mfile = self._tgcfg.masthead_file
            try:
                self._masthead = pygame.image.load(mfile).convert_alpha()
            except FileNotFoundError as fnf:
                log.warn("Masthead file not found: '{}' Will use the Masthead text instead.".format(mfile), dt="")
                text = self._tgcfg.masthead_text
                if text is None:
                    text = ""
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
            pass
        pass
        #
        # Create sprite surfaces with the Key-Closed state chars and the rectangle that contains them.
        status_font = None  # type: Font|None
        fpath = pygame.font.match_font("Arial, Helvetica, Sans-Serif")
        if fpath is not None:
            status_font = pygame.font.Font(fpath, 40)
        else:
            status_font = pygame.font.SysFont(None, 40)
        self._KC_closed_sprite = status_font.render("+", True, (255,255,255))  # Render a white '+' for closed
        self._KC_open_sprite = status_font.render("~", True, (255,255,255))  # Render a white '~' for open
        kc_w = 8 + max(self._KC_closed_sprite.width, self._KC_open_sprite.width)
        kc_h = 4 + status_font.get_linesize()
        kc_l = self._screen.width - kc_w
        kc_t = self._screen.height - kc_h
        # Create a background sprite. Chances are this will be black or the page color,
        # but it's possible that the border width is non-zero but narrower than the
        # status block width. So, we do the work here to create a sprite that might
        # have some of the left in the page color and the right in black.
        #
        # The black 'stripe' on the right is ((screen_width - page_width) / 2)
        sz = (kc_w, kc_h)
        self._KC_state_bg = Surface(sz)  # Per PyGame-CE docs, this creates a black surface
        pcw = kc_w - ((self._screen.width - self._page_width) // 2)
        if pcw > 0:
            state_pagec_rect = Rect(0, 0, pcw, kc_h)
            self._KC_state_bg.fill(self._page_color, state_pagec_rect)
        self._KC_statebg_pt = (kc_l, kc_t)
        self._KC_state_pt = (kc_l + 2, kc_t + 2)
        self._screen.fill(TGDisplay.BLACK)
        pygame.display.flip()
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
    PAGE_WIDTH_KEY = "page_width"
    TEXT_COLOR_KEY = "text_color"
    MASTHEAD_FILE_PATH = "masthead_file"
    MASTHEAD_FONT_KEY = "masthead_font"
    MASTHEAD_FONT_SIZE_KEY = "masthead_font_size"
    MASTHEAD_TEXT_KEY = "masthead_text"
    MASTHEAD_TEXT_COLOR_KEY = "masthead_text_color"
    SIDE_MARGIN_KEY = "side_margin"
    TOP_MARGIN_KEY = "top_margin"
    FORM_SPACING_KEY = "form_spacing"
    WRAP_COLUMNS_KEY = "wrap_columns"


    def __init__(self, tgcfg_file_path):  # type: (str|None) -> None
        self._cfg_filep = tgcfg_file_path
        # Default values...
        self._text_font = "courier"  # type: str
        self._text_font_bold = False  # type: bool
        self._text_font_italic = False  # type: bool
        self._text_font_size = 20  # type: int
        self._text_color = "black"  # type: str|tuple[int,int,int]
        self._page_clear_idle_time = 8.0  # type: float  # Seconds of idle before clear
        self._page_clear_speed = 1.8  # type: float  # Time to take to scroll the page (can be negative)
        self._page_color = (198,189,150)  # type: str|tuple[int,int,int] # Tan
        self._page_width = 980  # type: int  # The page color portion width. 980 is reasonable.
        self._masthead_filep = None  # type: str|None
        self._masthead_font = self._text_font
        self._masthead_font_size = self._text_font_size
        self._masthead_text = None  # type: str|None
        self._masthead_text_color = "black"  # type: str|tuple[int,int,int]
        self._side_margin = 28  # type: int
        self._top_margin = 38  # type: int
        self._form_spacing = 10  # type: int
        self._wrap_columns = 15  # type:int  # Number of spaces before right margin to wrap to next line
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
    def text_font(self):  # type: () -> str
        return self._text_font
    @text_font.setter
    def text_font(self, font):  # type: (str) -> None
        self._text_font = font
        return

    @property
    def text_font_bold(self):  # type: () -> bool
        return self._text_font_bold
    @text_font_bold.setter
    def text_font_bold(self, b):  # type: (bool) -> None
        self._bold = b
        return

    @property
    def text_font_italic(self):  # type: () -> bool
        return self._text_font_italic
    @text_font_italic.setter
    def text_font_italic(self, i):  # type: (bool) -> None
        self._italic = i
        return

    @property
    def text_font_size(self):  # type: () -> int
        return self._text_font_size
    @text_font_size.setter
    def text_font_size(self, size):  # type: (int) -> None
        self._text_font_size = size
        return

    @property
    def form_spacing(self):  # type: () -> int
        return self._form_spacing
    @form_spacing.setter
    def form_spacing(self, spacing):  # type: (int) -> None
        self._form_spacing = spacing
        return

    @property
    def masthead_file(self):  # type: () -> str
        return self._masthead_filep
    @masthead_file.setter
    def masthead_file(self, filepath):  # type: (str) -> None
        self._masthead_filep = filepath
        return

    @property
    def masthead_font(self):  # type: () -> str
        return self._masthead_font
    @masthead_font.setter
    def masthead_font(self, font):  # type: (str) -> None
        self._masthead_font = font
        return

    @property
    def masthead_font_size(self):  # type: () -> int
        return self._masthead_font_size
    @masthead_font_size.setter
    def masthead_font_size(self, size):  # type: (int) -> None
        self._masthead_font_size = size
        return

    @property
    def masthead_text(self):  # type: () -> str
        return self._masthead_text
    @masthead_text.setter
    def masthead_text(self, text):  # type: (str) -> None
        self._masthead_text = text
        return

    @property
    def masthead_text_color(self):  # type: () -> str|tuple[int,int,int]
        return self._masthead_text_color
    @masthead_text_color.setter
    def masthead_text_color(self, color):  # type: (str|tuple[int,int,int]) -> None
        self._masthead_text_color = color
        return

    @property
    def page_clear_idle_time(self):  # type: () -> float
        return self._page_clear_idle_time
    @page_clear_idle_time.setter
    def page_clear_idle_time(self, seconds):  # type: (float) -> None
        self._page_clear_idle_time = seconds
        return

    @property
    def page_clear_speed(self):  # type: () -> float
        return self._page_clear_speed
    @page_clear_speed.setter
    def page_clear_speed(self, seconds):  # type: (float) -> None
        self._page_clear_speed = seconds
        return

    @property
    def page_color(self):  # type: () -> str|tuple[int,int,int]
        return self._page_color
    @page_color.setter
    def page_color(self, color):  # type: (str|tuple[int,int,int]) -> None
        self._page_color = color
        return

    @property
    def page_width(self):  # type: () -> int
        return self._page_width
    @page_width.setter
    def page_width(self, width):  # type: (int) -> None
        self._page_width = width
        return

    @property
    def side_margin(self):  # type: () -> int
        return self._side_margin
    @side_margin.setter
    def side_margin(self, margin):  # type: (int) -> None
        self._side_margin = margin
        return

    @property
    def text_color(self):  # type: () -> str|tuple[int,int,int]
        return self._text_color
    @text_color.setter
    def text_color(self, color):  #type: (str|tuple[int,int,int]) -> None
        self._text_color = color
        return

    @property
    def top_margin(self):  # type: () -> int
        return self._top_margin
    @top_margin.setter
    def top_margin(self, margin):  # type(int) -> None
        self._top_margin = margin
        return

    @property
    def wrap_columns(self):  # type: () -> int
        return self._wrap_columns
    @wrap_columns.setter
    def wrap_columns(self, columns):  # type: (int) -> None
        self._wrap_columns = columns
        return

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
            data = None  # type: dict[Any]|None
            with open(filepath, 'r', encoding="utf-8") as fp:
                data = json.load(fp)
            if data:
                for key, value in data.items():
                    try:
                        match key:
                            case self.FONT_KEY:
                                self._text_font = value
                            case self.FONT_BOLD_KEY:
                                self._text_font_bold = value
                            case self.FONT_ITALIC_KEY:
                                self._text_font_italic = value
                            case self.FONT_SIZE_KEY:
                                self._text_font_size = int(value)
                            case self.PAGE_CLEAR_IDLE_TIME_KEY:
                                self._page_clear_idle_time = value
                            case self.PAGE_CLEAR_SPEED_KEY:
                                self._page_clear_speed = value
                            case self.PAGE_COLOR_KEY:
                                self._page_color = literal_eval(value) if value and value[0] == '(' else value
                            case self.PAGE_WIDTH_KEY:
                                self._page_width = value
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
                            case self.FORM_SPACING_KEY:
                                self._form_spacing = int(value)
                            case self.WRAP_COLUMNS_KEY:
                                self._wrap_columns = int(value)
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
        self._internet = None  # type: Internet|None
        self._kob = None  # type: KOB|None
        self._reader = None  # type: Reader|None
        self._sender = None  # type: Sender|None
        self._form = None  # type: TGDisplay|None
        self._clock = None
        self._running = False  # type: bool
        self._dt = 0  # type: int
        self._last_display_t = sys.float_info.min  # type: float  # force welcome screen
        self._last_decode_t = sys.float_info.max  # type: float  # no decodes so far
        self._flush_t = FLUSH * (1.2 / cfg.min_char_speed)  # type: float  # convert dots to seconds
        #
        self._closed = Event()  # type: Event
        self._control_c_pressed = Event()  # type: Event
        self._ignore_internet = Event()  # type: Event  # set to ignore incoming code, clear to process it
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

    def _display_text(self, char, update=True, spacing=0.0):  # type: (str, bool, float) -> None
        """
        Common function for displaying text on the form.
        """
        self._form.print(char, self._tgcfg.text_font_bold, self._tgcfg.text_font_italic, update, spacing)
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
        rdr = self._reader  # assign locally in case our reader gets swapped out
        if rdr is not None:
            self._last_decode_t = sys.float_info.max
            rdr.decode(code)
            self._last_decode_t = time.time()
        if self._connected and self._cfg.remote:
            self._internet.write(code)
        return

    # flush last characters from decode buffer
    def _flush_reader(self):
        self._last_decode_t = sys.float_info.max
        rdr = self._reader  # assign locally in case our reader gets swapped out
        if rdr is not None:
            rdr.flush()
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
        if self._ignore_internet.is_set():
            return
        if self._connected:
            if not self._sender_current == self._our_office_id:
                self._kob.soundCode(code, kob.CodeSource.wire)
                if code == STARTMSG:
                    self._form.new_form()
                    self._form.show_closer_state(self._kob.virtual_closer_is_open)
                elif code == ENDMSG:
                    # Don't do anything at end. Timeout or new message (STARTMSG)
                    # will display a new form.
                    pass
                else:
                    rdr = self._reader  # assign locally in case our reader gets swapped out
                    if rdr is not None:
                        rdr.decode(code)
                    pass
                pass
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

    def _new_Reader(self):  # type: () -> None
        rdr = self._reader  # assign locally in case our reader gets swapped out
        self._reader = None
        if rdr is not None:
            rdr.setCallback(None)
            rdr.exit()
        self._reader = morse.Reader(
            wpm=self._cfg.text_speed,
            cwpm=self._cfg.min_char_speed,
            codeType=self._cfg.code_type,
            callback=self._from_reader,
            decode_at_detected=self._cfg.decode_at_detected
            )
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

    def _set_virtual_closer_closed(self, close):
        """
        Handle change of Circuit Closer state.

        A state of:
        True: 'latch'
        False: 'unlatch'
        """
        was_closed = not self._kob.virtual_closer_is_open
        if close and was_closed:
            return
        open = not close
        self._kob.virtual_closer_is_open = open
        self._form.show_closer_state(open)
        code = LATCH_CODE if close else UNLATCH_CODE
        # if not self._internet_station_active:
        if True:  # Allow breaking in to an active wire message
            if self._cfg.local:
                if open:
                    self._handle_sender_update(self._our_office_id)
                rdr = self._reader  # assign locally in case our reader gets swapped out
                if rdr is not None:
                    rdr.decode(code)
                pass
            pass
        if self._connected and self._cfg.remote:
            self._internet.write(code)
        if code[-1] == 1:
            # Unlatch local (Key closed)
            self._set_local_loop_active(False)
        elif code[-1] == 2:
            # Latch local (Key open)
            self._set_local_loop_active(True)
        if was_closed:
            # The closer was closed and now it's open
            #  Flush the reader and display a new form
            self._ignore_internet.set()
            rdr = self._reader
            if rdr is not None:
                rdr.setCallback(None)  # Don't have it call back
                self._form.new_form()
                self._form.show_closer_state(self._kob.virtual_closer_is_open)
                self._new_Reader()
        else:
            self._ignore_internet.clear()
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
            if rdr is not None:
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
                            ignoring_inet = self._ignore_internet.is_set
                            self._ignore_internet.set()
                            self._form.new_form()
                            self._form.show_closer_state(self._kob.virtual_closer_is_open)
                            if not ignoring_inet:
                                self._ignore_internet.clear()
                        else:
                            if c == '\x1B':  # Escape toggles the virtual closer
                                open_vcloser = not self._kob.virtual_closer_is_open
                                if open_vcloser:
                                    c = '~'
                                else:
                                    c = '+'
                            if c < '\x20':  # Ignore other control chars
                                continue
                            vcloser_is_open = self._kob.virtual_closer_is_open
                            if (c == '~' and vcloser_is_open) or (c == '+' and not vcloser_is_open):
                                continue  # Don't repeat open when open or close when closed
                            self._from_keyboard(c)
                if time.time() - self._flush_t > self._last_decode_t:
                    self._flush_reader()
                if time.time() > self._last_display_t + self._tgcfg.page_clear_idle_time:
                    self._form.new_form()
                    self._form.show_closer_state(self._kob.virtual_closer_is_open)
                    self._last_display_t = sys.float_info.max
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
        if rdr is not None:
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
        self._kob.virtual_closer_is_open = False  # Start with the closer closed
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
        self._new_Reader()
        self._form = TGDisplay(None, self._tgcfg)
        self._form.start()
        self._form.caption = "Telegram"
        self._clock = pygame.time.Clock()
        self._form.new_form(fresh=True)
        self._form.show_closer_state(self._kob.virtual_closer_is_open)
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
        log.debug(traceback.format_exc(), 1, dt="")
    finally:
        if telegram is not None:
            telegram.shutdown()
            telegram.exit()
            telegram = None
    sys.exit(exit_status)
