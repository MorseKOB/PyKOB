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
just to run PyKOB applications. It also contains a class from the Python IDLE
library. It is copied here because the Linux Python distribution does not
include IDLE.

NOTE: Some portions, are copied from 'distutils', those functions have a comment
indicating such.
LICENSE: Python Software Foundation (PSF)

NOTE: Two classes are copied from Python's `idlelib` (the IDLE IDE). Those
classes have a comment indicating such.
LICENSE: Python Software Foundation (PSF)

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

def true_false_from_bool(b:bool) -> str:
    """
    Return 'TRUE' if `b` is `True` and 'FALSE' if `b` is `False`

    Parameters
    ----------
    b : boolean
        The value to evaluate
    Return
    ------
        'TRUE' for `True`, 'FALSE' for `False`
    """
    #print(b)
    r = "TRUE" if b else "FALSE"
    return r

# ###########################################################################
# Classes from Python idlelib (IDLE IDE)
#
# WidgetRedirector
# OriginalCommand - renamed to WR_OriginalCommand
#
#    NOTE: With this copy, the user must import TclError from tkinter for use
#    `from tkinter import TclError`
#
# ###########################################################################
class WidgetRedirector:
    """Support for redirecting arbitrary widget subcommands.

    Some Tk operations don't normally pass through tkinter.  For example, if a
    character is inserted into a Text widget by pressing a key, a default Tk
    binding to the widget's 'insert' operation is activated, and the Tk library
    processes the insert without calling back into tkinter.

    Although a binding to <Key> could be made via tkinter, what we really want
    to do is to hook the Tk 'insert' operation itself.  For one thing, we want
    a text.insert call in idle code to have the same effect as a key press.

    When a widget is instantiated, a Tcl command is created whose name is the
    same as the pathname widget._w.  This command is used to invoke the various
    widget operations, e.g. insert (for a Text widget). We are going to hook
    this command and provide a facility ('register') to intercept the widget
    operation.  We will also intercept method calls on the tkinter class
    instance that represents the tk widget.

    In IDLE, WidgetRedirector is used in Percolator to intercept Text
    commands.  The function being registered provides access to the top
    of a Percolator chain.  At the bottom of the chain is a call to the
    original Tk widget operation.
    """
    def __init__(self, widget):
        '''Initialize attributes and setup redirection.

        _operations: dict mapping operation name to new function.
        widget: the widget whose tcl command is to be intercepted.
        tk: widget.tk, a convenience attribute, probably not needed.
        orig: new name of the original tcl command.

        Since renaming to orig fails with TclError when orig already
        exists, only one WidgetDirector can exist for a given widget.
        '''
        self._operations = {}
        self.widget = widget            # widget instance
        self.tk = tk = widget.tk        # widget's root
        w = widget._w                   # widget's (full) Tk pathname
        self.orig = w + "_orig"
        # Rename the Tcl command within Tcl:
        tk.call("rename", w, self.orig)
        # Create a new Tcl command whose name is the widget's pathname, and
        # whose action is to dispatch on the operation passed to the widget:
        tk.createcommand(w, self.dispatch)

    def __repr__(self):
        w = self.widget
        return f"{self.__class__.__name__,}({w.__class__.__name__}<{w._w}>)"

    def close(self):
        "Unregister operations and revert redirection created by .__init__."
        for operation in list(self._operations):
            self.unregister(operation)
        widget = self.widget
        tk = widget.tk
        w = widget._w
        # Restore the original widget Tcl command.
        tk.deletecommand(w)
        tk.call("rename", self.orig, w)
        del self.widget, self.tk  # Should not be needed
        # if instance is deleted after close, as in Percolator.

    def register(self, operation, function):
        '''Return OriginalCommand(operation) after registering function.

        Registration adds an operation: function pair to ._operations.
        It also adds a widget function attribute that masks the tkinter
        class instance method.  Method masking operates independently
        from command dispatch.

        If a second function is registered for the same operation, the
        first function is replaced in both places.
        '''
        self._operations[operation] = function
        setattr(self.widget, operation, function)
        return WR_OriginalCommand(self, operation)

    def unregister(self, operation):
        '''Return the function for the operation, or None.

        Deleting the instance attribute unmasks the class attribute.
        '''
        if operation in self._operations:
            function = self._operations[operation]
            del self._operations[operation]
            try:
                delattr(self.widget, operation)
            except AttributeError:
                pass
            return function
        else:
            return None

    def dispatch(self, operation, *args):
        '''Callback from Tcl which runs when the widget is referenced.

        If an operation has been registered in self._operations, apply the
        associated function to the args passed into Tcl. Otherwise, pass the
        operation through to Tk via the original Tcl function.

        Note that if a registered function is called, the operation is not
        passed through to Tk.  Apply the function returned by self.register()
        to *args to accomplish that.  For an example, see colorizer.py.

        '''
        m = self._operations.get(operation)
        try:
            if m:
                return m(*args)
            else:
                return self.tk.call((self.orig, operation) + args)
        except TclError:
            return ""


class WR_OriginalCommand:
    '''Callable for original tk command that has been redirected.

    Returned by .register; can be used in the function registered.
    redir = WidgetRedirector(text)
    def my_insert(*args):
        print("insert", args)
        original_insert(*args)
    original_insert = redir.register("insert", my_insert)
    '''

    def __init__(self, redir, operation):
        '''Create .tk_call and .orig_and_operation for .__call__ method.

        .redir and .operation store the input args for __repr__.
        .tk and .orig copy attributes of .redir (probably not needed).
        '''
        self.redir = redir
        self.operation = operation
        self.tk = redir.tk  # redundant with self.redir
        self.orig = redir.orig  # redundant with self.redir
        # These two could be deleted after checking recipient code.
        self.tk_call = redir.tk.call
        self.orig_and_operation = (redir.orig, operation)

    def __repr__(self):
        return f"{self.__class__.__name__,}({self.redir!r}, {self.operation!r})"

    def __call__(self, *args):
        return self.tk_call(self.orig_and_operation + args)

# ###########################################################################
# End of classes from Python idlelib (IDLE IDE)
#
# WidgetRedirector
# OriginalCommend
#
# ###########################################################################
