# MorseKOB Version 4 - Python (Library, MKOB, MRT, Telegram, Utilities)

Originally written by Les Kerr, this is a Python library and programs that
implement the MorseKOB functionality familiar to users of the MorseKOB 2.5
application available for many years on Windows.

Written in Python (requires **version 3.11 or later**), that functionality
(and more) is now available on Window, Mac, and Linux.

The PyKOB library (pykob.*) provides modules, classes, and functions that
can be used within a Python program to perform Morse operations.

Additionally, there are three complete applications and a number of utilities
included. The applications and utilities can be used to learn/practice
copying and sending code. The applications and some of the utilities can also
connect to a KOB Server to receive wire feeds and communicate with others.

**Windows Installer for *MKOB Suite***

For Windows, executables have been created for the main applications and utilities and
packaged as a Windows Installer. You can get it here: https://www.aesilky.com/morse


**Note:**
 **For those that are familiar with this Repo, see the section on the reorganization**

## American Morse and International Code Encoding and Decoding

The pykob.morse module supports encoding (text to code) and decoding
(code to text) both **American Morse** and **International Code**.

American Morse (sometimes referred to as, *Landline Morse*) was used by
the railroads, Western Union, and other communications systems, connected
by telegraph wires. International Code is used for continuous wave (CW)
communications using radio.

The utilities and both of the applications can be configured to
receive/decode/print and encode/send either form.

## Physical Key & Sounder, Synthesized Sounder, Tone Support

The pykob.kob module provides support for a serial interface to a key and
sounder (wired either separately or in a loop). On Raspberry Pi, the key
and sounder can be connected using an interface connected to the GPIO.

The module also provides a synthesized sounder using the computer audio,
as well as the option to use CW style tone.

The utilities and the applications allow using any of these options.

## Applications

There are three applications included in PyKOB. All three applications
use either the shared global configuration or can use named configuration
files (created using the **Configure** utility or **MKOB**.)

### MKOB (Morse Key on Board)

The **MKOB** application provides a full graphical interface that allows
you to connect to a *Wire* on a **KOB Server** to communicate with others
or listen to feeds. It also has features to help you practice and learn
the code. Instructions for using the MKOB application are in the
**User Guide** in the **Documentation** folder.

### MRT (Morse Receive & Transmit 'Mr T')

The **MRT** application provides a command-line application that connects to a
*Wire* on a **KOB Server** and allows text to be typed and sent, plus full
support for a key and sounder. In addition, it supports a hardware selector
switch (or switch-board) that allows switching between different configurations
(either 4 or 16 depending on the hardware) without having to do anything in
the application. It also supports a scheduled feed option that will send
configured messages at specific times or when there is no activity.
Instructions for using the MRT application are in the MRT document and the
sample selector and scheduled-feed specifications in the **Documentation** folder.

### Telegram

This application is primarily intended for displays (museums, shows, etc.).
It runs full-screen and displays a telegram form that shows incoming
messages from a wire and messages keyed locally. At the end of a message
or a configured idle time, a new form is displayed for the next message.
The form's masthead can come from a graphic or configured text. The page
color, text color, text font and size, and other aspects of the operation
specific to Telegram are specified in a configuration file. The common
configuration is from the same global or named configurations used by
**MKOB** and **MRT**.

## Utilities

The following utilities can be useful for sending and listening to Morse
for fun and practice and providing **KOB Server** *Wire* feeds.

The utilities are in Python files that start with an uppercase character.
Files that start with a lowercase letter are support modules that are not
intended to be executed directly.

Most of the utilities support the **'-h'/'--help'** command line option to
provide a description of the utility and the available options.

Give it a try...
```
python3 Sample.py --help
```

### Configure.py

This is the configuration utility for all of the applications and utilities.
It is used to list and/or modify either the global configuration
or named configurations that are used by the applications.

The configuration can be set using option flags and values from the command
line, or it can launch a GUI that can be used.

Use the command line '-h' or '--help' option to see the usage. A copy of the
usage help is included in the **Documentation** folder.

### SysCheck.py

Collects and lists information about the current Python, PyKOB, and
comm interfaces available, that is relevent for running the PyKOB utilites
and applications. The comm port information is especially helpful when
using the CLI version of Configure or a Selector.

### Sample.py

Sounds a sample that can be used to test your configuration and output
hardware (sounder and computer audio).
Options are available to sound different content for fun and to use
for practice.

### Clock.py

Provides a Kuckoo Clock in Morse. Options allow setting how often to sound
and how verbose to be about the current time.

### Play.py

Plays PyKOB recorder JSON format files (session recordings saved by
the MKOB application and some of the utilities). Options allow
controlling the speed (slower or faster than the actual speed), how
much 'dead air' to include, and more.

### Receive.py

Connects to a **KOB Server *Wire*** and sounds and decodes the incoming
code. Although it is a useful utility, it was written before the **MRT**
application was written. Look at **MRT** as a more feature rich option.

### Feed.py

Source of a *Wire Feed* for a **KOB Server**. Connects for a KOB Server
on a specified Wire and sends code when one or more other clients
connect to the Wire.

The content can be from:

- PyKOB recorder format JSON file (a session recording from MKOB)
- An RSS format XML file
- An RSS feed from the internet

### More

- KeyTest.py - Continuously reads the key and prints the encoding.
- News.py - Sound and print a news feed (the source is `www.ansa.it/sito`)
- SchedFeed.py - Sends short, fixed, content at scheduled times. Edit the
  code to set your *Office/Station* ID and the wire to use.
