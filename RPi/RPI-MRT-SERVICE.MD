# PI Build

## Raspberry Pi 3 Model B - Debian Image

The latest, 'Debian Trixy', image had some issues working with the Pi 3 Model B, so the decision was made to drop back to the prior stable Debian Bookworm release. It can be found here:

```text
https://downloads.raspberrypi.com/raspios_armhf/images/raspios_armhf-2025-05-13/

2025-05-13-raspios-bookworm-armhf.img.xz
```

The 'armhf' image is used, as it is the 32-bit Hardware Floating-Point version, which works best for the 3-MB.

## Flash the Image to the SD Card

Run this from the directory on your ThinkPad where the downloaded image is saved (verifying your card’s target path like /dev/mmcblk0 via lsblk first):

```bash
xzcat 2025-05-13-raspios-bookworm-armhf.img.xz | sudo dd of=/dev/mmcblk0 bs=8M status=progress conv=fsync
```

## Set the Permissions for the pi User

Run this on the Pi to permanently grant the pi user direct hardware access to the audio system, GPIO pins, I2C bus, and the essential serial telegraph interfaces:

```bash
sudo usermod -aG dialout,audio,gpio,i2c pi
```

## Stop the PyKOB MRT Service

If you ever need to halt the background daemon to run configurations, pull manual git updates, or free up the hardware interfaces, use systemd over ssh:

```bash
sudo systemctl stop pykob.service
```

To bring it back up:

```bash
sudo systemctl start pykob.service
```

# MRT Service Output

Using `journalctl -u pykob.service -f` was tried, but the output is buffered line-by-line. The next attempt was with a named pipe.

## Using a Ram-Based Named Pipe (not perfect)

``` bash
sudo vi /etc/systemd/system/pykob.service
```

``` text
[Unit]
Description=PyKOB Telegraph Application
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/PyKOB
Environment=PYTHONUNBUFFERED=1
RuntimeDirectory=pykob
ExecStartPre=/bin/sh -c '[ -p /run/pykob/morse_stream ] || /usr/bin/mkfifo /run/pykob/morse_stream'
ExecStart=/bin/sh -c '/home/pi/PyKOB/venv/bin/python src.py/MRT.py > /run/pykob/morse_stream'
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

``` bash
sudo systemctl daemon-reload
sudo systemctl restart pykob.service
tail -f /run/pykob/morse_stream > /dev/null &
```

``` bash
cat -u /run/pykob/morse_stream
```

That provided character-by-character output, but suffered by only getting partial output due to the background reader (needed to keep the pipe from blocking when not being monitored) picking up some of the output.

Next, try a virtual 'screen'.

## Using a Virtual, Detached Linux Terminal Canvas

Using a utility called 'screen' or 'tmux' lets MRT print text naturally character-by-character into RAM. This allows hopping in and watching it live over SSH anytime, and doesn't drop a single byte when detached.

### Screen (problems due to cross-user execution)

Install 'screen'.

``` bash
sudo apt update && sudo apt install -y screen
```

``` bash
sudo vi /etc/systemd/system/pykob.service
```

``` text
[Unit]
Description=PyKOB Telegraph Application
After=network-online.target
Wants=network-online.target

[Service]
Type=forking
User=pi
WorkingDirectory=/home/pi/PyKOB
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/screen -dmS morse /home/pi/PyKOB/venv/bin/python src.py/MRT.py
ExecStop=/usr/bin/screen -S mrt-term -X quit
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl restart pykob.service
```

```bash
screen -r mrt-term
```

### Using (lightweight) 'tmux'

The 'tmux' approach is also a virtual screen that MRT can output to. It solves the problem of cross-user access.

Install it using:

```bash
sudo apt update && sudo apt install -y tmux
```

Edit the service to use 'tmux' rather than 'screen':

```bash
sudo vi /etc/systemd/system/pykob.service
```

This configuration switches the execution engine to Type=forking, launches MRT inside a background canvas named mrt_term, and keeps the Python venv paths intact:

```text
[Unit]
Description=PyKOB MRT Telegraph Application
After=network-online.target
Wants=network-online.target

[Service]
Type=forking
User=pi
WorkingDirectory=/home/pi/PyKOB
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/tmux new-session -d -s mrt_term '/home/pi/PyKOB/venv/bin/python src.py/MRT.py'
ExecStop=/usr/bin/tmux kill-session -t mrt_term
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Reload the service:

```bash
sudo systemctl daemon-reload
sudo systemctl restart pykob.service
```

Interact with MRT:

```bash
tmux attach -t mrt_term
```

To disconnect and leave it running safely: Press Ctrl+B, then D. That detaches while leaving the virtual tmux terminal intact.

To SSH in and immediately go into the tmux session...

```bash
ssh pi@192.168.68.86 -t "tmux attach -t mrt_term"
```
