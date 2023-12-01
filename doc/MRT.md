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

## Running at Start-Up on Linux
There have been requests to have something that automatically runs by just turning it on.
This can be done on a small Linux box like the Inovato Quadra or a Raspberry Pi Zero-W.

Here are instructions for the Quadra, but they can easily be applied to the RPi...

1. Script in /home/quadra: RunMRT.sh
```
#!/bin/sh
cd /home/quadra/PyKOB
/home/quadra/.local/bin/python3.11 MRT.py > MRT.out 2>/dev/null &
```
3. Make it executable:
```
$chmod +x RunMRT.sh
```
4. Create a crontab for the quadra user and have this run on reboot:
```
$crontab -e
```
(pick the editor you want to use)

-at the end after the comments-
```
@reboot /home/quadra/RunMRT.sh
```
5. Reboot:
```
$sudu reboot now
```
-After Reboot-

5. Check that it's running:
```
$ps -aux | grep MRT
```
should list something like this:
```
quadra      1504 21.8  2.4 461672 50412 ?        Sl   21:12   0:14 /home/quadra/.local/bin/python3.11 MRT.py
quadra      2915  0.0  0.0   5904   648 pts/0    S+   21:13   0:00 grep MRT
```
6. If you need to kill it, use `kill -9` with the process number from above:
```
$kill -9 1504
```
The script runs the command in the background (using the '&' at the end). That is needed to allow the crontab processing to continue past that command. The script also causes the command error output to be thrown away, as there is a lot of it from the ALSA subsystem. It sends the regular output to 'MRT.out' in the PyKOB directory.
The regular output could also thrown away, but it can be kind of nice to be able to check that it is doing something.

