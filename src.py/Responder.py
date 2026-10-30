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
Responder.py

Respond to messages. Also provide some scheduled feed functionality.

Connects to a wire and receives code from it. The text is monitored
for a message sent to a specified station (configured in a spec file). If
the message is for the specified station, the responder waits for the
sender to finish and then it responds with one of the configured responses.

This reads the current configuration and supports the common option flags.
A positional command line parameter specifying the path to the spec file
is required. The KOB Server wire can also be supplied on the command line.

Example:
    python Respond.py responses.mrtsfs 11

    Run `Respond` with a scheduled feed spec named 'responses.resps'
    connecting to wire 11.

"""

from pykob import config, config2, log, internet, morse
from pykob.config2 import Config
from pykob.internet import Internet
from pykob.morse import Reader, Sender
import pkappargs

import argparse
from datetime import datetime
from enum import IntEnum, unique
import json
import os
from pathlib import Path
import random
import re  # RegEx
import sys
from threading import Event, Thread
import time
from time import sleep
import traceback
from typing import Optional, Sequence

COMPILE_INFO = globals().get("__compiled__")
__version__ = '1.0.0'
VERSION = __version__ if COMPILE_INFO is None else __version__ + 'c'
RESP_VERSION_TEXT = "Responder " + VERSION


LATCH_CODE = (-0x7fff, +1)  # code sequence to force latching (close)
UNLATCH_CODE = (-0x7fff, +2)  # code sequence to unlatch (open)

# ###################################################################
# 
# Utility (non-class) Functions
#
# ###################################################################

def get_first_word(text: str) -> str:
    # \w+ matches the first sequence of word characters (letters/digits)
    match = re.search(r'\w+', text)
    return match.group(0) if match else ""

def strings_are_different(string_list: list[str]) -> bool:
    # An empty list or single item has no mismatches
    if not string_list:
        return False
    # If the set size is greater than 1, at least one is different
    return len(set(string_list)) > 1

def word_count_is(text: str, target_count: int) -> bool:
    # split() handles trimming and multiple spaces automatically
    return len(text.split()) == target_count

# ###################################################################
# 
# Sentence Parser/Categorizer (only for 'simple' sentences)
#
# ###################################################################

class SSParser:

    """ Sentence Types """
    BLANK_T = "BLANK"
    QUESTION_T = "QUESTION"
    STATEMENT_T = "STATEMENT"

    """ Parse Components """
    ADVERBIAL_C = "Adverbial"
    COMPLEMENT_C = "Complement"
    OBJECT_C = "Object"
    SENTENCE_C = "Sentence"
    SUBJECT_C = "Subject"
    TYPE_C = "SentenceType"
    VERB_C = "Verb"

    def __init__(self):
        # Common English auxiliary and linking verbs that initiate questions
        self.question_starters_verbs = {
            "is", "am", "are", "was", "were", "do", "does", "did",
            "can", "could", "will", "would", "should", "has", "have", "had"
        }
        
        # Common interrogative pronouns/adverbs
        self.question_starters_words = {
            "who", "what", "where", "when", "why", "how", "which"
        }

        self.linking_verbs = {
            "is", "am", "are", "was", "were", "be", "been", "being",
            "become", "becomes", "became", "seem", "seems", "seemed", "feels"
        }
        
        self.prepositions = {
            "at", "in", "on", "to", "for", "with", "by", "from", "into", 
            "through", "during", "under", "over", "between", "after", "before"
        }

    def parse(self, sentence: str) -> dict:
        """
        Parses a simple sentence string into its core grammatical parts
        and determines if it is a STATEMENT or a QUESTION (or BLANK).
        """
        # Ensure lowercase matching but preserve raw text tokens
        words = sentence.strip().split()
        
        result = {
            SSParser.SENTENCE_C: sentence,
            SSParser.TYPE_C: SSParser.STATEMENT_T,  # Default assumption
            SSParser.SUBJECT_C: None,
            SSParser.VERB_C: None,
            SSParser.OBJECT_C: None,
            SSParser.COMPLEMENT_C: None,
            SSParser.ADVERBIAL_C: None
        }
        
        if not words:
            result[SSParser.TYPE_C] = SSParser.BLANK_T
            return result

        # Change our assumption from 

        # --- Detect Sentence Type (Word-Order Heuristics) ---
        first_word_lower = words[0].lower()
        
        # If it starts with a question word or a leading verb, tag as QUESTION
        if (first_word_lower in self.question_starters_words or 
                first_word_lower in self.question_starters_verbs):
            result[SSParser.TYPE_C] = SSParser.QUESTION_T

        # --- Strip Adverbials (Prepositional Phrases) ---
        core_words = list(words)
        adverbial_words = []
        for i, word in enumerate(core_words):
            if word.lower() in self.prepositions:
                adverbial_words = core_words[i:]
                core_words = core_words[:i]
                break
        if adverbial_words:
            result[SSParser.ADVERBIAL_C] = " ".join(adverbial_words)

        # --- Step 3: Parse Grammatical Components based on Sentence Type ---
        if result[SSParser.TYPE_C] == "QUESTION":
            # For inverted syntax like "Is the car fast"
            # first word = Verb, remainder contains Subject + Object/Complement
            if first_word_lower in self.question_starters_verbs:
                verb_word = words[0]
                result[SSParser.VERB_C] = verb_word
                remaining = core_words[1:]
                
                # Simple rule for subject-complement inversion:
                # The last word is usually the adjective/complement (e.g., "fast")
                if len(remaining) >= 2:
                    result[SSParser.SUBJECT_C] = " ".join(remaining[:-1])
                    if result[SSParser.VERB_C].lower() in self.linking_verbs:
                        result[SSParser.COMPLEMENT_C] = remaining[-1]
                    else:
                        result[SSParser.OBJECT_C] = remaining[-1]
                elif len(remaining) == 1:
                    result[SSParser.SUBJECT_C] = remaining[0]
            else:
                # Handle WH-questions roughly (e.g., "Who saw the car")
                result[SSParser.SUBJECT_C] = words[0]
                if len(core_words) >= 2:
                    result[SSParser.VERB_C] = core_words[1]
                if len(core_words) > 2:
                    result[SSParser.OBJECT_C] = " ".join(core_words[2:])
                    
        else:
            # Standard STATEMENT handling (Subject + Verb + Remainder)
            verb_index = -1
            for i, word in enumerate(core_words):
                if i > 0 and (word.lower() in self.linking_verbs or 
                             word.endswith("ed") or word.endswith("s") or 
                             word.lower() in ["sing", "ran", "ate", "kicked"]):
                    verb_index = i
                    break
            
            if verb_index == -1 and len(core_words) >= 2:
                verb_index = 1
            elif verb_index == -1:
                verb_index = 0

            if verb_index > 0:
                result[SSParser.SUBJECT_C] = " ".join(core_words[:verb_index])
                verb_word = core_words[verb_index]
                result[SSParser.VERB_C] = verb_word
                remaining = core_words[verb_index + 1:]
            else:
                result[SSParser.SUBJECT_C] = "???"
                verb_word = core_words if core_words else None
                result[SSParser.VERB_C] = verb_word
                remaining = core_words[1:]

            if remaining:
                remainder_phrase = " ".join(remaining)
                # By checking 'isinstance', Pylance is guaranteed 'verb_word' is a string here
                if isinstance(verb_word, str) and verb_word.lower() in self.linking_verbs:
                    result[SSParser.COMPLEMENT_C] = remainder_phrase
                else:
                    result[SSParser.OBJECT_C] = remainder_phrase
                    
        return result


# --- Demonstration of Usage ---
if __name__ == "__main__":
    parser = SSParser()
    # Test cases without punctuation
    test_sentences = [
        "The car is fast",
        "Is the car fast",
        "The small dog barked",
        "Did the small dog bark",
        "Who saw the car",
        "I saw the car",
        "NOW  IS  THE  TIME"
    ]
    for sentence in test_sentences:
        parsed_data = parser.parse(sentence)
        print(f"Sentence: \"{parsed_data[SSParser.SENTENCE_C]}\"")
        print(f"  SentenceType: {parsed_data[SSParser.TYPE_C]}")
        for key, value in parsed_data.items():
            if key not in [SSParser.SENTENCE_C, SSParser.TYPE_C] and value is not None:
                print(f"    {key}: {value}")
        print("-" * 40)



# ###################################################################
# 
# Response Processor
#
# ###################################################################

class ResponseError(Exception):
    pass

class MultipleRESPConditions(ResponseError):
    pass

class RESPConditionUnknown(ResponseError):
    pass

class RESPConditionTimeInvalid(ResponseError):
    pass

class RESPConditionPeriodInvalid(ResponseError):
    pass

class RESPConditionMultipleMsgMsgsEntries(ResponseError):
    pass

class RESPConditionMsgsNotList(ResponseError):
    pass

class RESPControlInvalid(ResponseError):
    pass

class RESPSpecInvalid(ResponseError):
    pass


class _RESPSpecOp:
    """
    Internal class to contain a Responder Spec and operation history.

    Contains:
        condition   - The condition that triggers the feed
        isresp      - True if the condition is a Response type
        time        - The time/period specified for the condition
        msg         - A single message (if a single one was specified)
        msgs        - A list of messages (if multiple were specified, used randomly)
        --------
        last_dt     - The date-time of the last transmission
    """

    def __init__(self, spec):  # type: (dict[str,Any]) -> None
        self._condition = None      # type: RespProcessor._CondOp|None
        self._isresp = False        # type: bool
        self._time = None           # type: int|None
        self._period = None         # type: int|None
        self._msg = None            # type: str|None
        self._msgs = None           # type: list[str]|None
        self._last_activity = -1    # type: int
        self._last_dt = -1          # type: int
        #
        for key, value in spec.items():
            if (key in [
                    RespProcessor._CondOp.at.name,
                    RespProcessor._CondOp.at_ii.name,
                    RespProcessor._CondOp.when_i.name,
                    RespProcessor._CondOp.idle.name,
                    RespProcessor._CondOp.resp.name,
                    RespProcessor._CondOp.resp_tts.name,
                    RespProcessor._CondOp.resp_b.name,
                    RespProcessor._CondOp.resp_b_tts.name,
                    RespProcessor._CondOp.resp_q.name,
                    RespProcessor._CondOp.resp_q_tts.name,
                    RespProcessor._CondOp.resp_s.name,
                    RespProcessor._CondOp.resp_s_tts.name
                    ]):
                if self._condition is not None:
                    raise MultipleRESPConditions("Resp condition {} already set when condition {} was encountered in spec.".format(self._condition, value))
                self._condition = RespProcessor._CondOp[key]
                if self._condition in [
                    RespProcessor._CondOp.idle,
                    RespProcessor._CondOp.resp,
                    RespProcessor._CondOp.resp_tts,
                    RespProcessor._CondOp.resp_b,
                    RespProcessor._CondOp.resp_b_tts,
                    RespProcessor._CondOp.resp_q,
                    RespProcessor._CondOp.resp_q_tts,
                    RespProcessor._CondOp.resp_s,
                    RespProcessor._CondOp.resp_s_tts
                ]:
                    if self._condition is not RespProcessor._CondOp.idle:
                        self._isresp = True
                    try:
                        self._period = int(value)
                        if self._period < 1 or self._period >= 86400:
                            raise RESPConditionPeriodInvalid("Resp spec period value {} is not valid. Period must be 0 < p < 86,400 (24hrs).".format(self._period))
                    except ValueError as ex:
                        raise RESPConditionPeriodInvalid("Resp spec period specified is invalid {}. Must be an integer. Error: {}".format(value, ex))
                else:
                    try:
                        self._time = int(value)
                        if self._time < 0 or self._time > 2359:
                            raise RESPConditionPeriodInvalid("Resp spec time value {} is not valid. Time must be 0 <= p < 2400.".format(self._time))
                    except ValueError as ex:
                        raise RESPConditionPeriodInvalid("Resp spec time specified is invalid {}. Must be an integer. Error: {}".format(value, ex))
            elif key == "msg":
                if self._msg is not None or self._msgs is not None:
                    raise RESPConditionMultipleMsgMsgsEntries("Only a single 'msg' or 'msgs' entry is allowed in a Resp spec.")
                self._msg = value
            elif key == "msgs":
                if self._msg is not None or self._msgs is not None:
                    raise RESPConditionMultipleMsgMsgsEntries("Only a single 'msgs' or 'msg' entry is allowed in a Resp spec.")
                if not isinstance(value, list):
                    raise RESPConditionMsgsNotList("The Resp spec 'msgs' value must be a list of two or more message strings.")
                self._msgs = list()
                for v in value:
                    self._msgs.append(str(v))
                pass
            else:
                raise RESPConditionUnknown("Unknown Resp condition '{}'".format(key))
            pass
        # Adjust the last time sent and activity
        self._last_activity = int(time.time()//60)
        if self._time is not None:
            t0 = time.localtime()
            now_mins = t0.tm_hour*60 + t0.tm_min  # current time (min)
            tMsg = 60*(self._time//100) + (self._time%100)  # time to send message
            if tMsg < now_mins:
                # Trigger time is in the past for today. Indicate that we've sent.
                self._last_dt = now_mins
        return

    def __str__(self):
        s = ""
        if self._condition == RespProcessor._CondOp.idle:
            s = "When idle for {} seconds, send: ".format(self._period)
        elif self._condition == RespProcessor._CondOp.at:
            s = "At {} o'clock, send: ".format(self._time)
        elif self._condition == RespProcessor._CondOp.at_ii:
            s = "At {} o'clock, if idle, send: ".format(self._time)
        elif self._condition == RespProcessor._CondOp.when_i:
            s = "When idle at/after {} o'clock, send ".format(self._time)
        elif self._condition == RespProcessor._CondOp.resp:
            s = "Respond regardless, after waiting {} seconds. Send: ".format(self._period)
        elif self._condition == RespProcessor._CondOp.resp_tts:
            s = "Respond if to this station, after waiting {} seconds. Send: ".format(self._period)
        elif self._condition == RespProcessor._CondOp.resp_b:
            s = "Respond if message is blank, after waiting {} seconds. Send: ".format(self._period)
        elif self._condition == RespProcessor._CondOp.resp_b_tts:
            s = "Respond if to this station and message is blank, after waiting {} seconds. Send: ".format(self._period)
        elif self._condition == RespProcessor._CondOp.resp_q:
            s = "Respond if a question, after waiting {} seconds. Send: ".format(self._period)
        elif self._condition == RespProcessor._CondOp.resp_q_tts:
            s = "Respond if to this station and a question, after waiting {} seconds. Send: ".format(self._period)
        elif self._condition == RespProcessor._CondOp.resp_s:
            s = "Respond if a statement, after waiting {} seconds. Send: ".format(self._period)
        elif self._condition == RespProcessor._CondOp.resp_s_tts:
            s = "Respond if to this station and a statement, after waiting {} seconds. Send: ".format(self._period)
        else:
            s = "Not sure what we are doing!!! "
        if self._msg is not None:
            s += self._msg
        elif self._msgs is not None:
            s += "One of; "
            s += ", ".join(self._msgs)
        return (s)

    def __repr__(self):
        return self.__str__()

    @property
    def condition(self):  # type: () -> (RespProcessor._CondOp | None)
        return self._condition

    @property
    def is_resp_type(self):  # type: () -> bool
        return self._isresp

    @property
    def last_activity(self):  # type: () -> int
        return self._last_activity
    @last_activity.setter
    def last_activity(self, t):  # type: (int) -> None
        self._last_activity = t
        return

    @property
    def last_dt(self):  # type: () -> int
        return self._last_dt
    @last_dt.setter
    def last_dt(self, dt):  # type: (int) -> None
        self._last_dt = dt
        return

    @property
    def msg(self):  # type: () -> str|None
        return self._msg

    @property
    def msgs(self):  # type: () -> list[str]|None
        return self._msgs

    @property
    def period(self):  # type: () -> int|None
        return self._period

    @property
    def time(self):  # type: () -> int|None
        return self._time

class RespProcessor:
    """
    Loads and parses a Resp Spec to create a definition of what needs
    to be sent and what times.

    Methods are provided that need to be called as activity occurs such that
    the class knows when the wire is idle, and how long it has been idle.

    A method is also provided that needs to be called regularly so the
    current time can be checked to see if something needs to be sent.

    The format of a spec is as follows (example):
    {
        "specs": [
            {
                "at":815,
                "msg":"~ ES ON +     ~ OK ES +"
            },
            {
                "at_ii":1310,
                "msg":"~ ES CHECKING IN +     ~ OK ES +"
            },
            {
                "when_i":1310,
                "msg":"~ ES CHECKING IN +     ~ OK ES +"
            },
            {
                "idle":15,
                "msgs":[
                    "~ «$STN_NAME» SEEING WHO IS THERE. = OK «$STN_NAME» +",
                    "~ «$STN_NAME» INVITING YOU TO JOIN IN. = OK «$STN_NAME» +",
                    "~ «$STN_NAME» WELCOME TO OUR WIRE. = «P3.2» WE HOPE YOU ARE ENJOYING YOURSELF. OK «$STN_NAME» +",
                    "~ «$STN_NAME» PLEASE COME VISIT «$SITE_NAME» AND SEE US IN ACTION. = OK «$STN_NAME» +"
                ]
            }
        ]
    }

    The value of specs is an array/list with a condition and a time or period and a msg with a text_string or a msgs with an array/list of text_strings.
    condition is one of:
    at : Sends a message at a specified time. The message will be sent no matter what (it will break in if the wire is currently active).
    at_ii : Send a message at a specified time if the wire is idle. If the wire is active, the message will not be sent.
    when_i : Send a message as soon as the wire is idle at, or as soon after, the specified time.
    idle : Send a message if the wire is idle for the specified period (seconds).
    resp: Respond to a message (doesn't matter what type or to whom)
    resp_tts: Respond to a message if the message was directed to this station. The station directed to is the first three IDs (sines) received.
    resp_b: Respond to a blank message. If the last message was blank this will respond with a message.
    resp_b_tts: Respond to a blank message if the message was directed to this station. See: `resp_tts`
    resp_q: Respond to a question. If the last message was a question this will respond with a message.
    resp_q_tts: Respond to a question if the message was directed to this station. See: `resp_tts`
    resp_s: Respond to a statement. If the last message was a statement this will respond with a message.
    resp_s_tts: Respond to a statement if the message was directed to this station. See: `resp_tts`
    
    time or period : 24-Hour Hour+Minute value. 
        For the 'resp' conditions, this is how long to wait while the line is idle before responding.

    msg : A single text_string containing the message to be sent.
    msgs : Array/list of text_string values. One of the messages will be used at random when a message is to be sent.

    The text_string can include plain text, or the following special characters/sequences:
    '~' : Opens the key (same as keyboard sending)
    '+' : Closes the key (same as keyboard sending)
    «ctrl» : Control value, which is one of: 
        ('«' is Unicode U+00AB and '»' is Unicode U+00BB)
      $env_var : Replaced with the value of the environment variable env_var
      Pseconds : Pause the given number of seconds (can be fractional)
      OOID : Replaced with Our (full) Office ID (from the configuration/command line)
      OSID : Replaced with Our (short) ID/Sine (from the command line)
      -- additional for 'resp' messages (not valid in other messages) --
      FOID : Office ID of the sender ('from' as indicated by the wire)
      FOID1 : The first component of the sender Office ID ('from' as indicated by the wire)
      FSID : Short ID/Sine of the sender ('from' as received in the message)
      SENTENCE : The sentence received
      ADVERBIAL = The Adverb in the sentence
      COMPLEMENT = The Complement in the sentence
      OBJECT : The Object in the sentence
      SUBJECT = The Subject in the sentence
      TYPE : The sentence Type (BLANK/QUESTION/STATEMENT)
      VERB : The Verb in the sentence

    """

    RESPONSE_SPEC_EXT = ".resps"

    SPECS_KEY = "specs"
    #
    AT_KEY = "at"
    AT_IF_IDLE_KEY = "at_ii"
    WHEN_IDLE_KEY = "when_i"
    IDLE_KEY = "idle"
    #
    MSG_KEY = "msg"
    MSGS_KEY = "msgs"
    #
    CTRL_VAL_START_CHAR = '\u00AB'  # Unicode character: «
    CTRL_VAL_END_CHAR = '\u00BB'    # Unicode character: »
    CTRL_VAL_ENV_VAR_START = '$'    # Environment variables are specified by '$'
    CTRL_VAL_PAUSE_VAR_START = 'P'  # Pause 4.2 seconds example: "P4.2"
    CTRL_TOKEN_OOID = "OOID"        # Our (full) Office ID
    CTRL_TOKEN_OSID = "OSID"        # Our (short) Office ID (Sine)
    CTRL_TOKEN_FOID = "FOID"        # From (full) Office ID
    CTRL_TOKEN_FOID1 = "FOID1"      # 1st component of from (full) Office ID
    CTRL_TOKEN_FSID = "FSID"        # From (short) ID/Sine
    CTRL_TOKEN_SENTENCE = "SENTENCE" # The sentence from the message
    CTRL_TOKEN_ADVERBIAL = "ADVERBIAL" # The adverb from the message
    CTRL_TOKEN_COMPLEMENT = "COMPLEMENT" # The complement from the message
    CTRL_TOKEN_OBJECT = "OBJECT"    # The object from the message
    CTRL_TOKEN_SUBJECT = "SUBJECT"  # The subject from the message
    CTRL_TOKEN_TYPE = "TYPE"        # The type from the message
    CTRL_TOKEN_VERB = "VERB"        # The verb from the message

    @unique
    class _CondOp(IntEnum):
        at = 1
        at_ii = 2
        when_i = 3
        idle = 4
        resp = 5
        resp_tts = 6
        resp_b = 7
        resp_b_tts = 8
        resp_q = 9
        resp_q_tts = 10
        resp_s = 11
        resp_s_tts = 12

    @unique
    class _Mode(IntEnum):
        COLLECTING_TO = 1
        COLLECTING_FROM = 2
        COLLECTING_MSG = 3
        COLLECTED = 4
        IGNORE = 5
        SENT = 6
    
    @staticmethod
    def add_ext_if_needed(s: str) -> str:
        """
        Add the Response spec file extension if needed.

        Adds '.resps' to the string argument if it doesn't already end with it.
        """
        if s and not s.endswith(RespProcessor.RESPONSE_SPEC_EXT):
            return (s + RespProcessor.RESPONSE_SPEC_EXT)
        return s

    def __init__(self, oid, sid, resp_spec_path, morse_sender, code_char_send_callback, shutdown_event):  # type (str, Path|None, Sender, Callable, Event) -> None
        self._oid = oid
        self._sid = sid
        self._resp_spec_path = resp_spec_path
        self._morse_sender = morse_sender
        self._code_char_send = code_char_send_callback
        self._shutdown = shutdown_event
        self._spec_ops = list()  # type: list[_RESPSpecOp]
        #
        self._mode = RespProcessor._Mode.IGNORE
        self._msg_to = []
        self._msg_from = []
        self._msg = []
        self._sndr_oid = None  # type: str|None
        self._re_ctrlval = re.compile("^([^»]*)(»)")
        self._re_mwchar = re.compile("^[A-Z0-9 ]+$")
        self._sender_on = False  # type: bool
        self._sender_collected = []

        self._load_specs()
        self._sntnc_parser = SSParser()
        self._msg_parsed = self._sntnc_parser.parse("")
        #
        return

    def _load_specs(self):  # type: () -> None
        if self._resp_spec_path:
            specs = None
            jd = None
            with open(self._resp_spec_path, 'r', encoding="utf-8") as fp:
                jd = json.load(fp)
            if jd:
                specs = jd[RespProcessor.SPECS_KEY]
            if specs:
                self._spec_ops = list()
                for spec in specs:
                    self._spec_ops.append(_RESPSpecOp(spec))
                pass
            pass
        return

    def _process_ctrl(self, msg, index):  # type: (str, int) -> int
        """
        Process a control sequence within a message. The `index` param is pointing
        to the lead-in ctrl character.

        Return the index of the beginning of the remainder of the message.
        """
        i = index + 1  # The first character of the control sequence
        ctrl = msg[i]
        s = msg[i:]
        # Read the control string
        m = self._re_ctrlval.match(s)
        if m:
            cv = m.group(1)  # The Token
            ce = m.group(2)  # End character
            if not cv or len(cv) == 0:
                raise RESPControlInvalid("No Control Token/Value found for '{}' in message: '{}'".format(ctrl, msg))
            if not ce or len(ce) == 0:
                raise RESPControlInvalid("Control close not found for '{}' in message: '{}'".format(ctrl, msg))
            
            if not (ctrl == RespProcessor.CTRL_VAL_ENV_VAR_START or ctrl == RespProcessor.CTRL_VAL_PAUSE_VAR_START):
                # It's not an environment variable or a pause duration
                # see if the control content is one of our tokens
                if cv in [
                    self.CTRL_TOKEN_OOID,
                    self.CTRL_TOKEN_OSID,
                    self.CTRL_TOKEN_FOID,
                    self.CTRL_TOKEN_FOID1,
                    self.CTRL_TOKEN_FSID,
                    self.CTRL_TOKEN_SENTENCE,
                    self.CTRL_TOKEN_ADVERBIAL,
                    self.CTRL_TOKEN_COMPLEMENT,
                    self.CTRL_TOKEN_OBJECT,
                    self.CTRL_TOKEN_SUBJECT,
                    self.CTRL_TOKEN_TYPE,
                    self.CTRL_TOKEN_VERB
                ]:
                    # It is one of our tokens
                    #  Process it:
                    val: str|None = None
                    match cv:
                        case self.CTRL_TOKEN_OOID:
                            val = self._oid
                        case self.CTRL_TOKEN_OSID:
                            val = self._sid
                        case self.CTRL_TOKEN_FOID:
                            val = self._sndr_oid
                        case self.CTRL_TOKEN_FOID1:
                            if self._sndr_oid:
                                val = get_first_word(self._sndr_oid)
                        case self.CTRL_TOKEN_FSID:
                            val = self._msg_from[0]
                        case self.CTRL_TOKEN_SENTENCE:
                            val = self._msg_parsed[SSParser.SENTENCE_C]
                        case self.CTRL_TOKEN_ADVERBIAL:
                            val = self._msg_parsed[SSParser.ADVERBIAL_C]
                        case self.CTRL_TOKEN_COMPLEMENT:
                            val = self._msg_parsed[SSParser.COMPLEMENT_C]
                        case self.CTRL_TOKEN_OBJECT:
                            val = self._msg_parsed[SSParser.OBJECT_C]
                        case self.CTRL_TOKEN_SUBJECT:
                            val = self._msg_parsed[SSParser.SUBJECT_C]
                        case self.CTRL_TOKEN_TYPE:
                            val = self._msg_parsed[SSParser.TYPE_C]
                        case self.CTRL_TOKEN_VERB:
                            val = self._msg_parsed[SSParser.VERB_C]
                    if val is not None:
                        self._send_message(val)
                    return (i + len(cv) + len(ce))
                else:
                    raise RESPControlInvalid("Unknown Control '{}' in message: '{}'".format(ctrl, msg))
            if ctrl == RespProcessor.CTRL_VAL_ENV_VAR_START:
                # cv is the name of an environment variable. Get the value and send it.
                evv = os.environ.get(cv)
                if evv is not None:
                    self._send_message(evv)
                pass
            else:
                # ctrl_val should be a float value to use as a delay
                d = 0.0
                try:
                    d = float(cv)
                except ValueError as ex:
                    raise RESPControlInvalid("Invalid Pause value '{}' in message: '{}'  Error: {}".format(cv, msg, ex))
                self._shutdown.wait(d)
            return (i + len(cv) + len(ce))
        raise RESPControlInvalid("Invalid Control Value for '{}' in message: '{}'".format(ctrl, msg))

    def _send_msg_from_spec(self, spec):  # type: (_RESPSpecOp) -> None
        """
        Send the message if there is a single one, or randomly send one of the
        list of messages from the spec.
        """
        msg = None
        if spec.msg is not None:
            msg = spec.msg
        elif spec.msgs is not None:
            ec = len(spec.msgs)
            rnd_indx = random.randint(0, ec-1)
            msg = spec.msgs[rnd_indx]
        if msg is not None and len(msg) > 0:
            self._send_message(msg)
        return

    def _send_message(self, msg):  # type: (str) -> None
        """
        Send a message from the Resp Spec as though it was from an operator.
        """
        try:
            i = 0  # Use an index to allow processing parts
            while i < len(msg):
                ch = msg[i]
                # Check for a Control Sequence
                if ch == RespProcessor.CTRL_VAL_START_CHAR:
                    i = self._process_ctrl(msg, i)
                else:
                    i += 1
                    code = self._morse_sender.encode(ch)
                    self._code_char_send(code, ch)
                pass
            pass
        except Exception as ex:
            print("<<< Resp sender encountered an error on message: '{}'  Error: {}".format(msg, ex))
            raise
        return

    def activity(self, content, halfsp):  # type: (str,bool) -> None
        """
        Should be called by MrtCtrl any time characters are received.
        """
        stop_collecting = (content == '.' or content == '?')
        if not halfsp or (halfsp and self._mode == RespProcessor._Mode.COLLECTING_MSG):
            if (bool(self._re_mwchar.match(content)) or (self._mode == RespProcessor._Mode.COLLECTING_MSG and stop_collecting)):
                match self._mode:
                    case RespProcessor._Mode.COLLECTING_TO:
                        self._msg_to.append(content)
                        # see if we have collected 3 words
                        if content == ' ' and not halfsp:
                            collected = "".join(self._msg_to)
                            if word_count_is(collected, 3):
                                self._mode = RespProcessor._Mode.COLLECTING_FROM
                    case RespProcessor._Mode.COLLECTING_FROM:
                        self._msg_from.append(content)
                        # see if we have collected 1 word
                        if content == ' ' and not halfsp:
                            collected = "".join(self._msg_from)
                            if word_count_is(collected, 1):
                                self._mode = RespProcessor._Mode.COLLECTING_MSG
                    case RespProcessor._Mode.COLLECTING_MSG:
                        # collect the message but stop collecting at the first '.' or '?'
                        if (stop_collecting):
                            self._mode = RespProcessor._Mode.IGNORE
                        else:
                            self._msg.append(content)
                    case RespProcessor._Mode.IGNORE:
                        pass
                    case RespProcessor._Mode.COLLECTED:
                        # Shouldn't get here - as this is after sender has closed key
                        pass
        # Get current time now
        now = datetime.now()
        now_secs = int((now.hour * 3600) + (now.minute * 60) + now.second)
        for spec in self._spec_ops:
            if spec.condition == RespProcessor._CondOp.idle or spec.is_resp_type:
                spec.last_activity = now_secs
            pass
        return

    def exit(self):  # type () -> None
        pass
        return
    
    def process(self, wire_active):  # type: (bool) -> None
        """
        Process specs based on the message state, current time, and wire state.

        This MUST BE CALLED REGULARLY by the main code flow to allow Resp
        conditions to be checked to see if any messages need to be sent.

        Param wire_active indicates if a remote station is currently active on the wire.
        """
        #
        # Run through the specs and see if the condition is met.
        for spec in self._spec_ops:
            if spec.is_resp_type:  # This is a response, see if we have a complete message
                if self._mode is RespProcessor._Mode.COLLECTED:
                    # Yes. See if it meets the criteria
                    #  Work from the most specific to the most generic
                    if spec.condition in [
                        RespProcessor._CondOp.resp_s_tts,
                        RespProcessor._CondOp.resp_q_tts,
                        RespProcessor._CondOp.resp_b_tts,
                        RespProcessor._CondOp.resp_tts
                    ]:
                        # Requires that the message be directed 'To This Station'
                        # See if it was...
                        to_us = False
                        for t in self._msg_to:
                            if t == self._sid:
                                to_us = True
                                break
                        if not to_us:
                            continue  # The message wasn't to us, so the condition isn't met
                    # The message was to us or we don't care who it is to
                    #  See if the type matches
                    respond = False
                    if (spec.condition is RespProcessor._CondOp.resp_s or spec.condition is RespProcessor._CondOp.resp_s_tts):
                        if (self._msg_parsed[SSParser.TYPE_C] is not SSParser.STATEMENT_T):
                            continue  # We want a statement and the message isn't one
                    elif (spec.condition is RespProcessor._CondOp.resp_q or spec.condition is RespProcessor._CondOp.resp_q_tts):
                        if (self._msg_parsed[SSParser.TYPE_C] is not SSParser.QUESTION_T):
                            continue  # We want a question and the message isn't one
                    elif (spec.condition is RespProcessor._CondOp.resp_b or spec.condition is RespProcessor._CondOp.resp_b_tts):
                        if (self._msg_parsed[SSParser.TYPE_C] is not SSParser.BLANK_T):
                            continue  # We want a blank message and the message isn't blank
                    # If we've made it here it means that we should respond...
                    # But we might need to wait for some idle time
                    if spec.period is not None:
                        # Get current time now
                        now = datetime.now()
                        now_secs = int((now.hour * 3600) + (now.minute * 60) + now.second)
                        dt = now_secs - spec.last_activity
                        if dt >= spec.period:
                            self._send_msg_from_spec(spec)
                            self._mode = RespProcessor._Mode.SENT
                        pass
                    pass
                pass
            if spec.time is not None:   # If the spec has a time see if now is the time to do something
                tMsg = int((60*(spec.time//100) + (spec.time%100)) * 60)  # time to send message
                # Get current time now
                now = datetime.now()
                now_secs = int((now.hour * 3600) + (now.minute * 60) + now.second)
                if now_secs < tMsg and spec.last_dt >= 0:
                    # It is before the trigger time for today, yet the last sent time is set...
                    # Reset the last sent time for today.
                    self._last_dt = -1
                    continue
                if now_secs >= tMsg:   # Now could be the time
                    if spec.last_dt < 0:    # The operation has not yet been performed
                        if spec.condition == RespProcessor._CondOp.at:
                            # 'AT' Sends now, regardless of other activity.
                            spec.last_dt = now_secs  # Mark as done
                            self._send_msg_from_spec(spec)
                        elif spec.condition == RespProcessor._CondOp.at_ii:
                            # 'AT If Idle' Sends now, if the wire is idle, otherwise it is skipped.
                            spec.last_dt = now_secs  # Mark as done (even if we don't send)
                            if not wire_active:
                                self._send_msg_from_spec(spec)
                        elif spec.condition == RespProcessor._CondOp.when_i:
                            # 'When Idle' will send as soon as the wire is idle
                            if not wire_active:
                                self._send_msg_from_spec(spec)
                                spec.last_dt = now_secs
                        pass
                    pass
                pass
            elif spec.period is not None and not spec.is_resp_type:  # If the spec has a period, see if it has been long enough.
                # Get current time now
                now = datetime.now()
                now_secs = int((now.hour * 3600) + (now.minute * 60) + now.second)
                dt = now_secs - spec.last_activity
                if dt >= spec.period:
                    self._send_msg_from_spec(spec)
                    spec.last_activity = now_secs
                pass
            pass
        return

    def print_conditions(self, lead_in):  # (str) -> None
        if not self._spec_ops:
            print("{}No operations specified!".format(lead_in))
        else:
            for spec in self._spec_ops:
                print("{}{}".format(lead_in, spec))
        return

    def sender_closed(self):  # () -> None
        """
        Sender closed their key. See if we collected anything and 
        generate a response if appropriate.
        """
        self._sender_on = False
        sndr_msg = "".join(self._msg)
        sndr_msg = " ".join(sndr_msg.split()[-8:])
        # See if the message is blank, but we have a 'to'
        #  if so, and the 'to' has different words, assume
        #  the 'to' is actually the message.
        if not sndr_msg:
            s = "".join(self._msg_to)
            sl = s.split()
            if strings_are_different(sl):
                sndr_msg = " ".join(sl)
                self._msg_to = []
        self._msg_parsed = self._sntnc_parser.parse(sndr_msg)
        msg_to = "".join(self._msg_to)
        msg_from = "".join(self._msg_from)
        print(f"TO: {msg_to}")
        print(f"FROM: {msg_from}")
        print(f"Message: \"{self._msg_parsed[SSParser.SENTENCE_C]}\"")
        print(f"  Type: {self._msg_parsed[SSParser.TYPE_C]}")
        for key, value in self._msg_parsed.items():
            if key not in [SSParser.SENTENCE_C, SSParser.TYPE_C] and value is not None:
                print(f"    {key}: {value}")
        print("-" * 40, flush=True)
        # Combine the msg_to and msg_from into lists of strings
        self._msg_from = msg_from.split()
        self._msg_to = msg_to.split()
        # Indicate that the message has been collected
        self._mode = RespProcessor._Mode.COLLECTED
        return
    
    def sender_opened(self, sndr_oid):  # (str) -> None
        self._sndr_oid = sndr_oid
        self._sender_on = True
        self._msg = []
        self._msg_from = []
        self._msg_to = []
        self._msg_parsed = self._sntnc_parser.parse("")
        self._mode = RespProcessor._Mode.COLLECTING_TO
        return
    
    def shutdown(self): # type: () -> None
        pass
        return

# ###################################################################
# 
# Morse Receive and Transmit Controller
#
# ###################################################################

class _MrtcOptions:
    """
    Non-Config options passed in to MrtCtrl
    """
    def __init__(
            self,
            sender_dt: bool = False,
    ) -> None:
        self.sender_dt = sender_dt

class MrtCtrl:
    """
    Morse Receive & Transmit Controller.

    Receive from a wire, run the Responder, Send to a wire.
    """
    def __init__(
        self,
        app_name_version: str,
        wire: int,
        cfg: Config,
        oid: str,
        sid: str,
        sender_dt: bool,
        resp_spec_path: str|None = None
    ) -> None:
        self._app_name_version = app_name_version
        self._wire: int = wire
        self._cfg: Config = cfg
        self._oid: str = oid
        self._sid: str = sid
        self._sender_dt: bool = sender_dt
        self._shutdown: Event = Event()
        self._fst_stop: Event = Event()
        self._kbt_stop: Event = Event()
        self._prt_stop: Event = Event()
        self._closed: Event = Event()

        if not resp_spec_path:
            raise RESPSpecInvalid("Spec path missing")
        self._resp_spec_path = RespProcessor.add_ext_if_needed(resp_spec_path.strip())
        self._resp_proc = None

        self._internet: Optional[Internet] = None
        self._reader: Optional[Reader] = None
        self._sender: Optional[Sender] = None

        self._connected = False
        self._inet_breakin_open_cnt = 0        # Track consecutive Open count to break in to open wire
        self._internet_station_active = False  # True if a remote station has the wire open
        self._last_received_para = False # The last character received was a Paragraph ('=')
        self._our_office_id = cfg.station if not cfg.station is None else ""
        self._sender_current = ""

        self._exit_status = 1

        return

    def exit(self):
        if not self._closed.is_set():
            self._closed.set()
            print("\nClosing...")
            self._shutdown.set()
            sleep(0.3)
            log.debug("MrtCtrl.exit - 1", 3)
            self.shutdown()
            log.debug("MrtCtrl.exit - 2", 3)
            inet = self._internet
            if inet:
                log.debug("MrtCtrl.exit - 3a", 3)
                inet.exit()
                log.debug("MrtCtrl.exit - 3b", 3)
            rdr = self._reader
            if rdr:
                log.debug("MrtCtrl.exit - 4a", 3)
                rdr.exit()
                log.debug("MrtCtrl.exit - 4b", 3)
            rspndr = self._resp_proc
            if rspndr:
                log.debug("MrtCtrl.exit - 5a", 3)
                rspndr.exit()
                log.debug("MrtCtrl.exit - 5b", 3)
            sndr = self._sender
            if sndr:
                log.debug("MrtCtrl.exit - 6a", 3)
                sndr.exit()
                log.debug("MrtCtrl.exit - 6b", 3)
        return

    def main_loop(self):
        self._print_start_info()
        if not self._wire == 0:
            if self._internet:
                self._internet.connect(self._wire)
                self._connected = True
        self._shutdown.wait(0.5)
        try:
            #
            while not self._shutdown.is_set():
                if self._resp_proc:
                    try:
                        self._resp_proc.process(self._internet_station_active)
                    except Exception as ex:
                        print("Error encountered (continuing): {}".format(ex))
                        log.debug(traceback.format_exc(), 3)
                        self._set_virtual_closer_closed(True)
                self._shutdown.wait(0.05)  # Loop while background threads take care of 'stuff'
        except KeyboardInterrupt:
            raise
        finally:
            self.exit()
        return

    def shutdown(self):
        log.debug("MrtCtrl.shutdown - 1", 3)
        self._set_virtual_closer_closed(True)
        self._shutdown.set()
        log.debug("MrtCtrl.shutdown - 2", 3)
        inet = self._internet
        if inet:
            log.debug("MrtCtrl.shutdown - 3a", 3)
            inet.shutdown()
            log.debug("MrtCtrl.shutdown - 3b", 3)
        rdr = self._reader
        if rdr:
            log.debug("MrtCtrl.shutdown - 4a", 3)
            rdr.shutdown()
            log.debug("MrtCtrl.shutdown - 4b", 3)
        rspndr = self._resp_proc
        if rspndr:
            log.debug("MrtCtrl.shutdown - 5a", 3)
            rspndr.shutdown()
            log.debug("MrtCtrl.shutdown - 5b", 3)
        sndr = self._sender
        if sndr:
            log.debug("MrtCtrl.shutdown - 6a", 3)
            sndr.shutdown()
            log.debug("MrtCtrl.shutdown - 6b", 3)
        return

    def start(self):
        self._internet = internet.Internet(
            officeID=self._our_office_id,
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
            callback=self._reader_callback,
            decode_at_detected=self._cfg.decode_at_detected
            )
        if self._resp_spec_path:
            p = Path(self._resp_spec_path)
            p.resolve()
            if not p.is_file():
                print("Resp spec file not found. '{}'".format(self._resp_spec_path), flush=True)
                self._resp_spec_path = None
                raise FileNotFoundError(p)
            pass
            self._resp_proc = RespProcessor(self._oid, self._sid, p, self._sender, self._from_resp_processor, self._shutdown)
            print("Responder specification to use: {}".format(p))
        return

    def _emit_local_code(self, code, char:Optional[str]=None):
        """
        Emit local code. That involves:
        1. Send code to the wire if connected

        This is used indirectly from the Response Processor to emit code once it
        determines it should be emitted.
        """
        if len(code) > 0 and (not (code[-1] == 2 or code[-1] == 1)): # special code for open/closed
            self._inet_breakin_open_cnt = 0         # reset the break in count on other key actions
        self._handle_sender_update(self._our_office_id)
        if self._connected and self._cfg.remote and self._internet:
            self._internet.write(code)
        return

    def _err_msg_handler(self, msg):  # type: (str|None) -> None
        if msg is not None:
            log.log("\nError: {}\n".format(msg), dt="")
        return

    def _status_msg_handler(self, msg):  # type: (str|None) -> None
        if msg is not None:
            log.log("\n{}\n".format(msg), dt="")
        return

    def _from_internet(self, code):
        """handle inputs received from the internet"""
        if self._connected:
            if not self._sender_current == self._our_office_id:
                if self._reader:
                    self._reader.decode(code)
            if len(code) > 0:
                self._internet_station_active = True
                if code[-1] == 1:
                    self._internet_station_active = False
                    if self._resp_proc:
                        self._resp_proc.sender_closed()
                elif code[-1] == 2:
                    if self._resp_proc:
                        self._resp_proc.sender_opened(self._sender_current)
        return

    def _from_resp_processor(self, code, char):  # type: (list[int], str|None) -> None
        """
        Called by the Resp Processor.
        """
        if len(code) > 0:
            if code[-1] == 1: # special code for closer/circuit closed
                self._set_virtual_closer_closed(True)
                return
            elif code[-1] == 2: # special code for closer/circuit open
                self._set_virtual_closer_closed(False)
                return
            # disregard self._internet_station_active, as Resp Proc might send when active
            self._emit_local_code(code, char)
        return

    def _handle_sender_update(self, sender):
        """
        Handle a <<Current_Sender>> message by:
        1. Displaying the sender if new
        """
        if not self._sender_current == sender:
            self._sender_current = sender
            ts = ""
            if self._sender_dt:
                ts = time.strftime("%Y-%m-%d %I:%M:%S %p ")
            print()
            print(f"{ts}<<{self._sender_current}>>", flush=True)
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
        print("Our ID: {}".format(self._oid))
        if self._cfg.decode_at_detected:
            print("Using the detected incoming character speed for decoding.")
        # Let the user know if 'invert key input' is enabled (typically only used for MODEM input)
        if self._cfg.invert_key_input:
            print("IMPORTANT! Key input signal invert is enabled (typically only used with a MODEM). " + \
                "To enable/disable this setting use `Configure --iki`.")
        if self._resp_spec_path:
            print("Responder operation will be controlled by specification: {}".format(self._resp_spec_path))
        if self._resp_proc:
            print("Responder Actions/Conditions:")
            self._resp_proc.print_conditions("  ")
        return

    def _reader_callback(self, char, spacing):
        """
        Called by the Reader (Decoder) as code is decoded. The
        decoded text is fed to the Responder so it can collect
        input and process it for a possible response.
        """
        if self._sender_current == self._our_office_id:
            return
        # print(f"_sender_current: {repr(self._sender_current)}")
        # print(f"_our_office_id: {repr(self._our_office_id)}")

        if not char == '=':
            if self._last_received_para:
                print(flush=True)
            self._last_received_para = False
        else:
            self._last_received_para = True
        if self._resp_proc:
            halfSpaces = min(max(int(2 * spacing + 0.5), 0), 10)
            fullSpace = False
            if halfSpaces > 0:
                halfSpaces -=1
            if halfSpaces >= 2:
                fullSpace = True
                halfSpaces = (halfSpaces - 1) // 2
            for i in range(halfSpaces):
                self._resp_proc.activity(' ', True)
            if fullSpace:
                self._resp_proc.activity(' ', False)
            self._resp_proc.activity(char, False)
        return

    def _set_local_loop_active(self, active):
        """
        Set local_loop_active state

        True: Key or Keyboard active (Circuit Closer OPEN)
        False: Circuit Closer (physical and virtual) CLOSED
        """
        self._local_loop_active = active
        return

    def _set_virtual_closer_closed(self, closed):
        """
        Handle change of Circuit Closer state.

        A state of:
        True: 'latch'
        False: 'unlatch'
        """
        if self._internet_station_active:
            if not closed:
                self._inet_breakin_open_cnt += 1
                if self._inet_breakin_open_cnt > 1:
                    # Break in to open wire
                    self._internet_station_active = False
            if self._internet_station_active:
                return
        code = LATCH_CODE if closed else UNLATCH_CODE
        if not self._internet_station_active:
            if self._cfg.local:
                if not closed:
                    self._handle_sender_update(self._our_office_id)
        if self._connected and self._cfg.remote and self._internet:
            self._internet.write(code)
        if len(code) > 0:
            if code[-1] == 1:
                # Unlatch (Key closed)
                self._set_local_loop_active(False)
                if self._reader and (not self._sender_current == self._our_office_id):
                    self._reader.flush()
            elif code[-1] == 2:
                # Latch (Key open)
                self._set_local_loop_active(True)
        return

def status_msg_handler(msg):
    log.log("\n{}\n".format(msg), dt="")
    return

def mrtc_from_args(gopts: Optional[_MrtcOptions] = None, options: Optional[Sequence[str]] = None, cfg: Optional[Config] = None) -> tuple[MrtCtrl, _MrtcOptions]:
    arg_parser = argparse.ArgumentParser(description="Morse Receive & Transmit Controller for Responder. "
        + "Receive from wire and possibly respond. Also, provide scheduled content.\nThe Global configuration is used except as overridden by options.",
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
            pkappargs.sender_datetime_override
        ],
        exit_on_error=False
    )
    if gopts is None:
        gopts = _MrtcOptions()
    arg_parser.add_argument("--sine", metavar="sine", dest="sine",
        help="The Short ID (sine) to use (otherwise, first part of Station ID is used).")
    arg_parser.add_argument("resp_spec_path", type=str,
        help="Responder specification file path.")
    arg_parser.add_argument("wire", nargs='?', type=int,
        help="Wire to connect to. If specified, this is used rather than the configured wire.")

    args = arg_parser.parse_args(options)

    cfg = config2.process_config_args(args, cfg)
    log.set_logging_level(cfg.logging_level)

    station = args.station if args.station is not None else cfg.station
    sid = args.sine if args.sine is not None else get_first_word(station)
    sender_dt = gopts.sender_dt or args.sender_dt
    gopts.sender_dt = sender_dt
    if sender_dt:
        log.debug("New sender listed with Date-Time", 1)
    wire = args.wire if args.wire else cfg.wire
    resp_spec_path = args.resp_spec_path
    #

    mrtc = MrtCtrl(
        RESP_VERSION_TEXT,
            wire,
            cfg,
            station,
            sid,
            sender_dt,
            resp_spec_path=resp_spec_path
        )
    return (mrtc, gopts)



# ###################################################################
# 
# Main Code
#
# Creates a MRT Controller and starts it, then waits for completion.
#
# ###################################################################

if __name__ == "__main__":
    mrtc = None
    exit_status = 0
    try:
        # Main code
        print(RESP_VERSION_TEXT)
        print("Python: " + sys.version + " on " + sys.platform)
        print("pykob: " + VERSION)
        print("PySerial: " + config.pyserial_version, flush=True)


        mrtc, goptions = mrtc_from_args()

        if mrtc:
            mrtc.start()
            mrtc.main_loop()
            mrtc = None
            exit_status = 0
        else:
            raise Exception("Could not initialize MRT or Selector.")
    except KeyboardInterrupt:
        exit_status = 0
    except FileNotFoundError as fnf:
        exit_status = 1
        print("File not found: {}".format(fnf.args[0]))
    except Exception as ex:
        exit_status = 3
        print("Error encountered: {}".format(ex))
        log.debug(traceback.format_exc(), 0)
    except SystemExit as arg_err:
        print(arg_err)
        log.debug(traceback.format_exc(), 3)
    finally:
        if mrtc:
            mrtc.exit()
        print()
        print("~73", flush=True)
        sleep(0.5)
        sys.exit(exit_status)
