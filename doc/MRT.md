# MRT (Marty) - Morse Receive & Transmit
MRT, 'Marty', is a command-line Morse receive and transmit application.
It connects to a wire and receives, decodes, and displays incoming code on
the console, and allows a local key to open the circuit and send to the wire.

## Usage
Marty is executed from the command-line:

`>python3 MRT.py`

Marty uses the current configuration (set using the `Configure.py` application).
It accepts optional arguments to:
* Display help: `-h`|`--help`
* Specify a station/office name other than the one configured: `-S station`, `--station station`
* Specify a speed other than the one configured: `-t wpm`, `--textspeed wpm`
* Connect to a wire other than the one configured: (last, positional, argument)

Full CLI syntax:
`>python3 MRT.py [-h|--help] | [-S|--station station] [-t|--textspeed wpm] [wire]`

## Operation
Marty automatically connects to the wire when it is started and it remains connected
while it is running. There is no option to connect/disconnect. It monitors the wire
and the local key. If the local key is opened, keyed code will be sent to the wire.
While the local key is closed, Marty will sound, as well as decode and display, code
received from the wire.

The station name of the sending station is displayed when the sending station
changes.

## Exiting
Marty runs continuously once started. To stop, enter a Ctrl-C (^C) on the
keyboard or kill the process.
