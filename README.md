# MorseKOB Version 4 - Python

Written by Les Kerr, this is a Python library and programs that implement
the MorseKOB functionality. The library functions in pykob provide modules
and functions that can be used within a Python program to perform MorseKOB
operations.

The MKOB application provides a full graphical interface that allows the
station to connect to a MorseKOB wire on the Morse KOB server. Instructions
for running the MKOB application are in the MKOB-README.

# Simple 'Getting Started'
Even if you aren't familiar with Git/GitHub, it is easy to grab a ZIP file from it. You can also use the 'Issues' section to report problems and request features.
Of course, I recomment using Git/GitHUB, as that makes it trivial to get updates when they become available.

The repository on GitHub: https://github.com/MorseKOB/PyKOB

## Using Git/GitHub
To get going...

* `git clone --depth 1 https://github.com/MorseKOB/PyKOB.git`

To update, you then simply (from the PyKOB folder):

* `git pull`
That will 'pull' the latest updates.

## Using a ZIP
To grab a ZIP:

* Open the GitHub page: https://github.com/MorseKOB/PyKOB
* Click the green [<> Code] button
* At the bottom of the drop-down is 'Download ZIP'

Once you have the zip, simply unzip it (make sure you unzip it as the full folder/directory structure) into a folder.

## Install Python Libraries
PyKOB will run with just the base Python (3.11) installation, However, you will probably want to install these libraries to get the most out of it.

To use the system sound (to simulate a sounder) you will need **PyAudio**. To interface with a key & sounder, you will need **pySerial**
Follow the instructions here:

### PyAudio
 https://pypi.org/project/PyAudio/

### pySerial
 https://pyserial.readthedocs.io/en/latest/pyserial.html

## Getting Started
It is suggested that you set all of the configuration options before running utilities or MKOB for the first time. To do that:

* Open a Command/Terminal window in the PyKOB folder
* (I suggest running) `python3 --version` (to make sure you are running a 3.11.xx version)
* If your Python version is not 3.11.xx you will need to upgrade it.
* Run: `python3 Configure.py`
  That will list the current configuration. Since this is a new installation, the settings will all be the defaults.
* Run: 'python3 Configure.py --help'
  That will list all the option flags to use to set your desired configuration.
* Run: `python3 Configure.py <with the options you want to set>`

## Run 'Sample.py'
Once you have the settings you want, you are ready to run any of the utilities, or the MKOB application. The 'utilities' are in the root folder. The utilities start with a capitol letter - for example:

* `python3 Sample.py`

That is a good one to start with, as it is a simple way to make sure things are working correctly.

## Run MKOB
Once you are up and running, you can run:

`python3 MKOB.pyw`

This is the GUI application that will let you connect to the MorseKOB Server wires. Within MKOB, you can use `File > Preferences` to view and change the configuration. Please note that many (most) of the configuration changes are not picked up until you exit and restart MKOB. That is actually the focus of the current work (making them take effect immediately), as well as being able to save/use multiple, named, configurations.

## Wire List
To get a list of the wires that are currently active, use a browser to view: http://mtc-kob.dyndns.org/
I like to test by connecting to one of the news wires, for example, **Wire 108**.

## Good Luck
I hope to hear (from many of you) that you were successful.

BTW: You can see other things that might be of interest if you go up one level on GitHub: https://github.com/MorseKOB

-ES

# License
The following license information apply to the contents of this application,
modules, libraries and to libraries and modules used by this application.

## MIT License
Copyright (c) 2020 PyKOB - MorseKOB in Python

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

## Licenses for included/references Libraries/Modules
These applications/libraries/modules rely on other libraries/modules.
Refer to `LICENSE-MODULES` for the license details of these libraries/modules.

No modifications have been made to these libraries/modules and they are not
included with this distribution, and therefore must be provided by the user of
these applications/libraries/modules for proper operation. Refer to the library/module
documentation for details of installing the library/module.
