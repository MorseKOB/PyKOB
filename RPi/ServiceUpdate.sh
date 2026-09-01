#! /bin/sh

# Use when changes are made to '/etc/systemd/system/pykob.service'
# Must be run with 'sudo' (not included)
systemctl daemon-reload
systemctl restart pykob.service
