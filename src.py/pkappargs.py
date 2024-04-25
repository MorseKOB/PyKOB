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
pkappargs.py

Helpers for adding and handling PyKOB application common commandline arguments.

"""
import argparse
from typing import Optional

from pykob import recorder

record_session_override = argparse.ArgumentParser(add_help=False)
record_session_override.add_argument("--record", metavar="filepath|['A'|'AUTO']", dest="record_filepath",
    help="Record the session to a PyREC recording file. The file is 'filepath' if specified or is auto-generated if 'AUTO'.")

sender_datetime_override = argparse.ArgumentParser(add_help=False)
sender_datetime_override.add_argument(
    "--senderdt",
    dest="sender_dt",
    action='store_true',
    help="Add a date-time stamp to the current sender printed when the sender changes."
)

def record_filepath_from_args(args) -> Optional[str]:
    record_filepath = None
    if hasattr(args, "record_filepath"):
        record_filepath = args.record_filepath if args.record_filepath else None
        if record_filepath:
            rf = record_filepath.upper()
            if rf == 'A' or rf == "AUTO":
                record_filepath = recorder.generate_session_recording_name()
            else:
                record_filepath = recorder.add_ext_if_needed(record_filepath)
    return record_filepath