- Time.py - Send and sound a 'standard' time signal continuously, hourly, or daily.
- Weather.py - Waits for a station to send a message ending in WX XXXX, where XXXX
  is the 4- or 5-character code for a U.S. weather reporting station, and replies
  with the current weather conditions and short term forecast for that area.

## Development & Support

The library and applications are actively being developed and supported.
Feel free to submit issues for problems you find or features you would like.

## Repo Reorganization

For those familiar with this repo, please notice that the file structure has
changed. The most noticeable change is that the Python files have been moved
from the *root* and *pykob* directory to be rooted in the *src.py* directory.

The reorganization was done to help support the creation of executables (binary
versions) and installer, and to unclutter the root directory.

The *src.py* directory contains all (only) the Python files needed to run the
applications and utilities. So, to run the Python version, start there.

Also, the **MKOB** source changed from *MKOB.pyw* to *MKOB.py*. This was done
because the `.pyw` extension causes some libraries to be pulled into the
binary that aren't needed for this application.

# Documentation

Documentation for the applications is in the **Documentation** folder and
sub-folders.

## Simple 'Getting Started'

Even if you aren't familiar with Git/GitHub, it is easy to grab a ZIP file from it.
You can also use the 'Issues' section to report problems and request features.
Of course, I recommend using Git/GitHUB, as that makes it trivial to get
updates when they become available.

The repository on GitHub: https://github.com/MorseKOB/PyKOB

### Using Git/GitHub

To get going...

``` shell
git clone --depth 1 https://github.com/MorseKOB/PyKOB.git
```

To update, you then simply (from the PyKOB folder):

``` shell
git pull
```

That will 'pull' the latest updates.

### Using a ZIP

To grab a ZIP:

- Open the GitHub page: https://github.com/MorseKOB/PyKOB
- Click the green [<> Code] button
- At the bottom of the drop-down is 'Download ZIP'

Once you have the zip, simply unzip it (make sure you unzip it as the full
folder/directory structure) into a folder.

### Install Python Libraries

PyKOB will run with just the base Python (3.11) installation, However, you
will probably want to install these libraries to get the most out of it.

You can use a Python virtual environment. There is a *requirements.txt*
file in the root directory. It can be used to configure the virtual
environment using the command

``` shell
pip install -r requirements.txt
```

Using a Python virtual environment is a great way to do development or to
run tests. If you would rather configure the system Python environment,
you can still use the *requirements.txt*. Just use the main **pip**.

The following libraries are used.

To use the system sound (to simulate a sounder) you will need **PyAudio**.
To interface with a key & sounder, you will need **pySerial**.
The **Telegram** application requires **pygame-ce**. Note that it is
important to use the *CE* implementation of *PyGame*, as it contains
features and bug-fixes that **Telegram** relies on.

Follow the instructions here:

### PyAudio

 https://pypi.org/project/PyAudio/

### pySerial

 https://pyserial.readthedocs.io/en/latest/pyserial.html

### pygame-ce (for Telegram)

 https://pyga.me/docs/

## Getting Started

The best thing to run first is **SysCheck**. That will display information about
the system, Python, the libraries used, and the serial devices (if you are going to
use an interface to a physical key and/or sounder).

It is simple to run:

- Open a Command/Terminal window in the PyKOB folder
- (I suggest running) `python3 --version` (to make sure you are running a 3.11.xx  or later version)
- If your Python version is not 3.11.xx or later you will need to upgrade it.
- Then

``` shell
cd src.py
python3 SysCheck.py
```

Next, it is suggested that you set all of the configuration options before running
any of the Morse utilities or MKOB/MRT for the first time. To do that:

- Run: `python3 Configure.py`
  That will list the current configuration. Since this is a new installation,
  the settings will all be the defaults.
- Run: 'python3 Configure.py --help'
  That will list all the option flags to use to set your desired configuration.
- Run: `python3 Configure.py <with the options you want to set>`
- There is also a GUI for configuring. To use it, use the **--gui** option:

``` shell
python3 Configure.py --gui
```

## Run 'Sample.py'

Once you have the settings you want, you are ready to run any of the utilities,
or the MKOB application. The 'utilities' are in the base source folder (*src.py*).
The utilities start with a capitol letter - for example:

``` shell
python3 Sample.py
```

That is a good one to start with, as it is a simple way to make sure things are
working correctly.

## Run MKOB

Once you are up and running, you can run:

``` shell
python3 MKOB.py
```

This is the GUI application that will let you connect to the MorseKOB Server
wires. Within MKOB, you can use `File > Preferences` to view and change the
configuration. Please note that many (most) of the configuration changes are
not picked up until you exit and restart MKOB. That is actually the focus of
the current work (making them take effect immediately), as well as being able
to save/use multiple, named, configurations.

## Wire List

To get a list of the wires that are currently active, use a browser to view:
http://mtc-kob.dyndns.org/
I like to test by connecting to one of the news wires, for example, **Wire 108**.

## Good Luck

I hope to hear (from many of you) that you were successful.

BTW: You can see other things that might be of interest if you go up one level
on GitHub: https://github.com/MorseKOB


# License

The following license information apply to the contents of this application,
modules, libraries and to libraries and modules used by this application.

## MIT License

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

## Licenses for referenced Libraries/Modules

The PyKOB applications/utilities/modules rely on other libraries/modules.
Refer to `LICENSE-MODULES` for the license details of these libraries/modules.

No modifications have been made to these libraries/modules and they are not
included with this distribution, and therefore must be provided by the user of
these applications/utilities/modules for proper operation. Refer to the library/module
documentation for details of installing the library/module.
