from pykob import kob

myKOB = kob.KOB(port="com3")
myKOB.setSounder(False)
while True:
    print(myKOB.key())
