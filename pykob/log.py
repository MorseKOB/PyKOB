"""

internet module

Reads/writes code sequences from/to a KOB wire.

"""

import sys
import datetime

def log(txt):
    dt = str(datetime.datetime.now())[:19]
    sys.stderr.write('{0} {1}\n'.format(dt, txt))
    sys.stderr.flush()
    
def err(msg):
    typ, val, trc = sys.exc_info()
    log('{0} ({1})'.format(msg, val))
