# MorseKOB 4.0 package

VERSION = '4.0-21'

"""

Change history:

4.0-21  2014-10-05
- internet: improved connect/disconnect functionality

4.0-20  2014-09-08
- added log module
- newsreader: trap web page read errors and retry

4.0-19  2014-08-24
- codetable-american: decode [. .] as the letter O, not zero

4.0-18  2014-07-22
- kob: allow running without audio if pygame not available

4.0-17  2014-05-19
- display: word wrap on space characters
- newsreader: allow reading from file

4.0-16  2014-04-15
- morse: fixed problem with decoding long dashes in International as L
- morse: added Esperanto option

4.0-15  2014-02-22
- internet: don't send empty code packets

4.0-14  2014-02-18
- codetable-international: changed code for = to -...-

4.0-13  2014-02-14
- display: added FULLSCREEN constant, to allow multiple windows
- internet: removed print statements

4.0-12  2014-02-10
- kob: check current key state while initializing
- kob: accept longer code sequences (>0.25 sec space between sequences)???
- morse: improve reader performance for short dots at slow speeds
- morse: (really) require reader callback; code cleanup

4.0-11  2014-01-28
- kob: always import and initialize pygame to get better clock resolution
- kob: don't print pygame or pySerial version numbers
- kob: print error messages to stderr instead of stdout
- kob: assume circuit starts latched closed
- sounder: subsumed sounder module into kob module
- display: added SCREENSIZE constant to allow overriding default
- display: don't print screensize
- display: make wordwrap flexible based on amount of space between characters
- morse: handle circuit closures (~ for open, + for closed)
- morse: tweaked reader thresholds and allowed for extra space after dash
- morse: require reader callback function instead of returning decoded character
- internet: wait a second after connecting so the first read won't fail
- internet: detect breaks in packet sequence numbers and return maximum space

4.0-10  2013-11-18
- morse: default sender to CHARSPACING; eliminated NOSPACING option (superfluous)
- morse: added reader callback function with spacing parameter

4.0-09  2013-11-12
- display: make header parameter optional

4.0-08  2013-11-07
- kob: new module to accept input from a key and activate a sounder (real or simulated)
- display: new module to display text on a monitor
- morse: don't decode American letter 'o' as zero
- morse: minor cleanup

4.0-07  2013-10-22
- sounder: added GPIO option
- internet.write: copy code sequence instead of modifying in place
- codetable-american: send zero as 'o'

4.0-06  2013-09-08
- internet: send duplicate code packets
- internet: initialize tLastListener to 0.0 instead of now()
- internet: use IP address instead of host name; update in keepAlive
- internet: trap for DNS lookup error in keepAlive and keep using previous IP address
- internet: reordered actions in keepAlive to avoid out-of-order packets
- morse: encode the hyphen character as a half-space pause
- sounder: allow simulated sounder to handle consecutive latch or unlatch codes

4.0-05  2013-08-09
- internet: added idflag to internet module for compatibility with DD feeds

4.0-04  2013-08-08
- added internet module

4.0-03  2013-07-30
- added newsreader module
- made compatible with Python 2.7 and 3.3

4.0-02  2013-07-14
- added morse module

4.0-01  2013-07-10
- minor updates

4.0-00  2013-07-07
- initial release

"""
