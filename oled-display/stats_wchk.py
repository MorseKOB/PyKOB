# Created by: Michael Klements
# For Raspberry Pi Desktop Case with OLED Stats Display
# Base on Adafruit CircuitPython & SSD1306 Libraries
# Installation & Setup Instructions - https://www.the-diy-life.com/add-an-oled-stats-display-to-raspberry-pi-os-bullseye/
#
# ES - Added 'try' around loading the I2C and SSD1306 to avoid it erroring out if I2C isn't 
# enabled or a display isn't installed.
#
import sys
import time
import board
import busio
import digitalio

from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306

import subprocess

# Define the display device I2C address
OLED_DISPLAY_ADDR = 0x3C
# Define the Reset Pin
oled_reset = digitalio.DigitalInOut(board.D4)
# Line height for 4 lines on the 128x64 OLED display
LINE_HEIGHT = 16

# Display Parameters
WIDTH = 128
HEIGHT = 64
BORDER = 2
# Colors
WHITE = 255
BLACK = 0

# Use for I2C.
try:
    i2c = board.I2C()
    oled = adafruit_ssd1306.SSD1306_I2C(WIDTH, HEIGHT, i2c, addr=OLED_DISPLAY_ADDR, reset=oled_reset)
except:
    print("I2C OLED device not found at address %#X"%(OLED_DISPLAY_ADDR), file = sys.stderr)
    exit(1)

# Clear display.
oled.fill(BLACK)
oled.show()

# Create blank image for drawing.
# Make sure to create image with mode '1' for 1-bit color.
image = Image.new("1", (oled.width, oled.height))

# Get drawing object to draw on image.
draw = ImageDraw.Draw(image)

# Draw a white background
draw.rectangle((0, 0, oled.width, oled.height), outline=WHITE, fill=WHITE)

font = ImageFont.truetype('PixelOperator.ttf', LINE_HEIGHT)
#font = ImageFont.load_default()

while True:

    # Draw a black filled box to clear the image.
    draw.rectangle((0, 0, oled.width, oled.height), outline=BLACK, fill=BLACK)

    # Shell scripts for system monitoring from here : https://unix.stackexchange.com/questions/119126/command-to-display-memory-usage-disk-usage-and-cpu-load
    cmd = "hostname -I | cut -d\' \' -f1"
    IP = subprocess.check_output(cmd, shell = True )
    cmd = "top -bn1 | grep load | awk '{printf \"CPU: %.2f\", $(NF-2)}'"
    CPU = subprocess.check_output(cmd, shell = True )
    cmd = "free -m | awk 'NR==2{printf \"Mem: %s/%sMB %.2f%%\", $3,$2,$3*100/$2 }'"
    MemUsage = subprocess.check_output(cmd, shell = True )
    cmd = "df -h | awk '$NF==\"/\"{printf \"Disk: %d/%dGB %s\", $3,$2,$5}'"
    Disk = subprocess.check_output(cmd, shell = True )
    cmd = "vcgencmd measure_temp |cut -f 2 -d '='"
    temp = subprocess.check_output(cmd, shell = True )

    # Pi Stats Display
    draw.text((0, 0 * LINE_HEIGHT), "IP: " + str(IP,'utf-8'), font=font, fill=WHITE)
    draw.text((0, 1 * LINE_HEIGHT), str(CPU,'utf-8') + "%", font=font, fill=WHITE)
    draw.text((80, 1 * LINE_HEIGHT), str(temp,'utf-8') , font=font, fill=WHITE)
    draw.text((0, 2 * LINE_HEIGHT), str(MemUsage,'utf-8'), font=font, fill=WHITE)
    draw.text((0, 3 * LINE_HEIGHT), str(Disk,'utf-8'), font=font, fill=WHITE)
        
    # Display image
    oled.image(image)
    oled.show()
    time.sleep(.3)
