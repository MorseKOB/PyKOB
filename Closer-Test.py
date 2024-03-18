import sys
from pykob import kob
from pykob import config

try:
    interface = config.serial_port
    use_gpio = config.gpio

    myKOB = kob.KOB(useAudio=False, portToUse=interface, useGpio=use_gpio)
    while True:
        print(myKOB.key())
except KeyboardInterrupt:
    myKOB.exit()
    print()
    print("Thank you for using the Closer-Test!")
    sys.exit(0)     # Indicate this was a normal exit
