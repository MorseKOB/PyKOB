import sys
from pykob import kob
from pykob import config

try:
    interface = config.serial_port

    myKOB = kob.KOB(port=interface)
    myKOB.setSounder(False)
    while True:
        print(myKOB.key())
except KeyboardInterrupt:
    print()
    print("Thank you for using the Closer-Test!")
    sys.exit(0)     # Indicate this was a normal exit
    