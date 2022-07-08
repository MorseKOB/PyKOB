# OLED_Stats
OLED Stats Display Script For Raspberry Pi

Original from Michael Klements.
Full setup instructions: https://www.the-diy-life.com/add-an-oled-stats-display-to-raspberry-pi-os-bullseye/

The script is pre-configured for 128x64 I2C OLED Display, but can easily be modified to run on a 128x32 I2C OLED Display

Modified by Ed Silky to:
* Calculate text line height from display height rather than using a separate constent
* Test that the I2C interface is enabled and that a display is present, and exit nicely if not
* Update this README to include a summary of the software portion of the install

## Software Installation
These are the steps to update the Raspberry Pi, Install the CircuitPython library (from Adafruit), get the 'Stats' code in place, and configure it to run at start-up.

These are copied from the full article by Michael Klements.
### Update Raspberry Pi:
* `sudo apt-get update`
* `sudo apt-get full-upgrade`
* `sudo reboot`
  
* `sudo apt-get install python3-pip`
* `sudo pip3 install --upgrade setuptools`
### Install The CircuitPython Library
* `cd ~`
* `sudo pip3 install --upgrade adafruit-python-shell`
* `wget https://raw.githubusercontent.com/adafruit/Raspberry-Pi-Installer-Scripts/master/raspi-blinka.py`
* `sudo python3 raspi-blinka.py`
  
Hit yes to any prompts that come up and yes (Y) to reboot at the end.
### Check That The Display Can Be Found
* `sudo i2cdetect -y 1`

This will display a table of I2C devices. If the display is the only I2C device a single cell should be highlighted. If the table is empty, either I2C is not enabled or the display isn't connected correctly.

If there is more than one I2C device they must be configured for different addresses.

The previous steps should have enabled I2C, but it can also be enabled with the Raspberry Pi configuration tool:
* `sudo raspi-config`

**Make sure I2C is enabled and the display is detected before proceeding**
### Install OLED Libraries
* `pip3 install adafruit-circuitpython-ssd1306`
* `sudo apt-get install python3-pil`
### Test the Display
Run the 'Stats' script manually:
* `python3 stats_wchk.py`

The display should show (for example):
> IP: 192.168.10.101
>
> CPU: 1.49%  44.3°C
>
> Mem: 199/1872MB
>
> Disk: 3/29GB 12%
### Run On Start-Up
Crontab can be used to cause the script to be run automatically when the Pi boots.
* `crontab -e` <br/>
  If needed, select an editor

Add the following line to the very end of the file to run the script at startup:
* `@reboot cd /home/pi/PyKOB/oled-display && python3 stats_wchk.py &`

If needed, modify the path to the location of the script and font file (`PixelOperator.ttf`) - they must be in the same directory, and the command needs to change to that directory before running the script.

Remember to include the '&' at the end of the line to cause the script to be run in the background and allow the Pi to continue booting.

* Save the crontab file using the steps appropriate for the editor being used
* `sudo reboot`

When the Pi starts the display should show the status. It takes a moment for the IP address to display, as the Pi needs to connect to the network before it is assigned.
