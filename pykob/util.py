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
util.py - Utilities functions.

This is primarily to contain small utility functions from the
Python 'distutils' package, to avoid requiring people to install distutils
just to run PyKOB applications.

Some portions, are copied from 'distutils', those functions have a comment
indicating such.

"""
from typing import Optional

def on_off_from_bool(b:bool) -> str:
    """
    Return 'ON' if `b` is `True` and 'OFF' if `b` is `False`

    Parameters
    ----------
    b : boolean
        The value to evaluate
    Return
    ------
        'ON' for `True`, 'OFF' for `False`
    """
    #print(b)
    r = "ON" if b else "OFF"
    return r

def str_empty_or_value(s:str) -> str:
    """
    Return an empty string ("") if `s` is None or the string value otherwise.

    Parameters
    ----------
    s : str
        The string value to evaluate
    Return
    ------
        "" or the string value
    """
    return s if not s is None else ""

def str_none_or_value(s:str) -> Optional[str]:
    """
    Return `None` if `s` is None, empty, or the value 'NONE', else the string value.

    Parameters
    ----------
    s : str
        The string value to evaluate
    Return
    ------
        `None` or the string value
    """
    r = None if not s or not s.strip() or s.upper() == 'NONE' else s
    return r


def strtobool (val):
    """
    (from distutils) Convert a string representation of truth to true (1) or false (0).

    True values are 'y', 'yes', 't', 'true', 'on', and '1'; false values
    are 'n', 'no', 'f', 'false', 'off', and '0'.  Raises ValueError if
    'val' is anything else.
    """
    val = val.lower()
    if val in ('y', 'yes', 't', 'true', 'on', '1'):
        return 1
    elif val in ('n', 'no', 'f', 'false', 'off', '0'):
        return 0
    else:
        raise ValueError("invalid truth value %r" % (val,))

