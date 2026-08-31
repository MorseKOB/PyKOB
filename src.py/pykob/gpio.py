"""
MIT License

Copyright (c) 2020-26 PyKOB - MorseKOB in Python

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
    GPIO Utilities to use with `gpiod` library primarily on Raspberry Pi,
    though in theory it should apply to other Linux systems that support
    GPIO.
"""
from pykob import log

import os

def get_gpio_pins_dev():
    """
    Dynamically scan /dev/ for all available gpiochip devices and
    returns the path of the chip driving the main pin header.
    """
    for dev in sorted(os.listdir('/dev/')):
        if dev.startswith("gpiochip"):
            path = f"/dev/{dev}"
            try:
                # Open the chip layer to read its identifier label metadata
                import gpiod as pygpio
                with pygpio.Chip(path) as chip:
                    info = chip.get_info()
                    # On Pi 3/4 this label is usually 'bcm2835-gpiomem' or similar
                    # On Pi 5 this label tracks the 'pinctrl' sub-architecture
                    if "pinctrl" in info.label or "bcm2" in info.label:
                        return path
            except ImportError:
                log.debug("Error loading 'gpiod' module (is it installed?)")
                raise   # <- re-raise that exception
            except PermissionError as pex:
                log.error("Permission error scanning for GPIO hardware: {}".format(pex), dt="")
                raise
            except Exception as ex:
                log.debug("Error enumerating GPIO devices: {}".format(ex), 2)
                continue
    # NONE is returned if a GPIO isn't found
    return None
